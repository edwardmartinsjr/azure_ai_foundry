# Inventory Search Context Agent

This folder contains a Microsoft Agent Framework sample that uses Azure AI Search and Azure AI Foundry to analyze warehouse inventory data.

The sample demonstrates two related workflows:

- Loading a structured warehouse inventory CSV into an Azure AI Search index.
- Running an Azure AI Foundry-backed inventory agent with Azure AI Search context for inventory analysis prompts.

The inventory agent is designed to help identify inventory discrepancies, current slow movers, future slow-mover risk, likely root causes, and practical corrective actions.

## Files

| File | Description |
| --- | --- |
| `search_context_agentic.py` | Main Agent Framework sample that connects an Azure AI Foundry chat client to an Azure AI Search context provider in agentic mode. |
| `agent_instructions.md` | System instructions for the inventory agent. |
| `load_inventory.py` | Loads `warehouse_inventory.csv` into the configured Azure AI Search index in batches. |
| `ds_inventory_json_schema.json` | Azure AI Search index schema for the inventory dataset, including semantic configuration. |
| `warehouse_inventory.csv` | Synthetic warehouse inventory time-series dataset. |
| `warehouse_inventory_analysis.pbix` | Power BI report file for inventory analysis. |
| `.env` | Stores local Azure AI Foundry and Azure AI Search settings. |
| `requirements.txt` | Python package dependencies. |

## Prerequisites

- Python 3.12 or later
- Azure subscription
- Azure AI Foundry project
- Deployed model, such as `gpt-4o`
- Azure AI Search service
- Azure CLI sign-in with access to the Foundry project, or an Azure Search API key in `.env`
- An Azure AI Search index named for `AZURE_SEARCH_INDEX_NAME`
- Optional Azure AI Search Knowledge Base for agentic retrieval

## Setup

Install the required packages:

```powershell
pip install -r requirements.txt
```

Create a `.env` file in this folder:

```env
PROJECT_ENDPOINT=your_project_endpoint
MODEL_DEPLOYMENT_NAME=your_model_deployment_name
AZURE_SEARCH_ENDPOINT=https://your-search-service.search.windows.net
AZURE_SEARCH_INDEX_NAME=ds_inventory
AZURE_SEARCH_API_KEY=your_search_api_key
AZURE_SEARCH_KNOWLEDGE_BASE_NAME=your_knowledge_base_name
AZURE_OPENAI_RESOURCE_URL=your_azure_openai_resource_url
```

`AZURE_SEARCH_KNOWLEDGE_BASE_NAME` is used when connecting to an existing Foundry IQ Knowledge Base. `AZURE_OPENAI_RESOURCE_URL` is only required when the script auto-creates a knowledge base from an index.

Sign in to Azure if you are using Azure CLI credentials:

```powershell
az login
```

## Create the Search Index

Create or recreate the Azure AI Search index using `ds_inventory_json_schema.json`.

The schema includes fields for:

- `id`
- `sku`
- `warehouse_id`
- `category`
- `snapshot_date`
- `on_hand_qty`
- `received_qty`
- `shipped_qty`
- `unit_cost`

It also includes a default semantic configuration named:

```text
inventory-semantic-config
```

If you change field types, key fields, or searchable settings, recreate the index before loading data.

## Load Data

Load the inventory CSV into Azure AI Search:

```powershell
python load_inventory.py
```

For gentler pacing on the Azure AI Search Free tier:

```powershell
python load_inventory.py --batch-size 500 --batch-delay-seconds 1 --max-retries 10
```

The loader streams the CSV, converts values to the live index field types, generates document keys when needed, and retries transient Azure Search throttling errors.

## Knowledge Base Configuration

When creating a Foundry IQ Knowledge Base from the inventory index, use the existing semantic configuration:

```text
Semantic configuration: inventory-semantic-config
```

Recommended advanced settings:

```text
Source data fields:
id, sku, warehouse_id, category, snapshot_date, on_hand_qty, received_qty, shipped_qty, unit_cost

Search fields:
sku, warehouse_id, category
```

Use retrieval instructions that ask Foundry IQ to preserve time-series context, SKU and warehouse identifiers, dates, quantities, and unit cost values.

## Run the Agent

Start the inventory agent:

```powershell
python search_context_agentic.py
```

The script loads instructions from `agent_instructions.md`, connects to Azure AI Foundry, attaches the Azure AI Search context provider, and sends the sample prompt in `USER_INPUTS`.

Edit `USER_INPUTS` in `search_context_agentic.py` to test other inventory questions.

Example prompt:

```text
Using the knowledge base, retrieve records for warehouse_id WH-WEST in October 2024. Include snapshot_date, sku, on_hand_qty, received_qty, and shipped_qty in the response.
```

## Notes

- The inventory dataset is structured time-series data. Azure AI Search semantic and knowledge-base retrieval can help with lookup-style questions, but full analytical scans across all SKUs are usually better handled with direct Azure Search filters or Python aggregation before passing summarized findings to the agent.
- Keep `.env` local. Do not commit Azure Search keys or project credentials.
- The Azure AI Search Free tier has a 50 MB storage quota. If indexing fails with quota or throttling errors, reduce the CSV size, recreate the index, or move to a larger Search tier.
- If the agent says no data was provided, confirm that the Knowledge Base returns sources in the Azure portal and that the source data fields include the numeric and date fields needed for analysis.

## Troubleshooting

- If authentication fails, run `az login` or confirm `AZURE_SEARCH_API_KEY` is valid.
- If the app cannot find your project or model, check `PROJECT_ENDPOINT` and `MODEL_DEPLOYMENT_NAME`.
- If Foundry IQ cannot find eligible indexes, confirm the index has a default semantic configuration and that semantic fields are searchable, retrievable string fields.
- If indexing fails with `429 Too Many Requests`, lower `--batch-size`, increase `--batch-delay-seconds`, or wait for the Search service to recover.
- If the index is over quota, delete and recreate the index before reloading a smaller dataset.
