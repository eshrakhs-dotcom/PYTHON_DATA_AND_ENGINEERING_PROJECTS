from sqlalchemy import String, Float  # Column data types
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# Base class used by SQLAlchemy to define database tables
class Base(DeclarativeBase):
    pass


# Python class that maps to a PostgreSQL table called "payments"
class Payment(Base):
    __tablename__ = "payments"

    # Unique ID for each payment
    payment_id: Mapped[str] = mapped_column(String, primary_key=True)

    # Who sent/processed the payment
    merchant_id: Mapped[str] = mapped_column(String)

    # Customer linked to the payment
    customer_id: Mapped[str] = mapped_column(String)

    # Payment amount
    amount: Mapped[float] = mapped_column(Float)

    # Currency code such as USD
    currency: Mapped[str] = mapped_column(String)

    # Current payment status
    status: Mapped[str] = mapped_column(String)

    # Prevents the same payment request from being processed twice

    idempotency_key: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
    )
