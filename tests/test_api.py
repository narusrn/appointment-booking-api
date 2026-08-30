"""End-to-end tests for the booking API (FastAPI TestClient, in-memory store)."""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes.bookings import fake_bookings_db

client = TestClient(app)

TOKEN_URL = "/api/v1/user/token"
BOOKINGS = "/api/v1/bookings"


@pytest.fixture(autouse=True)
def _clear_store():
    fake_bookings_db.clear()
    yield
    fake_bookings_db.clear()


def token(username: str, password: str) -> str:
    r = client.post(TOKEN_URL, data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(username, password):
    return {"Authorization": f"Bearer {token(username, password)}"}


# --- authentication ---------------------------------------------------------

def test_login_ok():
    assert "access_token" in client.post(
        TOKEN_URL, data={"username": "alice", "password": "alice"}
    ).json()


def test_login_wrong_password():
    r = client.post(TOKEN_URL, data={"username": "alice", "password": "nope"})
    assert r.status_code == 401


def test_bookings_require_auth():
    assert client.get(BOOKINGS).status_code == 401
    assert client.get(BOOKINGS, headers={"Authorization": "Bearer garbage"}).status_code == 401


# --- create / ownership ----------------------------------------------------

def test_create_sets_owner_from_token():
    r = client.post(BOOKINGS, json={"slot": "10am-11am"}, headers=auth("alice", "alice"))
    assert r.status_code == 201
    assert r.json()["owner"] == "alice"


def test_empty_slot_rejected():
    r = client.post(BOOKINGS, json={"slot": ""}, headers=auth("alice", "alice"))
    assert r.status_code == 422


# --- list: admin vs non-admin --------------------------------------------

def test_list_scoping():
    client.post(BOOKINGS, json={"slot": "9-10"}, headers=auth("alice", "alice"))
    client.post(BOOKINGS, json={"slot": "10-11"}, headers=auth("johndoe", "secret"))

    alice_list = client.get(BOOKINGS, headers=auth("alice", "alice")).json()
    assert {b["owner"] for b in alice_list} == {"alice"}

    admin_list = client.get(BOOKINGS, headers=auth("johndoe", "secret")).json()
    assert {b["owner"] for b in admin_list} == {"alice", "johndoe"}


# --- non-admin cannot touch someone else's booking ---------------------

def test_non_admin_forbidden_on_others():
    bid = client.post(
        BOOKINGS, json={"slot": "1pm-2pm"}, headers=auth("johndoe", "secret")
    ).json()["id"]

    a = auth("alice", "alice")
    assert client.get(f"{BOOKINGS}/{bid}", headers=a).status_code == 403
    assert client.patch(f"{BOOKINGS}/{bid}", json={"slot": "x"}, headers=a).status_code == 403
    assert client.delete(f"{BOOKINGS}/{bid}", headers=a).status_code == 403


def test_owner_can_manage_own():
    a = auth("alice", "alice")
    bid = client.post(BOOKINGS, json={"slot": "1pm-2pm"}, headers=a).json()["id"]

    assert client.patch(f"{BOOKINGS}/{bid}", json={"slot": "2pm-3pm"}, headers=a).json()["slot"] == "2pm-3pm"
    assert client.delete(f"{BOOKINGS}/{bid}", headers=a).status_code == 200
    assert client.get(f"{BOOKINGS}/{bid}", headers=a).status_code == 404


def test_admin_can_delete_any():
    bid = client.post(
        BOOKINGS, json={"slot": "1pm-2pm"}, headers=auth("alice", "alice")
    ).json()["id"]
    assert client.delete(f"{BOOKINGS}/{bid}", headers=auth("johndoe", "secret")).status_code == 200


def test_unknown_id_404():
    assert client.get(f"{BOOKINGS}/does-not-exist", headers=auth("alice", "alice")).status_code == 404
