# Microsoft Learn MCP Agent

This folder contains a Python sample that creates an Azure AI Foundry agent with a Model Context Protocol (MCP) tool connected to Microsoft Learn.

The app in `microsoft-learn-agent.py`:

- Loads Azure AI Foundry settings from `.env`.
- Connects to an Azure AI Foundry project with `DefaultAzureCredential`.
- Gets an Azure OpenAI client from the project client.
- Registers the Microsoft Learn MCP endpoint as an agent tool.
- Creates an agent named `Microsoft-Learn-Assistant`.
- Starts a conversation and asks for AI-103 certification study topics.
- Handles MCP tool approval requests and auto-approves requests from the configured Microsoft Learn MCP server.
- Sends the approval response back to the agent and prints the final answer.
- Deletes the temporary agent version when the script finishes.

## Files

| File | Description |
| --- | --- |
| `microsoft-learn-agent.py` | Main Python sample that creates the Azure AI Foundry agent and connects it to the Microsoft Learn MCP server. |
| `.env` | Stores the Azure AI Foundry project endpoint and model deployment name. |
| `requirements.txt` | Python package dependencies. |

## Prerequisites

- Python 3.12 or later
- Azure subscription
- Azure AI Foundry project
- Deployed model, such as `gpt-4.1`
- Azure CLI sign-in, or another credential supported by `DefaultAzureCredential`
- Access to the Microsoft Learn MCP endpoint at `https://learn.microsoft.com/api/mcp`

## Setup

Install the required packages:

```powershell
pip install -r requirements.txt
```

Create a `.env` file in this folder:

```env
PROJECT_ENDPOINT=your_project_endpoint
MODEL_DEPLOYMENT_NAME=your_model_deployment_name
```

Sign in to Azure:

```powershell
az login
```

## Run

Start the sample:

```powershell
python microsoft-learn-agent.py
```

The script sends this prompt to the agent:

```text
Give me the all the topics to study to get ready for AI-103 certification.
```

The agent can use the Microsoft Learn MCP server to retrieve relevant Microsoft Learn content, then returns the final response in the console.

## MCP Tool Configuration

The script configures the MCP tool with:

```python
MCPTool(
    server_label="api-specs",
    server_url="https://learn.microsoft.com/api/mcp",
    require_approval="always",
)
```

Because `require_approval` is set to `always`, the first response can include an MCP approval request. The script checks for approval requests from the `api-specs` server label, approves them, and sends the approval response back with `previous_response_id`.

## Notes

- The agent version is created when the script starts and deleted before the script exits.
- The script currently uses a hard-coded AI-103 certification prompt. Edit the `input` value in `microsoft-learn-agent.py` to ask a different Microsoft Learn question.
- If authentication fails, run `az login` and confirm your Azure account has access to the Foundry project.
- If the app cannot find your project or model, check the `PROJECT_ENDPOINT` and `MODEL_DEPLOYMENT_NAME` values in `.env`.
- If the MCP call does not complete, confirm the Microsoft Learn MCP endpoint is reachable and that the approval response is sent for the matching server label.
