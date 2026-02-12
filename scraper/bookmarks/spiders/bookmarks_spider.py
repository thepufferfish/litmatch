import logging
import os
from datetime import datetime, timezone

import psycopg2
from scrapy.spiders import SitemapSpider

logger = logging.getLogger(__name__)

FETCH_METADATA_SQL = """
SELECT url, last_scraped
FROM book
WHERE last_scraped IS NOT NULL
"""


class BookmarksSpider(SitemapSpider):
    name = 'bookmarks'
    sitemap_urls = ['https://bookmarks.reviews/wp-sitemap.xml']
    sitemap_follow = ['posts-bookmark']
    sitemap_rules = [('/bookmark/', 'parse_bookmark')]

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(BookmarksSpider, cls).from_crawler(crawler, *args, **kwargs)
        spider.metadata = spider.fetch_metadata()
        return spider

    def sitemap_filter(self, entries):
        for entry in entries:
            loc = entry.get('loc')
            if not loc:
                logger.warning("Sitemap entry missing 'loc', skipping: %s", entry)
                continue

            try:
                lastmod = datetime.strptime(entry["lastmod"], '%Y-%m-%dT%H:%M:%S%z')
            except (KeyError, ValueError):
                lastmod = datetime.now(timezone.utc)

            lastscrape = self.metadata.get(loc)
            if lastscrape is None or lastmod > lastscrape:
                yield entry

    def parse_bookmark(self, response):
        title = response.xpath('//h1[contains(@class, "book_detail_title")][@itemprop="name"]/text()').get(default='').strip()
        author = response.xpath('//div[@itemprop="author"]/span[@itemprop="name"]/text()').get(default='').strip()
        publisher = response.xpath('//div[@itemprop="publisher"]/span[@itemprop="name"]/text()').get(default='').strip()
        publish_date = response.xpath('//div[@itemprop="datePublished"]/text()').get(default='').strip()
        description = ''.join(response.xpath('//div[@class="book_manual_description"]//text()').getall()).strip()
        cover = response.xpath('//div[@class="book_cover"]/img/@src').get(default='').strip()
        genres = [genre.strip() for genre in response.xpath('//span[@itemprop="genre"]/text()').getall()]

        book_data = {
            'title': title,
            'author': author,
            'publisher': publisher,
            'publish_date': publish_date,
            'description': description,
            'genres': genres,
            'url': response.url,
            'cover': cover,
            'last_scraped': datetime.now(timezone.utc),
            'reviews': []
        }

        see_all_reviews_link = response.xpath('//a[contains(text(), "See All Reviews")]/@href').get()
        if see_all_reviews_link:
            see_all_reviews_link = see_all_reviews_link.replace('//all', '/all')
            request = response.follow(see_all_reviews_link, self.parse_reviews)
            request.meta['book_data'] = book_data
            yield request
        else:
            yield book_data

    def parse_reviews(self, response):
        book_data = response.meta['book_data']

        reviews = response.xpath('//span[@itemprop="review"]')
        for review in reviews:
            critic = review.xpath('.//span[@itemprop="name"]/text()').get(default='').strip()
            publication = review.xpath('.//a[@class="bookmarks_source_link"]/text()').get(default='').strip()
            rating = review.xpath('.//span[contains(@class, "review_rating")]/text()').get(default='').strip()
            review_text = ''.join(review.xpath('.//div[@class="bookmarks_a_review_pullquote"]/text()').getall()).strip()
            url = review.xpath('.//a[@class="see_more_link"]/@href').get(default='')

            book_data['reviews'].append({
                'critic': critic,
                'publication': publication,
                'rating': rating,
                'review': review_text,
                'url': url
            })

        yield book_data

    def fetch_metadata(self) -> dict[str, datetime]:
        """Query the book table for url/last_scraped pairs.

        Returns a dict mapping book URLs to their last_scraped datetime.
        Returns an empty dict if DATABASE_URL is not set, the database is
        unreachable, or the book table does not exist.
        """
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            logger.info("DATABASE_URL not set; starting with empty metadata")
            return {}

        try:
            conn = psycopg2.connect(database_url, connect_timeout=10)
        except psycopg2.OperationalError:
            logger.warning(
                "Could not connect to database for metadata; "
                "starting with empty metadata",
            )
            return {}

        try:
            with conn.cursor() as cursor:
                cursor.execute(FETCH_METADATA_SQL)
                rows = cursor.fetchall()

            metadata: dict[str, datetime] = {}
            for url, last_scraped in rows:
                # The book.last_scraped column stores UTC datetimes.
                # Naive datetimes from the DB are assumed UTC.
                if last_scraped.tzinfo is None:
                    last_scraped = last_scraped.replace(tzinfo=timezone.utc)
                metadata[url] = last_scraped

            logger.info(
                "Loaded metadata for %d books from database", len(metadata)
            )
            return metadata
        except psycopg2.Error:
            logger.warning(
                "Database error loading metadata; "
                "starting with empty metadata",
            )
            return {}
        finally:
            conn.close()
