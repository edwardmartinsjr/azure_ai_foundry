import argparse
import base64
import csv
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from azure.core.exceptions import HttpResponseError
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.search.documents import IndexDocumentsBatch, SearchClient
from azure.search.documents.indexes import SearchIndexClient
from dotenv import load_dotenv


DEFAULT_CSV_NAME = "warehouse_inventory.csv"
DEFAULT_BATCH_SIZE = 1000
DEFAULT_MAX_RETRIES = 10
DEFAULT_RETRY_DELAY_SECONDS = 5.0
DEFAULT_BATCH_DELAY_SECONDS = 0.5
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def get_credential() -> AzureKeyCredential | DefaultAzureCredential:
    """Return an Azure Search credential from .env or fall back to Azure identity."""
    api_key = (
        os.getenv("AZURE_SEARCH_ADMIN_KEY")
        or os.getenv("AZURE_SEARCH_API_KEY")
        or os.getenv("AZURE_SEARCH_KEY")
    )
    if api_key:
        return AzureKeyCredential(api_key)

    return DefaultAzureCredential()


def require_env(name: str) -> str:
    """Read a required environment variable and trim surrounding quotes."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.strip().strip('"').strip("'")


def normalize_type(field_type: Any) -> str:
    """Normalize an Azure Search field type to a lowercase string for comparisons."""
    return str(field_type).lower()


def convert_value(value: str | None, field_type: Any) -> Any:
    """Convert a CSV string value into the Python value expected by an index field."""
    if value is None:
        return None

    text = value.strip()
    if text == "":
        return None

    type_name = normalize_type(field_type)
    if "edm.double" in type_name or "edm.single" in type_name:
        return float(text)
    if "edm.int32" in type_name or "edm.int64" in type_name:
        return int(text)
    if "edm.boolean" in type_name:
        return text.lower() in {"1", "true", "yes", "y"}
    if "edm.datetimeoffset" in type_name:
        return parse_datetimeoffset(text)

    return text


def parse_datetimeoffset(text: str) -> str:
    """Parse a CSV date/datetime value and return an Azure Search DateTimeOffset string."""
    if len(text) == 10:
        return f"{date.fromisoformat(text).isoformat()}T00:00:00Z"

    normalized = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def generated_key(row_number: int, row: dict[str, str]) -> str:
    """Create a stable URL-safe document key for CSV rows that do not include one."""
    source = "|".join(
        [
            row.get("LCLid", ""),
            row.get("Date", ""),
            row.get("KWH", ""),
            str(row_number),
        ]
    )
    return base64.urlsafe_b64encode(source.encode("utf-8")).decode("ascii").rstrip("=")


def load_index_fields(endpoint: str, index_name: str, credential: Any) -> tuple[dict[str, Any], str]:
    """Fetch the target index schema and return its fields plus the key field name."""
    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)
    index = index_client.get_index(index_name)

    fields = {field.name: field for field in index.fields}
    key_fields = [field.name for field in index.fields if getattr(field, "key", False)]
    if not key_fields:
        raise RuntimeError(f"Index '{index_name}' does not define a key field.")

    return fields, key_fields[0]


def row_to_document(
    row_number: int,
    row: dict[str, str],
    fields: dict[str, Any],
    key_field_name: str,
) -> dict[str, Any]:
    """Map a CSV row to an Azure Search document using the live index field types."""
    fields_by_lower_name = {name.lower(): name for name in fields}
    document: dict[str, Any] = {}

    for csv_name, value in row.items():
        index_field_name = fields_by_lower_name.get(csv_name.lower())
        if not index_field_name:
            continue
        document[index_field_name] = convert_value(value, fields[index_field_name].type)

    if key_field_name not in document or document[key_field_name] in {None, ""}:
        document[key_field_name] = generated_key(row_number, row)

    return document


def submit_batch(
    search_client: SearchClient,
    documents: list[dict[str, Any]],
    action: str,
    max_retries: int,
    retry_delay_seconds: float,
) -> tuple[int, int]:
    """Submit one IndexDocumentsBatch, retry throttling, and return success counts."""
    batch = IndexDocumentsBatch()
    if action == "merge_or_upload":
        batch.add_merge_or_upload_actions(documents)
    else:
        batch.add_upload_actions(documents)

    results = index_documents_with_retry(
        search_client=search_client,
        batch=batch,
        max_retries=max_retries,
        retry_delay_seconds=retry_delay_seconds,
    )
    succeeded = sum(1 for result in results if getattr(result, "succeeded", False))
    return succeeded, len(documents) - succeeded


def index_documents_with_retry(
    search_client: SearchClient,
    batch: IndexDocumentsBatch,
    max_retries: int,
    retry_delay_seconds: float,
) -> list[Any]:
    """Send documents to Azure Search with exponential backoff for transient errors."""
    for attempt in range(max_retries + 1):
        try:
            return list(search_client.index_documents(batch))
        except HttpResponseError as error:
            status_code = getattr(error, "status_code", None)
            if status_code not in RETRYABLE_STATUS_CODES or attempt == max_retries:
                raise

            retry_after = get_retry_after_seconds(error)
            delay = retry_after or retry_delay_seconds * (2**attempt)
            print(
                f"Azure Search throttled or returned HTTP {status_code}. "
                f"Retrying in {delay:.1f}s ({attempt + 1}/{max_retries})."
            )
            time.sleep(delay)

    raise RuntimeError("Retry loop ended unexpectedly.")


def get_retry_after_seconds(error: HttpResponseError) -> float | None:
    """Read Azure's Retry-After response header when the service provides one."""
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None

    value = headers.get("retry-after") or headers.get("Retry-After")
    if not value:
        return None

    try:
        return float(value)
    except ValueError:
        return None


