import asyncio
import json
import os
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

from agent_framework import Agent, ContextProvider, Message, tool
from agent_framework.foundry import FoundryChatClient
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.identity.aio import AzureCliCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.search.documents.knowledgebases.aio import KnowledgeBaseRetrievalClient
from azure.search.documents.knowledgebases.models import (
    KnowledgeBaseMessage,
    KnowledgeBaseMessageTextContent,
    KnowledgeBaseRetrievalRequest,
    KnowledgeRetrievalLowReasoningEffort,
    SearchIndexKnowledgeSourceParams,
)
from dotenv import load_dotenv
from pydantic import Field


SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

USER_INPUTS = [
    "Using the knowledge base, summarize quantities for warehouse_id WH-WEST in all periods.", # This one should use the KB source-data context path because it asks for a grounded narrative summary from the knowledge base.
    "Calculate exact totals for received_qty and shipped_qty for warehouse_id WH-WEST from 2024-07-01 through 2024-08-31, grouped by month.", # call aggregate_inventory_metrics because it asks for exact totals, a date range, and grouping.
]


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_search_credential() -> AzureKeyCredential | DefaultAzureCredential:
    search_key = os.getenv("AZURE_SEARCH_API_KEY")
    if search_key:
        return AzureKeyCredential(search_key)
    return DefaultAzureCredential()


def get_async_search_credential() -> AzureKeyCredential | AzureCliCredential:
    search_key = os.getenv("AZURE_SEARCH_API_KEY")
    if search_key:
        return AzureKeyCredential(search_key)
    return AzureCliCredential()


def escape_odata_string(value: str) -> str:
    return value.replace("'", "''")


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def date_filter(field_name: str, operator: str, value: str) -> str:
    parsed = date.fromisoformat(value)
    return f"{field_name} {operator} {parsed.isoformat()}T00:00:00Z"


def build_inventory_filter(
    *,
    warehouse_id: str | None,
    sku: str | None,
    category: str | None,
    start_date: str | None,
    end_date: str | None,
) -> str | None:
    filters = []
    if warehouse_id:
        filters.append(f"warehouse_id eq '{escape_odata_string(warehouse_id)}'")
    if sku:
        filters.append(f"sku eq '{escape_odata_string(sku)}'")
    if category:
        filters.append(f"category eq '{escape_odata_string(category)}'")
    if start_date:
        filters.append(date_filter("snapshot_date", "ge", start_date))
    if end_date:
        filters.append(date_filter("snapshot_date", "le", end_date))
    return " and ".join(filters) if filters else None


def group_key(document: dict[str, Any], group_by: str) -> str:
    if group_by == "all":
        return "all"
    if group_by == "month":
        return str(document.get("snapshot_date", ""))[:7]
    return str(document.get(group_by, ""))


def summarize_documents(
    documents: list[dict[str, Any]],
    *,
    group_by: str,
    limit: int,
) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "records": 0,
            "received_qty_total": 0,
            "shipped_qty_total": 0,
            "on_hand_qty_latest": None,
            "inventory_value_latest": None,
            "latest_snapshot_date": None,
            "skus": set(),
            "warehouses": set(),
            "categories": set(),
        }
    )

    for document in documents:
        key = group_key(document, group_by)
        group = groups[key]
        snapshot_date = str(document.get("snapshot_date", ""))
        on_hand_qty = int(document.get("on_hand_qty") or 0)
        unit_cost = float(document.get("unit_cost") or 0)

        group["records"] += 1
        group["received_qty_total"] += int(document.get("received_qty") or 0)
        group["shipped_qty_total"] += int(document.get("shipped_qty") or 0)
        group["skus"].add(document.get("sku"))
        group["warehouses"].add(document.get("warehouse_id"))
        group["categories"].add(document.get("category"))

        if not group["latest_snapshot_date"] or snapshot_date > group["latest_snapshot_date"]:
            group["latest_snapshot_date"] = snapshot_date
            group["on_hand_qty_latest"] = on_hand_qty
            group["inventory_value_latest"] = round(on_hand_qty * unit_cost, 2)

    rows = []
    for key, group in groups.items():
        rows.append(
            {
                "group": key,
                "records": group["records"],
                "received_qty_total": group["received_qty_total"],
                "shipped_qty_total": group["shipped_qty_total"],
                "latest_snapshot_date": group["latest_snapshot_date"],
                "on_hand_qty_latest": group["on_hand_qty_latest"],
                "inventory_value_latest": group["inventory_value_latest"],
                "sku_count": len({item for item in group["skus"] if item}),
                "warehouse_count": len({item for item in group["warehouses"] if item}),
                "categories": sorted(item for item in group["categories"] if item),
            }
        )

    rows.sort(key=lambda row: (row["group"] != "all", row["group"]))
    return {
        "group_by": group_by,
        "returned_groups": len(rows[:limit]),
        "total_groups": len(rows),
        "rows": rows[:limit],
    }


