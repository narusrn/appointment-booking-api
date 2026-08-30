# Appointment Booking API

A small REST API where users log in and book time slots. Built for the Python
Developer Assessment.

- **Authentication** — OAuth2 password flow, JWT bearer tokens.
- **Authorization** — admins see/manage every booking; everyone else only their own.
- **Storage** — in-memory dicts (no database); data resets on restart.

Stack: FastAPI · PyJWT · pwdlib (argon2) · Pydantic v2.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # then edit SECRET_KEY
```

## Run

```bash
uvicorn api.main:app --reload
```

## Tests

```bash
pytest
```

`tests/test_api.py` uses FastAPI's `TestClient` against the in-memory store
(cleared between tests) and covers login, auth on protected routes, `owner`
binding, admin-vs-user list scoping, and 403/404 ownership rules.

- API base: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs` (use the **Authorize** button)

## Seed users

| username | password | admin |
|----------|----------|-------|
| `johndoe` | `secret` | yes   |
| `alice`   | `alice`  | no    |

## Endpoints

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `POST` | `/api/v1/user/token` | – | form login, returns `access_token` |
| `GET`  | `/api/v1/user/me/` | Bearer | current user profile |
| `GET`  | `/api/v1/bookings` | Bearer | admin → all; user → own only |
| `POST` | `/api/v1/bookings` | Bearer | `owner` taken from token |
| `GET`  | `/api/v1/bookings/{id}` | Bearer | own or admin, else 403/404 |
| `PATCH`| `/api/v1/bookings/{id}` | Bearer | update `slot` |
| `DELETE`| `/api/v1/bookings/{id}` | Bearer | own or admin |

All errors share one shape: `{"error": {"code": int, "message": str}}`.

## Example

```bash
# 1. log in
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/user/token \
  -d "username=alice&password=alice" | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. create a booking
curl -s -X POST http://127.0.0.1:8000/api/v1/bookings \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"slot": "10am-11am"}'

# 3. list — alice sees only her own
curl -s http://127.0.0.1:8000/api/v1/bookings -H "Authorization: Bearer $TOKEN"
```

## Design notes

- **In-memory store** (`fake_users_db` in `api/routes/authentication.py`,
  `fake_bookings_db` in `api/routes/bookings.py`) per the assignment. Swapping in
  a database means changing those two spots plus the helper functions.
- **Booking ids** are `uuid4` hex strings — unguessable and collision-free.
- **`owner`** is always read from the JWT `sub`, never from the request body, so a
  user cannot create or reassign a booking to someone else.
- **Passwords** are argon2-hashed; login runs a dummy verify on unknown usernames
  to keep response timing constant (avoids user enumeration).
- Tokens expire 30 minutes after issue.

## Not included

- Frontend (optional in the brief).
