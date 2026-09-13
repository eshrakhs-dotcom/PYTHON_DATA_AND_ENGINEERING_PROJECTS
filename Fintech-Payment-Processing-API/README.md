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