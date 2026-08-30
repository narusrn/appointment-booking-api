from pydantic import BaseModel, Field


class BookingIn(BaseModel):
    # ponytail: slot is free text ("10am-11am") per the assignment; only guard against empty
    slot: str = Field(min_length=1, examples=["10am-11am"])


class BookingOut(BaseModel):
    id: str
    owner: str
    slot: str
    created_at: str
