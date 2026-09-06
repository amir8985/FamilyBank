import uuid

from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin


class RequestLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One row per backend request, or per client-reported timing
    (`source="client"`) — written by `app.core.request_logging`. Exists to
    diagnose production latency (which routes/users are actually slow) and
    to double as the seed data for a future per-family/user activity
    dashboard, so family_id/user_id are captured from day one even though
    this feature itself only uses them for performance analysis.
    """

    __tablename__ = "request_logs"

    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4)
    # "server" (measured by the backend middleware) or "client" (reported
    # by the frontend via POST /internal/client-metrics).
    source: Mapped[str] = mapped_column(String(16), default="server")
    method: Mapped[str] = mapped_column(String(16))
    # The route's path *template* (e.g. "/kids/{kid_id}/debt"), not the
    # raw URL — otherwise every distinct kid_id/UUID fragments the stats.
    # Text, not a capped VARCHAR: an unmatched/malformed raw URL could
    # exceed any cap we picked, and a Postgres VARCHAR(n) raises rather
    # than truncates — the one thing a *logging* write must never do.
    path: Mapped[str] = mapped_column(Text)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float)
    family_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Only set for a server-side request that raised an unhandled
    # exception (repr(exc)) — never a stack trace, this isn't a crash log.
    # Text for the same reason as path above.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_request_logs_family_id", "family_id"),
        Index("ix_request_logs_created_at", "created_at"),
        Index("ix_request_logs_path_duration", "path", "duration_ms"),
    )
