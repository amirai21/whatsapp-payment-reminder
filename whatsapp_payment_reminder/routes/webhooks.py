from fastapi import APIRouter, Request

from whatsapp_payment_reminder.services.interaction_service import (
    handle_state,
    handle_name_step,
    handle_amount_step,
    handle_style_step,
    handle_freq_step,
    handle_delay_step,
    show_user_events,
    send_main_menu,
)
from whatsapp_payment_reminder.services.whatsapp_utils import send_whatsapp_message
from whatsapp_payment_reminder.services.session_store import session_store
from whatsapp_payment_reminder.services.events_service import handle_create_event
from whatsapp_payment_reminder.services.members_service import handle_add_members, handle_mark_paid
from whatsapp_payment_reminder.utils.templates import HELP_MSG

webhook_router = APIRouter()


@webhook_router.post("/webhook")
async def whatsapp_webhook(request: Request):
    data = await request.form()
    from_number = data.get("From", "")
    body = data.get("Body", "").strip()

    state = session_store.get(from_number, {"state": "IDLE"})

    # delegate non-IDLE state handling
    if handle_state(from_number, body, state):
        return {"status": "ok"}

    # Main menu options
    if body == "1":
        session_store[from_number] = {"state": "CREATING_EVENT_NAME"}
        send_whatsapp_message(from_number, "מה שם האירוע?")
        return {"status": "ok"}
    elif body == "2":
        show_user_events(from_number)
    elif body == "3":
        send_whatsapp_message(from_number, HELP_MSG)
    elif body.lower().startswith("create event:"):
        handle_create_event(from_number, body)
    elif "paid" in body.lower():
        handle_mark_paid(from_number, body)
    else:
        send_main_menu(from_number)
    return {"status": "ok"}
