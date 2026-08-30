import logging
import os
from datetime import datetime, timedelta, timezone

import jwt
from typing import Annotated
from jwt.exceptions import InvalidTokenError
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import (
    APIKeyHeader,
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
)
from pwdlib import PasswordHash

from api.schemas.authentication import Token, TokenData, User, UserInDB

load_dotenv()

logger = logging.getLogger(__name__)

fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$wagCPXjifgvUFBzq4hqe3w$CYaIb8sB+wtD+Vu/P4uod1+Qof8h+1g7bbDlBID48Rc",
        "admin": True,
        "disabled": False,
    },
    "alice": {
        "username": "alice",
        "full_name": "Alice",
        "email": "alice@example.com",
        "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$tpFo2NwJoRXNoKnpLfCSxw$/3cfXDoxcPffj5DXrgF6hkW6BWXo3+eAGPyYnNGg3NU",
        "admin": False,
        "disabled": False,
    },

}

password_hash = PasswordHash.recommended()

DUMMY_HASH = password_hash.hash("dummypassword")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/user/token")

router = APIRouter(prefix="/api/v1/user", tags=["User"])

def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password, hashed_password)

def get_password_hash(password):
    return password_hash.hash(password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    
def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        verify_password(password, DUMMY_HASH)
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, os.getenv("SECRET_KEY"), algorithm=os.getenv("ALGORITHM"))
    return encoded_jwt

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=[os.getenv("ALGORITHM")])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@router.post(
    "/token",
    summary="Log in and get a bearer token",
    description=(
        "OAuth2 password flow. Send `username` and `password` as form fields "
        "(`application/x-www-form-urlencoded`) and receive a signed JWT.\n\n"
        "Put the returned `access_token` in the `Authorization: Bearer <token>` "
        "header on every other endpoint. The token carries the username in `sub` "
        "and expires 30 minutes after issue.\n\n"
        "Seed users: `johndoe`/`secret` (admin), `alice`/`alice` (non-admin)."
    ),
    responses={
        200: {"description": "Authentication succeeded; token returned."},
        401: {"description": "Unknown username or wrong password."},
        422: {"description": "Missing `username` or `password` form field."},
    },
)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Token:
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")

@router.get(
    "/me/",
    summary="Get the current user's profile",
    description=(
        "Returns the profile of the user identified by the bearer token, including "
        "the `admin` flag. Useful for a frontend to decide what to show. Disabled "
        "accounts get **400**."
    ),
    responses={
        200: {"description": "The authenticated user's profile."},
        400: {"description": "The account is disabled."},
        401: {"description": "Missing, expired, or invalid bearer token."},
    },
)
async def read_users_me(current_user: User = Depends(get_current_active_user)) -> User:
    return current_user
