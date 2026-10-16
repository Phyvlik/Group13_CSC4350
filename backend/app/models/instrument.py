from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.types import UuidPk


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("symbol", "exchange"),)

    instrument_id: Mapped[UuidPk]
    symbol: Mapped[str] = mapped_column(String(20))
    exchange: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    quote_currency: Mapped[str] = mapped_column(String(10))
