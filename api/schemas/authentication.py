from typing import Literal

from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    username: str | None = None
    password: str | None = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    admin: bool | None = None
    disabled: bool | None = None

class UserInDB(User):
    hashed_password: str