from pydantic import BaseModel


class GoogleSyncRequest(BaseModel):
    id_token: str


class SessionResponse(BaseModel):
    session_token: str
    family_id: str
    user_id: str
    email: str
    base_currency: str
