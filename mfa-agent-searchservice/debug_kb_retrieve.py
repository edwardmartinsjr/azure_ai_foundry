import asyncio
import json
import os
from pathlib import Path
from typing import Any

from azure.core.credentials import AzureKeyCredential
from azure.identity.aio import AzureCliCredential
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


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_QUERY = "Using the knowledge base, summarize quantities for warehouse_id WH-WEST in all periods."


def get_credential() -> AzureKeyCredential | AzureCliCredential:
    search_key = os.getenv("AZURE_SEARCH_API_KEY")
    if search_key:
        return AzureKeyCredential(search_key)
    return AzureCliCredential()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


async def resolve_knowledge_source_name(
    index_client: SearchIndexClient,
    knowledge_base_name: str,
) -> str:
    explicit_name = os.getenv("AZURE_SEARCH_KNOWLEDGE_SOURCE_NAME")
    if explicit_name:
        return explicit_name

    knowledge_base = await index_client.get_knowledge_base(knowledge_base_name)
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


def print_response(result: Any) -> None:
    print("\n=== KB response ===")
    for message in result.response or []:
        for content in message.content or []:
            text = getattr(content, "text", None)
            if text:
                print(text)


def print_references(result: Any) -> None:
    print("\n=== References and source_data ===")
    references = result.references or []
    if not references:
        print("No references returned.")
        return

    for index, reference in enumerate(references, start=1):
        source_data = getattr(reference, "source_data", None)
        print(f"\nReference {index}: {reference.id}")
        print(f"type: {getattr(reference, 'type', None)}")
        print(f"reranker_score: {getattr(reference, 'reranker_score', None)}")
        if source_data:
            print(json.dumps(to_jsonable(source_data), indent=2, default=str))
        else:
            print("source_data: <empty>")


def print_activity(result: Any) -> None:
    print("\n=== Activity ===")
    activity = result.activity or []
    if not activity:
        print("No activity returned.")
        return
    print(json.dumps(to_jsonable(activity), indent=2, default=str))


async def main() -> None:
    load_dotenv(SCRIPT_DIR / ".env")

    endpoint = require_env("AZURE_SEARCH_ENDPOINT")
    knowledge_base_name = require_env("AZURE_SEARCH_KNOWLEDGE_BASE_NAME")
    query = os.getenv("KB_DEBUG_QUERY", DEFAULT_QUERY)
    credential = get_credential()

    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)
    retrieval_client = KnowledgeBaseRetrievalClient(
        endpoint=endpoint,
        knowledge_base_name=knowledge_base_name,
        credential=credential,
    )

    try:
        knowledge_source_name = await resolve_knowledge_source_name(
            index_client=index_client,
            knowledge_base_name=knowledge_base_name,
        )

        print(f"Knowledge base: {knowledge_base_name}")
        print(f"Knowledge source: {knowledge_source_name}")
        print(f"Query: {query}")

        request = KnowledgeBaseRetrievalRequest(
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

        result = await retrieval_client.retrieve(retrieval_request=request)
        print_response(result)
        print_references(result)
        print_activity(result)
    finally:
        await retrieval_client.close()
        await index_client.close()
        close = getattr(credential, "close", None)
        if close:
            await close()


if __name__ == "__main__":
    asyncio.run(main())
