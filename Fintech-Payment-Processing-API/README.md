# Fintech Payment Processing API

A production-style payment processing backend built with **Python, FastAPI, PostgreSQL, SQLAlchemy, Alembic, and Docker**, designed around transaction reliability, idempotency, auditable payment state transitions, and containerized deployment.

This project models core backend infrastructure used in modern payment systems: creating transactions, safely handling duplicate requests, retrieving payment records, enforcing valid payment lifecycle transitions, cancelling transactions without destroying financial history, and persisting transaction data in PostgreSQL.

## Tech Stack

**Backend:** Python · FastAPI · REST APIs · Pydantic  
**Database:** PostgreSQL · SQLAlchemy  
**Database Migrations:** Alembic  
**Infrastructure:** Docker · Docker Compose · AWS ECR  
**Testing:** Pytest · HTTPX  
**API Documentation:** OpenAPI / Swagger UI

## Why I Built This

Payment APIs have requirements that go beyond standard CRUD applications. A duplicate network request should not accidentally create a second payment, transaction states should not change arbitrarily, and financial records should remain auditable rather than being permanently deleted.

I built this project to explore those problems through a production-oriented backend architecture and implement several of the reliability controls used in payment infrastructure.

## Architecture

The application follows a layered backend architecture that separates the API layer, payment business logic, persistence layer, and infrastructure.

```text
                         CLIENT
                (Swagger UI / API Consumer)
                            │
                            │ HTTP / REST
                            ▼
                  ┌───────────────────┐
                  │      FastAPI      │
                  │   REST API Layer  │
                  └─────────┬─────────┘
                            │
                            ▼
              ┌───────────────────────────┐
              │ Payment Processing Logic  │
              │                           │
              │ • Payment creation        │
              │ • Idempotency protection  │
              │ • Lifecycle validation    │
              │ • Cancellation / refunds  │
              └─────────────┬─────────────┘
                            │
                            ▼
                  ┌───────────────────┐
                  │    SQLAlchemy     │
                  │    ORM Layer      │
                  └─────────┬─────────┘
                            │
                            ▼
                  ┌───────────────────┐
                  │    PostgreSQL     │
                  │ Transaction Store │
                  └───────────────────┘


        DATABASE MIGRATIONS              CONTAINERIZATION

        ┌───────────────┐                ┌───────────────┐
        │    Alembic    │                │    Docker     │
        │ Schema History│                │  API Image    │
        └───────────────┘                └───────┬───────┘
                                                │
                                                ▼
                                        ┌───────────────┐
                                        │    AWS ECR    │
                                        │Image Registry │
                                        └───────────────┘


### Why this architecture section matters

This is where an engineer looking at the repository can quickly see that this isn't simply:

**Python → database.**

I've actually built several distinct engineering concerns:

**API → validation/business rules → ORM → persistent database**, with migrations, containerization, testing, and a cloud container registry surrounding the core application.

And notice that I wrote **“stored in AWS ECR,”** not “deployed on AWS.” That's accurate to where we are right now. If we later get the API publicly hosted, we'll update the diagram with the actual runtime and public URL.

After this, the next section should be **Payment Lifecycle & State Machine**. That's probably one of the strongest sections of this project because it explains *why* you replaced destructive DELETE behavior with controlled financial transaction state transitions.                          
## Payment Lifecycle

I implemented a state machine to enforce valid transaction transitions and preserve payment history instead of deleting financial records.

```text
created ──► authorized ──► captured ──► refunded
   │            │
   ├──► failed  └──► cancelled
   │
   └──► cancelled
```

```python
ALLOWED_TRANSITIONS = {
    "created": ["authorized", "failed", "cancelled"],
    "authorized": ["captured", "cancelled"],
    "captured": ["refunded"],
    "failed": [],
    "cancelled": [],
    "refunded": [],
}
```

Invalid transitions are rejected by the API, preventing states such as a `refunded` payment becoming `captured` again.

## Idempotent Payment Creation

I implemented idempotency protection to prevent duplicate payments when clients retry the same request because of network failures or timeouts.

Clients provide an `Idempotency-Key` header when creating a payment.

```http
POST /payments
Idempotency-Key: checkout_8f92a1
```

The API handles retries using both the key and request payload:

- **New key** → creates a new payment.
- **Same key + same payload** → returns the existing payment.
- **Same key + different payload** → returns `409 Conflict`.

```python
existing_payment = (
    db.query(Payment).filter(Payment.idempotency_key == idempotency_key).first()
)

