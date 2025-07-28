from fastapi import APIRouter, Request
from db.db_models import Event, Member
from db.database import SessionLocal
from services.whatsapp_utils import send_whatsapp_message
from services.session_store import session_store
from services.events_service import handle_create_event
from services.members_service import handle_add_members, handle_mark_paid
from utils.templates import REMINDER_STYLES, MAIN_MENU_MSG, CREATE_EVENT_INSTRUCT_MSG, HELP_MSG


webhook_router = APIRouter()


def send_main_menu(to: str):
    send_whatsapp_message(
        to,
        MAIN_MENU_MSG
    )


@webhook_router.post("/webhook")
async def whatsapp_webhook(request: Request):
    data = await request.form()
    from_number = data.get("From", "")
    body = data.get("Body", "").strip()

    db = SessionLocal()
    state = session_store.get(from_number, {"state": "IDLE"})

    if body == "1":
        send_whatsapp_message(from_number, CREATE_EVENT_INSTRUCT_MSG)
    elif body == "2":
        phone_number = from_number.replace("whatsapp:", "")
        members = db.query(Member).filter(Member.phone == phone_number).all()
        if not members:
            send_whatsapp_message(from_number, "📋 אתה לא נמצא באף אירוע עדיין.")
        else:
            event_ids = set(m.event_id for m in members)
            events = db.query(Event).filter(Event.id.in_(event_ids)).all()
            message_lines = ["📋 אתה חלק מהאירועים הבאים:"]
            for e in events:
                unpaid_count = len([m for m in e.members if not m.paid])
                message_lines.append(f"• *{e.title}* – {e.amount} ({e.style}) | {unpaid_count} לא שילמו")
            send_whatsapp_message(from_number, "\n".join(message_lines))
    elif body == "3":
        send_whatsapp_message(from_number, HELP_MSG)
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
