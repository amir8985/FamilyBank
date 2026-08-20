import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()

bearer_scheme = HTTPBearer(auto_error=False)


class AuthContext:
    """Resolved from a backend session JWT. `family_id` is what every
    downstream query must be scoped by (architecture 5.5) — never trust
    a family_id that comes from the request body/path instead of this.
    """

    def __init__(self, user_id: uuid.UUID, family_id: uuid.UUID, email: str):
        self.user_id = user_id
        self.family_id = family_id
        self.email = email


def verify_google_id_token(raw_id_token: str) -> dict:
    """Verify a Google-issued ID token's signature, expiry, and audience.
    Raises ValueError if invalid. Returns the decoded claims (sub, email,
    name, ...).
    """
    return google_id_token.verify_oauth2_token(
        raw_id_token, google_requests.Request(), audience=settings.google_client_id
    )


def issue_session_token(user_id: uuid.UUID, family_id: uuid.UUID, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "family_id": str(family_id),
        "email": email,
        "iat": now,
        "exp": now + timedelta(days=settings.backend_jwt_ttl_days),
    }
    return jwt.encode(payload, settings.backend_jwt_secret, algorithm=settings.backend_jwt_algorithm)


def get_current_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthContext:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.backend_jwt_secret,
            algorithms=[settings.backend_jwt_algorithm],
        )
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session") from exc

    try:
        return AuthContext(
            user_id=uuid.UUID(payload["sub"]),
            family_id=uuid.UUID(payload["family_id"]),
            email=payload["email"],
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed session token") from exc
