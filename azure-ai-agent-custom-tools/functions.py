import json
from pathlib import Path
import uuid


def create_expense(email_address: str, description: str, claim_amount: str):
    script_dir = Path(__file__).parent # Get current application path
    ticket_number = str(uuid.uuid4()).replace('-','')[:6]
    file_name = f"ticket-{ticket_number}.txt"
    file_path = script_dir / file_name
    text = f"Support ticket: {ticket_number}\nSubimited by: {email_address}\nDescription: {description}\nClaim amount: {claim_amount}"
    file_path.write_text(text)
    message_json = json.dumps({"message":f"Support ticket {ticket_number} subimitted."})
    return message_json
