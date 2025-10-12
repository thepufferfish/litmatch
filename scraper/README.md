# Bookmarks.reviews Scraper

This is a web scraper built using Scrapy to extract data from [bookmarks.reviews](https://bookmarks.reviews/) website. The scraper extracts information about books and their reviews from the site.

## Prerequisites

Before running the scraper, make sure you have the following installed:

- Python 3.11 or greater
- Pipenv

## Installation

1. Clone this repository:

```bash
git clone https://github.com/thepufferfish/bookmarks.git
```

2. Navigate to the project directory

```bash
cd bookmarks
```

3. Install dependencies using **pipenv**

```bash
pipenv install
```

## Usage

To run the scraper, use the following command:

```bash
pipenv run scrapy crawl bookmarks -o data/books.jsonl
```

This command will start the scraping process and save the extracted data to a JSON Lines file.

## Configuration

You can configure the scraper behavior by modifying the settings in the bookmarks/settings.py file. 

## License

This project is licensed under the MIT License.

Feel free to customize it according to your project's specifics and preferences.
