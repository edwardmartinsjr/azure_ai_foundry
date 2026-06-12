# Agent Framework Microsoft Learn MCP Agent

This folder contains a Microsoft Agent Framework sample that connects an Azure AI Foundry-backed agent to the Microsoft Learn Model Context Protocol (MCP) server.

## What is MCP?

The Model Context Protocol (MCP) is an open standard for connecting AI agents to external tools, data sources, and services through a standardized protocol. In this sample, the agent uses the Microsoft Learn MCP endpoint to retrieve information that can help answer Microsoft Learn and certification-related questions.

## Example

| Sample file | Description |
| --- | --- |
| `microsoft-learn-agent.py` | Creates a Microsoft Agent Framework agent backed by Azure AI Foundry and configures a hosted MCP tool for Microsoft Learn. |

The app in `microsoft-learn-agent.py`:

- Loads Azure AI Foundry settings from `.env`.
- Authenticates with `AzureCliCredential`.
- Creates a `FoundryChatClient` for the configured Azure AI Foundry project and model deployment.
- Registers the Microsoft Learn MCP endpoint with `client.get_mcp_tool(...)`.
- Creates an Agent Framework agent named `Microsoft-Learn-Assistant`.
- Sends a sample AI-103 certification study prompt to the agent.
- Prints the agent response in the console.

## Prerequisites

- Python 3.12 or later
- Azure subscription
- Azure AI Foundry project
- Deployed model, such as `gpt-4.1`
- Azure CLI sign-in with access to the Foundry project
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

The agent can call the hosted Microsoft Learn MCP tool through Azure AI Foundry and then return the final answer in the console.

## MCP Tool Configuration

The script creates the MCP tool with:

```python
microsoft_learn_mcp_tool = client.get_mcp_tool(
    name="LearnMicrosoft",
    url="https://learn.microsoft.com/api/mcp",
    approval_mode="never_require",
)
```

The tool is converted to a plain dictionary before it is passed to `Agent`. This avoids a non-blocking Agent Framework parser warning for hosted MCP tool objects while preserving the same Foundry MCP tool definition.

## Notes

- `approval_mode="never_require"` allows the MCP tool to run without an interactive approval step.
- The MCP tool is hosted and executed remotely by Azure AI Foundry, not by this local Python process.
- The sample currently uses a hard-coded AI-103 certification prompt. Edit the `query` value in `microsoft-learn-agent.py` to ask a different Microsoft Learn question.
- If authentication fails, run `az login` and confirm your Azure account has access to the Foundry project.
- If the app cannot find your project or model, check the `PROJECT_ENDPOINT` and `MODEL_DEPLOYMENT_NAME` values in `.env`.
