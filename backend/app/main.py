from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import bcrypt
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import selectinload
from sqlmodel import Session, create_engine, func, or_, select, case, text

from backend.app.auth import (
    create_access_token,
    create_refresh_token,
    decode_bearer_token,
    revoke_refresh_token,
    store_refresh_token,
    validate_refresh_token,
)
from backend.app.config import (
    COOKIE_SECURE,
    CORS_ORIGINS,
    DATABASE_URL,
    REFRESH_COOKIE_PATH,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from backend.app.rate_limit import limiter
from backend.db.models import (
    Author,
    AuthResponse,
    Book,
    BookRead,
    Genre,
    PaginatedResponse,
    RatingCreate,
    Review,
    ReviewRead,
    User,
    UserCreate,
    UserPublic,
    UserRating,
)

engine = create_engine(DATABASE_URL)


def _annotate_books_with_ratings(
    session: Session, books: list[Book]
) -> list[BookRead]:
    """Convert Book ORM objects to BookRead with avg_critic_rating and review_count."""
    if not books:
        return []

    book_ids = [b.id for b in books]
    rating_stmt = (
        select(
            Review.book_id,
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.id).label("review_count"),
        )
        .where(Review.book_id.in_(book_ids))
        .group_by(Review.book_id)
    )
    rows = session.exec(rating_stmt).all()
    rating_map: dict[int, tuple[float, int]] = {
        row.book_id: (round(float(row.avg_rating), 1), row.review_count)
        for row in rows
    }

    result = []
    for book in books:
        book_read = BookRead.model_validate(book)
        if book.id in rating_map:
            avg, count = rating_map[book.id]
            book_read = book_read.model_copy(
                update={"avg_critic_rating": avg, "review_count": count}
            )
        result.append(book_read)
    return result

def _hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def get_session():
    with Session(engine) as session:
        yield session


def get_current_user(
    payload: dict = Depends(decode_bearer_token),
    session: Session = Depends(get_session),
) -> User:
    """Extract the current user from a Bearer token."""
    user_id = int(payload["sub"])
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


app = FastAPI()

# Rate limiter setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health_check(*, session: Session = Depends(get_session)):
    """Health check that verifies database connectivity."""
    try:
        session.exec(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": "database unreachable"},
        )
    return {"status": "ok"}


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    """Set the httpOnly refresh token cookie on a response."""
    response.set_cookie(
        key="refresh_token",
        value=raw_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Clear the refresh token cookie."""
    response.delete_cookie(
        key="refresh_token",
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
    )


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/auth/register", response_model=AuthResponse)
@limiter.limit("3/minute")
def register(
    request: Request,
    response: Response,
    *,
    session: Session = Depends(get_session),
    user_in: UserCreate,
):
    existing = session.exec(
        select(User).where(User.username == user_in.username)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Registration failed")

    hashed_pw = _hash_password(user_in.password)
    user = User.model_validate(user_in, update={"password_hash": hashed_pw})
    session.add(user)
    session.commit()
    session.refresh(user)

    access_token = create_access_token(user.id, user.username)
    raw_refresh = create_refresh_token()
    store_refresh_token(session, user.id, raw_refresh)
    _set_refresh_cookie(response, raw_refresh)

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserPublic(id=user.id, username=user.username),
    )


@app.post("/auth/login", response_model=AuthResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
    response: Response,
    *,
    session: Session = Depends(get_session),
    user_in: UserCreate,
):
    user = session.exec(
        select(User).where(User.username == user_in.username)
    ).first()
    if not user or not _verify_password(user_in.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(user.id, user.username)
    raw_refresh = create_refresh_token()
    store_refresh_token(session, user.id, raw_refresh)
    _set_refresh_cookie(response, raw_refresh)

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserPublic(id=user.id, username=user.username),
    )


@app.post("/auth/refresh", response_model=AuthResponse)
def refresh(request: Request, response: Response, *, session: Session = Depends(get_session)):
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    token_record = validate_refresh_token(session, raw_token)
    if not token_record:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Rotate: revoke old, issue new
    user = session.get(User, token_record.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    revoke_refresh_token(session, raw_token)

    access_token = create_access_token(user.id, user.username)
    new_raw_refresh = create_refresh_token()
    store_refresh_token(session, user.id, new_raw_refresh)
    _set_refresh_cookie(response, new_raw_refresh)

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserPublic(id=user.id, username=user.username),
    )


@app.post("/auth/logout")
def logout(request: Request, response: Response, *, session: Session = Depends(get_session)):
    raw_token = request.cookies.get("refresh_token")
    if raw_token:
        revoke_refresh_token(session, raw_token)
    _clear_refresh_cookie(response)
    return {"detail": "Logged out"}


# ---------------------------------------------------------------------------
# Book endpoints
# ---------------------------------------------------------------------------

@app.get("/books/", response_model=PaginatedResponse[BookRead])
def read_books(
    *,
    session: Session = Depends(get_session),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=24, ge=1, le=100),
    genre: int | None = None,
    user_id: int | None = None,
):
    stmt = select(Book).options(
        selectinload(Book.author),
        selectinload(Book.publisher),
        selectinload(Book.genres),
    )
    count_stmt = select(func.count(Book.id))
    if genre:
        stmt = stmt.join(Book.genres).where(Genre.id == genre)
        count_stmt = count_stmt.join(Book.genres).where(Genre.id == genre)
    if user_id:
        stmt = stmt.join(Book.user_ratings).where(UserRating.user_id == user_id)
        count_stmt = count_stmt.join(Book.user_ratings).where(UserRating.user_id == user_id)
    total = session.exec(count_stmt).one()
    offset = (page - 1) * limit
    books = session.exec(stmt.offset(offset).limit(limit)).all()
    items = _annotate_books_with_ratings(session, list(books))
    return PaginatedResponse(items=items, total=total, page=page, limit=limit)


def escape_like(value: str) -> str:
    """Escape SQL LIKE/ILIKE wildcards to prevent pattern injection."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@app.get("/books/search", response_model=PaginatedResponse[BookRead])
def search_books(
    *,
    session: Session = Depends(get_session),
    q: str = Query(default="", max_length=200),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=24, ge=1, le=100),
):
    if len(q.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail="Search query must be at least 2 characters",
        )
    pattern = f"%{escape_like(q)}%"
    filter_clause = or_(Book.title.ilike(pattern), Author.name.ilike(pattern))
    rank = case(
        (func.lower(Book.title) == q.lower(), 0),
        (Book.title.ilike(pattern), 1),
        (Author.name.ilike(pattern), 2),
        else_=3,
    )
    stmt = (
        select(Book)
        .options(
            selectinload(Book.author),
            selectinload(Book.publisher),
            selectinload(Book.genres),
        )
        .outerjoin(Author, Book.author_id == Author.id)
        .where(filter_clause)
        .order_by(rank, Book.title)
    )
    count_stmt = (
        select(func.count(Book.id))
        .outerjoin(Author, Book.author_id == Author.id)
        .where(filter_clause)
    )
    total = session.exec(count_stmt).one()
    offset = (page - 1) * limit
    books = session.exec(stmt.offset(offset).limit(limit)).all()
    items = _annotate_books_with_ratings(session, list(books))
    return PaginatedResponse(items=items, total=total, page=page, limit=limit)


