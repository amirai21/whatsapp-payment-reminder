from fastapi import FastAPI, Request, HTTPException, Depends
from twilio.rest import Client
from sqlalchemy.orm import Session
from typing import List
import os, re
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from database import SessionLocal, engine
from db import Base, Event, Member
import random
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

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

# ✅ Create tables on startup
Base.metadata.create_all(bind=engine)

# ✅ DB session dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

load_dotenv()

# --- Twilio Config ---
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = "whatsapp:+14155238886"  # ✅ WhatsApp Sandbox Number
client = Client(account_sid, auth_token)

# --- Session store just for multi-step flows ---
session_store = {}

# --- FastAPI App ---
app = FastAPI()

# --- Scheduler ---
scheduler = BackgroundScheduler()

def scheduled_reminder_job():
    """Periodic job to send reminders for all events"""
    db = SessionLocal()
    now = datetime.utcnow()
    events = db.query(Event).all()

    for event in events:
        # Skip until event start_time
        if now < event.start_time:
            continue

        # ⏱ Calculate how many minutes have passed since the event start
        time_since_start = (now - event.start_time).total_seconds() / 60  # convert to minutes

        # ✅ Trigger if current time is within 1-minute window of the next reminder
        if time_since_start % event.scheduler_interval < 1:
            send_event_reminders(event.id, db)

    db.close()

@app.on_event("startup")
def start_scheduler():
    scheduler.add_job(scheduled_reminder_job, "interval", minutes=1)  # dev = every 1 minute
    scheduler.start()

@app.on_event("shutdown")
def shutdown_scheduler():
    scheduler.shutdown()

# =======================
# 🔧 Helper Functions
# =======================

def send_whatsapp_message(to: str, message: str):
    """Send WhatsApp message via Twilio sandbox"""
    print(f"📤 Sending message to {to}: {message}")
    client.messages.create(
        from_=twilio_number,
        body=message,
        to=to
    )

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

    # ✅ Save members to DB
    for m in members:
        db_member = Member(name=m["name"], phone=m["phone"], paid=False, event_id=event_id)
        db.add(db_member)
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

# =======================
# 🚀 Webhook Endpoint
# =======================

def send_main_menu(to: str):
    """Send a fake menu (sandbox-friendly)"""
    send_whatsapp_message(
        to,
        "👋 Hi! What do you want to do?\n\n"
        "1️⃣ Create Event\n"
        "2️⃣ View My Events\n"
        "3️⃣ Help"
    )

@app.post("/webhook")
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
        # ✅ FIX: Remove extra `data` argument
        handle_add_members(from_number, body, db)

    elif "paid" in body.lower():
        handle_mark_paid(from_number, db)

    else:
        send_main_menu(from_number)

    db.close()
    return {"status": "ok"}

# =======================
# 📡 Manual Trigger Endpoint
# =======================

@app.post("/send_reminders/{event_id}")
async def trigger_event_reminders(event_id: str):
    db = SessionLocal()
    res = send_event_reminders(event_id, db)
    db.close()
    return res

@app.get("/events")
async def list_events():
    db = SessionLocal()
    events = db.query(Event).all()
    events_list = []
    for e in events:
        events_list.append({
            "id": e.id,
            "title": e.title,
            "amount": e.amount,
            "style": e.style,
            "members": [
                {"name": m.name, "phone": m.phone, "paid": m.paid} for m in e.members
            ]
        })
    db.close()
    return events_list