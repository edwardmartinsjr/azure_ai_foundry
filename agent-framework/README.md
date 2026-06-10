# Agent Framework Expense Agent

This folder contains a Python console app that creates a Microsoft Agent Framework agent backed by Azure AI Foundry and registers a local Python function as a tool for submitting expense claims.

The app in `agent.py`:

- Loads Azure AI Foundry settings from `.env`.
- Connects to an Azure AI Foundry project with `AzureCliCredential`.
- Creates an Agent Framework agent named `ExpenseAgent-PRO`.
- Uses `FoundryChatClient` to call a deployed model in Azure AI Foundry.
- Registers the `create_expense` function from `functions.py` as a tool.
- Runs a single sample expense-submission request.
- Writes the submitted claim to a local `ticket-<number>.txt` file.

## Files

| File | Description |
| --- | --- |
| `agent.py` | Main console application that creates and runs the Agent Framework expense agent. |
| `functions.py` | Defines the `create_expense` function tool used by the agent. |
| `.env` | Stores the Azure AI Foundry endpoint and model deployment name. |

## Prerequisites

- Python 3.12 or later
- Azure subscription
- Azure AI Foundry project
- Deployed model, such as `gpt-4.1`
- Azure CLI sign-in with access to the Foundry project

## Setup

Install the required packages:

```powershell
pip install -r requirements.txt
```

Update `.env` with your project values:

```env
PROJECT_ENDPOINT=your_project_endpoint
MODEL_DEPLOYMENT_NAME=your_model_deployment_name
```

Sign in to Azure:

```powershell
az login
```

## Run

Start the agent:

```powershell
python agent.py
```

The script sends this sample request to the agent:

```text
Submit an expense: mail@mail.com, Travel to Pila Factory, $550,00
```

If the model decides the request should create an expense claim, Agent Framework calls the registered `create_expense` tool and returns the tool result in the response.

## Function Tool

The agent can call this local function:

```python
create_expense(email_address: str, description: str, claim_amount: str)
```

The function creates a local ticket file in the same folder as the script. The ticket contains:

- Ticket number
- Submitter email address
- Expense description
- Claim amount

The function returns a JSON message confirming the ticket number.

## Agent Framework Notes

- Microsoft Agent Framework separates the agent definition from the model provider.
- `Agent` contains the agent name, instructions, and tools.
- `FoundryChatClient` connects the agent to Azure AI Foundry.
- Tools can be ordinary Python callables registered in the `tools` list.
- The Python Agent Framework APIs are async, so this sample uses `asyncio.run`.

## Notes

- This sample runs one request and then exits.
- If the app fails to authenticate, run `az login` and confirm your Azure account has access to the Foundry project.
- If the app cannot find your project or model, check the `PROJECT_ENDPOINT` and `MODEL_DEPLOYMENT_NAME` values in `.env`.
- Generated `ticket-*.txt` files are created locally and are not submitted to an external expense system.
