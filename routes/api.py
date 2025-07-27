from dotenv import load_dotenv
from fastapi import APIRouter

load_dotenv()

from db.database import SessionLocal
from db.db_models import Event
from services.events_service import send_event_reminders

# =======================
# 📡 Manual Trigger Endpoint
# =======================

api_router = APIRouter()


@api_router.post("/send_reminders/{event_id}")
async def trigger_event_reminders(event_id: str):
    db = SessionLocal()
    res = send_event_reminders(event_id, db)
    db.close()
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
