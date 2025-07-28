from sqlalchemy.orm import Session
from db.db_models import Event, Member
from services.whatsapp_utils import send_whatsapp_message
from services.session_store import session_store
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

def handle_add_members(from_number: str, body: str, db: Session):
    """Handle member additions"""
    state = session_store[from_number]
    event_id = state["event_id"]
    event = db.query(Event).filter(Event.id == event_id).first()

    if body.lower().strip() == "done":
        session_store[from_number] = {"state": "IDLE"}
        send_whatsapp_message(from_number,
            f"✅ האירוע *{event.title}* הושלם עם {len(event.members)} משתתפים.\n📇 מזהה אירוע: `{event.id}`")
        return

    members = parse_members_from_text(body)
    if not members:
        send_whatsapp_message(from_number, "❌ לא הצלחתי לקרוא משתתפים. נסה שוב.")
        return

    for m in members:
        db_member = Member(name=m["name"], phone=m["phone"], paid=False, event_id=event_id)
        db.add(db_member)
        print(f"[LOG] Adding member: name={m['name']}, phone={m['phone']}, event_id={event_id}")  # TODO: migrate to logging
    db.commit()

    # ✅ Confirm to admin only
    send_whatsapp_message(from_number,
        f"✅ נוספו {len(members)} משתתפים ל-*{event.title}* עד כה.\nשלח עוד או כתוב 'done' לסיום.")

def handle_mark_paid(from_number: str, db: Session):
    phone = from_number.replace("whatsapp:", "")

    print(f"[LOG] Handling mark paid for {phone}")

    # ✅ Check if we have context (preferred event)
    event_context = session_store.get(phone, {}).get("awaiting_payment_for")

    if event_context:
        member = db.query(Member).filter(
            Member.phone == phone,
            Member.event_id == event_context
        ).first()

        if member and not member.paid:
            member.paid = True
            db.commit()
            event = db.query(Event).filter(Event.id == member.event_id).first()
            send_whatsapp_message(from_number,
                f"✅ תודה {member.name}! סומן כשולם עבור *{event.title}*.")
        else:
            send_whatsapp_message(from_number,
                "⚠️ כבר סומנת כשולם עבור האירוע הזה.")
    else:
        unpaid = db.query(Member).filter(Member.phone == phone, Member.paid == False).all()

        if len(unpaid) == 0:
            send_whatsapp_message(from_number,
                "⚠️ אינך נמצא באירועים לא משולמים.")
        elif len(unpaid) == 1:
            member = unpaid[0]
            member.paid = True
            db.commit()
            event = db.query(Event).filter(Event.id == member.event_id).first()
            send_whatsapp_message(from_number,
                f"✅ תודה {member.name}! סומן כשולם עבור *{event.title}*.")
        else:
            event_titles = ", ".join([db.query(Event).filter(Event.id == m.event_id).first().title for m in unpaid])
            send_whatsapp_message(from_number,
                f"⚠️ אתה נמצא במספר אירועים לא משולמים: {event_titles}. השב עם שם האירוע.")
            session_store[phone] = {"awaiting_event_selection": True}

