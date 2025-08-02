from whatsapp_payment_reminder.services import db_service
from whatsapp_payment_reminder.services.whatsapp_utils import send_whatsapp_message
from whatsapp_payment_reminder.services.session_store import session_store
from whatsapp_payment_reminder.services.events_service import handle_create_event
from whatsapp_payment_reminder.utils.templates import MAIN_MENU_MSG
from whatsapp_payment_reminder.services.members_service import handle_add_members


def send_main_menu(to: str):
    send_whatsapp_message(
        to,
        MAIN_MENU_MSG
    )


def show_user_events(from_number: str):
    """Send a list of events the user is part of."""
    phone_number = from_number.replace("whatsapp:", "")
    events = db_service.get_events_for_member_phone(phone_number)
    if not events:
        send_whatsapp_message(from_number, "📋 אתה לא נמצא באף אירוע עדיין.")
        return

    lines = ["📋 אתה חלק מהאירועים הבאים:"]
    for e in events:
        unpaid_count = len([m for m in e.members if not m.paid])
        lines.append(f"• *{e.title}* – {e.amount} ({e.style}) | {unpaid_count} לא שילמו")
    send_whatsapp_message(from_number, "\n".join(lines))


def handle_style_step(from_number: str, body: str):
    style = body if body in ["mafia", "grandpa", "broker"] else "mafia"
    session_store[from_number]["event_style"] = style
    session_store[from_number]["state"] = "CREATING_EVENT_FREQ"
    send_whatsapp_message(from_number, "כל כמה דקות לשלוח תזכורת? (ברירת מחדל: 60)")


def handle_freq_step(from_number: str, body: str):
    try:
        freq = int(body)
    except ValueError:
        freq = 60
    session_store[from_number]["event_freq"] = freq
    session_store[from_number]["state"] = "CREATING_EVENT_DELAY"
    send_whatsapp_message(from_number, "כמה דקות לחכות לפני התזכורת הראשונה? (ברירת מחדל: 0)")


# helper for amount step
def handle_amount_step(from_number: str, body: str):
    try:
        amount = float(body)
        session_store[from_number]["event_amount"] = amount
        session_store[from_number]["state"] = "CREATING_EVENT_STYLE"
        send_whatsapp_message(from_number, "איזה סגנון תזכורת תרצה? (mafia, grandpa, broker) ברירת מחדל: mafia")
    except ValueError:
        send_whatsapp_message(from_number, "אנא הזן סכום חוקי (מספר בלבד). מה הסכום לכל משתתף?")


def handle_name_step(from_number: str, body: str):
    session_store[from_number]["event_name"] = body.strip()
    session_store[from_number]["state"] = "CREATING_EVENT_AMOUNT"
    send_whatsapp_message(from_number, "מה הסכום שכל משתתף צריך לשלם? (מספר בלבד)")


# helper for delay step
def handle_delay_step(from_number: str, body: str):
    try:
        delay = int(body)
    except ValueError:
        delay = 0
    sess = session_store[from_number]
    event_body = (
        f"create event: {sess['event_name']} {sess['event_amount']} "
        f"{sess['event_style']} freq={sess['event_freq']} delay={delay}"
    )
    session_store[from_number]["state"] = "IDLE"
    handle_create_event(from_number, event_body)


# ---------------- State dispatcher -----------------
def handle_state(from_number: str, body: str, state: dict) -> bool:
    """Handle non-IDLE wizard/member states. Returns True if handled."""
    current = state.get("state")
    if current == "CREATING_EVENT_NAME":
        handle_name_step(from_number, body)
        return True
    if current == "CREATING_EVENT_AMOUNT":
        handle_amount_step(from_number, body)
        return True
    if current == "CREATING_EVENT_STYLE":
        handle_style_step(from_number, body)
        return True
    if current == "CREATING_EVENT_FREQ":
        handle_freq_step(from_number, body)
        return True
    if current == "CREATING_EVENT_DELAY":
        handle_delay_step(from_number, body)
        return True
    if current == "ADDING_MEMBERS":
        handle_add_members(from_number, body)
        return True
    return False


def get_user_state(from_number: str) -> dict:
    """Return user's session state dict with default IDLE."""
    return session_store.get(from_number, {"state": "IDLE"})
