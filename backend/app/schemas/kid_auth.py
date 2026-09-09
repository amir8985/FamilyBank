import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class KidInviteOut(BaseModel):
    """Returned to the parent once, when they generate an invite. `pin`
    is shown here and never again — it's only stored hashed."""

    claim_url: str
    pin: str
    expires_at: datetime


class KidInviteStatusOut(BaseModel):
    """For the Settings UI — whether a link is currently out there to be
    used, and whether any device is signed in (→ offer 'sign out of all
    devices')."""

    has_pending_invite: bool
    sessions_active: bool
    expires_at: datetime | None = None


class KidClaimRequest(BaseModel):
    claim_token: str = Field(min_length=1, max_length=200)
    pin: str = Field(min_length=4, max_length=12)


class KidClaimResponse(BaseModel):
    session_token: str
    kid_id: uuid.UUID
    public_id: str
    kid_name: str
    avatar_color: str
    base_currency: str


class KidMeOut(BaseModel):
    kid_id: uuid.UUID
    public_id: str
    name: str
    avatar_color: str
    family_id: uuid.UUID
    base_currency: str
