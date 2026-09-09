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

    Two token shapes resolve into this one type:
      - parent (role "parent"): `user_id` set, `kid_id`/`token_version`
        None. This is the Google-sign-in session.
      - kid (role "kid"): `kid_id`/`token_version` set, `user_id` None,
        `email` None. Minted by routes_kid_auth after an invite claim,
        scoped to exactly one kid — `get_kid`/`get_kid_and_family`
        enforce that the path kid_id matches and the version is current.
    """

    def __init__(
        self,
        family_id: uuid.UUID,
        *,
        role: str = "parent",
        user_id: uuid.UUID | None = None,
        email: str | None = None,
        kid_id: uuid.UUID | None = None,
        token_version: int | None = None,
    ):
        self.family_id = family_id
        self.role = role
        self.user_id = user_id
        self.email = email
        self.kid_id = kid_id
        self.token_version = token_version

    @property
    def is_kid(self) -> bool:
        return self.role == "kid"


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


def issue_kid_session_token(kid_id: uuid.UUID, family_id: uuid.UUID, token_version: int) -> str:
    """Minted after an invite claim (routes_kid_auth). Same TTL and secret
    as the parent token — a kid re-authing means the parent has to send a
    fresh link, so a short TTL would be all downside. `tv` is checked
    against `kids.token_version` on every request, which is the actual
    revocation mechanism.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(kid_id),
        "family_id": str(family_id),
        "role": "kid",
        "kid_id": str(kid_id),
        "tv": token_version,
        "iat": now,
        "exp": now + timedelta(days=settings.kid_jwt_ttl_days),
    }
    return jwt.encode(payload, settings.backend_jwt_secret, algorithm=settings.backend_jwt_algorithm)


def _auth_from_payload(payload: dict) -> AuthContext:
    """Build an AuthContext from a verified JWT payload, dispatching on
    `role`. Raises KeyError/ValueError on a malformed payload — callers
    translate that into a 401.
    """
    family_id = uuid.UUID(payload["family_id"])
    if payload.get("role") == "kid":
        return AuthContext(
            family_id=family_id,
            role="kid",
            kid_id=uuid.UUID(payload["kid_id"]),
            token_version=int(payload["tv"]),
        )
    return AuthContext(
        family_id=family_id,
        role="parent",
        user_id=uuid.UUID(payload["sub"]),
        email=payload["email"],
    )


def get_current_auth_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthContext | None:
    """Like get_current_auth, but returns None instead of 401ing when the
    token is missing/expired/malformed — for endpoints (client-side metric
    reporting) where an unattributed request is still worth logging rather
    than rejecting outright.
    """
    if credentials is None:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.backend_jwt_secret,
            algorithms=[settings.backend_jwt_algorithm],
        )
        return _auth_from_payload(payload)
    except (JWTError, KeyError, ValueError):
        return None


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
        return _auth_from_payload(payload)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed session token") from exc
