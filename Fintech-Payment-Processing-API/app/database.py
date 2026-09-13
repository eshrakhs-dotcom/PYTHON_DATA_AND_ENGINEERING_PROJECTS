# Import os so Python can read environment variables
import os

# SQLAlchemy tools for connecting to PostgreSQL
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Read DATABASE_URL from the environment.
# If none exists, use our local Docker PostgreSQL database.
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required.")


# Engine = manages the connection between SQLAlchemy and PostgreSQL
engine = create_engine(DATABASE_URL)


# SessionLocal = factory used to create database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
