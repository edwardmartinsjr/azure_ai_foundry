# Agent Framework MCP Agents

This folder contains Microsoft Agent Framework samples that connect Azure AI Foundry-backed agents to remote Model Context Protocol (MCP) servers.

## What is MCP?

The Model Context Protocol (MCP) is an open standard for connecting AI agents to external tools, data sources, and services through a standardized protocol. These samples use hosted MCP tools with Azure AI Foundry so the agent can call external services through MCP.

## Example

| Sample file | Description |
| --- | --- |
| `microsoft-learn-agent.py` | Creates a Microsoft Agent Framework agent backed by Azure AI Foundry and configures a hosted MCP tool for Microsoft Learn. |
| `github-pat-agent.py` | Creates a Microsoft Agent Framework agent backed by Azure AI Foundry and configures a hosted MCP tool for GitHub using a Personal Access Token (PAT). |

The app in `microsoft-learn-agent.py`:

- Loads Azure AI Foundry settings from `.env`.
- Authenticates with `AzureCliCredential`.
- Creates a `FoundryChatClient` for the configured Azure AI Foundry project and model deployment.
- Registers the Microsoft Learn MCP endpoint with `client.get_mcp_tool(...)`.
- Creates an Agent Framework agent named `Microsoft-Learn-Assistant`.
- Sends a sample AI-103 certification study prompt to the agent.
- Prints the agent response in the console.

The app in `github-pat-agent.py`:

- Loads Azure AI Foundry and GitHub settings from `.env`.
- Authenticates to Azure with `AzureCliCredential`.
- Creates a `FoundryChatClient` for the configured Azure AI Foundry project and model deployment.
- Reads `GITHUB_PAT` and sends it to the GitHub MCP server in an authorization header.
- Registers the GitHub MCP endpoint with `client.get_mcp_tool(...)`.
- Creates an Agent Framework agent named `GitHubAgent`.
- Sends sample prompts to inspect the authenticated GitHub account and list repositories.
- Prints the agent responses in the console.

## Prerequisites

- Python 3.12 or later
- Azure subscription
- Azure AI Foundry project
- Deployed model, such as `gpt-4.1`
- Azure CLI sign-in with access to the Foundry project
- Access to the Microsoft Learn MCP endpoint at `https://learn.microsoft.com/api/mcp`
- For the GitHub sample, a GitHub Personal Access Token with scopes appropriate for the operations you want to test

## Setup

Install the required packages:

```powershell
pip install -r requirements.txt
```

Create a `.env` file in this folder:

```env
PROJECT_ENDPOINT=your_project_endpoint
MODEL_DEPLOYMENT_NAME=your_model_deployment_name
GITHUB_PAT=your_github_personal_access_token
```

`GITHUB_PAT` is only required for `github-pat-agent.py`.

Sign in to Azure:

```powershell
az login
```

## Run

Start the Microsoft Learn sample:

```powershell
python microsoft-learn-agent.py
```

The script sends this prompt to the agent:

```text
Give me the all the topics to study to get ready for AI-103 certification.
```

The agent can call the hosted Microsoft Learn MCP tool through Azure AI Foundry and then return the final answer in the console.

Start the GitHub PAT sample:

```powershell
python github-pat-agent.py
```

The script sends two prompts to the agent:

```text
What is my GitHub username and tell me about my account?
List all the repositories I own on GitHub
```

The agent can call the hosted GitHub MCP tool through Azure AI Foundry and return account and repository information based on the permissions granted to the PAT.

## MCP Tool Configuration

The Microsoft Learn sample creates the MCP tool with:

```python
microsoft_learn_mcp_tool = client.get_mcp_tool(
    name="LearnMicrosoft",
    url="https://learn.microsoft.com/api/mcp",
    approval_mode="never_require",
)
```

The GitHub sample creates the MCP tool with:

```python
github_mcp_tool = client.get_mcp_tool(
    name="GitHub",
    url="https://api.githubcopilot.com/mcp/",
    headers=auth_headers,
    approval_mode="never_require",
)
```

Both samples convert the MCP tool to a plain dictionary before it is passed to `Agent`. This avoids a non-blocking Agent Framework parser warning for hosted MCP tool objects while preserving the same Foundry MCP tool definition.

## Notes

- `approval_mode="never_require"` allows the MCP tool to run without an interactive approval step.
- The MCP tool is hosted and executed remotely by Azure AI Foundry, not by this local Python process.
- The samples currently use hard-coded prompts. Edit the `query` values in each script to ask different Microsoft Learn or GitHub questions.
- Keep `GITHUB_PAT` in `.env` or another local secret store. Do not commit it.
- If authentication fails, run `az login` and confirm your Azure account has access to the Foundry project.
- If the app cannot find your project or model, check the `PROJECT_ENDPOINT` and `MODEL_DEPLOYMENT_NAME` values in `.env`.
