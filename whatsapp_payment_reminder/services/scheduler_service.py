from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

from whatsapp_payment_reminder.services.db_service import get_all_events
from whatsapp_payment_reminder.services.events_service import send_event_reminders


class ReminderScheduler:
    """Background scheduler that periodically checks events and sends reminders."""

    def __init__(self, interval_minutes: int = 1):

        self.interval_minutes = interval_minutes
        self._scheduler = BackgroundScheduler()
        # Schedule the job
        self._scheduler.add_job(self._reminder_cycle, "interval", minutes=self.interval_minutes, id="reminder_cycle")

    def start(self) -> None:
        """Start the background scheduler (non-blocking)."""
        if not self._scheduler.running:
            self._scheduler.start()

    def shutdown(self) -> None:
        """Shut down the scheduler gracefully."""
        if self._scheduler.running:
            self._scheduler.shutdown()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _reminder_cycle(self) -> None:
        """Send reminders for all events that are due in this cycle."""
        events = get_all_events()
        now = datetime.utcnow()
        for event in events:
            if now < event.start_time:
                continue

            time_since_start = (now - event.start_time).total_seconds() / 60

            if time_since_start % event.scheduler_interval < 1:
                send_event_reminders(event.id)
