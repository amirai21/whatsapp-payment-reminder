from pydantic import BaseModel


class Member(BaseModel):
    name: str
    phone: str
    paid: bool = False