import asyncio
import json
import os
from pathlib import Path
from typing import Any

from agent_framework import Agent, Message
from agent_framework.azure import AzureAISearchContextProvider
from agent_framework.foundry import FoundryChatClient
from azure.identity.aio import AzureCliCredential
from azure.search.documents.knowledgebases.models import (
    KnowledgeBaseMessage,
    KnowledgeBaseMessageTextContent,
    KnowledgeBaseRetrievalRequest,
    KnowledgeRetrievalIntent,
    KnowledgeRetrievalLowReasoningEffort,
    KnowledgeRetrievalMediumReasoningEffort,
    KnowledgeRetrievalMinimalReasoningEffort,
    KnowledgeRetrievalOutputMode,
    KnowledgeRetrievalSemanticIntent,
    SearchIndexKnowledgeSourceParams,
)
from dotenv import load_dotenv

# Load environment variables from .env file
SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

"""
This sample demonstrates how to use Azure AI Search with agentic mode for RAG
(Retrieval Augmented Generation) with Azure AI agents.

**Agentic mode** is recommended for most scenarios:
- Uses Knowledge Bases in Azure AI Search for query planning
- Performs multi-hop reasoning across documents
- Provides more accurate results through intelligent retrieval
- Slightly slower with more token consumption for query planning
- See: https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/foundry-iq-boost-response-relevance-by-36-with-agentic-retrieval/4470720

For simple queries where speed is critical, use semantic mode instead (see azure_ai_with_search_context_semantic.py).

Prerequisites:
1. An Azure AI Search service
2. An Azure AI Foundry project with a model deployment
3. Either an existing Knowledge Base OR a search index (to auto-create a KB)

Environment variables:
   - AZURE_SEARCH_ENDPOINT: Your Azure AI Search endpoint
   - AZURE_SEARCH_API_KEY: (Optional) API key - if not provided, uses AzureCliCredential
   - FOUNDRY_PROJECT_ENDPOINT: Your Azure AI Foundry project endpoint
   - FOUNDRY_MODEL: Your model deployment name (e.g., "gpt-4o")

For using an existing Knowledge Base (recommended):
   - AZURE_SEARCH_KNOWLEDGE_BASE_NAME: Your Knowledge Base name

For auto-creating a Knowledge Base from an index:
   - AZURE_SEARCH_INDEX_NAME: Your search index name
   - AZURE_OPENAI_RESOURCE_URL: Azure OpenAI resource URL (e.g., "https://myresource.openai.azure.com")
"""

# Sample queries to demonstrate agentic RAG
USER_INPUTS = [
    "Using the knowledge base, summarize quantities for warehouse_id WH-WEST in all periods.",
    # "Identify SKUs that are currently slow-moving based on recent history",
    # "Forecast which SKUs are likely to become slow movers using trends",
    # "For each discrepancy or slow-moving pattern, propose likely causes grounded in the data",
    # "Recommend practical actions, prioritized by business impact",
]


