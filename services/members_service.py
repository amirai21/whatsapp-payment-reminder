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
            f"✅ Event *{event.title}* finalized with {len(event.members)} members.\n📇 Event ID: `{event.id}`")
        return

    members = parse_members_from_text(body)
    if not members:
        send_whatsapp_message(from_number, "❌ Couldn't parse any members. Try again.")
        return

    for m in members:
        db_member = Member(name=m["name"], phone=m["phone"], paid=False, event_id=event_id)
        db.add(db_member)
        print(f"[LOG] Adding member: name={m['name']}, phone={m['phone']}, event_id={event_id}")  # TODO: migrate to logging
    db.commit()

    # ✅ Confirm to admin only
    send_whatsapp_message(from_number,
        f"✅ Added {len(members)} members to *{event.title}* so far.\nSend more or type 'done' to finish.")

def handle_mark_paid(from_number: str, db: Session):
    phone = from_number.replace("whatsapp:", "")

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
                f"✅ Thanks {member.name}! Marked as paid for *{event.title}*.")
        else:
            send_whatsapp_message(from_number,
                "⚠️ You’re already marked as paid for that event.")
    else:
        unpaid = db.query(Member).filter(Member.phone == phone, Member.paid == False).all()

        if len(unpaid) == 0:
            send_whatsapp_message(from_number,
                "⚠️ You’re not in any unpaid events.")
        elif len(unpaid) == 1:
            member = unpaid[0]
            member.paid = True
            db.commit()
            event = db.query(Event).filter(Event.id == member.event_id).first()
            send_whatsapp_message(from_number,
                f"✅ Thanks {member.name}! Marked as paid for *{event.title}*.")
        else:
            event_titles = ", ".join([db.query(Event).filter(Event.id == m.event_id).first().title for m in unpaid])
            send_whatsapp_message(from_number,
                f"⚠️ You’re in multiple unpaid events: {event_titles}. Reply with the event name.")
            session_store[phone] = {"awaiting_event_selection": True}

