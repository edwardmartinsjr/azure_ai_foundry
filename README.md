# Azure AI Foundry Exercises

Hands-on exercises for learning how to build AI agents and AI-powered applications with Azure AI Foundry.

Each exercise is organized in its own folder and includes the code, dependencies, setup notes, and run instructions needed for that scenario. Use this root README as the starting point, then open the README inside a specific exercise folder for detailed guidance.

## Repository Contents

| Exercise | Description |
| --- | --- |
| [`azure-ai-agent-custom-tools/`](azure-ai-agent-custom-tools/) | Python console app that creates an Azure AI Foundry agent with a custom function tool for submitting expense claims. |
| [`azure-ai-agent-mcp/`](azure-ai-agent-mcp/) | Python sample that creates an Azure AI Foundry agent with a Microsoft Learn Model Context Protocol (MCP) tool. |
| [`maf-agent-custom-tools/`](maf-agent-custom-tools/) | Microsoft Agent Framework samples for an Azure AI Foundry-backed expense agent, including console and Dev UI variants. |
| [`azure-ai-agent-workflow/`](azure-ai-agent-workflow/) | Python client for invoking a Microsoft Foundry customer support triage workflow that classifies tickets and drafts responses. |

## Prerequisites

Requirements can vary by exercise, but most local exercises use:

- Python 3.12 or later
- An Azure subscription
- An Azure AI Foundry project
- One or more deployed model deployments
- Azure CLI sign-in, or another credential supported by the Azure SDK

Your Azure account must have permission and quota to create the required Azure resources and use the selected model deployments. If you do not already have an Azure subscription, you can create one at [azure.microsoft.com/free](https://azure.microsoft.com/free).

## How to Use This Repository

Choose an exercise folder, then follow the README in that folder.

For example, to run the Agent Framework exercise:

```powershell
cd maf-agent-custom-tools
pip install -r requirements.txt
```

Create any required local configuration files described by the exercise README. Create a `.env` file with:

```env
PROJECT_ENDPOINT=your_project_endpoint
MODEL_DEPLOYMENT_NAME=your_model_deployment_name
```

Sign in to Azure:

```powershell
az login
```

Run the exercise:

```powershell
python expenses-agent.py
```

Follow the exercise README for sample prompts, expected behavior, and cleanup notes.

## Exercise READMEs

Each exercise folder should include its own `README.md` with:

- What the exercise demonstrates
- Required Azure resources and model deployments
- Local setup steps
- Run commands
- Cleanup notes
- Troubleshooting guidance

For example, start with [maf-agent-custom-tools/README.md](maf-agent-custom-tools/README.md) for the Agent Framework expense-agent exercise, or [azure-ai-agent-mcp/README.md](azure-ai-agent-mcp/README.md) for the Microsoft Learn MCP agent exercise.

## Generated Files

Some exercises may create local output files, logs, temporary agents, or other generated artifacts. Check each exercise README for details about what is created and whether cleanup is automatic.

## Reporting Issues

If you encounter a problem with an exercise, open an issue in this repository and include:

- The exercise folder you were running
- Your Python version
- The command that failed
- The relevant error message or traceback