class SourceDataAzureAISearchContextProvider(AzureAISearchContextProvider):
    """Agentic Search provider that exposes reference source_data as model context.

    Azure AI Search Knowledge Base retrieval can return two different layers of
    grounding information:

    1. ``response``: the compact extractive response used by the default
       ``AzureAISearchContextProvider``. For this inventory index, that response
       contains only semantic fields such as ``sku``, ``warehouse_id``, and
       ``category``.
    2. ``references[].source_data``: the structured source records returned when
       the retrieve request sets ``include_reference_source_data=True``. This is
       where row-level fields such as ``snapshot_date``, ``on_hand_qty``,
       ``received_qty``, ``shipped_qty``, and ``unit_cost`` are available.

    The default Agent Framework provider attaches only the compact KB response
    to the model context. That is fine for prose documents, but it loses the
    structured inventory measures needed for quantitative questions. This
    subclass keeps the official agentic retrieval flow, but adds runtime
    ``SearchIndexKnowledgeSourceParams`` so the KB response includes references
    and structured source data, then converts those source rows into a JSON
    context message for the final agent.

    Use this provider when the KB is backed by a structured Azure AI Search
    index and the agent must reason over retrievable fields that are not part of
    the semantic response text. For exact large-scale aggregation, prefer direct
    Azure AI Search filters/aggregation before asking the model to summarize.
    """

    async def _agentic_search(self, messages: list[Message]) -> list[Message]:
        """Run KB retrieval and return source_data rows as context messages.

        This overrides the base provider's agentic search implementation only at
        the retrieve-request boundary. Query planning, output mode, reasoning
        effort, and KB client usage remain aligned with the base provider.
        """
        await self._ensure_knowledge_base()

        reasoning_effort_map = {
            "minimal": KnowledgeRetrievalMinimalReasoningEffort(),
            "medium": KnowledgeRetrievalMediumReasoningEffort(),
            "low": KnowledgeRetrievalLowReasoningEffort(),
        }
        reasoning_effort = reasoning_effort_map[self.retrieval_reasoning_effort]

        output_mode = (
            KnowledgeRetrievalOutputMode.EXTRACTIVE_DATA
            if self.knowledge_base_output_mode == "extractive_data"
            else KnowledgeRetrievalOutputMode.ANSWER_SYNTHESIS
        )

        source_name = await self._resolve_knowledge_source_name()
        source_params = [
            SearchIndexKnowledgeSourceParams(
                knowledge_source_name=source_name,
                include_references=True,
                include_reference_source_data=True,
                always_query_source=True,
            )
        ]

        if self.retrieval_reasoning_effort == "minimal":
            query = "\n".join(msg.text for msg in messages if msg.text)
            intents: list[KnowledgeRetrievalIntent] = [
                KnowledgeRetrievalSemanticIntent(search=query)
            ]
            retrieval_request = KnowledgeBaseRetrievalRequest(
                intents=intents,
                retrieval_reasoning_effort=reasoning_effort,
                output_mode=output_mode,
                include_activity=True,
                knowledge_source_params=source_params,
            )
        else:
            kb_messages = self._prepare_messages_for_kb_search(messages)
            retrieval_request = KnowledgeBaseRetrievalRequest(
                messages=kb_messages,
                retrieval_reasoning_effort=reasoning_effort,
                output_mode=output_mode,
                include_activity=True,
                knowledge_source_params=source_params,
            )

        if not self._retrieval_client:
            raise RuntimeError("Retrieval client not initialized.")

        retrieval_result = await self._retrieval_client.retrieve(
            retrieval_request=retrieval_request
        )
        return self._parse_source_data_from_kb_response(retrieval_result)

    async def _resolve_knowledge_source_name(self) -> str:
        """Resolve the search index knowledge source used by the Knowledge Base.

        Portal-created knowledge sources often have generated names, so callers
        can set ``AZURE_SEARCH_KNOWLEDGE_SOURCE_NAME`` in ``.env``. If it is not
        set, the provider reads the KB definition and uses its first knowledge
        source. The final fallback matches the base provider's auto-created
        naming convention: ``{index_name}-source``.
        """
        explicit_name = os.getenv("AZURE_SEARCH_KNOWLEDGE_SOURCE_NAME")
        if explicit_name:
            return explicit_name

        if self._index_client and self.knowledge_base_name:
            knowledge_base = await self._index_client.get_knowledge_base(
                self.knowledge_base_name
            )
            knowledge_sources = getattr(knowledge_base, "knowledge_sources", None) or []
            if knowledge_sources:
                return knowledge_sources[0].name

        if self.index_name:
            return f"{self.index_name}-source"

        raise RuntimeError(
            "Could not infer the knowledge source name. "
            "Set AZURE_SEARCH_KNOWLEDGE_SOURCE_NAME in .env."
        )

    @staticmethod
    def _parse_source_data_from_kb_response(retrieval_result: Any) -> list[Message]:
        """Convert KB reference source_data into model-visible JSON context.

        The KB ``response`` may still contain only semantic fields, so this
        method prefers ``references[].source_data`` when available. Duplicate
        rows are removed by document ``id`` and rows with ``snapshot_date`` are
        sorted chronologically to make time-series analysis easier for the
        final model. If no source data is present, it falls back to the base
        provider's normal KB response parsing.
        """
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

        if rows:
            rows.sort(key=lambda row: str(row.get("snapshot_date", "")))
            context = (
                "Retrieved Azure AI Search source_data rows. "
                "Use only these rows as inventory facts:\n"
                f"{json.dumps(rows, indent=2, default=str)}"
            )
            return [Message(role="user", contents=[context])]

        return AzureAISearchContextProvider._parse_messages_from_kb_response(
            retrieval_result
        )


