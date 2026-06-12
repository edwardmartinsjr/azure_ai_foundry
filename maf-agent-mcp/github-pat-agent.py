import asyncio
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential
from dotenv import load_dotenv

"""
MCP GitHub Integration with Personal Access Token (PAT)

This example demonstrates how to connect to GitHub's remote MCP server using a Personal Access
Token (PAT) for authentication. The agent can use GitHub operations like searching repositories,
reading files, creating issues, and more depending on how you scope your token.

Prerequisites:
1. A GitHub Personal Access Token with appropriate scopes
   - Create one at: https://github.com/settings/tokens
   - For read-only operations, you can use more restrictive scopes
2. Environment variables:
   - GITHUB_PAT: Your GitHub Personal Access Token (required)
   - OPENAI_API_KEY: Your OpenAI API key (required)
   - OPENAI_MODEL: Your OpenAI model ID (required)
"""

async def github_mcp_example() -> None:
    # Load environment variables from .env file
    load_dotenv()
    project_endpoint = os.getenv("PROJECT_ENDPOINT")
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")
    # Get Github configuration from environment
    github_pat = os.getenv("GITHUB_PAT")
    if not github_pat:
        raise ValueError(
        "GITHUB_PAT environment variable must be set. Create a token at https://github.com/settings/tokens"
    )

    # Create authentication headers with GitHub PAT
    auth_headers = {
        "Authorization": f"Bearer {github_pat}",
    }

    # Agent Framework separates the agent definition from the model provider.
    # `Agent` owns the name, instructions, and tools. `FoundryChatClient`
    # connects that agent to an Azure AI Foundry project and model deployment.
    client=FoundryChatClient(
            # AzureCliCredential uses the current `az login` session. This keeps
            # the sample keyless for local development while still using Azure
            # identity and role assignments.
            credential=AzureCliCredential(),
            project_endpoint=project_endpoint,
            model=model_deployment,
        )

    # The MCP tool manages the connection to the MCP server and makes its tools available
    # Set approval_mode="never_require" to allow the MCP tool to execute without approval
    # Note that the tool created here will be executed remotely by OpenAI, not locally by
    # your application.
    github_mcp_tool = client.get_mcp_tool(
        name="GitHub",
        url="https://api.githubcopilot.com/mcp/",
        headers=auth_headers,
        approval_mode="never_require",
    )

    # In agent_framework._tools._tools_to_dict, it logs Can't parse tool. when a tool is 
    # not a FunctionTool, Pydantic model, SerializationMixin, or plain dict. 
    # FoundryChatClient.get_mcp_tool(...) returns an Azure Projects MCPTool object, which Foundry can use, but the core parser warns about it.
    # Convert the MCP tool to a plain dict before passing it to Agent.
    github_mcp_tool_definition = dict(github_mcp_tool)

    # Create agent with the GitHub MCP tool using instance method
    async with Agent(
        client=client,
        name="GitHubAgent",
        instructions=(
            "You are a helpful assistant that can help users interact with GitHub. "
            "You can search for repositories, read file contents, check issues, and more. "
            "Always be clear about what operations you're performing."
        ),
        tools=[github_mcp_tool_definition],
    ) as agent:
        # Example 1: Get authenticated user information
        query1 = "What is my GitHub username and tell me about my account?"
        print(f"\nUser: {query1}")
        result1 = await agent.run(query1)
        print(f"Agent: {result1.text}")

        # Example 2: List my repositories
        query2 = "List all the repositories I own on GitHub"
        print(f"\nUser: {query2}")
        result2 = await agent.run(query2)
        print(f"Agent: {result2.text}")


if __name__ == "__main__":
    asyncio.run(github_mcp_example())
