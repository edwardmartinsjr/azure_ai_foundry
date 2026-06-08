import os
import json
from dotenv import load_dotenv

# Add references
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FunctionTool
from azure.identity import DefaultAzureCredential
from azure.ai.projects.models import PromptAgentDefinition, FunctionTool
from openai.types.responses.response_input_param import FunctionCallOutput, ResponseInputParam
# from functions import next_visible_event, calculate_observation_cost, generate_observation_report
from functions import create_expense


def main(): 
    # Clear the console
    os.system('cls' if os.name=='nt' else 'clear')

    # Load environment variables from .env file
    load_dotenv()
    project_endpoint = os.getenv("PROJECT_ENDPOINT")
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")

    # Connect to the project client
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=project_endpoint, credential=credential) as project_client,
        project_client.get_openai_client() as openai_client,
    ):    
    
        # Define Create Expense
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
        

        # Create a new agent with the function tools
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
        
        
        # Create a thread for the chat session
        conversation = openai_client.conversations.create()
        

        # Create a list to hold function call outputs that will be sent back as input to the agent
        input_list: ResponseInputParam = []
        
        
        while True:
            user_input = input("Enter a prompt for the expense agent. Use 'quit' to exit.\nUSER: ").strip()
            if user_input.lower() == "quit":
                print("Exiting chat.")
                break

            # Send a prompt to the agent
            openai_client.conversations.items.create(
                conversation_id=conversation.id,
                items=[{"type": "message", "role": "user", "content": user_input}],
            )
            
        
            # Retrieve the agent's response, which may include function calls
            response = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
                input=input_list,
            )            


            # Process function calls
            for item in response.output:
                if item.type == "function_call":
                    # Retrieve the matching function tool
                    function_name = item.name
                    result = None
                    if item.name == "create_expense":
                        result = create_expense(**json.loads(item.arguments))
                            
                    # Append the output text
                    input_list.append(
                        FunctionCallOutput(
                            type="function_call_output",
                            call_id=item.call_id,
                            output=result,
                        )
                    )            
            

            # Send function call outputs back to the model and retrieve a response
            if input_list:
                response = openai_client.responses.create(
                    input=input_list,
                    previous_response_id=response.id,
                    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
                )

            # Display the agent's response
            print(f"AGENT: {response.output_text}")
        

        # Delete the agent when done
        project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
        print("Deleted agent.")    
            

if __name__ == '__main__': 
    main()
