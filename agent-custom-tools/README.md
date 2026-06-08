# Expense Agent

This folder contains a Python console app that creates an Azure AI Foundry agent with a custom function tool for submitting expense claims.

The app in `agent.py`:

- Loads Azure AI Foundry settings from `.env`.
- Connects to an Azure AI Foundry project with `DefaultAzureCredential`.
- Creates an agent named `ExpenseAgent-PRO`.
- Registers the `create_expense` custom function from `functions.py` as a tool.
- Starts an interactive chat loop in the terminal.
- Calls the custom function when the user wants to submit an expense claim.
- Writes each submitted claim to a local `ticket-<number>.txt` file.
- Deletes the temporary agent version when the chat session ends.

## Files

| File | Description |
| --- | --- |
| `agent.py` | Main console application that creates and runs the expense agent. |
| `functions.py` | Defines the `create_expense` function tool used by the agent. |
| `.env` | Stores the Azure AI Foundry endpoint and model deployment name. |
| `requirements.txt` | Python package dependencies. |
| `ticket-*.txt` | Generated expense claim ticket files. |

## Prerequisites

- Python 3.13 or later
- Azure subscription
- Azure AI Foundry project
- Deployed model, such as `gpt-4.1`
- Azure CLI sign-in or another credential supported by `DefaultAzureCredential`

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

At the prompt, ask the agent to create an expense claim. For example:

```text
I need to submit an expense claim. My email is alex@contoso.com. The claim is for a client dinner, and the amount is 84.50 USD.
```

To exit the chat, enter:

```text
quit
```

## Function Tool

The agent can call this custom function:

```python
create_expense(email_address: str, description: str, claim_amount: str)
```

The function creates a local ticket file in the same folder as the script. The ticket contains:

- Ticket number
- Submitter email address
- Expense description
- Claim amount

The function returns a JSON message confirming the ticket number.

## Notes

- The agent version is created when the app starts and deleted after you enter `quit`.
- If the app fails to authenticate, run `az login` and confirm your Azure account has access to the Foundry project.
- If the app cannot find your project or model, check the `PROJECT_ENDPOINT` and `MODEL_DEPLOYMENT_NAME` values in `.env`.
- Generated `ticket-*.txt` files are created locally and are not submitted to an external expense system.
