import asyncio
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential
from dotenv import load_dotenv

async def microsoft_learn_mcp() -> None:
    # Load environment variables from .env file
    load_dotenv()
    project_endpoint = os.getenv("PROJECT_ENDPOINT")
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")

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
    microsoft_learn_mcp_tool = client.get_mcp_tool(
        name="LearnMicrosoft",
        url="https://learn.microsoft.com/api/mcp",
        approval_mode="never_require",
    )

    # In agent_framework._tools._tools_to_dict, it logs Can't parse tool. when a tool is 
    # not a FunctionTool, Pydantic model, SerializationMixin, or plain dict. 
    # FoundryChatClient.get_mcp_tool(...) returns an Azure Projects MCPTool object, which Foundry can use, but the core parser warns about it.
    # Convert the MCP tool to a plain dict before passing it to Agent.
    microsoft_learn_mcp_tool_definition = dict(microsoft_learn_mcp_tool)

    # Create agent with the Microsoft Learn MCP tool using instance method
    async with Agent(
        client=client,
        name="Microsoft-Learn-Assistant",
        instructions=(
            "You are a helpful agent that can use MCP tools to assist users. Use the available MCP tools to answer questions and perform tasks."
        ),
        tools=[microsoft_learn_mcp_tool_definition],
    ) as agent:
        query = "Give me the all the topics to study to get ready for AI-103 certification."
        print(f"\nUser: {query}")
        result = await agent.run(query)
        print(f"Agent: {result.text}")


if __name__ == "__main__":
    asyncio.run(microsoft_learn_mcp())
