import uuid  # Generates unique payment IDs
from typing import Literal  # Restricts values to specific allowed options
from sqlalchemy import text

from fastapi import FastAPI, HTTPException  # API framework + HTTP errors
from pydantic import BaseModel  # Validates incoming request data

from app.database import SessionLocal  # Opens PostgreSQL database sessions
from app.models import Payment  # SQLAlchemy model mapped to the payments table


# =========================================================
# STEP 1: CREATE FASTAPI APPLICATION
# =========================================================

# Main backend application object
app = FastAPI(
    title="Fintech Payment Processing API",
    description=(
        "Backend API for payment processing, "
        "transaction lifecycle management, and risk controls."
    ),
    version="0.1.0",
)


# =========================================================
# STEP 2: PAYMENT INPUT SCHEMAS
# =========================================================


# Defines what a client must send when creating a payment
class PaymentCreate(BaseModel):
    merchant_id: str
    customer_id: str
    amount: float
    currency: str = "USD"


# Defines which payment statuses the API will accept
class PaymentStatusUpdate(BaseModel):
    status: Literal[
        "created",
        "authorized",
        "captured",
        "failed",
        "cancelled",
        "refunded",
    ]


# =========================================================
# STEP 3: PAYMENT LIFECYCLE RULES
# =========================================================

# Defines which status transitions are allowed
ALLOWED_TRANSITIONS = {
    "created": ["authorized", "failed", "cancelled"],
    "authorized": ["captured", "cancelled"],
    "captured": ["refunded"],
    "failed": [],
    "refunded": [],
}


# ============================================================
# STEP 4: ROOT / HEALTH-CHECK ENDPOINTS
# ============================================================


# GET / confirms that the FastAPI server itself is alive
@app.get("/")
def root():
    return {"message": "Fintech Payment Processing API is running"}


# GET /health confirms that both the API and PostgreSQL are working
@app.get("/health")
def health_check():
    # Create a temporary connection/session to PostgreSQL
    db = SessionLocal()

    try:
        # Send the simplest possible SQL query to PostgreSQL.
        # We don't need data — we only want to know whether PostgreSQL responds.
        db.execute(text("SELECT 1"))

        # If Python reaches here, the database successfully responded.
        return {
            "status": "healthy",
            "database": "connected",
        }

    finally:
        # Close the database session whether the query succeeds or fails.
        db.close()


# ============================================================
# STEP 5 — CREATE PAYMENT WITH IDEMPOTENCY
# ============================================================
from fastapi import FastAPI, Header, HTTPException


@app.post("/payments")
def create_payment(
    payment: PaymentCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    # Open a database session for this request
    db = SessionLocal()

    try:
        # Look for a payment that already used this request key
        existing_payment = (
            db.query(Payment).filter(Payment.idempotency_key == idempotency_key).first()
        )

        if existing_payment:
            # Reject the key if the new request has different payment data
            if (
                existing_payment.merchant_id != payment.merchant_id
                or existing_payment.customer_id != payment.customer_id
                or existing_payment.amount != payment.amount
                or existing_payment.currency != payment.currency
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency key already used with different payment data",
                )

            # Same key + same data: return the original payment
            return existing_payment

        # Create a new payment when the key has never been used
        new_payment = Payment(
            payment_id=f"pay_{uuid.uuid4().hex[:8]}",
            merchant_id=payment.merchant_id,
            customer_id=payment.customer_id,
            amount=payment.amount,
            currency=payment.currency,
            status="created",
            idempotency_key=idempotency_key,
        )

        # Persist the new payment in PostgreSQL
        db.add(new_payment)
        db.commit()

        # Reload database-generated values into the Python object
        db.refresh(new_payment)

        return new_payment

    finally:
        # Close the session even if an error occurs
        db.close()


# =========================================================
# STEP 6: LIST ALL PAYMENTS — GET
# =========================================================


# GET /payments returns all payment records
@app.get("/payments")
def list_payments():
    db = SessionLocal()

    try:
        # Query every payment stored in PostgreSQL
        payments = db.query(Payment).all()

        # Convert SQLAlchemy objects into JSON-friendly dictionaries
        return [
            {
                "payment_id": payment.payment_id,
                "merchant_id": payment.merchant_id,
                "customer_id": payment.customer_id,
                "amount": payment.amount,
                "currency": payment.currency,
                "status": payment.status,
            }
            for payment in payments
        ]

    finally:
        db.close()


# =========================================================
# STEP 7: READ ONE PAYMENT — GET
# =========================================================


# GET /payments/{payment_id} retrieves one specific payment
@app.get("/payments/{payment_id}")
def get_payment(payment_id: str):
    db = SessionLocal()

    try:
        # Find the payment by its unique payment ID
        payment = db.query(Payment).filter(Payment.payment_id == payment_id).first()

        # Return 404 if the payment does not exist
        if payment is None:
            raise HTTPException(
                status_code=404,
                detail="Payment not found",
            )

        return {
            "payment_id": payment.payment_id,
            "merchant_id": payment.merchant_id,
            "customer_id": payment.customer_id,
            "amount": payment.amount,
            "currency": payment.currency,
            "status": payment.status,
        }

    finally:
        db.close()


# =========================================================
# STEP 8: UPDATE PAYMENT STATUS — PATCH
# =========================================================


# PATCH /payments/{payment_id} changes only the payment status
@app.patch("/payments/{payment_id}")
def update_payment_status(
    payment_id: str,
    update: PaymentStatusUpdate,
):
    db = SessionLocal()

    try:
        # Find the payment in PostgreSQL
        payment = db.query(Payment).filter(Payment.payment_id == payment_id).first()

        # Return 404 if the payment does not exist
        if payment is None:
            raise HTTPException(
                status_code=404,
                detail="Payment not found",
            )

        # Look up which states are allowed from the current status
        allowed_next_statuses = ALLOWED_TRANSITIONS[payment.status]

        # Reject invalid lifecycle transitions
        if update.status not in allowed_next_statuses:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot change payment status "
                    f"from '{payment.status}' to '{update.status}'"
                ),
            )

        # Apply the valid status change
        payment.status = update.status

        # Persist the update
        db.commit()
        db.refresh(payment)

        return {
            "payment_id": payment.payment_id,
            "status": payment.status,
        }

    finally:
        db.close()


# =========================================================
# STEP 9: DELETE PAYMENT — DELETE
# =========================================================

# Instead of permanently deleting a financial transaction,
# we preserve the payment record and change its status.
# This gives us an auditable transaction history.


@app.post("/payments/{payment_id}/cancel")
def cancel_payment(payment_id: str):
    # Open a connection/session to PostgreSQL
    db = SessionLocal()

    try:
        # Find the payment using its primary key
        payment = db.query(Payment).filter(Payment.payment_id == payment_id).first()

        # If no payment exists with that ID, return HTTP 404
        if payment is None:
            raise HTTPException(
                status_code=404,
                detail="Payment not found",
            )

        # Only a newly created payment can be cancelled.
        # Settled/refunded/etc. payments should not simply be cancelled.
        if payment.status != "created":
            raise HTTPException(
                status_code=409,
                detail=f"Payment with status '{payment.status}' cannot be cancelled",
            )

        # IMPORTANT:
        # We do NOT delete the database row.
        # We preserve it and change its lifecycle state.
        payment.status = "cancelled"

        # Permanently save the status change to PostgreSQL
        db.commit()

        # Reload the record from PostgreSQL
        db.refresh(payment)

        # Return the updated payment
        return payment

    finally:
        # Always close the database session
        db.close()
