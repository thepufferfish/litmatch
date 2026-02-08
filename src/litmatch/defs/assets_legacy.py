import os
import re
import json
import pandas as pd
import dagster as dg

from typing import List, Dict
from datetime import date, datetime
from sqlmodel import Session, create_engine, select

from backend.db.models import Book, Genre, Author, Publisher, Review, Critic, Publication

RAW_DATA_DIR = '/home/framework/.local/share/containers/storage/volumes/litmatch_shared_scraper_output/_data/raw'

# NOTE: This file is deprecated and not imported by active code.
# Kept for reference only. Use the modular assets in assets/ directory instead.
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable must be set")

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
def raw_data(context: dg.AssetExecutionContext) -> pd.DataFrame:

    fn = os.path.join(RAW_DATA_DIR, 'books.jsonl')
    if not os.path.exists(fn):
            context.log.error(f'Raw data path does not exist: {fn}')

    data = pd.read_json(fn, lines=True)
    
    return data

def fix_publish_dates(data: pd.DataFrame) -> pd.DataFrame:
    """ Some publish dates are bad, so this fixes the ones I've seen in EDA """
    data.loc[:,'publish_date'] = data['publish_date'].str.replace('0209', '2019')
    data.loc[:,'publish_date'] = data['publish_date'].str.replace('0000', '2019')
    data.loc[:,'publish_date'] = data['publish_date'].str.replace('-0001', '2019')
    data.loc[:,'publish_date'] = pd.to_datetime(data['publish_date'], format="%B %d, %Y")
    return data

def check_if_fiction(x: List) -> bool:
    if 'Fiction' in x:
        return True
    elif 'Non-Fiction' in x:
        return False
    else:
        return None

def add_fiction_flag(data: pd.DataFrame) -> pd.DataFrame:
    data.loc[:,'is_fiction'] = data['genres'].apply(check_if_fiction)
    return data

@dg.asset
def cleaned_data(context: dg.AssetExecutionContext, raw_data: pd.DataFrame) -> pd.DataFrame:
    data = raw_data
    data = fix_publish_dates(data)
    data = add_fiction_flag(data)
    return data

@dg.asset
def load_to_db(context: dg.AssetExecutionContext, extract) -> None:
    data = extract

    if isinstance(data, Dict):
        data = [data]

    context.log.info(f'Found {len(data)} books to load')

    with Session(engine) as session:
        for record in data:
            context.log.debug(f'Loading {record['title']}')
            book = prepare_book(session, record)
            if book:
                # add genres to Book model
                genres = []
                for genre_name in record['genres']:
                    statement = select(Genre).where(Genre.name == genre_name)
                    genre = session.exec(statement).first()
                    if not genre:
                        genre = Genre(name=genre_name)
                    genres.append(genre)
                book.genres = genres
                # add reviews to Book model
                reviews = []
                urls = []
                for r in record['reviews']:
                    # there are some occasional duplicates so this is a workaround for now
                    if r['url'] not in urls:
                        review = prepare_review(session, r)
                        reviews.append(review)
                        urls.append(r['url'])
                book.reviews = reviews
                session.add(book)
                session.commit()

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

def fix_publish_date(date_str: str) -> date | None:
    """Fix and parse a single publish date string."""
    if not date_str:
        return None
    date_str = date_str.replace('0209', '2019')
    date_str = date_str.replace('0000', '2019')
    date_str = date_str.replace('-0001', '2019')
    try:
        return datetime.strptime(date_str, "%B %d, %Y").date()
    except ValueError:
        return None

def prepare_book(session: Session, record: dict) -> Book:
    
    scrape_date = datetime.strptime(record['last_scraped'], '%Y-%m-%d %H:%M:%S')
    publish_date = fix_publish_date(record['publish_date'])

    statement = select(Book).where(Book.url == record['url'])
    book = session.exec(statement).first()

    statement = select(Author).where(Author.name == record['author'])
    author = session.exec(statement).first()
    if not author:
        author = Author(name=record['author'])

    statement = select(Publisher).where(Publisher.name == record['publisher'])
    publisher = session.exec(statement).first()
    if not publisher:
        publisher = Publisher(name=record['publisher'])

    if book:
        if book.last_scraped < scrape_date:
            book.title = record['title']
            book.author = author
            book.publisher = publisher
            book.publish_date = publish_date
            book.description = record['description']
            book.url = record['url']
            book.cover = record['cover']
            book.last_scraped = scrape_date
        else:
            return None
    else:
        book = Book(
            title = record['title'],
            author = author,
            publisher = publisher,
            publish_date = publish_date,
            description = record['description'],
            url = record['url'],
            cover = record['cover'],
            last_scraped = scrape_date
        )

    return book

def prepare_review(session: Session, record: dict) -> Review:

    rating = encode_rating(record['rating'])

    statement = select(Review).where(Review.url == record['url'])
    review = session.exec(statement).first()

    if not review:

        critic_name = record['critic']
        critic_name = re.sub(r',$', '', critic_name)
        if critic_name == '':
            if record['publication'] == '':
                critic_name = 'Unknown'
            else:
                critic_name = record['publication']

        statement = select(Critic).where(Critic.name == critic_name)
        critic = session.exec(statement).first()
        if not critic:
            critic = Critic(name=critic_name)

        statement = select(Publication).where(Publication.name == record['publication'])
        publication = session.exec(statement).first()
        if not publication:
            publication = Publication(name=record['publication'])

        review = Review(
            critic = critic,
            publication = publication,
            rating = rating,
            review = record['review'],
            url = record['url']
        )
    
    return review
