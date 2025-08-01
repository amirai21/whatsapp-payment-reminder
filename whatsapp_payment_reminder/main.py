from fastapi import FastAPI
from dotenv import load_dotenv

from whatsapp_payment_reminder.routes.api import api_router
from whatsapp_payment_reminder.services.scheduler_service import scheduler, scheduled_reminder_job

load_dotenv()

from whatsapp_payment_reminder.db.database import engine
from whatsapp_payment_reminder.db.db_models import Base
from whatsapp_payment_reminder.routes.webhooks import webhook_router as webhooks_router

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(webhooks_router)
app.include_router(api_router)


@app.on_event("startup")
def start_scheduler():
    scheduler.add_job(scheduled_reminder_job, "interval", minutes=1)  # dev = every 1 minute
    scheduler.start()


@app.on_event("shutdown")
def shutdown_scheduler():
    scheduler.shutdown()
