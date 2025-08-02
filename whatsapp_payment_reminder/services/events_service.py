from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
import random
from fastapi import HTTPException
from whatsapp_payment_reminder.services.session_store import session_store
from whatsapp_payment_reminder.services.whatsapp_utils import send_whatsapp_message
from whatsapp_payment_reminder.utils.templates import REMINDER_STYLES, admin_confirmation_msg
from whatsapp_payment_reminder.services import db_service


def handle_create_event(from_number: str, body: str):
    try:
        # --- Split command & arguments ---
        _, content = body.split(":", 1)
        parts = content.strip().split()

        if len(parts) < 2:
            send_whatsapp_message(
                from_number,
                "❌ Format: create event: Title Amount [style] [freq=MINUTES] [delay=MINUTES]\n\n"
                "👉 Example: create event: Picnic 50 mafia freq=30 delay=10"
            )
            return

        # --- Required fields ---
        title = parts[0]
        try:
            amount = float(parts[1])
        except ValueError:
            send_whatsapp_message(from_number, "❌ Amount must be a number (e.g. create event: Picnic 30 mafia)")
            return

        # --- Defaults ---
        style = "mafia"               # default style
        frequency_minutes = 60        # default: every 60 minutes
        start_delay_minutes = 0       # default: start immediately

        # --- Parse optional style, freq=, delay= ---
        for part in parts[2:]:
            if part in ["mafia", "grandpa", "broker"]:
                style = part
            elif part.startswith("freq="):
                try:
                    frequency_minutes = int(part.split("=")[1])
                except ValueError:
                    send_whatsapp_message(from_number, "❌ Invalid freq= value (must be a number, e.g. freq=30)")
                    return
            elif part.startswith("delay="):
                try:
                    start_delay_minutes = int(part.split("=")[1])
                except ValueError:
                    send_whatsapp_message(from_number, "❌ Invalid delay= value (must be a number, e.g. delay=10)")
                    return

        # --- Calculate start time ---
        start_time = datetime.utcnow() + timedelta(minutes=start_delay_minutes)

        # --- Unique event ID (phone + title) ---
        event_id = from_number.replace("whatsapp:", "") + "-" + title.lower()

        # --- Admin lookup or creation ---
        # --- ✅ Create event in DB ---
        new_event = db_service.create_event(
            from_number=from_number,
            title=title,
            amount=amount,
            style=style,
            frequency_minutes=frequency_minutes,
            start_time=start_time,
        )

        # --- ✅ Track state for adding members ---
        session_store[from_number] = {"state": "ADDING_MEMBERS", "event_id": event_id}

        # --- ✅ Confirmation to admin ---
        send_whatsapp_message(
            from_number,
            admin_confirmation_msg.format(
                title=title,
                style=style,
                frequency_minutes=frequency_minutes,
                start_time=start_time.strftime('%Y-%m-%d %H:%M UTC')
            )
        )

    except IntegrityError:
        send_whatsapp_message(
            from_number,
            f"⚠️ An event with the name *{title}* already exists for you.\n"
            f"🛑 Choose another title or delete the existing one first."
        )
    except Exception as e:
        send_whatsapp_message(from_number, f"❌ Unexpected error: {str(e)}")

def send_event_reminders(event_id: str):
    """Send WhatsApp reminders to unpaid members for the given event."""
    event = db_service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    unpaid_members = db_service.get_unpaid_members(event_id)
    for member in unpaid_members:
        style = event.style if event.style in REMINDER_STYLES else "default"
        template = random.choice(REMINDER_STYLES[style])
        message = template.format(name=member.name, amount=event.amount, event=event.title)
        send_whatsapp_message(f"whatsapp:{member.phone}", message)

    return {"status": "reminders sent", "event": event_id}
