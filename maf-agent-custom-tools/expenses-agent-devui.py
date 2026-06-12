
from dotenv import load_dotenv
import os
import logging

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential
from agent_framework.devui import serve

from functions import create_expense

def main():
    load_dotenv()
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")
    project_endpoint = os.getenv("PROJECT_ENDPOINT")

    # Configure concise console logging before starting Dev UI. The Dev UI host
    # and Agent Framework internals emit useful startup and request information
    # through Python logging, and this keeps those messages readable.
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    agent = Agent(
        client=FoundryChatClient(
            credential=AzureCliCredential(),
            project_endpoint=project_endpoint,
            model=model_deployment,
        ),
        name = "ExpenseAgent-PRO",
        instructions=
                    """You answer questions about expenses based on the expenses policy data. 
                    If a user wants to submit an expense claim, you get their email address, 
                    a description of the claim, and the amount to be claimed and call the 
                    expense report function tools (create_expense_tool)""",
        tools=[create_expense],
    )

    # Start Agent Framework Dev UI and expose the configured agent in the
    # browser. `serve` owns the web server lifecycle, so this variant does not
    # call `agent.run(...)` or await an async chat request directly.
    serve(entities=[agent], port=8090, auto_open=True)

if __name__ == "__main__":
    # Dev UI setup is synchronous from this script's perspective; the framework
    # handles any async work inside the server started by `serve`.
    main()
