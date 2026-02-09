import re
from typing import Generic, TypeVar

from pydantic import BaseModel, field_validator
from sqlmodel import Field, Relationship, SQLModel
from datetime import date, datetime

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int

class BookGenreLink(SQLModel, table=True):
    book_id: int | None = Field(foreign_key='book.id', primary_key=True)
    genre_id: int | None = Field(foreign_key='genre.id', primary_key=True)

class Author(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)

    books: list['Book'] = Relationship(back_populates='author')

class Publisher(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)

    books: list['Book'] = Relationship(back_populates='publisher')

class Book(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    author_id: int | None = Field(default=None, foreign_key='author.id')
    publisher_id: int | None = Field(default=None, foreign_key='publisher.id')
    publish_date: date | None
    description: str
    url: str = Field(unique=True)
    cover: str | None
    is_fiction: bool | None = Field(default=None)
    last_scraped: datetime | None = Field(default=datetime.now())

    author: Author | None = Relationship(back_populates='books')
    publisher: Publisher | None = Relationship(back_populates='books')
    genres: list['Genre'] = Relationship(back_populates='books', link_model=BookGenreLink)
    reviews: list['Review'] = Relationship(back_populates='book')
    user_ratings: list['UserRating'] = Relationship(back_populates='book')

class Genre(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)

    books: list['Book'] = Relationship(back_populates='genres', link_model=BookGenreLink)


# --- Read models (include relationships for API responses) ---

class GenreRead(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}

class AuthorRead(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}

class PublisherRead(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}

class BookRead(BaseModel):
    id: int
    title: str
    author_id: int | None
    publisher_id: int | None
    publish_date: date | None
    description: str
    url: str
    cover: str | None
    author: AuthorRead | None = None
    publisher: PublisherRead | None = None
    genres: list[GenreRead] = []
    model_config = {"from_attributes": True}


class Critic(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)

    reviews: list['Review'] = Relationship(back_populates='critic')

class Publication(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)

    reviews: list['Review'] = Relationship(back_populates='publication')

class Review(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key='book.id')
    critic_id: int | None = Field(default=None, foreign_key='critic.id')
    publication_id: int | None = Field(default=None, foreign_key='publication.id')
    rating: int
    review: str
    url: str | None = Field(default=None, unique=True)

    book: Book = Relationship(back_populates='reviews')
    critic: Critic | None = Relationship(back_populates='reviews')
    publication: Publication | None = Relationship(back_populates='reviews')

class UserBase(SQLModel):
    username: str = Field(unique=True)
    # email: EmailStr = Field(unique=True, index=True)
    # is_active: bool = True
    # is_superuser: bool = False

class UserCreate(UserBase):
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]{3,30}$", v):
            raise ValueError(
                "Username must be 3-30 characters, alphanumeric and underscores only"
            )
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 72:
            raise ValueError("Password must not exceed 72 characters")
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        return v

class UserPublic(UserBase):
    id: int | None = Field(default=None, primary_key=True)

class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    password_hash: str

    user_ratings: list['UserRating'] = Relationship(back_populates='user')
    refresh_tokens: list['RefreshToken'] = Relationship(back_populates='user')

class UserRating(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key='user.id')
    book_id: int = Field(foreign_key='book.id')
    rating: int
    created_at: datetime
    updated_at: datetime

    user: User = Relationship(back_populates='user_ratings')
    book: Book = Relationship(back_populates='user_ratings')


class RefreshToken(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key='user.id')
    token_hash: str = Field(unique=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.now)

    user: User = Relationship(back_populates='refresh_tokens')


class RatingCreate(SQLModel):
    book_id: int
    rating: int = Field(ge=1, le=5)


class AuthResponse(SQLModel):
    access_token: str
    token_type: str
    user: UserPublic
