import os
import re
import json
import pandas as pd
import dagster as dg

from typing import List, Dict
from tldextract import extract
from datetime import date, datetime
from sqlmodel import Session, create_engine, and_, or_, select

from backend.db.models import Book, Genre, BookGenreLink, Review

RAW_DATA_DIR = '/home/framework/.local/share/containers/storage/volumes/litmatch_shared_scraper_output/_data/raw'

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://bookuser:bookpassword@localhost:5432/bookdb')

engine = create_engine(DATABASE_URL, echo=True)

@dg.asset
def extract(context: dg.AssetExecutionContext) -> List[Dict]:

    fn = os.path.join(RAW_DATA_DIR, 'books.jsonl')
    if not os.path.exists(fn):
            context.log.error(f'Raw data path does not exist: {fn}')

    data = []
    with open(fn, 'r', encoding='utf-8') as file:
        for line_number, line in enumerate(file, start=1):
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                context.log.error(f'Error parsing line {line_number}: {line.strip()}')
    return data

@dg.asset
def transform_and_load(context: dg.AssetExecutionContext, extract) -> None:
    data = extract

    if isinstance(data, Dict):
        data = [data]

    context.log.info(f'Found {len(data)} books to load')

    with Session(engine) as session:
        for record in data:
            context.log.debug(f'Loading {record['title']}')
            book_id = load_book(session, record)
            if book_id:
                load_genres(session, record['genres'], book_id)
                load_reviews(session, record['reviews'], book_id)
        session.commit()

def deduplicate(data: pd.DataFrame) -> pd.DataFrame:
    return data.sort_values('last_scraped').drop_duplicates(['link'], keep='last').reset_index()

def normalize_reviews(data: pd.DataFrame) -> pd.DataFrame:
    reviews = data.explode('reviews')[['url', 'reviews']].reset_index(drop=True)
    reviews = pd.concat((reviews.drop(columns=['reviews']), pd.json_normalize(reviews['reviews'])), axis=1)
    reviews.loc[reviews['review_author'] == '', 'review_author'] = reviews.loc[reviews['review_author'] == '', 'review_publisher']
    reviews.loc[:,'review_author'] = reviews['review_author'].map(lambda x: re.sub(r',$', '', x))
    reviews.loc[:,'review_author'] = reviews['review_author'].replace('', 'Unknown')
    reviews.loc[:,'numeric_rating'] = reviews['review_rating'].map({
        'Rave': 4,
        'Positive': 3,
        'Mixed': 2,
        'Pan': 1
    }).astype(int)
    return reviews

def fix_publisher_dates(data: pd.DataFrame) -> pd.DataFrame:
    data.loc[:,'publish_date'] = data['publish_date'].str.replace('0209', '2019')
    data.loc[:,'publish_date'] = data['publish_date'].str.replace('0000', '2019')
    data.loc[:,'publish_date'] = data['publish_date'].str.replace('-0001', '2019')
    return data

def parse_publish_date(date_string: str) -> date:
    date_string = date_string.replace('0209', '2019')
    date_string = date_string.replace('0000', '2019')
    date_string = date_string.replace('-0001', '2019')
    publish_date = datetime.strptime(date_string, '%B %d, %Y')
    return publish_date
    
def encode_rating(rating: str) -> int:
    if rating == 'Rave':
        return 4
    elif rating == 'Positive':
        return 3
    elif rating == 'Mixed':
        return 2
    elif rating == 'Pan':
        return 1
    else:
        raise ValueError(f'Error encoding review rating: unknown rating {rating}')

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
