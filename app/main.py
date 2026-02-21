from datetime import timedelta
from urllib.parse import urlparse

from sqlalchemy import select

from app.domain.scheduler.schedulers import Scheduler
from app.domain.crawler.crawlers import build_crawler
from app.domain.crawler.parsers import BezRealitkyParser
from app.model.models.models import RealEstateRecord, Description, Domain, Site, Crawl
from app.model.session import aget_session
from app.domain.utils.time import now


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

    parsed_url = urlparse(url)
    domain_name = parsed_url.netloc
    site_url = f"{parsed_url.scheme}://{domain_name}"

    async with aget_session() as session:
        # 1. Get or create Domain  # TODO: vibecoded - update this
        stmt = select(Domain).where(Domain.url == domain_name)
        domain = (await session.execute(stmt)).scalar_one_or_none()
        if not domain:
            domain = Domain(url=domain_name)
            session.add(domain)
            await session.flush()

        # 2. Get or create Site  # TODO: vibecoded - udpate this
        stmt = select(Site).where(Site.url == site_url)
        site = (await session.execute(stmt)).scalar_one_or_none()
        if not site:
            site = Site(url=site_url, domain=domain)
            session.add(site)
            await session.flush()

        # 3. Create Crawl
        crawl = Crawl(site=site)
        session.add(crawl)
        await session.commit()

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
                    published_at=now(),
                    title=item["title"],
                    price=item["price"],
                    currency=item["currency"],
                    flooring_m_squared=item["flooring_m_squared"],
                    crawl=crawl,
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
