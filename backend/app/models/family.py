from decimal import Decimal

from sqlalchemy import Boolean, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin


class Family(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "families"

    # ISO 4217 code, e.g. "ILS", "USD", "EUR". Single value per family in
    # v1 — see spec 2.1 / architecture 1 for the v2 per-viewer display
    # currency note; conversion happens at read time so this stays a
    # zero-migration change later.
    base_currency: Mapped[str] = mapped_column(default="USD")

    # Gates the onboarding flow (spec 2.1: currency + first kids before
    # landing on the home screen) — set true once the parent finishes or
    # explicitly skips it.
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Monthly boost rate, as a percentage (e.g. 3.000 means 3%/month),
    # applied to every kid's stock purchases in this family — see
    # investing_service.buy()/boost_service. NULL means boost is off.
    # Family-wide, not per-kid: every open investment_lot at any given
    # moment shares this exact rate, because changing it is only allowed
    # while no kid holds any stock at all (enforced in routes_family.py).
    boost_buffer_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