@app.get("/books/{book_id}", response_model=BookRead)
def read_book(*, session: Session = Depends(get_session), book_id: int):
    stmt = (
        select(Book)
        .options(
            selectinload(Book.author),
            selectinload(Book.publisher),
            selectinload(Book.genres),
        )
        .where(Book.id == book_id)
    )
    book = session.exec(stmt).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return _annotate_books_with_ratings(session, [book])[0]


# ---------------------------------------------------------------------------
# Reviews & Genres
# ---------------------------------------------------------------------------

@app.get("/reviews/{book_id}", response_model=list[ReviewRead])
def read_reviews(*, session: Session = Depends(get_session), book_id: int):
    stmt = (
        select(Review)
        .options(
            selectinload(Review.critic),
            selectinload(Review.publication),
        )
        .where(Review.book_id == book_id)
    )
    reviews = session.exec(stmt).all()
    return reviews


@app.get("/genres/", response_model=list[Genre])
def read_genres(*, session: Session = Depends(get_session)):
    genres = session.exec(select(Genre)).all()
    return genres


# ---------------------------------------------------------------------------
# Ratings
# ---------------------------------------------------------------------------

@app.get("/ratings/", response_model=list[UserRating])
def read_ratings(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    book_id: int | None = None,
):
    """Return the current user's ratings, optionally filtered by book."""
    stmt = select(UserRating).where(UserRating.user_id == current_user.id)
    if book_id:
        stmt = stmt.where(UserRating.book_id == book_id)
    ratings = session.exec(stmt).all()
    return ratings


@app.post("/ratings/", response_model=UserRating)
@limiter.limit("30/minute")
def add_rating(
    request: Request,
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    rating_in: RatingCreate,
):
    stmt = (
        select(UserRating)
        .where(UserRating.user_id == current_user.id)
        .where(UserRating.book_id == rating_in.book_id)
    )
    rating = session.exec(stmt).first()
    if rating:
        rating.rating = rating_in.rating
        rating.updated_at = datetime.now()
    else:
        rating = UserRating(
            user_id=current_user.id,
            book_id=rating_in.book_id,
            rating=rating_in.rating,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
    session.add(rating)
    session.commit()
    session.refresh(rating)
    return rating
