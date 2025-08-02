from fastapi import APIRouter, Request

from whatsapp_payment_reminder.services import db_service
from whatsapp_payment_reminder.services.whatsapp_utils import send_whatsapp_message
from whatsapp_payment_reminder.services.session_store import session_store
from whatsapp_payment_reminder.services.events_service import handle_create_event
from whatsapp_payment_reminder.services.members_service import handle_add_members, handle_mark_paid
from whatsapp_payment_reminder.utils.templates import MAIN_MENU_MSG, HELP_MSG

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

    state = session_store.get(from_number, {"state": "IDLE"})

    # Interactive event creation flow
    if state.get("state") == "CREATING_EVENT_NAME":
        session_store[from_number]["event_name"] = body
        session_store[from_number]["state"] = "CREATING_EVENT_AMOUNT"
        send_whatsapp_message(from_number, "מה הסכום שכל משתתף צריך לשלם? (מספר בלבד)")
        return {"status": "ok"}
    elif state.get("state") == "CREATING_EVENT_AMOUNT":
        try:
            amount = float(body)
            session_store[from_number]["event_amount"] = amount
            session_store[from_number]["state"] = "CREATING_EVENT_STYLE"
            send_whatsapp_message(from_number, "איזה סגנון תזכורת תרצה? (mafia, grandpa, broker) ברירת מחדל: mafia")
        except ValueError:
            send_whatsapp_message(from_number, "אנא הזן סכום חוקי (מספר בלבד). מה הסכום לכל משתתף?")
        return {"status": "ok"}
    elif state.get("state") == "CREATING_EVENT_STYLE":
        style = body if body in ["mafia", "grandpa", "broker"] else "mafia"
        session_store[from_number]["event_style"] = style
        session_store[from_number]["state"] = "CREATING_EVENT_FREQ"
        send_whatsapp_message(from_number, "כל כמה דקות לשלוח תזכורת? (ברירת מחדל: 60)")
        return {"status": "ok"}
    elif state.get("state") == "CREATING_EVENT_FREQ":
        try:
            freq = int(body)
        except ValueError:
            freq = 60
        session_store[from_number]["event_freq"] = freq
        session_store[from_number]["state"] = "CREATING_EVENT_DELAY"
        send_whatsapp_message(from_number, "כמה דקות לחכות לפני התזכורת הראשונה? (ברירת מחדל: 0)")
        return {"status": "ok"}
    elif state.get("state") == "CREATING_EVENT_DELAY":
        try:
            delay = int(body)
        except ValueError:
            delay = 0
        session = session_store[from_number]
        # Compose the body for handle_create_event
        event_body = f"create event: {session['event_name']} {session['event_amount']} {session['event_style']} freq={session['event_freq']} delay={delay}"
        session_store[from_number]["state"] = "IDLE"
        handle_create_event(from_number, event_body)
        return {"status": "ok"}

    if body == "1":
        session_store[from_number] = {"state": "CREATING_EVENT_NAME"}
        send_whatsapp_message(from_number, "מה שם האירוע?")
        return {"status": "ok"}
    elif body == "2":
        phone_number = from_number.replace("whatsapp:", "")
        events = db_service.get_events_for_member_phone(phone_number)
        if not events:
            send_whatsapp_message(from_number, "📋 אתה לא נמצא באף אירוע עדיין.")
        else:
            message_lines = ["📋 אתה חלק מהאירועים הבאים:"]
            for e in events:
                unpaid_count = len([m for m in e.members if not m.paid])
                message_lines.append(f"• *{e.title}* – {e.amount} ({e.style}) | {unpaid_count} לא שילמו")
            send_whatsapp_message(from_number, "\n".join(message_lines))
    elif body == "3":
        send_whatsapp_message(from_number, HELP_MSG)
    elif body.lower().startswith("create event:"):
        handle_create_event(from_number, body)
    elif state["state"] == "ADDING_MEMBERS":
        handle_add_members(from_number, body)
    elif "paid" in body.lower():
        handle_mark_paid(from_number, body)
    else:
        send_main_menu(from_number)
    return {"status": "ok"}
