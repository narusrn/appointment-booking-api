"""Appointment booking endpoints.

Every route requires a valid `Authorization: Bearer <token>` (obtain one from
`POST /api/v1/user/token`). Authorization rules:

* **admin** users may read / modify / delete *any* booking.
* **non-admin** users may only read / modify / delete bookings they created;
  `owner` is always taken from the token, never from the request body.

Storage is an in-memory dict — bookings are lost on server restart.

All error responses share the app-wide shape: ``{"error": {"code": int, "message": str}}``.
"""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from api.routes.authentication import get_current_user
from api.schemas.authentication import UserInDB
from api.schemas.bookings import BookingIn, BookingOut

# in-memory store — id (uuid4 hex string) -> {id, owner, slot, created_at}
fake_bookings_db: dict[str, dict] = {}

router = APIRouter(prefix="/api/v1/bookings", tags=["Bookings"])

# Reused across routes so Swagger documents the same failure modes everywhere.
_AUTH_RESPONSES = {
    401: {"description": "Missing, expired, or invalid bearer token."},
}
_OWNERSHIP_RESPONSES = {
    **_AUTH_RESPONSES,
    403: {"description": "Booking exists but belongs to another user (and caller is not admin)."},
    404: {"description": "No booking with this id."},
}


def _owned_or_admin(booking_id: str, user: UserInDB) -> dict:
    """Return the booking if `user` may act on it, else raise 404/403."""
    booking = fake_bookings_db.get(booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if booking["owner"] != user.username and not user.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only manage your own bookings")
    return booking


@router.get(
    "",
    response_model=list[BookingOut],
    summary="List bookings visible to the caller",
    description=(
        "Returns bookings the caller is allowed to see:\n\n"
        "* **admin** → every booking in the system.\n"
        "* **non-admin** → only bookings where `owner` matches the caller's username.\n\n"
        "The list is unpaginated (in-memory demo store) and unsorted."
    ),
    responses={
        **_AUTH_RESPONSES,
        200: {"description": "Array of bookings (may be empty)."},
    },
)
async def list_bookings(current: UserInDB = Depends(get_current_user)):
    if current.admin:
        return list(fake_bookings_db.values())
    return [b for b in fake_bookings_db.values() if b["owner"] == current.username]


@router.post(
    "",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a booking for the current user",
    description=(
        "Books a time slot for the authenticated user. `slot` is free-form text "
        "(e.g. `10am-11am`); only a non-empty string is enforced.\n\n"
        "`owner` is set from the bearer token — any `owner` sent in the body is ignored. "
        "`id` and `created_at` (UTC ISO-8601) are assigned by the server."
    ),
    responses={
        **_AUTH_RESPONSES,
        201: {"description": "Booking created; the stored record is returned."},
        422: {"description": "Body failed validation (e.g. `slot` missing or empty)."},
    },
)
async def create_booking(body: BookingIn, current: UserInDB = Depends(get_current_user)):
    bid = uuid4().hex
    fake_bookings_db[bid] = {
        "id": bid,
        "owner": current.username,  # from token, never from body
        "slot": body.slot,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return fake_bookings_db[bid]


@router.get(
    "/{booking_id}",
    response_model=BookingOut,
    summary="Get one booking by id",
    description=(
        "Returns a single booking. Non-admin callers may only fetch their own "
        "bookings; requesting someone else's returns **403**, and an unknown id "
        "returns **404**."
    ),
    responses={**_OWNERSHIP_RESPONSES, 200: {"description": "The booking."}},
)
async def get_booking(booking_id: str, current: UserInDB = Depends(get_current_user)):
    return _owned_or_admin(booking_id, current)


@router.patch(
    "/{booking_id}",
    response_model=BookingOut,
    summary="Update a booking's time slot",
    description=(
        "Replaces the `slot` of an existing booking. Same ownership rules as "
        "`GET /{booking_id}` — non-admin callers can only edit their own bookings. "
        "`owner`, `id`, and `created_at` are immutable."
    ),
    responses={
        **_OWNERSHIP_RESPONSES,
        200: {"description": "Updated booking."},
        422: {"description": "Body failed validation (e.g. `slot` missing or empty)."},
    },
)
async def update_booking(
    booking_id: str,
    body: BookingIn,
    current: UserInDB = Depends(get_current_user),
):
    booking = _owned_or_admin(booking_id, current)
    booking["slot"] = body.slot
    return booking


@router.delete(
    "/{booking_id}",
    summary="Delete a booking",
    description=(
        "Removes a booking. Same ownership rules as `GET /{booking_id}`. Returns a "
        "confirmation message rather than an empty body."
    ),
    responses={
        **_OWNERSHIP_RESPONSES,
        200: {
            "description": "Booking deleted.",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Booking deleted",
                        "id": "3fa85f6457174562b3fc2c963f66afa6",
                    }
                }
            },
        },
    },
)
async def delete_booking(booking_id: str, current: UserInDB = Depends(get_current_user)):
    _owned_or_admin(booking_id, current)
    del fake_bookings_db[booking_id]
    return {"message": "Booking deleted", "id": booking_id}
