# Bakery Agent Workflow

This sample implements a multi-agent customer-support workflow for Edward's
Bakery in Microsoft Foundry. The workflow runs in the Foundry workflow builder,
and every agent is created directly in the Foundry portal by using the
instructions and structured-output definitions in this folder.

The orchestrator classifies each customer message, the workflow routes it to the
appropriate specialist, and a synthesizer turns the specialist's structured
answer into a friendly customer-facing response.

## Architecture

```text
Customer message
      |
      v
bakery-orchestrator
      |
      +-- orders ------> bakery-orders ---------+
      +-- menu --------> bakery-menu -----------+
      +-- complaints --> bakery-complaints -----+--> bakery-synthesizer
      +-- hours -------> bakery-hours ----------+         |
      |                                                   v
      +-- else --> Out-of-scope message             Final response
```

All agent invocations use the Foundry conversation ID so that follow-up
questions can retain the conversation context.

## Files

| File | Foundry agent or purpose |
| --- | --- |
| `OrchestratorAgent.md` | Defines `bakery-orchestrator`, which returns an `orders`, `menu`, `complaints`, `hours`, or `else` route. |
| `OrdersAgent.md` | Defines `bakery-orders` for order status, modifications, cancellations, refunds, and custom-order timelines. |
| `MenuAgent.md` | Defines `bakery-menu` for products, prices, ingredients, allergens, and dietary options. |
| `ComplaintsAgent.md` | Defines `bakery-complaints` for service recovery and escalation. |
| `HoursAgent.md` | Defines `bakery-hours` for opening hours, locations, holidays, and delivery coverage. |
| `SynthesizerAgent.md` | Defines `bakery-synthesizer`, which creates the final customer-facing response. |
| `workflow.yaml` | Contains the Foundry workflow definition, including variables, agent invocations, routing conditions, and the fallback response. |

## Prerequisites

- An Azure subscription
- A Microsoft Foundry project
- Access to the Foundry portal at [https://ai.azure.com](https://ai.azure.com)
- GPT-4o and Claude Opus model deployments available to the project
- Permission to create agents and workflows in the project

The workflow builder may be shown as a preview feature, depending on the
Foundry portal version and region.

## Create the Agents in Foundry

Create the agents before creating the workflow, because `workflow.yaml`
references them by name.

For each Markdown file:

1. Open the Foundry portal and select your project.
2. Open the agent builder and create a new agent.
3. Select the model deployment listed in the table below.
4. Set the agent name exactly as shown below.
5. Copy the text between the **Instructions** separators into the agent's
   instructions field.
6. When the Markdown file includes a **Structured JSON** section, configure the
   agent to use that JSON schema as its structured response format.
7. Save the agent.

Create these agents:

| Markdown definition | Required agent name | Model | Structured output |
| --- | --- | --- | --- |
| `OrchestratorAgent.md` | `bakery-orchestrator` | GPT-4o | Required |
| `OrdersAgent.md` | `bakery-orders` | GPT-4o | Required |
| `MenuAgent.md` | `bakery-menu` | GPT-4o | Required |
| `ComplaintsAgent.md` | `bakery-complaints` | GPT-4o | Required |
| `HoursAgent.md` | `bakery-hours` | GPT-4o | Required |
| `SynthesizerAgent.md` | `bakery-synthesizer` | Claude Opus | Required |

Agent names must match exactly. The workflow looks up each agent by its saved
name. GPT-4o handles routing and structured specialist responses. Claude Opus
is used for the synthesizer to produce the best customer-facing tone and
wording.

## Create the Workflow in Foundry

Create a blank workflow in the Foundry workflow builder. Use
`BakeryOrchestrator` as the workflow name, then load or reproduce the
definition in `workflow.yaml` using the workflow code editor.

If your Foundry portal does not provide a workflow code editor or import action,
create the same nodes in the visual designer:

1. Use an **On conversation start** trigger.
2. Store `System.LastMessage.Text` in `Local.question`.
3. Convert the incoming text to a user message and store it in
   `Local.UserMessage`.
4. Invoke `bakery-orchestrator` with `Local.UserMessage` and save its structured
   response as `Local.OrchestratorResponse`.
5. Convert `Local.OrchestratorResponse.route` to lowercase and save it as
   `Local.Route`.
6. Add conditional branches that invoke the matching specialist:

   | Route | Agent | Response variable |
   | --- | --- | --- |
   | `orders` | `bakery-orders` | `Local.SpecialistResponse` |
   | `menu` | `bakery-menu` | `Local.SpecialistResponse` |
   | `complaints` | `bakery-complaints` | `Local.SpecialistResponse` |
   | `hours` | `bakery-hours` | `Local.SpecialistResponse` |

7. In the `else` branch, send the out-of-scope message defined in
   `workflow.yaml`.
8. For a recognized route, build `Local.SynthesizerInput` from the original
   question and `Local.SpecialistResponse.answer`.
9. Invoke `bakery-synthesizer` with `Local.SynthesizerInput` and use its output
   as the final customer response.
10. Save the workflow.

The workflow definition uses `System.ConversationId` for every agent invocation.
Keep this mapping when reproducing the workflow so agents can interpret
follow-up questions in the current conversation.

## Preview and Test

Open the workflow preview and try messages such as:

| Test message | Expected route |
| --- | --- |
| `Can I change order B-1042?` | `orders` |
| `Does the almond croissant contain nuts?` | `menu` |
| `My cake arrived damaged.` | `complaints` |
| `Is the Midtown store open on Sunday?` | `hours` |
| `What is the weather today?` | `else` |

For a recognized bakery request, the final visible answer should be concise,
friendly prose from `bakery-synthesizer`. An unrelated request should receive
the workflow's supported-topics message.

Also test a follow-up in the same conversation, for example:

```text
Customer: Can you check order B-1042?
Customer: What was that order number?
```

The orchestrator instructions tell it to use conversation history when routing
such references.

## Troubleshooting

- **Agent not found:** Confirm that all six agent names exactly match the names
  listed in this README.
- **A routing condition never matches:** Verify that the orchestrator uses its
  strict structured-output schema and returns the `route` property.
- **The specialist response has no `answer`:** Confirm that each specialist has
  the structured schema from its Markdown definition.
- **The synthesizer receives an empty value:** Check that every specialist saves
  its structured response object to `Local.SpecialistResponse`.
- **Follow-up questions lose context:** Ensure every agent node uses
  `System.ConversationId`.
- **Customers see intermediate JSON:** Disable automatic sending on the
  orchestrator and specialist invocations in the visual designer, while still
  saving their response objects. Only the fallback or synthesizer result should
  be customer-facing.

## Notes

This sample keeps bakery facts inside the agent instructions to make the
workflow self-contained. For a production solution, store changing information
such as menus, prices, hours, order state, and delivery coverage in authoritative
data sources and connect the specialist agents to those sources. Add
authentication and human approval before allowing an agent to modify an order,
issue a refund, or perform another real-world action.
