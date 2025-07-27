from fastapi import APIRouter, Request
from db.db_models import Event, Member
from db.database import SessionLocal
from services.whatsapp_utils import send_whatsapp_message
from services.session_store import session_store
from services.events_service import handle_create_event
from services.members_service import handle_add_members, handle_mark_paid

# --- Reminder Styles ---
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

webhook_router = APIRouter()

# Only keep send_main_menu and the /webhook endpoint in this file.


def send_main_menu(to: str):
    """Send a main menu to the user (sandbox-friendly)."""
    send_whatsapp_message(
        to,
        "👋 Hi! What do you want to do?\n\n"
        "1️⃣ Create Event\n"
        "2️⃣ View My Events\n"
        "3️⃣ Help"
    )


@webhook_router.post("/webhook")
async def whatsapp_webhook(request: Request):
    data = await request.form()
    from_number = data.get("From", "")
    body = data.get("Body", "").strip()

    db = SessionLocal()
    state = session_store.get(from_number, {"state": "IDLE"})

    if body == "1":
        send_whatsapp_message(from_number,
                              "🎉 *Let's create a new event!*\n\n"
                              "Use this format:\n"
                              "`create event: Title Amount [style] [freq=MINUTES] [delay=MINUTES]`\n\n"
                              "📌 *Parameters explained:*\n"
                              "• *Title* – Name of the event (e.g. Birthday, Picnic)\n"
                              "• *Amount* – How much each person should pay (e.g. 50)\n"
                              "• *Style* – Optional tone for reminders: `mafia`, `grandpa`, `broker` (default: mafia)\n"
                              "• *freq=MINUTES* – Optional, how often reminders are sent (default: every 60 minutes)\n"
                              "• *delay=MINUTES* – Optional, delay before the first reminder starts (default: immediately)\n\n"
                              "✅ Example:\n"
                              "`create event: Picnic 50 mafia freq=120 delay=30`\n"
                              "👉 This will:\n"
                              "- Create event *Picnic* with 50 per person\n"
                              "- Use the *mafia* reminder style\n"
                              "- Send reminders every 2 hours\n"
                              "- Start sending reminders 30 minutes from now\n\n"
                              "After event creation, you’ll paste the group members (name + phone)."
                              )
    elif body == "2":
        phone_number = from_number.replace("whatsapp:", "")
        members = db.query(Member).filter(Member.phone == phone_number).all()
        if not members:
            send_whatsapp_message(from_number, "📋 You’re not in any events yet.")
        else:
            event_ids = set(m.event_id for m in members)
            events = db.query(Event).filter(Event.id.in_(event_ids)).all()
            message_lines = ["📋 You’re part of these events:"]
            for e in events:
                unpaid_count = len([m for m in e.members if not m.paid])
                message_lines.append(f"• *{e.title}* – {e.amount} ({e.style}) | {unpaid_count} unpaid")
            send_whatsapp_message(from_number, "\n".join(message_lines))
    elif body == "3":
        send_whatsapp_message(from_number, "ℹ️ Help: Type 'create event: Title Amount Style' to start an event.")
    elif body.lower().startswith("create event:"):
        handle_create_event(from_number, body, db)
    elif state["state"] == "ADDING_MEMBERS":
        handle_add_members(from_number, body, db)
    elif "paid" in body.lower():
        handle_mark_paid(from_number, db)
    else:
        send_main_menu(from_number)
    db.close()
    return {"status": "ok"}
