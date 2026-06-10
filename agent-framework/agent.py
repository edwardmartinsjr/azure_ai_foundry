
from dotenv import load_dotenv
import os
import asyncio

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

# This local Python function is exposed as an Agent Framework tool.
# The framework inspects the callable signature and lets the model invoke it
# when the user's request matches the tool's purpose.
from functions import create_expense

async def main():
    # Keep project-specific settings outside the source file. The sample reads
    # the Foundry project endpoint and deployed model name from `.env`, matching
    # the configuration style used in Microsoft Agent Framework quickstarts.
    load_dotenv()
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")
    project_endpoint = os.getenv("PROJECT_ENDPOINT")

    # Agent Framework separates the agent definition from the model provider.
    # `Agent` owns the name, instructions, and tools. `FoundryChatClient`
    # connects that agent to an Azure AI Foundry project and model deployment.
    agent = Agent(
        client=FoundryChatClient(
            # AzureCliCredential uses the current `az login` session. This keeps
            # the sample keyless for local development while still using Azure
            # identity and role assignments.
            credential=AzureCliCredential(),
            # These can also be passed directly here, but environment variables
            # make the sample easier to move between Foundry projects and models.
            project_endpoint=project_endpoint,
            model=model_deployment,
        ),
        name = "ExpenseAgent-PRO",
        # Instructions define the agent's behavior and tool-use policy. Here they
        # tell the model when to gather missing expense details and when to call the
        # local `create_expense` tool registered below.
        instructions=
                    """You answer questions about expenses based on the expenses policy data. 
                    If a user wants to submit an expense claim, you get their email address, 
                    a description of the claim, and the amount to be claimed and call the 
                    expense report function tools (create_expense_tool)""",
        # Register callable tools with the agent. When the model decides that an
        # expense claim should be submitted, Agent Framework handles the tool call
        # and passes the function result back into the conversation.
        tools=[create_expense],
    )

    # Run a single-turn request. For an interactive app, wrap `agent.run(...)`
    # in a prompt loop and pass each user message to the same agent instance.
    print(await agent.run("Submit an expense: mail@mail.com, Travel to Pila Factory, $550,00"))

if __name__ == "__main__":
    # Agent Framework's Python APIs are async, so the script starts an asyncio
    # event loop for the sample entry point.
    asyncio.run(main())