def load_csv(
    csv_path: Path,
    endpoint: str,
    index_name: str,
    batch_size: int,
    action: str,
    max_retries: int,
    retry_delay_seconds: float,
    batch_delay_seconds: float,
) -> None:
    """Stream the CSV file and upload documents to Azure Search in bounded batches."""
    credential = get_credential()
    fields, key_field_name = load_index_fields(endpoint, index_name, credential)
    search_client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)

    total = 0
    failed = 0
    documents: list[dict[str, Any]] = []

    with csv_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row_number, row in enumerate(reader, start=1):
            documents.append(row_to_document(row_number, row, fields, key_field_name))

            if len(documents) >= batch_size:
                succeeded, batch_failed = submit_batch(
                    search_client=search_client,
                    documents=documents,
                    action=action,
                    max_retries=max_retries,
                    retry_delay_seconds=retry_delay_seconds,
                )
                total += succeeded
                failed += batch_failed
                print(f"Indexed {total} documents; failed {failed}.")
                documents.clear()
                if batch_delay_seconds > 0:
                    time.sleep(batch_delay_seconds)

    if documents:
        succeeded, batch_failed = submit_batch(
            search_client=search_client,
            documents=documents,
            action=action,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
        )
        total += succeeded
        failed += batch_failed

    print(f"Done. Indexed {total} documents into '{index_name}'. Failed: {failed}.")


def parse_args() -> argparse.Namespace:
    """Parse command-line options for the CSV path, batch size, and indexing action."""
    parser = argparse.ArgumentParser(
        description="Load warehouse_inventory.csv into an Azure AI Search index."
    )
    parser.add_argument(
        "--csv",
        default=os.getenv("INVENTORY_CSV_PATH", DEFAULT_CSV_NAME),
        help="Path to the CSV file. Defaults to warehouse_inventory.csv next to this script.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.getenv("AZURE_SEARCH_BATCH_SIZE", DEFAULT_BATCH_SIZE)),
        help="Documents per indexing batch. Azure AI Search supports up to 1000 actions per batch.",
    )
    parser.add_argument(
        "--action",
        choices=("upload", "merge_or_upload"),
        default=os.getenv("AZURE_SEARCH_ACTION", "upload"),
        help="Indexing action to use for each batch.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=int(os.getenv("AZURE_SEARCH_MAX_RETRIES", DEFAULT_MAX_RETRIES)),
        help="Maximum retry attempts for throttled or transient Azure Search requests.",
    )
    parser.add_argument(
        "--retry-delay-seconds",
        type=float,
        default=float(
            os.getenv("AZURE_SEARCH_RETRY_DELAY_SECONDS", DEFAULT_RETRY_DELAY_SECONDS)
        ),
        help="Initial retry delay. Each retry doubles this unless Azure sends Retry-After.",
    )
    parser.add_argument(
        "--batch-delay-seconds",
        type=float,
        default=float(os.getenv("AZURE_SEARCH_BATCH_DELAY_SECONDS", DEFAULT_BATCH_DELAY_SECONDS)),
        help="Delay between successful batches to reduce Azure Search throttling.",
    )
    return parser.parse_args()


def main() -> None:
    """Load environment settings, resolve inputs, and start the CSV indexing job."""
    script_dir = Path(__file__).resolve().parent
    load_dotenv(script_dir / ".env")
    args = parse_args()

    endpoint = require_env("AZURE_SEARCH_ENDPOINT")
    index_name = require_env("AZURE_SEARCH_INDEX_NAME")
    csv_path = Path(args.csv)
    if not csv_path.is_absolute():
        csv_path = script_dir / csv_path

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    load_csv(
        csv_path=csv_path,
        endpoint=endpoint,
        index_name=index_name,
        batch_size=args.batch_size,
        action=args.action,
        max_retries=args.max_retries,
        retry_delay_seconds=args.retry_delay_seconds,
        batch_delay_seconds=args.batch_delay_seconds,
    )


if __name__ == "__main__":
    main()
