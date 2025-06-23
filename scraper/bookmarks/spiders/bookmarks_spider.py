import os
import json
from scrapy.spiders import SitemapSpider
from datetime import datetime

class BookmarksSpider(SitemapSpider):
    name = 'bookmarks'
    sitemap_urls = ['https://bookmarks.reviews/wp-sitemap.xml']
    sitemap_follow = ['posts-bookmark']
    sitemap_rules = [('/bookmark/', 'parse_bookmark')]

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(BookmarksSpider, cls).from_crawler(crawler, *args, **kwargs)
        spider.metadata = spider.fetch_metadata()
        spider.default_date = '2010-01-01T00:00:00-05:00'
        return spider

    def close(self, reason):
        with open("data/metadata/metadata.json", "w") as f:
            json.dump(self.metadata, f, indent=4)

    def sitemap_filter(self, entries):
        for entry in entries:
            try:
                lastmod = datetime.strptime(entry["lastmod"], '%Y-%m-%dT%H:%M:%S%z')
            except:
                lastmod = datetime.now().astimezone()
            lastscrape = datetime.strptime(self.metadata.get(entry['loc'], self.default_date), '%Y-%m-%dT%H:%M:%S%z') 
            if lastmod > lastscrape:
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
            'last_scraped': datetime.now().astimezone(),
            'reviews': []
        }

        see_all_reviews_link = response.xpath('//a[contains(text(), "See All Reviews")]/@href').get()
        see_all_reviews_link = see_all_reviews_link.replace('//all', '/all')
        if see_all_reviews_link:
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

    def fetch_metadata(self):
        fn = "data/metadata/metadata.json"
        if os.path.exists(fn):
            with open(fn) as f:
                metadata = json.load(f)
                return metadata
        elif not os.path.exists("data/metadata"):
            os.makedirs("data/metadata")
        return {}
        