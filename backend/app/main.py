import os

from fastapi import FastAPI, Depends, HTTPException, Query
from sqlmodel import SQLModel, Session, create_engine, select
from passlib.context import CryptContext

from backend import database
from backend.db.models import User, Book, Review, UserCreate, UserPublic

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://bookuser:bookpassword@localhost:5432/bookdb")

engine = create_engine(DATABASE_URL)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_session():
    with Session(engine) as session:
        yield session

app = FastAPI()

@app.post('/auth/register', response_model=UserPublic)
def create_user(*, session=Depends(get_session), user_in: UserCreate):
    user = session.exec(select(User).where(User.username == user_in.username)).first()
    if user:
        raise HTTPException(status_code=400, detail="Username already exists")
    hashed_pw = pwd_context.hash(user_in.password)
    user = User.model_validate(
        user_in, update={"password_hash": hashed_pw}
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return {'id': user.id, 'username': user.username}

@app.post("/auth/login", response_model=UserPublic)
def login(*, session: Session = Depends(get_session), user_in: UserCreate):
    user = session.exec(select(User).where(User.username == user_in.username)).first()
    if not user or not pwd_context.verify(user_in.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {'id': user.id, 'username': user.username}

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