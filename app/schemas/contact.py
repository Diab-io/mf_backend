from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.constants import ContactService


class ContactRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    company: str | None = Field(default=None, max_length=150)
    service: ContactService  # required: the form dropdown must be selected
    message: str = Field(min_length=10, max_length=5000)
    # Honeypot: hidden field that real users never fill. Bots usually do.
    website: str | None = Field(default=None, max_length=200)

    @field_validator("name", "company", "phone", "message", mode="before")
    @classmethod
    def strip_whitespace(cls, v):
        return v.strip() if isinstance(v, str) else v


class ContactResponse(BaseModel):
    message: str
