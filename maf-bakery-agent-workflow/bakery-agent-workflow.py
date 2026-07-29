import asyncio
import json
import os
from typing import Any

from agent_framework import workflow
from agent_framework.foundry import FoundryAgent
from azure.identity import AzureCliCredential
from dotenv import load_dotenv


AGENT_NAMES = {
    "orchestrator": "bakery-orchestrator",
    "orders": "bakery-orders",
    "menu": "bakery-menu",
    "complaints": "bakery-complaints",
    "hours": "bakery-hours",
    "synthesizer": "bakery-synthesizer",
}

CATCH_ALL_TEXT = """\
That question is outside what I can help with at our bakery.
I can help with:
- Order status, changes, and refunds.
- Menu items, prices, ingredients, and allergens.
- Complaints and feedback about your order.
- Store hours, locations, and delivery coverage.
Try one of those, and I will get you the right answer."""


def parse_json_response(response_text: str) -> dict[str, Any]:
    """Parse structured agent output, tolerating an accidental Markdown fence."""
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().lower() in {"```", "```json"}:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("The agent response must be a JSON object.")
    return payload


def connect_to_agent(
    project_endpoint: str,
    credential: AzureCliCredential,
    agent_key: str,
) -> FoundryAgent:
    """Connect to the latest version of an existing Microsoft Foundry agent."""
    # Omitting agent_version makes Foundry resolve the latest saved version for
    # the requested agent name. It also keeps this compatible with Hosted Agents,
    # which are addressed by name and do not accept an explicit version.
    return FoundryAgent(
        project_endpoint=project_endpoint,
        agent_name=AGENT_NAMES[agent_key],
        credential=credential,
    )


def build_bakery_workflow(
    project_endpoint: str,
    credential: AzureCliCredential,
):
    """Build a functional workflow over the existing Foundry agents."""
    orchestrator = connect_to_agent(
        project_endpoint,
        credential,
        "orchestrator",
    )
    specialists = {
        route: connect_to_agent(project_endpoint, credential, route)
        for route in ("orders", "menu", "complaints", "hours")
    }
    synthesizer = connect_to_agent(
        project_endpoint,
        credential,
        "synthesizer",
    )

    @workflow
    async def bakery_support_workflow(user_message_text: str) -> str:
        """Route a request, call one specialist, and synthesize its response."""
        # Step 1: Invoke the existing orchestrator. Its Foundry definition
        # returns {"route": "orders|menu|complaints|hours|else"}.
        orchestrator_response = await orchestrator.run(user_message_text)
        try:
            route_payload = parse_json_response(orchestrator_response.text)
            route = str(route_payload.get("route", "else")).strip().lower()
        except (json.JSONDecodeError, TypeError, ValueError):
            route = "else"

        # Step 2: Reproduce the workflow ConditionGroup and catch-all branch.
        selected_specialist = specialists.get(route)
        if selected_specialist is None:
            return CATCH_ALL_TEXT

        # Step 3: Invoke the existing specialist. Each specialist's structured
        # response contains an answer plus its domain-specific metadata.
        specialist_response = await selected_specialist.run(user_message_text)
        try:
            specialist_payload = parse_json_response(specialist_response.text)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"The {route} specialist returned invalid JSON."
            ) from exc

        specialist_answer = specialist_payload.get("answer")
        if not isinstance(specialist_answer, str) or not specialist_answer.strip():
            raise RuntimeError(
                f"The {route} specialist response did not contain an answer."
            )

        # Step 4: Pass the original question and the complete specialist JSON to
        # the existing customer-facing synthesizer agent.
        synthesizer_input = (
            f"Customer question: {user_message_text}\n"
            f"Specialist response: {json.dumps(specialist_payload)}"
        )
        final_response = await synthesizer.run(synthesizer_input)
        return final_response.text.strip()

    return bakery_support_workflow


async def main() -> None:
    """Load configuration and stream one functional workflow execution."""
    load_dotenv()
    project_endpoint = os.getenv("PROJECT_ENDPOINT")
    if not project_endpoint:
        raise RuntimeError("Set PROJECT_ENDPOINT in .env.")

    user_message_text = os.getenv("USER_MESSAGE")
    if not user_message_text:
        user_message_text = input("Customer: ").strip()
    if not user_message_text:
        raise ValueError("Enter a customer message or set USER_MESSAGE in .env.")

    credential = AzureCliCredential()
    try:
        bakery_support_workflow = build_bakery_workflow(
            project_endpoint,
            credential,
        )

        # The functional workflow API returns a ResponseStream when stream=True.
        # It includes lifecycle events as well as the final workflow output.
        stream = bakery_support_workflow.run(user_message_text, stream=True)
        async for event in stream:
            if event.type == "output":
                print(f"\nBakery Support:\n{event.data}")

        # Awaiting the final response surfaces workflow failures and makes the
        # completed WorkflowRunResult available for state/output inspection.
        await stream.get_final_response()
    finally:
        credential.close()


if __name__ == "__main__":
    asyncio.run(main())
