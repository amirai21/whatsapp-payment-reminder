from fastapi import FastAPI
from dotenv import load_dotenv

from routes.api import api_router
from services.scheduler_service import scheduler, scheduled_reminder_job

load_dotenv()

from db.database import engine
from db.db_models import Base
from routes.webhooks import webhook_router as webhooks_router

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