if existing_payment:
    same_request = (
        existing_payment.merchant_id == payment.merchant_id
        and existing_payment.customer_id == payment.customer_id
        and existing_payment.amount == payment.amount
        and existing_payment.currency == payment.currency
    )

    if not same_request:
        raise HTTPException(
            status_code=409,
            detail="Idempotency key already used with different payment data",
        )

    return existing_payment
```

This allows clients to safely retry payment requests without creating duplicate transaction records.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/payments` | Create an idempotent payment |
| `GET` | `/payments` | List payments |
| `GET` | `/payments/{payment_id}` | Retrieve a payment |
| `PATCH` | `/payments/{payment_id}` | Update payment status through validated transitions |
| `POST` | `/payments/{payment_id}/cancel` | Cancel an eligible payment |
| `GET` | `/health` | Verify API and database connectivity |

Interactive API documentation is available through FastAPI's **Swagger UI** at `/docs`.

## Database & Migrations

I used **PostgreSQL** for persistent transaction storage, **SQLAlchemy** for ORM-based database access, and **Alembic** for version-controlled schema migrations.

```text
FastAPI → SQLAlchemy → PostgreSQL
              ↑
           Alembic
      schema migrations
```

## Testing

Automated tests validate core payment behavior against an isolated PostgreSQL test database.

```text
✓ Payment creation
✓ Idempotent retries
✓ Idempotency conflicts
✓ Payment retrieval
✓ Cancellation
✓ Valid lifecycle transitions
✓ Invalid transition rejection

7 passed
```

Run the suite with:

```bash
python -m pytest -v
```



## Containerization & AWS

I containerized the API and PostgreSQL environment with **Docker and Docker Compose**, making the application reproducible across environments.

```text
Docker Compose
├── FastAPI container
└── PostgreSQL container
```

The API exposes a `/health` endpoint to verify application and database connectivity.

I also built and published the API container image to a private **Amazon ECR** repository, validating the cloud container delivery workflow:

```text
Source Code → Docker Image → Amazon ECR
```

## Run Locally

### 1. Clone the repository

```bash
git clone https://github.com/eshrakhs-dotcom/Fintech-Payment-Processing-API.git
cd Fintech-Payment-Processing-API
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
POSTGRES_USER=fintech_user
POSTGRES_PASSWORD=your_local_password
POSTGRES_DB=payments_db
DATABASE_URL=postgresql+psycopg://fintech_user:your_local_password@db:5432/payments_db
```

The `.env` file is excluded from Git to keep credentials out of source control.

### 3. Start the containers

```bash
docker compose up --build
```

### 4. Apply database migrations

```bash
docker compose exec api alembic upgrade head
```

### 5. Explore the API

```text
Swagger UI:  http://localhost:8000/docs
Health:      http://localhost:8000/health
```

Stop the environment with:

```bash
docker compose down
```

## Project Structure

```text
Fintech-Payment-Processing-API/
├── app/
│   ├── main.py              # API routes and payment logic
│   ├── models.py            # SQLAlchemy payment model
│   └── database.py          # Database configuration
├── alembic/
│   └── versions/            # Version-controlled migrations
├── tests/
│   └── test_payments.py     # Automated API tests
├── Dockerfile               # FastAPI container image
├── compose.yaml             # API + PostgreSQL environment
├── alembic.ini              # Migration configuration
├── requirements.txt         # Python dependencies
└── README.md
```

## Engineering Highlights

- **Idempotency:** prevents duplicate transactions during client retries.
- **Payment state machine:** enforces valid transaction lifecycle transitions.
- **Auditability:** cancellation and refunds preserve payment records instead of deleting them.
- **Persistence:** PostgreSQL stores transaction state through SQLAlchemy.
- **Schema versioning:** Alembic provides reproducible database migrations.
- **Testing:** automated behavioral tests run against an isolated test database.
- **Containerization:** Docker Compose reproduces the API and database environment.
- **Cloud delivery:** production-style container image published to Amazon ECR.

## Production Roadmap

This project models payment infrastructure but does **not move real funds or integrate with a live payment network**. A production implementation could extend the architecture with:

- Authentication and authorization
- Payment processor / banking rail integration
- Webhooks and asynchronous event processing
- Immutable transaction/event ledger
- Observability, logging, and alerting
- Cloud-managed PostgreSQL and container runtime
- Secrets management and CI/CD

## Author

**Eshrak Hasan**

Finance + Information Systems graduate building at the intersection of **fintech, payments, risk, data, and software engineering**.

