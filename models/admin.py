from pydantic import BaseModel
from typing import Optional

class Admin(BaseModel):
    id: Optional[int]
    phone: str
