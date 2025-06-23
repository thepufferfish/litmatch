import os

from sqlmodel import SQLModel, Field, create_engine, Session

from backend.db import models

DATABASE_URL = os.environ.get("DATABASE_URL")

engine = create_engine(DATABASE_URL, echo=True)
SQLModel.metadata.create_all(engine)