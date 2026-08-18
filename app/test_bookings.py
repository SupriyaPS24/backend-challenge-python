import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.main import app, get_db

Path("data").mkdir(parents=True, exist_ok=True)
SQLALCHEMY_DATABASE_URL = "sqlite:///./data/test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

GUEST_A_UNIT_1: dict = {
    'unit_id': '1', 'guest_name': 'GuestA', 'check_in_date': datetime.date.today().strftime('%Y-%m-%d'),
    'number_of_nights': 5
}
GUEST_A_UNIT_2: dict = {
    'unit_id': '2', 'guest_name': 'GuestA', 'check_in_date': datetime.date.today().strftime('%Y-%m-%d'),
    'number_of_nights': 5
}
GUEST_B_UNIT_1: dict = {
    'unit_id': '1', 'guest_name': 'GuestB', 'check_in_date': datetime.date.today().strftime('%Y-%m-%d'),
    'number_of_nights': 5
}


@pytest.fixture()
def test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.mark.freeze_time('2023-05-21')
def test_create_fresh_booking(test_db):
    response = client.post(
        "/api/v1/booking",
        json=GUEST_A_UNIT_1
    )
    response.raise_for_status()
    assert response.status_code == 200, response.text


@pytest.mark.freeze_time('2023-05-21')
def test_same_guest_same_unit_booking(test_db):
    response = client.post("/api/v1/booking", json=GUEST_A_UNIT_1)
    assert response.status_code == 200, response.text

    response = client.post("/api/v1/booking", json=GUEST_A_UNIT_1)
    assert response.status_code == 400, response.text
    assert response.json()['detail'] == 'The given guest name cannot book the same unit multiple times'


@pytest.mark.freeze_time('2023-05-21')
def test_same_guest_different_unit_booking(test_db):
    response = client.post("/api/v1/booking", json=GUEST_A_UNIT_1)
    assert response.status_code == 200, response.text

    response = client.post("/api/v1/booking", json=GUEST_A_UNIT_2)
    assert response.status_code == 400, response.text
    assert response.json()['detail'] == 'The same guest cannot be in multiple units at the same time'


@pytest.mark.freeze_time('2023-05-21')
def test_different_guest_same_unit_booking(test_db):
    response = client.post("/api/v1/booking", json=GUEST_A_UNIT_1)
    assert response.status_code == 200, response.text

    response = client.post("/api/v1/booking", json=GUEST_B_UNIT_1)
    assert response.status_code == 400, response.text
    assert response.json()['detail'] == 'For the given check-in date, the unit is already occupied'


@pytest.mark.freeze_time('2023-05-21')
def test_different_guest_same_unit_booking_different_date(test_db):
    response = client.post("/api/v1/booking", json=GUEST_A_UNIT_1)
    assert response.status_code == 200, response.text

    response = client.post(
        "/api/v1/booking",
        json={
            'unit_id': '1',
            'guest_name': 'GuestB',
            'check_in_date': (datetime.date.today() + datetime.timedelta(1)).strftime('%Y-%m-%d'),
            'number_of_nights': 5
        }
    )
    assert response.status_code == 400, response.text
    assert response.json()['detail'] == 'For the given check-in date, the unit is already occupied'


@pytest.mark.freeze_time('2023-05-21')
def test_extend_stay_success(test_db):
    response = client.post("/api/v1/booking", json=GUEST_A_UNIT_1)
    booking_id = response.json()['id']

    response = client.patch(
        f"/api/v1/booking/{booking_id}/extend",
        json={'number_of_nights': 8}
    )
    assert response.status_code == 200, response.text
    assert response.json()['number_of_nights'] == 8


@pytest.mark.freeze_time('2023-05-21')
def test_extend_stay_is_idempotent(test_db):
    response = client.post("/api/v1/booking", json=GUEST_A_UNIT_1)
    booking_id = response.json()['id']

    for _ in range(3):
        response = client.patch(
            f"/api/v1/booking/{booking_id}/extend",
            json={'number_of_nights': 7}
        )
        assert response.status_code == 200, response.text
        assert response.json()['number_of_nights'] == 7


@pytest.mark.freeze_time('2023-05-21')
def test_extend_stay_blocked_by_next_booking(test_db):
    response = client.post("/api/v1/booking", json=GUEST_A_UNIT_1)
    booking_id = response.json()['id']

    # GuestB books unit 1 right after GuestA checks out
    response = client.post(
        "/api/v1/booking",
        json={
            'unit_id': '1',
            'guest_name': 'GuestB',
            'check_in_date': (datetime.date.today() + datetime.timedelta(days=5)).strftime('%Y-%m-%d'),
            'number_of_nights': 3,
        }
    )
    assert response.status_code == 200, response.text

    response = client.patch(
        f"/api/v1/booking/{booking_id}/extend",
        json={'number_of_nights': 7}
    )
    assert response.status_code == 400, response.text
    assert response.json()['detail'] == 'The unit is not available for the extended period'


@pytest.mark.freeze_time('2023-05-21')
def test_extend_stay_cannot_shorten(test_db):
    response = client.post("/api/v1/booking", json=GUEST_A_UNIT_1)
    booking_id = response.json()['id']

    response = client.patch(
        f"/api/v1/booking/{booking_id}/extend",
        json={'number_of_nights': 3}
    )
    assert response.status_code == 400, response.text
    assert response.json()['detail'] == 'number_of_nights cannot be less than the current value'


@pytest.mark.freeze_time('2023-05-21')
def test_extend_stay_not_found(test_db):
    response = client.patch(
        "/api/v1/booking/9999/extend",
        json={'number_of_nights': 10}
    )
    assert response.status_code == 400, response.text
    assert response.json()['detail'] == 'Booking not found'


@pytest.mark.freeze_time('2023-05-21')
def test_extend_stay_invalid_nights(test_db):
    response = client.patch(
        "/api/v1/booking/1/extend",
        json={'number_of_nights': 0}
    )
    assert response.status_code == 422, response.text
