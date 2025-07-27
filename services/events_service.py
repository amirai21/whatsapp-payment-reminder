from sqlalchemy.orm import Session
from db.db_models import Event, Member
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
import random
from fastapi import HTTPException
from services.session_store import session_store
from services.whatsapp_utils import send_whatsapp_message


REMINDER_STYLES = {
    "mafia": [
        "💼 Listen up, {name}. You owe {amount} for *{event}*. Don't make me ask again.",
        "🔫 Hey {name}, the family needs that {amount} for *{event}*. Pay up."
    ],
    "grandpa": [
        "👴 Back in my day, we paid our dues, {name}. Time to send {amount} for *{event}*.",
        "☕ {name}, I’m too old to chase payments. Please send {amount} for *{event}*."
    ],
    "broker": [
        "📈 Hey {name}, think of this as an investment. Send {amount} for *{event}*.",
        "💹 {name}, your portfolio is missing {amount} for *{event}*. Time to settle."
    ],
    "default": [
        "🔔 Reminder: {name}, please pay {amount} for *{event}*."
    ]
}


def handle_create_event(from_number: str, body: str, db: Session):
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

        # --- ✅ Insert new event ---
        new_event = Event(
            id=event_id,
            title=title,
            amount=amount,
            style=style,
            scheduler_interval=frequency_minutes,  # ⚠️ store minutes
            start_time=start_time
        )
        db.add(new_event)
        db.commit()

        # --- ✅ Track state for adding members ---
        session_store[from_number] = {"state": "ADDING_MEMBERS", "event_id": event_id}

        # --- ✅ Confirmation to admin ---
        send_whatsapp_message(
            from_number,
            f"📌 Event *{title}* created (style: {style}).\n"
            f"⏳ Reminders every {frequency_minutes} minutes, starting {start_time.strftime('%Y-%m-%d %H:%M UTC')}.\n"
            f"📇 Paste group members (name + phone):"
        )

    except IntegrityError:
        db.rollback()
        send_whatsapp_message(
            from_number,
            f"⚠️ An event with the name *{title}* already exists for you.\n"
            f"🛑 Choose another title or delete the existing one first."
        )
    except Exception as e:
        db.rollback()
        send_whatsapp_message(from_number, f"❌ Unexpected error: {str(e)}")

def send_event_reminders(event_id: str, db: Session):
    """Send reminders for an event to all unpaid members"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    unpaid_members = db.query(Member).filter(Member.event_id == event_id, Member.paid == False).all()
    for member in unpaid_members:
        style = event.style if event.style in REMINDER_STYLES else "default"
        template = random.choice(REMINDER_STYLES[style])
        message = template.format(name=member.name, amount=event.amount, event=event.title)
        send_whatsapp_message(f"whatsapp:{member.phone}", message)

    return {"status": "reminders sent", "event": event_id}
