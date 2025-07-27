from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from db.database import SessionLocal
from services.events_service import send_event_reminders
from db.db_models import Event

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