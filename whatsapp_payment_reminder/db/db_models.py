from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String, unique=True, nullable=False)
    events = relationship("Event", back_populates="admin")

class Event(Base):
    __tablename__ = "events"
    id = Column(String, primary_key=True)
    title = Column(String)
    amount = Column(Float)
    style = Column(String)
    scheduler_interval = Column(Float, default=1.0)  # in hours
    start_time = Column(DateTime, default=datetime.utcnow)  # first reminder start time
    admin_id = Column(Integer, ForeignKey("admins.id"), nullable=False)
    admin = relationship("Admin", back_populates="events")
    members = relationship("Member", back_populates="event")

class Member(Base):
    __tablename__ = "members"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    phone = Column(String)
    paid = Column(Boolean, default=False)
    event_id = Column(String, ForeignKey("events.id"))
    event = relationship("Event", back_populates="members")

