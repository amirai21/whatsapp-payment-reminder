from whatsapp_payment_reminder.db.database import get_session_local
from whatsapp_payment_reminder.db.db_models import Event, Member, Admin
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from typing import List
from sqlalchemy.orm import joinedload

SessionLocal = get_session_local()


def get_all_events():
    """Return list of all Event rows."""
    db = SessionLocal()
    try:
        events = db.query(Event).all()
        # Detach objects before closing session
        for ev in events:
            db.expunge(ev)
        return events
    finally:
        db.close()


def get_event(event_id: str):
    """Return a single Event by id or None if not found."""
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if event:
            db.expunge(event)
        return event
    finally:
        db.close()


def get_unpaid_members(event_id: str):
    """Return a list of unpaid Member rows for the given event."""
    db = SessionLocal()
    try:
        unpaid_members = (
            db.query(Member)
            .filter(Member.event_id == event_id, Member.paid == False)
            .all()
        )
        # Detach
        for m in unpaid_members:
            db.expunge(m)
        return unpaid_members
    finally:
        db.close()


def create_event(*, from_number: str, title: str, amount: float, style: str, frequency_minutes: int, start_time: datetime):
    """Create a new Event row and its Admin if needed.

    Returns
    -------
    Event
        The newly created Event ORM object (detached).
    Raises
    ------
    IntegrityError
        If an event with the same id already exists.
    """
    db = SessionLocal()
    try:
        admin_phone = from_number.replace("whatsapp:", "")
        admin = db.query(Admin).filter(Admin.phone == admin_phone).first()
        if not admin:
            admin = Admin(phone=admin_phone)
            db.add(admin)
            db.commit()
            db.refresh(admin)

        event_id = admin_phone + "-" + title.lower()

        new_event = Event(
            id=event_id,
            title=title,
            amount=amount,
            style=style,
            scheduler_interval=frequency_minutes,
            start_time=start_time,
            admin_id=admin.id,
        )
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        db.expunge(new_event)
        return new_event
    except IntegrityError:
        db.rollback()
        raise
    finally:
        db.close()


def add_members_to_event(event_id: str, members: List[dict]) -> int:
    """Add a list of members to the given event_id.
    Returns the number of members added so far (total)."""
    db = SessionLocal()
    try:
        for m in members:
            db_member = Member(name=m["name"], phone=m["phone"], paid=False, event_id=event_id)
            db.add(db_member)
        db.commit()
        total = db.query(Member).filter(Member.event_id == event_id).count()
        return total
    finally:
        db.close()


def count_event_members(event_id: str) -> int:
    db = SessionLocal()
    try:
        return db.query(Member).filter(Member.event_id == event_id).count()
    finally:
        db.close()


def get_admin(admin_id: int):
    db = SessionLocal()
    try:
        admin = db.query(Admin).filter(Admin.id == admin_id).first()
        if admin:
            db.expunge(admin)
        return admin
    finally:
        db.close()


def set_member_paid(phone: str, event_id: str):
    """Mark member as paid and return lightweight info.

    Returns
    -------
    tuple | None
        (member_name, member_phone, event_title, admin_id) on success
        None if the member was already marked as paid or not found.
    """
    db = SessionLocal()
    try:
        member = db.query(Member).filter(Member.phone == phone, Member.event_id == event_id).first()
        if not member:
            return None
        event = db.query(Event).filter(Event.id == event_id).first()
        if member.paid:
            return None
        member.paid = True
        db.commit()
        db.refresh(member)
        result = (member.name, member.phone, event.title, event.admin_id)
        return result
    finally:
        db.close()


def get_unpaid_members_by_phone(phone: str):
    """Return list of unpaid Member objects for this phone with event relationship eager-loaded."""
    db = SessionLocal()
    try:
        members = (
            db.query(Member)
            .options(joinedload(Member.event))
            .filter(Member.phone == phone, Member.paid == False)
            .all()
        )
        for m in members:
            db.expunge(m)
        return members
    finally:
        db.close()


def get_events_for_member_phone(phone: str):
    """Return a detached list of Event objects that the given phone belongs to (members relationship pre-loaded)."""
    db = SessionLocal()
    try:
        members = db.query(Member).filter(Member.phone == phone).all()
        if not members:
            return []
        event_ids = {m.event_id for m in members}
        events = (
            db.query(Event)
            .options(joinedload(Event.members))
            .filter(Event.id.in_(event_ids))
            .all()
        )
        for e in events:
            db.expunge(e)
        return events
    finally:
        db.close()
