import asyncio
import os
from pathlib import Path

from agent_framework import Agent
from agent_framework.azure import AzureAISearchContextProvider
from agent_framework.foundry import FoundryChatClient
from azure.identity.aio import AzureCliCredential
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
    "Using the knowledge base, retrieve records for warehouse_id WH-WEST in October 2024. Include snapshot_date, sku, on_hand_qty, received_qty, and shipped_qty in the response.",
    # "Identify SKUs that are currently slow-moving based on recent history",
    # "Forecast which SKUs are likely to become slow movers using trends",
    # "For each discrepancy or slow-moving pattern, propose likely causes grounded in the data",
    # "Recommend practical actions, prioritized by business impact",
]


def load_agent_instructions() -> str:
    """Load the agent system instructions from agent_instructions.md."""
    instructions_path = Path(__file__).resolve().parent / "agent_instructions.md"
    return instructions_path.read_text(encoding="utf-8")


async def main() -> None:
    """Main function demonstrating Azure AI Search agentic mode."""

    agent_instructions = load_agent_instructions()

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
        search_provider = AzureAISearchContextProvider(
            source_id="search_provider",
            endpoint=search_endpoint,
            api_key=search_key,
            credential=AzureCliCredential() if not search_key else None,
            mode="agentic",
            knowledge_base_name=knowledge_base_name,
            # Optional: Configure retrieval behavior
            knowledge_base_output_mode="answer_synthesis",  # or "extractive_data"
            retrieval_reasoning_effort="minimal",  # or "minimal", "low"
            top_k=20,
        )
    else:
        # Auto-create Knowledge Base from index
        if not index_name:
            raise ValueError("Set AZURE_SEARCH_KNOWLEDGE_BASE_NAME or AZURE_SEARCH_INDEX_NAME")
        if not azure_openai_resource_url:
            raise ValueError("AZURE_OPENAI_RESOURCE_URL required when using index_name")
        search_provider = AzureAISearchContextProvider(
            source_id="search_provider",
            endpoint=search_endpoint,
            index_name=index_name,
            api_key=search_key,
            credential=AzureCliCredential() if not search_key else None,
            mode="agentic",
            azure_openai_resource_url=azure_openai_resource_url,
            model=model_deployment,
            # Optional: Configure retrieval behavior
            knowledge_base_output_mode="answer_synthesis",  # or "extractive_data"
            retrieval_reasoning_effort="minimal",  # or "medium", "low"
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
