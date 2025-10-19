import os
import logging
# import pandas as pd

from datetime import date, datetime
from sqlmodel import Session, create_engine, and_, or_, select

from etl.transform import parse_publish_date, encode_rating
from backend.db.models import Book, Genre, BookGenreLink, Review

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://bookuser:bookpassword@localhost:5432/bookdb")

engine = create_engine(DATABASE_URL, echo=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('etl.log')
    ]
)
logger = logging.getLogger(__name__)

def load_books(data: dict | list[dict]) -> None:

    if isinstance(data, dict):
        data = [data]

    logger.info(f'Found {len(data)} books to load')

    with Session(engine) as session:
        for record in data:
            logger.debug(f'Loading {record['title']}')
            book_id = load_book(session, record)
            if book_id:
                load_genres(session, record['genres'], book_id)
                load_reviews(session, record['reviews'], book_id)
        session.commit()

def load_book(session: Session, record: dict) -> int:
    
    scrape_date = datetime.strptime(record['last_scraped'], '%Y-%m-%d %H:%M:%S')
    publish_date = parse_publish_date(record['publish_date'])

    statement = select(Book).where(Book.url == record['url'])
    book = session.exec(statement).first()

    if book:
        
        if book.last_scraped < scrape_date:
            book.title = record['title']
            book.author = record['author']
            book.publisher = record['publisher']
            book.publish_date = publish_date
            book.description = record['description']
            book.url = record['url']
            book.cover = record['cover']
            book.last_scraped = scrape_date

            session.add(book)
        else:
            return None
    else:
        book = Book(
            title = record['title'],
            author = record['author'],
            publisher = record['publisher'],
            publish_date = publish_date,
            description = record['description'],
            url = record['url'],
            cover = record['cover'],
            last_scraped = scrape_date
        )

        session.add(book)
        session.commit()

    return book.id

def load_genres(session: Session, data: dict | list[dict], book_id: int) -> None:
    
    if isinstance(data, dict):
        data = [data]

    for record in data:
        genre_id = load_genre(session, record)
        load_book_genre_link(session, genre_id, book_id)

def load_genre(session: Session, genre_name: str) -> int:
    statement = select(Genre).where(Genre.name == genre_name)
    genre = session.exec(statement).first()
    if not genre:
        genre = Genre(name=genre_name)
        session.add(genre)
        session.commit()
    return genre.id

def load_book_genre_link(session: Session, genre_id: int, book_id: int):
    statement = select(BookGenreLink).where(BookGenreLink.genre_id == genre_id, BookGenreLink.book_id == book_id)
    book_genre_link = session.exec(statement).first()
    if not book_genre_link:
        book_genre_link = BookGenreLink(genre_id=genre_id, book_id=book_id)
        session.add(book_genre_link)

def load_reviews(session: Session, data: dict | list[dict], book_id: int) -> None:
    
    if isinstance(data, dict):
        data = [data]

    for record in data:
        load_review(session, record, book_id)

def load_review(session: Session, record: dict, book_id: int) -> int:

    rating = encode_rating(record['rating'])

    statement = select(Review).where(Review.url == record['url'])
    review = session.exec(statement).first()

    if not review:
        review = Review(
            book_id = book_id,
            critic = record['critic'],
            publication = record['publication'],
            rating = rating,
            review = record['review'],
            url = record['url']
        )
        session.add(review)

# def load_books(df: pd.DataFrame) -> None:
#     with Session(engine) as session:
#         for _, row in df.iterrows():
#             book = Book(
#                 title = row.title,
#                 author = row.author,
#                 publisher = row.publisher,
#                 publish_date = row.publish_date,
#                 description = row.description,
#                 link = row.link,
#                 last_scrape = row.scraped
#             )
#             session.add(book)
#         session.commit()
    
# def load_genres(df: pd.Dataframe) -> None:
#     with Session(engine) as session:
#         for _, row in df.iterrows():
#             statement = select(Genre).where(Genre.name == row.genre)
#             results = session.exec(statement)
#             genre = results.one()
#             if not genre:
#                 genre = Genre(name=genre_name)
#                 session.add(genre)
#                 session.commit()
#                 session.refresh(genre)
#             book = select(Book).where(Book.link == row.link)
#             if not book:
#                 raise Exception('Book does not exist in database.')
#             book_genre = BookGenreLink(
#                 book_id=book.id,
#                 genre_id=genre.id
#             )
#             session.add(book_genre)
#         session.commit()

# def upsert(data: dict, model: str, columns: Union[str, List[str]]) -> None:
#     """ Given a dict record or list of records, update existing records on specified columns, or
#      insert new record. This works by building clauses and reducing them into the statement.

#     Usage:
#     data = {"name": John, "ticket": "A95134"}
    
#     # perform upsert matching on a single column
#     upsert(data, "Entries", "ticket")
    
#     # perform upsert matching on multiple columns
#     psert(data, "Entries", ["name", "ticket"])

#     Parameters:
#     :param data: Union[Dict, Sequence[Dict]]: A dictionary or list of dictionary representing 
#      records in a table.
#     :param model: str: The name of the SQLModel representing a table.
#     :param columns: Union[str, List[str]]: Column(s) to match on for upsert.
#     :return: None: Takes internal action; bulk upsert.
#     """

#     # ensure listyness
#     if isinstance(data, Dict):
#         data = [data]

#     if isinstance(columns, str):
#         columns = [columns]

#     # open a session with the database engine
#     with Session(engine) as session:

#         # get specified model
#         obj = getattr(models, model)

#         # get obj columns and designate matches
#         match_on = [getattr(obj, col) == data.get(col) for col in columns]

#         # reduce clauses into statement
#         statement = select(obj).where(and_(*match_on))

#         # check for existing record
#         upsert = session.exec(statement).first()

#         # prepare the upsert
#         if upsert:
#             _ = [setattr(upsert, key, record[key]) for key in data]
#             # print(f"Upserting {upsert.id} with {record}")
#         else:
#             upsert = obj(**record)
#             # print(f"Inserting {record}")

#         # add to the session
#         session.add(upsert)

#         # commit session
#         session.commit()