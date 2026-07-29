# Bakery Agent Framework Workflow

This sample implements the Bakery customer-support workflow with the
[Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
functional workflow API.

The workflow is defined and executed in Python rather than in the Microsoft
Foundry visual workflow designer. Its six agents already exist in Foundry. The
Python application connects to the latest version of each agent, invokes them
in the required order, and processes their structured JSON responses.

## Architecture

```text
Customer message
      |
      v
@workflow bakery_support_workflow
      |
      v
bakery-orchestrator
      |
      +-- orders ------> bakery-orders ---------+
      +-- menu --------> bakery-menu -----------+
      +-- complaints --> bakery-complaints -----+--> bakery-synthesizer
      +-- hours -------> bakery-hours ----------+         |
      |                                                   v
      +-- else --> Out-of-scope response            Workflow output event
```

The orchestrator returns a route as structured JSON. Native Python control flow
selects one specialist, and the specialist's complete JSON response is passed
to the synthesizer. The functional workflow is executed with `stream=True`, and
the final customer response is emitted as a workflow `output` event.

## Files

| File | Purpose |
| --- | --- |
| `bakery-agent-workflow.py` | Connects to the existing Foundry agents, defines the functional workflow, streams workflow events, and prints the final response. |
| `../azure-ai-bakery-agent-workflow/OrchestratorAgent.md` | Source definition for `bakery-orchestrator`. |
| `../azure-ai-bakery-agent-workflow/OrdersAgent.md` | Source definition for `bakery-orders`. |
| `../azure-ai-bakery-agent-workflow/MenuAgent.md` | Source definition for `bakery-menu`. |
| `../azure-ai-bakery-agent-workflow/ComplaintsAgent.md` | Source definition for `bakery-complaints`. |
| `../azure-ai-bakery-agent-workflow/HoursAgent.md` | Source definition for `bakery-hours`. |
| `../azure-ai-bakery-agent-workflow/SynthesizerAgent.md` | Source definition for `bakery-synthesizer`. |

The Markdown files document the behavior and structured output configured on
the agents in Foundry. The Python application does not recreate or override
those definitions.

## Foundry Agents

All six agents must already exist in the Foundry project with these exact names:

| Agent name | Role | Model | Structured output |
| --- | --- | --- | --- |
| `bakery-orchestrator` | Classifies the request and returns its route. | GPT-4o | Required |
| `bakery-orders` | Handles order status, changes, cancellations, and refunds. | GPT-4o | Required |
| `bakery-menu` | Handles products, prices, ingredients, and allergens. | GPT-4o | Required |
| `bakery-complaints` | Handles service recovery and escalation. | GPT-4o | Required |
| `bakery-hours` | Handles hours, locations, holidays, and delivery coverage. | GPT-4o | Required |
| `bakery-synthesizer` | Produces the final customer-facing response. | Claude Opus | Required |

Models, instructions, tools, and structured-output schemas remain owned by the
Foundry agent definitions. The application uses `FoundryAgent` because it is
calling service-managed agents rather than defining agents locally with
`Agent` and `FoundryChatClient`.

The application supplies each `FoundryAgent` with its name but no explicit
version, allowing Foundry to resolve the latest saved agent version.

## Prerequisites

- Python 3.11 or later
- Azure subscription
- Microsoft Foundry project
- Six configured Foundry agents listed above
- Azure CLI
- Permission to invoke agents in the Foundry project

Install the Python dependencies:

```powershell
pip install agent-framework-foundry azure-identity python-dotenv
```

The functional workflow API is provided by Agent Framework core, which is
installed as a dependency of the Foundry integration.

## Configure the Environment

Create `.env` inside `maf-bakery-agent-workflow`:

```env
PROJECT_ENDPOINT=https://your-project.services.ai.azure.com/api/projects/your-project
```

`PROJECT_ENDPOINT` is the only required application setting. Copy the project
endpoint from the Foundry portal.

For automated or repeatable testing, an input message can optionally be
provided through:

```env
USER_MESSAGE=Can I change my order? It was placed 10 minutes ago.
```

When `USER_MESSAGE` is omitted, the application prompts for a customer message.

## Authenticate

The sample uses `AzureCliCredential`, so sign in before running it:

```powershell
az login
```

Confirm that the signed-in identity can access the Foundry project and invoke
its agents.

## Functional Workflow

The workflow is created with the Agent Framework `@workflow` decorator:

```python
@workflow
async def bakery_support_workflow(user_message_text: str) -> str:
    ...
```

The pipeline performs four stages:

1. Invoke `bakery-orchestrator` and parse its structured `route`.
2. Select `bakery-orders`, `bakery-menu`, `bakery-complaints`, or
   `bakery-hours` using native Python control flow.
3. Parse the selected specialist's structured JSON response.
4. Send the original question and complete specialist response to
   `bakery-synthesizer`.

If the orchestrator returns `else` or invalid routing JSON, the workflow returns
the supported-topics message without invoking a specialist or the synthesizer.

## Why `@workflow` Instead of `WorkflowBuilder`?

Microsoft Agent Framework supports more than one way to define a workflow. This
sample uses the **functional workflow API**, where an ordinary asynchronous
Python function is decorated with `@workflow`:

```python
@workflow
async def bakery_support_workflow(user_message_text: str) -> str:
    route = await determine_route(user_message_text)

    if route == "orders":
        specialist_response = await run_orders_agent(user_message_text)
    elif route == "menu":
        specialist_response = await run_menu_agent(user_message_text)
    ...
```

The decorator turns the function into an Agent Framework workflow. It adds the
workflow runtime, `.run()`, event streaming, lifecycle state, and final-result
handling while allowing the implementation to use normal Python control flow.

This approach fits the bakery workflow because its logic is small and maps
naturally to an `if`/`elif` branch:

1. Invoke the orchestrator.
2. Select one specialist from the returned route.
3. Return the catch-all response or invoke the selected specialist.
4. Send the specialist response to the synthesizer.

### Functional API

The functional API emphasizes plain asynchronous Python:

```python
stream = bakery_support_workflow.run(message, stream=True)
```

It is a good fit when:

- Native Python `if`/`else`, loops, and `asyncio.gather()` express the workflow
  clearly.
- The pipeline is relatively small.
- Minimal framework-specific plumbing is preferred.
- Workflow execution, lifecycle events, streaming, and final-state handling are
  still required.
- Individual operations may later be decorated with `@step` for checkpointing
  or observability.

### `WorkflowBuilder` API

`WorkflowBuilder` is the explicit graph API. Each activity is represented as an
executor node, and edges define how data moves between nodes. The bakery
workflow could instead be modeled as:

```text
OrchestratorExecutor
    |
    +-- route=orders ------> OrdersExecutor ------+
    +-- route=menu --------> MenuExecutor --------+
    +-- route=complaints --> ComplaintsExecutor --+--> SynthesizerExecutor
    +-- route=hours -------> HoursExecutor -------+
    |
    +-- route=else --------> CatchAllExecutor
```

That representation makes the graph topology explicit and inspectable. It is a
better fit when the solution needs:

- Explicit executor nodes and conditional edges.
- Switch-case edge groups.
- Fan-out/fan-in or parallel branches.
- Reusable executor components.
- Graph visualization.
- Detailed executor-level events and observability.
- Complex loops, handoffs, or checkpoint boundaries.
- A code representation that closely mirrors a visual workflow diagram.

### Why the Functional API Was Chosen

Both APIs can implement equivalent bakery-routing behavior. The functional API
was selected because the route-to-specialist decision is straightforward and
more readable as native Python control flow. It avoids introducing executor
classes and graph edges when a single decorated function expresses the same
logic clearly.

`WorkflowBuilder` would be a reasonable alternative if this sample grows into a
larger orchestration, needs graph visualization, or should mirror the Foundry
visual workflow node-for-node. Choosing `@workflow` does not mean the code is
running outside Agent Framework: the decorated function is executed by the
Agent Framework workflow runtime and exposes the same streaming entry point
used by the functional workflow samples.

## Streaming Execution

The application starts the functional workflow as a stream:

```python
stream = bakery_support_workflow.run(user_message_text, stream=True)
```

Agent Framework emits lifecycle and application events while the workflow runs.
The application filters for the final workflow output:

```python
async for event in stream:
    if event.type == "output":
        print(event.data)
```

After consuming the stream, `get_final_response()` completes the workflow run
and surfaces workflow failures:

```python
await stream.get_final_response()
```

This is workflow-event streaming. The current sample emits the completed
customer response as one output event; it does not print token-by-token output
from the individual Foundry agents.

## Run the Workflow

From the repository root:

```powershell
python maf-bakery-agent-workflow\bakery-agent-workflow.py
```

Without `USER_MESSAGE`, enter a request at the prompt:

```text
Customer: Does the almond croissant contain nuts?
```

Example output:

```text
Bakery Support:
Yes. The almond croissant contains tree nuts, along with gluten, dairy, and eggs.
```

## Test Cases

| Test message | Expected route |
| --- | --- |
| `Can I change order B-1042?` | `orders` |
| `Does the almond croissant contain nuts?` | `menu` |
| `My cake arrived damaged.` | `complaints` |
| `Is the Midtown store open on Sunday?` | `hours` |
| `What is the weather today?` | `else` |

For the first four routes, the final visible text should come from
`bakery-synthesizer`. An out-of-scope request should return the local catch-all
message.

## Error Handling

The application:

- Defaults to the `else` route when orchestrator JSON is invalid.
- Accepts an accidental JSON Markdown code fence.
- Raises a clear error when a specialist returns invalid JSON.
- Requires a non-empty specialist `answer`.
- Raises a clear error when `PROJECT_ENDPOINT` is missing.
- Uses `get_final_response()` so workflow execution failures are not silently
  ignored.

## Troubleshooting

- **Agent not found:** Confirm all six names match the table exactly and exist
  in the project referenced by `PROJECT_ENDPOINT`.
- **Authentication fails:** Run `az login` and verify the signed-in identity has
  access to the Foundry project.
- **Import fails:** Install or update `agent-framework-foundry`,
  `azure-identity`, and `python-dotenv`.
- **Routing always falls back:** Verify the orchestrator's Foundry response
  format returns a JSON object with a `route` property.
- **Specialist JSON fails:** Verify the selected specialist uses the structured
  schema in its corresponding Markdown definition.
- **No final output appears:** Inspect all streamed event types and await
  `stream.get_final_response()` to expose the underlying workflow error.
- **Follow-up messages lose context:** This sample runs one independent workflow
  invocation. Add Agent Framework sessions and reuse them across invocations
  when multi-turn conversation history is required.

## Agent Framework References

- [Workflow samples](https://github.com/microsoft/agent-framework/tree/main/python/samples/03-workflows)
- [Basic streaming functional pipeline](https://github.com/microsoft/agent-framework/blob/main/python/samples/03-workflows/functional/basic_streaming_pipeline.py)
- [Functional workflow agent integration](https://github.com/microsoft/agent-framework/blob/main/python/samples/03-workflows/functional/agent_integration.py)
- [Microsoft Foundry provider](https://learn.microsoft.com/agent-framework/agents/providers/microsoft-foundry)

## Production Considerations

For a production application:

- Reuse credentials, agents, and workflow instances instead of rebuilding them
  for every request.
- Add persistent Agent Framework sessions for multi-turn conversations.
- Add telemetry, correlation IDs, retries, and timeout policies.
- Validate structured output against explicit application schemas.
- Keep menu, order, hours, and delivery data in authoritative systems connected
  to the specialist agents.
- Require authentication and human approval before modifying orders, issuing
  refunds, or performing other real-world actions.
