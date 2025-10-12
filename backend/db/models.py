from sqlmodel import Field, Relationship, SQLModel
from pydantic import EmailStr
from datetime import date, datetime

class BookGenreLink(SQLModel, table=True):
    book_id: int| None = Field(foreign_key='book.id', primary_key=True)
    genre_id: int| None = Field(foreign_key='genre.id', primary_key=True)

class Book(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    author: str
    publisher: str
    publish_date: date | None
    description: str
    url: str = Field(unique=True)
    cover: str | None
    last_scraped: datetime | None = Field(default=datetime.now())

    genres: list['Genre'] = Relationship(back_populates='books', link_model=BookGenreLink)
    reviews: list['Review'] = Relationship(back_populates='book')
    user_ratings: list['UserRating'] = Relationship(back_populates='book')

class Genre(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str

    books: list[Book] = Relationship(back_populates='genres', link_model=BookGenreLink)

class Review(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key='book.id')
    critic: str
    publication: str
    rating: int
    review: str
    url: str = Field(unique=True)

    book: Book = Relationship(back_populates='reviews')

class UserBase(SQLModel):
    username: str = Field(unique=True)
    # email: EmailStr = Field(unique=True, index=True)
    # is_active: bool = True
    # is_superuser: bool = False

class UserCreate(UserBase):
    password: str

class UserPublic(UserBase):
    id: int | None = Field(default=None, primary_key=True)

class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    password_hash: str

    user_ratings: list['UserRating'] = Relationship(back_populates='user')

class UserRating(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key='user.id')
    book_id: int = Field(foreign_key='book.id')
    rating: int
    created_at: datetime
    updated_at: datetime

    user: User = Relationship(back_populates='user_ratings')
    book: Book = Relationship(back_populates='user_ratings')
