from contextlib import asynccontextmanager
import asyncio

from app.domain.crawler.engines import StealthPlaywrightEngine

URL = "https://www.bezrealitky.cz/vyhledat?estateType=BYT&location=exact&offerType=PRODEJ&osm_value=Hlavn%C3%AD+m%C4%9Bsto+Praha%2C+Praha%2C+%C4%8Cesko&regionOsmIds=R435514&currency=CZK&locale=CS"


class Crawler:
    def __init__(self):
        self._url = None
        self._engine = None

    def set_engine(self, engine):
        if self._engine is not None:
            raise ValueError("Engine is already set")
        self._engine = engine

    def set_url(self, url):
        if self._url is not None:
            raise ValueError("URL is already set")
        self._url = url

    @property
    def is_ready(self):
        return self._engine is not None and self._url is not None

    @asynccontextmanager
    async def get_page(self):
        if not self.is_ready:
            raise ValueError(
                "Crawler is not ready. Please set engine, parser, and URL before using."
            )

        async with self._engine() as engine:
            async with engine.page() as page:
                await page.goto(self._url)
                try:
                    yield page
                finally:
                    print("Page context closed")


def build_crawler(url: str) -> Crawler:
    crawler = Crawler()
    crawler.set_url(url)
    crawler.set_engine(StealthPlaywrightEngine)
    return crawler


async def main():
    crawler = build_crawler(URL)
    async with crawler.get_page() as page:
        html = await page.content()
        from app.domain.crawler.parsers import BezRealitkyParser

        parser = BezRealitkyParser()
        results = parser.parse(html)
        print(results)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
