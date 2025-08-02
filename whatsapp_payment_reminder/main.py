from fastapi import FastAPI
from dotenv import load_dotenv

from whatsapp_payment_reminder.db.database import get_engine
from whatsapp_payment_reminder.routes.api import api_router
from whatsapp_payment_reminder.services.scheduler_service import ReminderScheduler

load_dotenv()

from whatsapp_payment_reminder.db.db_models import Base
from whatsapp_payment_reminder.routes.webhooks import webhook_router as webhooks_router

engine = get_engine()
Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(webhooks_router)
app.include_router(api_router)

reminder_scheduler = ReminderScheduler(interval_minutes=1)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.on_event("startup")
def start_scheduler():
    reminder_scheduler.start()
    print("Scheduler started! It will run every minute to send reminders.")


@app.on_event("shutdown")
def shutdown_scheduler():
    reminder_scheduler.shutdown()
