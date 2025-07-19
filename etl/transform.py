import re
import pandas as pd

from tldextract import extract
from datetime import datetime, date

def deduplicate(data: pd.DataFrame) -> pd.DataFrame:
    return data.sort_values("last_scraped").drop_duplicates(["link"], keep='last').reset_index()

def normalize_reviews(data: pd.DataFrame) -> pd.DataFrame:
    reviews = data.explode("reviews")[["url", "reviews"]].reset_index(drop=True)
    reviews = pd.concat((reviews.drop(columns=["reviews"]), pd.json_normalize(reviews["reviews"])), axis=1)
    reviews.loc[reviews["review_author"] == "", "review_author"] = reviews.loc[reviews["review_author"] == "", "review_publisher"]
    reviews.loc[:,"review_author"] = reviews["review_author"].map(lambda x: re.sub(r",$", "", x))
    reviews.loc[:,"review_author"] = reviews["review_author"].replace("", "Unknown")
    reviews.loc[:,"numeric_rating"] = reviews["review_rating"].map({
        "Rave": 4,
        "Positive": 3,
        "Mixed": 2,
        "Pan": 1
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
