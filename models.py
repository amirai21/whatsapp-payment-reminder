from pydantic import BaseModel
from typing import List


class Member(BaseModel):
    name: str
    phone: str
    paid: bool = False


class GroupEvent(BaseModel):
    id: str
    title: str
    amount: float
    members: List[Member] = []
    reminder_style: str = "mafia"