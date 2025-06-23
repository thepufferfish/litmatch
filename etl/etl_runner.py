import os
import pandas as pd
import logging
import json

from datetime import datetime
# from sqlmodel import create_engine
# from transform import deduplicate, normalize_reviews, fix_publisher_dates

from backend.db.models import Book, Review, Genre
from etl.load import load_books

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('etl.log')
    ]
)
logger = logging.getLogger(__name__)

RAW_DATA_DIR = "data/raw/"

# DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://bookuser:bookpass@localhost:5432/bookdb")

# engine = create_engine(DATABASE_URL)

def extract(file_path: str) -> list[dict]:
    data = []
    with open(file_path, 'r', encoding='utf-8') as file:
        for line_number, line in enumerate(file, start=1):
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Error parsing line {line_number}: {line.strip()}")
    return data
    # logger.info(f"Starting extraction from: {file}")
    # try:
    #     data = pd.read_json(file, lines=True)
    #     data.loc[:, "last_scraped"] = data["last_scraped"].apply(lambda x: datetime.strptime(x, "%Y-%m-%d %H:%M:%S"))
    #     logger.info(f"Successfully extracted {len(data)} records")
    #     return data
    # except Exception as e:
    #     logger.error(f"Error during extraction: {str(e)}")
    #     raise

def etl():
    logger.info("Starting ETL process")
    try:
        fn = os.path.join(RAW_DATA_DIR, "books.jsonl")
        logger.info(f"Input file: {fn}")
        
        raw_data = extract(fn)
        logger.info("Starting to load raw data")
        load_books(raw_data)
        # # Transformation steps with logging
        # data = deduplicate(raw_data)
        # logger.info(f"After deduplication: {len(data)} records")
        
        # data = fix_publisher_dates(data)
        # logger.info("Publisher dates fixed")
        
        # data.loc[:, 'is_fiction'] = data['genres'].apply(lambda x: 1 if 'Fiction' in x else 0)
        # data = data.rename(columns={"link": "url"})
        
        # # Split data into separate tables
        # books = data[[
        #     "url", "title", "author", "publisher", "publish_date", "description", "is_fiction"
        # ]]
        # genres = data[["url", "genres"]].explode("genres").rename(columns={"genres": "genre"})
        # reviews = normalize_reviews(data)
        
        # logger.info(f"Preparing to load {len(books)} books, {len(genres)} genres, and {len(reviews)} reviews")
        
        # # Database operations
        # try:
        #     with engine.connect() as conn:
        #         logger.info("Creating database tables if they don't exist")
        #         conn.execute("CREATE TABLE IF NOT EXISTS books (id SERIAL PRIMARY KEY, url VARCHAR(255) UNIQUE, title VARCHAR(255), author VARCHAR(255), publisher VARCHAR(255), publish_date DATE, description TEXT, is_fiction INTEGER);")
        #         conn.execute("CREATE TABLE IF NOT EXISTS genres (id SERIAL PRIMARY KEY, book_id INTEGER, genre VARCHAR(255), FOREIGN KEY (book_id) REFERENCES books(id));")
        #         conn.execute("CREATE TABLE IF NOT EXISTS reviews (id SERIAL PRIMARY KEY, book_id INTEGER, numeric_rating INTEGER, review_author VARCHAR(255), review_publisher VARCHAR(255), review_rating VARCHAR(255), review_text TEXT, review_link VARCHAR(255), FOREIGN KEY (book_id) REFERENCES books(id));")
        # except Exception as e:
        #     logger.error(f"Error creating tables: {str(e)}")
        #     raise
        
        # # Load data
        # logger.info("Starting books upsert")
        # upsert_df(books, "books", ["url"], ["title", "author", "publisher", "publish_date", "description", "is_fiction"])
        
        # # Get book IDs
        # with engine.connect() as conn:
        #     result = conn.execute("SELECT id, url FROM books")
        #     book_ids = pd.DataFrame(result.fetchall(), columns=result.keys()).set_index("url")
        
        # # Map book IDs
        # genres["book_id"] = genres["url"].map(book_ids["id"])
        # reviews["book_id"] = reviews["url"].map(book_ids["id"])
        
        # # Load genres and reviews
        # logger.info("Starting genres upsert")
        # upsert_df(genres.dropna(subset=["book_id"]).drop(columns=["url"]), "genres", ["book_id"], ["genre"])
        
        # logger.info("Starting reviews upsert")
        # upsert_df(reviews.dropna(subset=["book_id"]).drop(columns=["url"]), "reviews", ["book_id"], ["numeric_rating", "review_author", "review_publisher", "review_text", "review_link"])
        
        # logger.info("ETL process completed successfully")
        
    except Exception as e:
        logger.error(f"ETL process failed: {str(e)}")
        raise

# if __name__ == "__main__":
#     etl()