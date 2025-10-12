import os

from sqlmodel import create_engine, Session, SQLModel

from backend.db import models

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://bookuser:bookpassword@localhost:5432/bookdb")

engine = create_engine(DATABASE_URL, echo=True)
SQLModel.metadata.create_all(engine)