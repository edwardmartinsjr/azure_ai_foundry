import json
from pathlib import Path
import uuid
from typing import Annotated
from pydantic import Field

from agent_framework import tool

# <define_tool>
# NOTE: approval_mode="never_require" is for sample brevity.
# Use "always_require" in production for user confirmation before tool execution.
@tool(approval_mode="never_require")
def create_expense(
    email_address: Annotated[str, Field(description="User email address")],
    description: Annotated[str, Field(description="Description of the expense claim")],
    claim_amount: Annotated[str, Field(description="Claim amount")],
    ) -> str:
    script_dir = Path(__file__).parent # Get current application path
    ticket_number = str(uuid.uuid4()).replace('-','')[:6]
    file_name = f"ticket-{ticket_number}.txt"
    file_path = script_dir / file_name
    text = f"Support ticket: {ticket_number}\nSubimited by: {email_address}\nDescription: {description}\nClaim amount: {claim_amount}"
    file_path.write_text(text)
    message_json = json.dumps({"message":f"Support ticket {ticket_number} subimitted."})
    return message_json
# </define_tool>
