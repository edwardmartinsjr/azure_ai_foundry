# Agent Framework Expense Agent

This folder contains Python samples that create a Microsoft Agent Framework agent backed by Azure AI Foundry and register a local Python function as a tool for submitting expense claims.

The app in `agent.py`:

- Loads Azure AI Foundry settings from `.env`.
- Connects to an Azure AI Foundry project with `AzureCliCredential`.
- Creates an Agent Framework agent named `ExpenseAgent-PRO`.
- Uses `FoundryChatClient` to call a deployed model in Azure AI Foundry.
- Registers the `create_expense` function from `functions.py` as a tool.
- Runs a single sample expense-submission request.
- Writes the submitted claim to a local `ticket-<number>.txt` file.

The app in `agent-devui.py` uses the same agent configuration, but hosts it in Agent Framework Dev UI so you can chat with the agent from a browser instead of running one hard-coded request.

## Files

| File | Description |
| --- | --- |
| `agent.py` | Main console application that creates and runs the Agent Framework expense agent. |
| `agent-devui.py` | Dev UI host that exposes the same expense agent in a browser on port `8090`. |
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

## Run Console Sample

Start the agent:

```powershell
python agent.py
```

The script sends this sample request to the agent:

```text
Submit an expense: mail@mail.com, Travel to Pila Factory, $550,00
```

If the model decides the request should create an expense claim, Agent Framework calls the registered `create_expense` tool and returns the tool result in the response.

## Run Dev UI

Start the browser-based Dev UI host:

```powershell
python agent-devui.py
```

The script calls:

```python
serve(entities=[agent], port=8090, auto_open=True)
```

This starts a local Dev UI server, registers the configured `ExpenseAgent-PRO` agent, and opens the browser automatically. If the browser does not open, go to:

```text
http://localhost:8090
```

Use the chat UI to submit prompts such as:

```text
Submit an expense for alex@example.com: customer visit travel, $125.50
```

Unlike `agent.py`, the Dev UI sample does not call `agent.run(...)` directly and does not need an explicit `asyncio.run(...)` entry point in the script. The `serve(...)` helper owns the local web server lifecycle and handles the framework's async work behind the browser experience.

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
- The console sample uses `asyncio.run` because it calls `agent.run(...)` directly.
- The Dev UI sample uses `serve(...)`, which starts the browser UI and handles request execution through the hosted app.

## Notes

- The console sample runs one request and then exits.
- The Dev UI sample keeps running until you stop the process with `Ctrl+C`.
- If the app fails to authenticate, run `az login` and confirm your Azure account has access to the Foundry project.
- If the app cannot find your project or model, check the `PROJECT_ENDPOINT` and `MODEL_DEPLOYMENT_NAME` values in `.env`.
- Generated `ticket-*.txt` files are created locally and are not submitted to an external expense system.
