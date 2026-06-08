# Azure AI Foundry Exercises

Hands-on exercises for learning how to build AI agents and AI-powered applications with Azure AI Foundry.

Each exercise is organized in its own folder and includes the code, dependencies, setup notes, and run instructions needed for that scenario. Use this root README as the starting point, then open the README inside a specific exercise folder for detailed guidance.

## Repository Contents

| Exercise | Description |
| --- | --- |
| [`agent-custom-tools/`](agent-custom-tools/) | Python console app that creates an Azure AI Foundry agent with a custom function tool for submitting expense claims. |

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

For example, to run the custom-tools exercise:

```powershell
cd agent-custom-tools
pip install -r requirements.txt
```

Create any required local configuration files described by the exercise README. For `agent-custom-tools/`, create a `.env` file with:

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
python agent.py
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

Start with [agent-custom-tools/README.md](agent-custom-tools/README.md) for the current exercise.

## Generated Files

Some exercises may create local output files, logs, temporary agents, or other generated artifacts. Check each exercise README for details about what is created and whether cleanup is automatic.

## Reporting Issues

If you encounter a problem with an exercise, open an issue in this repository and include:

- The exercise folder you were running
- Your Python version
- The command that failed
- The relevant error message or traceback