def load_agent_instructions() -> str:
    """Load the agent system instructions from agent_instructions.md."""
    instructions_path = SCRIPT_DIR / "agent_instructions.md"
    return instructions_path.read_text(encoding="utf-8")


async def main() -> None:
    """Main function demonstrating Azure AI Search agentic mode."""

    agent_instructions = load_agent_instructions()
    agent_instructions = (
        f"{agent_instructions}\n\n"
        "Grounding rules:\n"
        "- Never create mock, sample, or illustrative inventory records.\n"
        "- For record retrieval requests, only return records present in the retrieved knowledge base context.\n"
        "- If the retrieved context does not contain matching records, say that no matching records were found in the knowledge base.\n"
    )

    # Get configuration from environment
    project_endpoint = os.environ["PROJECT_ENDPOINT"]
    model_deployment = os.environ.get("MODEL_DEPLOYMENT_NAME")    
    search_endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    search_key = os.environ.get("AZURE_SEARCH_API_KEY")

    # Use existing Knowledge Base (Recomended)
    knowledge_base_name = os.environ.get("AZURE_SEARCH_KNOWLEDGE_BASE_NAME")
    # Another Option: Auto-create KB from index (requires azure_openai_resource_url)
    index_name = os.environ.get("AZURE_SEARCH_INDEX_NAME")
    azure_openai_resource_url = os.environ.get("AZURE_OPENAI_RESOURCE_URL")

    # Create Azure AI Search context provider with agentic mode (recommended for accuracy)
    print("Using AGENTIC mode (Knowledge Bases with query planning, recommended)\n")
    print("This mode is slightly slower but provides more accurate results.\n")

    # Configure based on whether using existing KB or auto-creating from index
    if knowledge_base_name:
        # Use existing Knowledge Base - simplest approach
        search_provider = SourceDataAzureAISearchContextProvider(
            source_id="search_provider",
            endpoint=search_endpoint,
            api_key=search_key,
            credential=AzureCliCredential() if not search_key else None,
            mode="agentic",
            knowledge_base_name=knowledge_base_name,
            # Optional: Configure retrieval behavior
            knowledge_base_output_mode="extractive_data",
            retrieval_reasoning_effort="low",  # or "minimal", "medium"
            top_k=20,
        )
    else:
        # Auto-create Knowledge Base from index
        if not index_name:
            raise ValueError("Set AZURE_SEARCH_KNOWLEDGE_BASE_NAME or AZURE_SEARCH_INDEX_NAME")
        if not azure_openai_resource_url:
            raise ValueError("AZURE_OPENAI_RESOURCE_URL required when using index_name")
        search_provider = SourceDataAzureAISearchContextProvider(
            source_id="search_provider",
            endpoint=search_endpoint,
            index_name=index_name,
            api_key=search_key,
            credential=AzureCliCredential() if not search_key else None,
            mode="agentic",
            azure_openai_resource_url=azure_openai_resource_url,
            model=model_deployment,
            # Optional: Configure retrieval behavior
            knowledge_base_output_mode="extractive_data",
            retrieval_reasoning_effort="low",  # or "minimal", "medium"
            top_k=3,
        )
        
    # Create agent with search context provider
    async with (
        search_provider,
        Agent(
            client=FoundryChatClient(
                project_endpoint=project_endpoint,
                model=model_deployment,
                credential=AzureCliCredential(),
            ),
            name="Inventory-Assistant",
            instructions=agent_instructions,
            context_providers=[search_provider],
        ) as agent,
    ):
        print("=== Azure AI Agent with Search Context (Agentic Mode) ===\n")

        for user_input in USER_INPUTS:
            print(f"User: {user_input}")
            print("Agent: ", end="", flush=True)

            # Stream response
            async for chunk in agent.run(user_input, stream=True):
                if chunk.text:
                    print(chunk.text, end="", flush=True)
                for content in chunk.contents:
                    if content.annotations:
                        print(f"\n[Sources: {content.annotations}]", end="", flush=True)

            print("\n")        




if __name__ == "__main__":
    asyncio.run(main())    
