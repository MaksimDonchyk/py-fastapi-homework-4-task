from datetime import date
from pydantic import BaseModel, field_validator, ConfigDict
from validation import (
    validate_name,
    validate_image,
    validate_gender,
    validate_birth_date
)

class ProfileCreateSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: bytes

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, v: str) -> str:
        validate_name(v)
        return v.lower()

    @field_validator("gender")
    @classmethod
    def validate_gen(cls, v: str) -> str:
        validate_gender(v)
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date) -> date:
        validate_birth_date(v)
        return v

    @field_validator("info")
    @classmethod
    def validate_inf(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Info field cannot be empty or contain only spaces.")
        return v

    @field_validator("avatar")
    @classmethod
    def validate_av(cls, v: bytes) -> bytes:
        validate_image(v)
        return v


class ProfileResponseSchema(BaseModel):
    id: int
    user_id: int
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date
    info: str
    avatar: str

    class Config:
        from_attributes = True
