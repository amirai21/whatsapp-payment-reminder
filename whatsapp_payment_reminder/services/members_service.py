from whatsapp_payment_reminder.services import db_service
from whatsapp_payment_reminder.services.whatsapp_utils import send_whatsapp_message
from whatsapp_payment_reminder.services.session_store import session_store
from typing import List
import re

def parse_members_from_text(text: str) -> List[dict]:
    """Parse pasted members (name + phone) from WhatsApp Web"""
    members = []
    lines = text.strip().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""

        match_current = re.search(r'(\+?\d{9,15})', line)
        match_next = re.search(r'(\+?\d{9,15})', next_line)

        if match_current:
            phone = match_current.group()
            name = line.replace(phone, "").strip()
            members.append({"name": name if name else "Unknown", "phone": phone})
            i += 1
        elif match_next:
            members.append({"name": line, "phone": match_next.group()})
            i += 2
        else:
            i += 1
    return members

def handle_add_members(from_number: str, body: str):
    """Handle member additions"""
    state = session_store[from_number]
    event_id = state["event_id"]
    event = db_service.get_event(event_id)

    if body.lower().strip() == "done":
        session_store[from_number] = {"state": "IDLE"}
        total = db_service.count_event_members(event_id)
        send_whatsapp_message(
            from_number,
            f"✅ האירוע *{event.title}* הושלם עם {total} משתתפים.\n📇 מזהה אירוע: `{event.id}`",
        )
        return

    members = parse_members_from_text(body)
    if not members:
        send_whatsapp_message(from_number, "❌ לא הצלחתי לקרוא משתתפים. נסה שוב.")
        return

    total = db_service.add_members_to_event(event_id, members)

    # ✅ Confirm to admin only
    send_whatsapp_message(from_number,
        f"✅ נוספו {len(members)} משתתפים ל-*{event.title}* עד כה.\nשלח עוד או כתוב 'done' לסיום.")

def notify_admin_by_ids(member_name: str, member_phone: str, event_title: str, admin_id: int):
    admin = db_service.get_admin(admin_id)
    if admin:
        send_whatsapp_message(
            f"whatsapp:{admin.phone}",
            f"\u200Fℹ️ המשתתף {member_name} ({member_phone}) שילם עבור האירוע {event_title}.",
        )

def handle_mark_paid(from_number: str, body: str):
    phone = from_number.replace("whatsapp:", "")

    # ✅ Check if we have context (preferred event)
    event_context = session_store.get(phone, {}).get("awaiting_payment_for")

    if event_context:
        result = db_service.set_member_paid(phone, event_context)

        if result:
            member_name, member_phone, event_title, admin_id = result
            send_whatsapp_message(from_number,
                                 f"✅ תודה {member_name}! סומן כשולם עבור *{event_title}*.")
            notify_admin_by_ids(member_name, member_phone, event_title, admin_id)
        else:
            send_whatsapp_message(from_number,
                "⚠️ כבר סומנת כשולם עבור האירוע הזה.")
    else:
        # If the user specified an event name (e.g. "paid Picnic") try to use it directly
        specified_event_title = None
        tokens = body.strip().split(maxsplit=1)
        if len(tokens) == 2 and tokens[0].lower() == "paid":
            specified_event_title = tokens[1].strip().lower()

        unpaid = db_service.get_unpaid_members_by_phone(phone)

        if specified_event_title:
            match_member = next((m for m in unpaid if m.event.title.lower() == specified_event_title), None)
            if match_member:
                result = db_service.set_member_paid(phone, match_member.event_id)
                if result:
                    member_name, member_phone, event_title, admin_id = result
                    send_whatsapp_message(from_number,
                                         f"✅ תודה {member_name}! סומן כשולם עבור *{event_title}*.")
                    notify_admin_by_ids(member_name, member_phone, event_title, admin_id)
                return

        if len(unpaid) == 0:
            send_whatsapp_message(from_number,
                "⚠️ אינך נמצא באירועים לא משולמים.")
        elif len(unpaid) == 1:
            member = unpaid[0]
            result = db_service.set_member_paid(phone, member.event_id)
            if result:
                member_name, member_phone, event_title, admin_id = result
                send_whatsapp_message(from_number,
                                     f"✅ תודה {member_name}! סומן כשולם עבור *{event_title}*.")
                notify_admin_by_ids(member_name, member_phone, event_title, admin_id)
        else:
            event_titles = ", ".join([m.event.title for m in unpaid])
            send_whatsapp_message(from_number,
                f"⚠️ אתה נמצא במספר אירועים לא משולמים: {event_titles}. השב עם שם האירוע.")
            session_store[phone] = {"awaiting_event_selection": True}

