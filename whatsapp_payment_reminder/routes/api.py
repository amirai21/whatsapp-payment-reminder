from dotenv import load_dotenv
from fastapi import APIRouter

from whatsapp_payment_reminder.db.database import get_session_local

load_dotenv()

from whatsapp_payment_reminder.db.db_models import Event
from whatsapp_payment_reminder.services.events_service import send_event_reminders

SessionLocal = get_session_local()

# =======================
# 📡 Manual Trigger Endpoint
# =======================

api_router = APIRouter()


@api_router.post("/send_reminders/{event_id}")
async def trigger_event_reminders(event_id: str):
    res = send_event_reminders(event_id)
    return res


@api_router.get("/events")
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
