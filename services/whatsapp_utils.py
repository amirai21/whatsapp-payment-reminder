import os
from twilio.rest import Client

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = "whatsapp:+14155238886"
client = Client(account_sid, auth_token)

print(f"📱 Twilio WhatsApp client initialized with {account_sid} and {twilio_number}")

def send_whatsapp_message(to: str, message: str):
    """Send WhatsApp message via Twilio sandbox."""
    print(f"📤 Sending message to {to}: {message}")
    client.messages.create(
        from_=twilio_number,
        body=message,
        to=to
    )
