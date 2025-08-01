from pydantic import BaseModel
from typing import List

from whatsapp_payment_reminder.models.member import Member


class GroupEvent(BaseModel):
    id: str
    title: str
    amount: float
    members: List[Member] = []
    reminder_style: str = "mafia"