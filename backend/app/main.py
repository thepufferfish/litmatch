import os

from fastapi import FastAPI, Depends, HTTPException, Query
from sqlmodel import SQLModel, Session, create_engine, select

from backend import database
from backend.db.models import Book, Review

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://bookuser:bookpassword@localhost:5432/bookdb")

engine = create_engine(DATABASE_URL)

def get_session():
    with Session(engine) as session:
        yield session

app = FastAPI()

@app.get("/books/", response_model=list[Book])
def read_books(*, session=Depends(get_session), offset: int = 0, limit: int = Query(default=100, le=100)):
    books = session.exec(select(Book).offset(offset).limit(limit)).all()
    return books

@app.get("/books/{book_id}", response_model=Book)
def read_book(*, session=Depends(get_session), book_id: int):
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@app.get("/reviews/{book_id}", response_model=list[Review])
def read_reviews(*, session=Depends(get_session), book_id: int):
    reviews = session.exec(select(Review).where(Review.book_id == book_id)).all()
    if not reviews:
        raise HTTPException(status_code=404, detail="Reviews for book not found")
    return reviews