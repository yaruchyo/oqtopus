from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class ContactFormEmail(BaseModel):
    name: str = Field(description="Name of the User", min_length=1)
    email: EmailStr
    subject: Optional[str] = Field(
        description="subject of the email", min_length=1, default="Oqtopus Feedback"
    )
    message: str = Field(description="message", min_length=1)
