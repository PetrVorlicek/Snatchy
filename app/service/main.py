from datetime import timedelta

from app.domain.scheduler.schedulers import Scheduler
from app.domain.crawler.crawlers import build_crawler
from app.domain.crawler.parsers import BezRealitkyParser
from app.model.models.models import RealEstateRecord, Description
from app.model.session import aget_session

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hardcoded for now as requested
URLS = [
    "https://www.bezrealitky.cz/vyhledat?estateType=BYT&location=exact&offerType=PRODEJ&osm_value=Hlavn%C3%AD+m%C4%9Bsto+Praha%2C+Praha%2C+%C4%8Cesko&regionOsmIds=R435514&currency=CZK&locale=CS"
]
FREQUENCY = timedelta(hours=24)



async def run_crawl(url: str):
    print(f"Starting crawl for {url}")

    try:
        # Setup Crawler
        crawler = build_crawler(url)
        async with crawler.get_page() as page:
            html = await page.content()
        parser = BezRealitkyParser()
        results = parser.parse(html)
        async with aget_session() as session:
            for item in results:
                record = RealEstateRecord(
                    title=item["title"],
                    price=item["price"],
                    currency=item["currency"],
                    flooring_m_squared=item["flooring_m_squared"],
                    location=item["location"],
                )
                description = Description(text=item["description"], record=record)
                session.add(record)
                session.add(description)
            await session.commit()
    except Exception as e:
        logger.error(f"Error during crawling: {e}")
        return
    logger.info(f"Crawl completed for {url} with {len(results)} records found.")


def crawl():
    scheduler = Scheduler(
        callback=run_crawl,
        callback_kwargs=[{"url": url} for url in URLS],
        frequency=FREQUENCY,
    )

    logger.info(f"Starting Scheduler with frequency: {FREQUENCY}")
    scheduler.run_forever()


if __name__ == "__main__":
    crawl()
