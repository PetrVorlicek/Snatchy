from contextlib import asynccontextmanager
import asyncio

from app.domain.crawler.engines import StealthPlaywrightEngine


class Crawler:
    def __init__(self):
        self._url = None
        self._engine = None
        self._parser = None

    def set_engine(self, engine):
        if self._engine is not None:
            raise ValueError("Engine is already set")
        self._engine = engine

    def set_parser(self, parser):
        if self._parser is not None:
            raise ValueError("Parser is already set")
        self._parser = parser

    def set_url(self, url):
        if self._url is not None:
            raise ValueError("URL is already set")
        self._url = url

    @property
    def is_ready(self):
        return (
            self._engine is not None
            and self._parser is not None
            and self._url is not None
        )

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


def build_crawler(url: str, parser):
    crawler = Crawler()
    crawler.set_url(url)
    crawler.set_parser(parser)
    crawler.set_engine(StealthPlaywrightEngine)
    return crawler


async def main():
    crawler = build_crawler("https://google.com", parser="dummy_parser")
    async with crawler.get_page() as page:
        html = await page.content()  # TODO: Use parser to parse different sites
        print(html)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