@tool(approval_mode="never_require")
def aggregate_inventory_metrics(
    warehouse_id: Annotated[
        str | None,
        Field(description="Optional warehouse filter, for example WH-WEST."),
    ] = None,
    sku: Annotated[
        str | None,
        Field(description="Optional SKU filter, for example SKU-00406."),
    ] = None,
    category: Annotated[
        str | None,
        Field(description="Optional category filter, for example Fasteners."),
    ] = None,
    start_date: Annotated[
        str | None,
        Field(description="Optional inclusive start date in YYYY-MM-DD format."),
    ] = None,
    end_date: Annotated[
        str | None,
        Field(description="Optional inclusive end date in YYYY-MM-DD format."),
    ] = None,
    group_by: Annotated[
        Literal["all", "month", "sku", "warehouse_id", "category"],
        Field(description="Aggregation grouping dimension."),
    ] = "all",
    limit: Annotated[
        int,
        Field(description="Maximum number of grouped result rows to return."),
    ] = 25,
) -> str:
    """Calculate exact inventory metrics by filtering Azure AI Search rows.

    Use this tool for exact totals, rankings, counts, and grouped metrics. It
    queries the structured Azure AI Search index, performs aggregation in
    Python, and returns JSON that the agent can narrate.
    """
    endpoint = require_env("AZURE_SEARCH_ENDPOINT")
    index_name = require_env("AZURE_SEARCH_INDEX_NAME")
    credential = get_search_credential()
    search_client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)

    warehouse_id = normalize_optional_text(warehouse_id)
    sku = normalize_optional_text(sku)
    category = normalize_optional_text(category)
    start_date = normalize_optional_text(start_date)
    end_date = normalize_optional_text(end_date)

    filter_expression = build_inventory_filter(
        warehouse_id=warehouse_id,
        sku=sku,
        category=category,
        start_date=start_date,
        end_date=end_date,
    )

    selected_fields = [
        "sku",
        "warehouse_id",
        "category",
        "snapshot_date",
        "on_hand_qty",
        "received_qty",
        "shipped_qty",
        "unit_cost",
    ]
    try:
        results = search_client.search(
            search_text="*",
            filter=filter_expression,
            select=selected_fields,
            include_total_count=True,
        )
        documents = [dict(result) for result in results]
    finally:
        search_client.close()

    summary = summarize_documents(documents, group_by=group_by, limit=max(1, min(limit, 100)))
    summary["filters"] = {
        "warehouse_id": warehouse_id,
        "sku": sku,
        "category": category,
        "start_date": start_date,
        "end_date": end_date,
        "odata_filter": filter_expression,
    }
    summary["total_documents"] = len(documents)
    return json.dumps(summary, indent=2, default=str)


