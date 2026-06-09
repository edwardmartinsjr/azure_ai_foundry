"""Run an Azure AI Foundry expense agent with a custom function tool.

This sample creates a temporary agent version, connects it to a local Python
function, and starts a terminal chat loop. When the model decides that an
expense claim should be submitted, it calls the `create_expense` function from
`functions.py`; the app then returns that function result back to the model so
the agent can respond to the user with the final confirmation.
"""

import os
import json
from dotenv import load_dotenv

# Azure AI Foundry and Azure Identity SDK imports.
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FunctionTool
from azure.identity import DefaultAzureCredential
from azure.ai.projects.models import PromptAgentDefinition, FunctionTool
from openai.types.responses.response_input_param import FunctionCallOutput, ResponseInputParam

# Local tool implementation exposed to the agent.
from functions import create_expense


def main():
    """Create the agent, run the chat loop, and clean up the agent version."""
    # Start each console session with a clean screen.
    os.system('cls' if os.name=='nt' else 'clear')

    # Load Azure AI Foundry settings from `.env`.
    # PROJECT_ENDPOINT should point to the Foundry project endpoint.
    # MODEL_DEPLOYMENT_NAME should match a deployed model in that project.
    load_dotenv()
    project_endpoint = os.getenv("PROJECT_ENDPOINT")
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")

    # DefaultAzureCredential supports Azure CLI sign-in, managed identity,
    # environment credentials, and other standard Azure authentication flows.
    # The context manager closes the credential and SDK clients automatically.
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=project_endpoint, credential=credential) as project_client,
        project_client.get_openai_client() as openai_client,
    ):    
    
        # Describe the local Python function as a callable tool for the model.
        # The JSON schema tells the model which arguments it must collect before
        # it can call `create_expense`.
        create_expense_tool = FunctionTool(
            name="create_expense",
            description="Create expense report.",
            parameters={
                "type": "object",
                "properties": {
                    "email_address": {
                        "type": "string",
                        "description": "user email address",
                    },
                    "description": {
                            "type": "string",
                            "description": "description of the expense claim",
                        },
                    "claim_amount": {
                            "type": "string",
                            "description": "claim amount",
                        },        
                },
                "required": ["email_address","description","claim_amount"],
                "additionalProperties": False,
            },
            strict=True,
        )        
        

        # Create a temporary agent version for this run. The instructions define
        # when the agent should ask for missing expense details and when it
        # should call the registered function tool.
        agent = project_client.agents.create_version(
        agent_name="ExpenseAgent-PRO",
        definition=PromptAgentDefinition(
            model=model_deployment,
            instructions=
                """You answer questions about expenses based on the expenses policy data. 
                If a user wants to submit an expense claim, you get their email address, 
                a description of the claim, and the amount to be claimed and call the 
                expense report function tools (create_expense_tool)""",
            tools=[create_expense_tool],
            ),
        )       
        
        
        # Create a conversation to retain user and agent messages during this
        # terminal session.
        conversation = openai_client.conversations.create()
        

        while True:
            user_input = input("Enter a prompt for the expense agent. Use 'quit' to exit.\nUSER: ").strip()
            if user_input.lower() == "quit":
                print("Exiting chat.")
                break

            # Function-call outputs are scoped to this user turn. The
            # conversation stores the chat history, so this list should only
            # contain tool results that need to be returned for the current
            # response.
            input_list: ResponseInputParam = []

            # Add the user's message to the conversation history.
            openai_client.conversations.items.create(
                conversation_id=conversation.id,
                items=[{"type": "message", "role": "user", "content": user_input}],
            )
            
        
            # Ask the agent for its next response. The response may contain
            # normal text, one or more function calls, or both.
            response = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
                input=input_list,
            )            


            # Execute any function calls requested by the model. In a larger app,
            # this dispatch block is where you would route each tool name to the
            # matching local function or service.
            for item in response.output:
                if item.type == "function_call":
                    # The model provides function arguments as JSON text. Convert
                    # them to Python keyword arguments before calling the local
                    # implementation.
                    function_name = item.name
                    result = None
                    if item.name == "create_expense":
                        result = create_expense(**json.loads(item.arguments))
                            
                    # Preserve the tool result with the original call ID so the
                    # model can match this output to the function call it made.
                    input_list.append(
                        FunctionCallOutput(
                            type="function_call_output",
                            call_id=item.call_id,
                            output=result,
                        )
                    )            
            

            # If a tool was called, send the tool output back to the model and
            # request a follow-up response that summarizes the completed action.
            if input_list:
                response = openai_client.responses.create(
                    input=input_list,
                    previous_response_id=response.id,
                    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
                )

            # Display the final text returned for this turn.
            print(f"AGENT: {response.output_text}")
        

        # Delete the temporary agent version created for this session. This keeps
        # the Foundry project tidy after the local console app exits.
        project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
        print("Deleted agent.")    
            

if __name__ == '__main__': 
    main()
