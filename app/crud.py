import datetime
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas


class UnableToBook(Exception):
    pass


def create_booking(db: Session, booking: schemas.BookingBase) -> models.Booking:
    is_possible, reason = is_booking_possible(db=db, booking=booking)
    if not is_possible:
        raise UnableToBook(reason)
    db_booking = models.Booking(
        guest_name=booking.guest_name, unit_id=booking.unit_id,
        check_in_date=booking.check_in_date, number_of_nights=booking.number_of_nights)
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    return db_booking


def is_unit_available(
    db: Session,
    unit_id: str,
    check_in_date: datetime.date,
    number_of_nights: int,
    exclude_booking_id: int | None = None,
) -> bool:
    new_check_out = check_in_date + datetime.timedelta(days=number_of_nights)

    query = select(models.Booking).where(models.Booking.unit_id == unit_id)
    if exclude_booking_id is not None:
        query = query.where(models.Booking.id != exclude_booking_id)

    for existing in db.execute(query).scalars().all():
        existing_check_out = existing.check_in_date + datetime.timedelta(days=existing.number_of_nights)
        if existing.check_in_date < new_check_out and check_in_date < existing_check_out:
            return False

    return True


def is_booking_possible(db: Session, booking: schemas.BookingBase) -> Tuple[bool, str]:
    # check 1 : The Same guest cannot book the same unit multiple times
    if db.execute(
        select(models.Booking).where(
            models.Booking.guest_name == booking.guest_name,
            models.Booking.unit_id == booking.unit_id,
        )
    ).scalars().first():
        return False, 'The given guest name cannot book the same unit multiple times'

    # check 2 : the same guest cannot be in multiple units at the same time
    if db.execute(
        select(models.Booking).where(models.Booking.guest_name == booking.guest_name)
    ).scalars().first():
        return False, 'The same guest cannot be in multiple units at the same time'

    # check 3 : Unit is available for the full stay duration
    if not is_unit_available(db, booking.unit_id, booking.check_in_date, booking.number_of_nights):
        return False, 'For the given check-in date, the unit is already occupied'

    return True, 'OK'
