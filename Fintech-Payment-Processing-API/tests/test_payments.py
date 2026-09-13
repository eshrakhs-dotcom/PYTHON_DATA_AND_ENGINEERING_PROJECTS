# tests/test_payments.py

import os

import pytest
from fastapi.testclient import TestClient

# Force this test process to use the isolated test database.
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

if not TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL environment variable is required.")

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.database import SessionLocal
from app.main import app
from app.models import Payment


# Create a client that can send simulated HTTP requests to FastAPI.
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_payments_table():
    # Open a database session before each test.
    db = SessionLocal()

    try:
        # Delete any payment rows left over from earlier tests.
        db.query(Payment).delete()

        # Save the cleanup.
        db.commit()

        # Let the test itself run.
        yield

    finally:
        # Clean again after the test finishes.
        db.query(Payment).delete()
        db.commit()

        # Always close the database session.
        db.close()


def test_root():
    # Send a GET request to the root endpoint.
    response = client.get("/")

    # Confirm the API responds successfully.
    assert response.status_code == 200


def test_create_payment():
    # Send a brand-new payment request.
    response = client.post(
        "/payments",
        headers={
            "Idempotency-Key": "pytest-payment-001",
        },
        json={
            "merchant_id": "merchant_test",
            "customer_id": "customer_test",
            "amount": 125.50,
            "currency": "USD",
        },
    )

    # Confirm the API accepted the request.
    assert response.status_code == 200

    # Convert the JSON response into a Python dictionary.
    data = response.json()

    # Verify the returned payment values.
    assert data["merchant_id"] == "merchant_test"
    assert data["customer_id"] == "customer_test"
    assert data["amount"] == 125.50
    assert data["currency"] == "USD"
    assert data["status"] == "created"
    assert data["idempotency_key"] == "pytest-payment-001"

    # Confirm the backend generated a payment ID.
    assert data["payment_id"].startswith("pay_")


def test_idempotent_payment():
    # Define one payment request that will be sent twice.
    payment_data = {
        "merchant_id": "merchant_test",
        "customer_id": "customer_test",
        "amount": 75.00,
        "currency": "USD",
    }

    # Use the same idempotency key for both requests.
    headers = {
        "Idempotency-Key": "pytest-idempotency-001",
    }

    # First request creates the payment.
    first_response = client.post(
        "/payments",
        headers=headers,
        json=payment_data,
    )

    # Second request retries the exact same payment.
    second_response = client.post(
        "/payments",
        headers=headers,
        json=payment_data,
    )

    # Both requests should succeed.
    assert first_response.status_code == 200
    assert second_response.status_code == 200

    # Convert responses into Python dictionaries.
    first_payment = first_response.json()
    second_payment = second_response.json()

    # Both requests must return the same payment ID.
    assert first_payment["payment_id"] == second_payment["payment_id"]


def test_idempotency_conflict():
    # Original payment request.
    original_payment = {
        "merchant_id": "merchant_conflict",
        "customer_id": "customer_conflict",
        "amount": 100.00,
        "currency": "USD",
    }

    headers = {
        "Idempotency-Key": "pytest-conflict-001",
    }

    # First request creates the payment.
    first_response = client.post(
        "/payments",
        headers=headers,
        json=original_payment,
    )

    assert first_response.status_code == 200

    # Change the amount while reusing the same idempotency key.
    changed_payment = {
        "merchant_id": "merchant_conflict",
        "customer_id": "customer_conflict",
        "amount": 500.00,
        "currency": "USD",
    }

    second_response = client.post(
        "/payments",
        headers=headers,
        json=changed_payment,
    )

    # Conflicting reuse should be rejected.
    assert second_response.status_code == 409

    # Confirm the correct error message is returned.
    assert second_response.json()["detail"] == (
        "Idempotency key already used with different payment data"
    )


def test_cancel_payment():
    # First create a payment that is in "created" status.
    create_response = client.post(
        "/payments",
        headers={
            "Idempotency-Key": "pytest-cancel-001",
        },
        json={
            "merchant_id": "merchant_cancel",
            "customer_id": "customer_cancel",
            "amount": 200.00,
            "currency": "USD",
        },
    )

    # Make sure the payment was created successfully.
    assert create_response.status_code == 200

    # Pull the generated payment ID from the API response.
    payment_id = create_response.json()["payment_id"]

    # Call our new cancel endpoint.
    cancel_response = client.post(f"/payments/{payment_id}/cancel")

    # The cancellation should succeed.
    assert cancel_response.status_code == 200

    # Convert the response JSON into a Python dictionary.
    cancelled_payment = cancel_response.json()

    # Confirm the status changed instead of deleting the record.
    assert cancelled_payment["payment_id"] == payment_id
    assert cancelled_payment["status"] == "cancelled"


def test_valid_payment_lifecycle():
    # Create a brand-new payment.
    create_response = client.post(
        "/payments",
        headers={
            "Idempotency-Key": "pytest-lifecycle-001",
        },
        json={
            "merchant_id": "merchant_lifecycle",
            "customer_id": "customer_lifecycle",
            "amount": 300.00,
            "currency": "USD",
        },
    )

    assert create_response.status_code == 200

    payment_id = create_response.json()["payment_id"]

    # created -> authorized
    authorize_response = client.patch(
        f"/payments/{payment_id}",
        json={"status": "authorized"},
    )

    assert authorize_response.status_code == 200
    assert authorize_response.json()["status"] == "authorized"

    # authorized -> captured
    capture_response = client.patch(
        f"/payments/{payment_id}",
        json={"status": "captured"},
    )

    assert capture_response.status_code == 200
    assert capture_response.json()["status"] == "captured"

    # captured -> refunded
    refund_response = client.patch(
        f"/payments/{payment_id}",
        json={"status": "refunded"},
    )

    assert refund_response.status_code == 200
    assert refund_response.json()["status"] == "refunded"


def test_invalid_payment_transition():
    # Create a payment that starts in "created".
    create_response = client.post(
        "/payments",
        headers={
            "Idempotency-Key": "pytest-invalid-transition-001",
        },
        json={
            "merchant_id": "merchant_invalid",
            "customer_id": "customer_invalid",
            "amount": 150.00,
            "currency": "USD",
        },
    )

    assert create_response.status_code == 200

    payment_id = create_response.json()["payment_id"]

    # Try to skip directly from created -> refunded.
    invalid_response = client.patch(
        f"/payments/{payment_id}",
        json={"status": "refunded"},
    )

    # The API should reject an impossible lifecycle transition.
    assert invalid_response.status_code == 400