class KnowledgeBaseSourceDataContextProvider(ContextProvider):
    """Retrieve flexible grounded context from an Azure AI Search Knowledge Base.

    This provider is for broad Q&A and exploratory analysis where agentic
    retrieval is useful. It calls ``KnowledgeBaseRetrievalClient`` directly
    with ``include_reference_source_data=True`` and injects the retrieved source
    rows into the agent context.

    Exact totals and rankings should use ``aggregate_inventory_metrics`` so the
    computation happens deterministically in Python instead of in the model.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        knowledge_base_name: str,
        source_id: str = "inventory_kb_source_data",
        knowledge_source_name: str | None = None,
        max_rows: int = 50,
    ) -> None:
        super().__init__(source_id)
        self.endpoint = endpoint
        self.knowledge_base_name = knowledge_base_name
        self.knowledge_source_name = knowledge_source_name
        self.max_rows = max_rows

    async def before_run(self, *, agent: Any, session: Any, context: Any, state: dict[str, Any]) -> None:
        del agent, session, state
        query = "\n".join(
            message.text
            for message in context.input_messages
            if message.text and message.role in {"user", "assistant"}
        )
        if not query:
            return

        credential = get_async_search_credential()
        retrieval_client = KnowledgeBaseRetrievalClient(
            endpoint=self.endpoint,
            knowledge_base_name=self.knowledge_base_name,
            credential=credential,
        )
        index_client = SearchIndexClient(endpoint=self.endpoint, credential=credential)

        try:
            knowledge_source_name = self.knowledge_source_name or await self._resolve_knowledge_source_name(index_client)
            retrieval_request = KnowledgeBaseRetrievalRequest(
                messages=[
                    KnowledgeBaseMessage(
                        role="user",
                        content=[KnowledgeBaseMessageTextContent(text=query)],
                    )
                ],
                retrieval_reasoning_effort=KnowledgeRetrievalLowReasoningEffort(),
                output_mode="extractiveData",
                include_activity=True,
                max_output_size=6000,
                knowledge_source_params=[
                    SearchIndexKnowledgeSourceParams(
                        knowledge_source_name=knowledge_source_name,
                        include_references=True,
                        include_reference_source_data=True,
                        always_query_source=True,
                    )
                ],
            )
            result = await retrieval_client.retrieve(retrieval_request=retrieval_request)
            rows = self._source_rows(result)
            if not rows:
                return

            message = (
                "Azure AI Search Knowledge Base source_data rows for grounded Q&A. "
                "Use these rows as factual context, but call aggregate_inventory_metrics "
                "for exact totals, rankings, or grouped metrics:\n"
                f"{json.dumps(rows[: self.max_rows], indent=2, default=str)}"
            )
            context.extend_messages(self, [Message(role="user", contents=[message])])
        finally:
            await retrieval_client.close()
            await index_client.close()
            close = getattr(credential, "close", None)
            if close:
                await close()

    async def _resolve_knowledge_source_name(self, index_client: SearchIndexClient) -> str:
        explicit_name = os.getenv("AZURE_SEARCH_KNOWLEDGE_SOURCE_NAME")
        if explicit_name:
            return explicit_name

        knowledge_base = await index_client.get_knowledge_base(self.knowledge_base_name)
        knowledge_sources = getattr(knowledge_base, "knowledge_sources", None) or []
        if knowledge_sources:
            return knowledge_sources[0].name

        index_name = os.getenv("AZURE_SEARCH_INDEX_NAME")
        if index_name:
            return f"{index_name}-source"

        raise RuntimeError(
            "Could not infer the knowledge source name. "
            "Set AZURE_SEARCH_KNOWLEDGE_SOURCE_NAME in .env."
        )

    @staticmethod
    def _source_rows(retrieval_result: Any) -> list[dict[str, Any]]:
        rows = []
        seen_ids = set()
        for reference in retrieval_result.references or []:
            source_data = getattr(reference, "source_data", None)
            if not source_data:
                continue
            row_id = source_data.get("id")
            if row_id and row_id in seen_ids:
                continue
            if row_id:
                seen_ids.add(row_id)
            rows.append(source_data)
        rows.sort(key=lambda row: str(row.get("snapshot_date", "")))
        return rows


def load_agent_instructions() -> str:
    return (SCRIPT_DIR / "agent_instructions.md").read_text(encoding="utf-8")


async def main() -> None:
    project_endpoint = require_env("PROJECT_ENDPOINT")
    model_deployment = require_env("MODEL_DEPLOYMENT_NAME")
    search_endpoint = require_env("AZURE_SEARCH_ENDPOINT")
    knowledge_base_name = require_env("AZURE_SEARCH_KNOWLEDGE_BASE_NAME")

    instructions = (
        f"{load_agent_instructions()}\n\n"
        "Routing guidance:\n"
        "- For flexible grounded Q&A, use the supplied Knowledge Base source_data context.\n"
        "- For exact totals, rankings, counts, grouped metrics, or date-bounded calculations, "
        "call aggregate_inventory_metrics and base the answer on its JSON result.\n"
        "- Never invent inventory records or quantities.\n"
    )

    kb_context_provider = KnowledgeBaseSourceDataContextProvider(
        endpoint=search_endpoint,
        knowledge_base_name=knowledge_base_name,
        knowledge_source_name=os.getenv("AZURE_SEARCH_KNOWLEDGE_SOURCE_NAME"),
    )

    agent = Agent(
        client=FoundryChatClient(
            project_endpoint=project_endpoint,
            model=model_deployment,
            credential=AzureCliCredential(),
        ),
        name="Inventory-Hybrid-Assistant",
        instructions=instructions,
        context_providers=[kb_context_provider],
        tools=[aggregate_inventory_metrics],
    )

    async with agent:
        print("=== Inventory Hybrid Agent ===\n")
        for user_input in USER_INPUTS:
            print(f"User: {user_input}")
            response = await agent.run(user_input)
            print(f"Agent: {response}\n")


if __name__ == "__main__":
    asyncio.run(main())
