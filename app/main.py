import argparse
import asyncio
import copy
from datetime import timedelta
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

from sqlalchemy import select, update

from app.domain.scheduler.schedulers import Scheduler
from app.domain.crawler.crawlers import build_crawler, is_block_page_html
from app.domain.crawler.parsers import BezRealitkyParser, SrealityParser
from app.model.models.models import (
    RealEstateRecord,
    Description,
    Domain,
    Site,
    Crawl,
    CrawlTarget,
    Record,
)
from app.model.session import aget_session
from app.domain.utils.time import now


import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional seed to keep old behavior for fresh databases.
DEFAULT_TARGETS = [
    {
        "url": "https://www.bezrealitky.cz/vyhledat?estateType=BYT&location=exact&offerType=PRODEJ&osm_value=Hlavn%C3%AD+m%C4%9Bsto+Praha%2C+Praha%2C+%C4%8Cesko&regionOsmIds=R435514&currency=CZK&locale=CS",
        "parser_key": "bezrealitky",
        "frequency_minutes": 24 * 60,
    }
]
FREQUENCY = timedelta(minutes=5)
PARSER_MAP = {
    "bezrealitky": BezRealitkyParser,
    "sreality": SrealityParser,
}
SITE_CRAWLER_CONFIGS: dict[str, dict[str, dict[str, object]]] = {
    # Hardcoded site profile so Sreality runs consistently without shell env flags.
    "sreality": {
        "engine_kwargs": {
            "user_data_dir": ".snatchy_profile/sreality",
            "nav_timeout_ms": 35000,
        },
        "runtime_config": {
            "max_attempts": 2,
            "retry_sleep_ms": 1000,
            "networkidle_timeout_ms": 10000,
            "cookie_wait_ms": 2500,
            "cmp_wait_ms": 4000,
            "manual_wait_ms": 0,
            "preseed_consent": True,
        },
    }
}
TARGET_ENGINE_OVERRIDE_FIELDS = ("headless", "nav_timeout_ms")
TARGET_RUNTIME_OVERRIDE_FIELDS = (
    "max_attempts",
    "retry_sleep_ms",
    "networkidle_timeout_ms",
    "cookie_wait_ms",
    "cmp_wait_ms",
    "manual_wait_ms",
)
PRINT_HTML = os.getenv("SNATCHY_PRINT_HTML", "").lower() in {"1", "true", "yes"}
HTML_PREVIEW_CHARS = int(os.getenv("SNATCHY_HTML_PREVIEW_CHARS", "0"))
HTML_DUMP_PATH = os.getenv("SNATCHY_HTML_DUMP_PATH")
_seed_done = False


async def ensure_target(
    session, url: str, parser_key: str, frequency_minutes: int
) -> None:
    parsed_url = urlparse(url)
    domain_name = parsed_url.netloc
    site_url = f"{parsed_url.scheme}://{domain_name}"

    stmt = select(Domain).where(Domain.url == domain_name)
    domain = (await session.execute(stmt)).scalar_one_or_none()
    if not domain:
        domain = Domain(url=domain_name)
        session.add(domain)
        await session.flush()

    stmt = select(Site).where(Site.url == site_url)
    site = (await session.execute(stmt)).scalar_one_or_none()
    if not site:
        site = Site(url=site_url, domain=domain)
        session.add(site)
        await session.flush()

    stmt = select(CrawlTarget).where(CrawlTarget.url == url)
    target = (await session.execute(stmt)).scalar_one_or_none()
    if target:
        return

    session.add(
        CrawlTarget(
            site=site,
            url=url,
            parser_key=parser_key,
            frequency_minutes=frequency_minutes,
            enabled=True,
        )
    )


async def ensure_seed_targets() -> None:
    async with aget_session() as session:
        for target in DEFAULT_TARGETS:
            await ensure_target(
                session=session,
                url=target["url"],
                parser_key=target["parser_key"],
                frequency_minutes=target["frequency_minutes"],
            )
        await session.commit()


async def maybe_seed_targets() -> None:
    global _seed_done
    if _seed_done:
        return
    await ensure_seed_targets()
    _seed_done = True


def get_parser(parser_key: str):
    parser_cls = PARSER_MAP.get(parser_key)
    if parser_cls is None:
        raise ValueError(f"Unknown parser key: {parser_key}")
    return parser_cls()


def get_crawler_config(target: CrawlTarget) -> dict[str, dict[str, object]]:
    config = copy.deepcopy(SITE_CRAWLER_CONFIGS.get(target.parser_key, {}))
    engine_kwargs = dict(config.get("engine_kwargs", {}))
    runtime_config = dict(config.get("runtime_config", {}))

    for field in TARGET_ENGINE_OVERRIDE_FIELDS:
        value = getattr(target, field, None)
        if value is not None:
            engine_kwargs[field] = value

    for field in TARGET_RUNTIME_OVERRIDE_FIELDS:
        value = getattr(target, field, None)
        if value is not None:
            runtime_config[field] = value

    config["engine_kwargs"] = engine_kwargs
    config["runtime_config"] = runtime_config
    return config


async def get_due_targets() -> list[CrawlTarget]:
    async with aget_session() as session:
        stmt = select(CrawlTarget).where(CrawlTarget.enabled.is_(True))
        targets = (await session.execute(stmt)).scalars().all()

    now_ts = now()
    return [
        target
        for target in targets
        if target.last_run_at is None
        or now_ts - target.last_run_at >= timedelta(minutes=target.frequency_minutes)
    ]


async def mark_crawl_finished(crawl_id: int) -> None:
    async with aget_session() as session:
        crawl = await session.get(Crawl, crawl_id)
        if crawl:
            crawl.finished_at = now()
            await session.commit()


def normalize_listing_id(raw: object) -> str:
    return str(raw or "").strip()


def normalize_text(raw: object) -> str:
    return str(raw or "").strip()


async def get_existing_listing_ids_for_site(
    session, *, site_id: int, listing_ids: set[str]
) -> set[str]:
    if not listing_ids:
        return set()

    stmt = (
        select(Description.text)
        .join(Record, Description.record_id == Record.id)
        .join(Crawl, Record.crawl_id == Crawl.id)
        .where(Crawl.site_id == site_id, Description.text.in_(listing_ids))
    )
    return set((await session.execute(stmt)).scalars().all())


async def refresh_existing_listing_for_listing_id(
    session,
    *,
    site_id: int,
    listing_id: str,
    seen_at,
    listing_url: str,
    location: str,
) -> tuple[int, int]:
    if not listing_id:
        return (0, 0)

    record_ids_stmt = (
        select(Record.id)
        .join(Description, Description.record_id == Record.id)
        .join(Crawl, Record.crawl_id == Crawl.id)
        .where(Crawl.site_id == site_id, Description.text == listing_id)
    )

    touch_stmt = (
        update(RealEstateRecord)
        .where(RealEstateRecord.id.in_(record_ids_stmt))
        .values(last_seen=seen_at)
    )
    touched_result = await session.execute(touch_stmt)

    updated_other_fields = 0

    if listing_url:
        stmt = (
            update(RealEstateRecord)
            .where(
                RealEstateRecord.id.in_(record_ids_stmt),
                RealEstateRecord.source_url.is_(None),
            )
            .values(source_url=listing_url)
        )
        result = await session.execute(stmt)
        updated_other_fields += int(result.rowcount or 0)

    if location:
        location_stmt = (
            update(RealEstateRecord)
            .where(
                RealEstateRecord.id.in_(record_ids_stmt),
                (RealEstateRecord.location.is_(None))
                | (RealEstateRecord.location != location),
            )
            .values(location=location)
        )
        location_result = await session.execute(location_stmt)
        updated_other_fields += int(location_result.rowcount or 0)

    return (
        int(touched_result.rowcount or 0),
        updated_other_fields,
    )


async def run_crawl(target_id: int, ignore_disabled: bool = False):
    crawl_id = None
    results = []
    site_id = None
    crawler_config: dict[str, dict[str, object]] = {}

    try:
        async with aget_session() as session:
            target = await session.get(CrawlTarget, target_id)
            if not target:
                logger.warning(f"Crawl target {target_id} does not exist.")
                return
            if not target.enabled and not ignore_disabled:
                logger.info(f"Crawl target {target_id} is disabled. Skipping.")
                return

            started_at = now()
            target.last_run_at = started_at
            crawl = Crawl(site_id=target.site_id, started_at=started_at)
            session.add(crawl)
            await session.commit()

            crawl_id = crawl.id
            site_id = target.site_id
            target_url = target.url
            parser_key = target.parser_key
            crawler_config = get_crawler_config(target)

        logger.info(f"Starting crawl for target={target_id} url={target_url}")

        crawler = build_crawler(
            target_url,
            engine_kwargs=crawler_config.get("engine_kwargs"),
            runtime_config=crawler_config.get("runtime_config"),
        )
        async with crawler.get_page() as page:
            html = await page.content()
        if PRINT_HTML:
            preview = html if HTML_PREVIEW_CHARS <= 0 else html[:HTML_PREVIEW_CHARS]
            try:
                print(preview)
            except UnicodeEncodeError:
                output_encoding = sys.stdout.encoding or "utf-8"
                safe_preview = preview.encode(output_encoding, errors="replace").decode(
                    output_encoding, errors="replace"
                )
                print(safe_preview)
        if HTML_DUMP_PATH:
            dump_path = Path(HTML_DUMP_PATH.format(target_id=target_id))
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            dump_path.write_text(html, encoding="utf-8")
            logger.info(f"Saved HTML dump for target={target_id} to {dump_path}")
        if is_block_page_html(html):
            raise RuntimeError(
                "Detected anti-bot/error page instead of listings HTML. "
                "Try running headed mode (set crawl_targets.headless=false for this target), "
                "adjust retries/timeouts on this target, or use a different network/IP."
            )
        parser = get_parser(parser_key)
        results = parser.parse(html)

        # First drop duplicates produced within one parser run by listing ID.
        unique_items = []
        seen_listing_ids: set[str] = set()
        duplicate_in_payload = 0
        for item in results:
            listing_id = normalize_listing_id(item.get("description"))
            if not listing_id:
                unique_items.append(item)
                continue
            if listing_id in seen_listing_ids:
                duplicate_in_payload += 1
                continue
            seen_listing_ids.add(listing_id)
            item["description"] = listing_id
            unique_items.append(item)

        async with aget_session() as session:
            existing_ids = (
                await get_existing_listing_ids_for_site(
                    session, site_id=site_id, listing_ids=seen_listing_ids
                )
                if site_id is not None
                else set()
            )

            observed_at = now()
            inserted = 0
            skipped_existing = 0
            touched_last_seen = 0
            backfilled_fields = 0
            for item in unique_items:
                listing_id = normalize_listing_id(item.get("description"))
                if listing_id and listing_id in existing_ids:
                    if site_id is not None:
                        touched_count, backfilled_count = (
                            await refresh_existing_listing_for_listing_id(
                            session,
                            site_id=site_id,
                            listing_id=listing_id,
                            seen_at=observed_at,
                            listing_url=normalize_text(item.get("listing_url")),
                            location=normalize_text(item.get("location")),
                        ))
                        touched_last_seen += touched_count
                        backfilled_fields += backfilled_count
                    skipped_existing += 1
                    continue

                record = RealEstateRecord(
                    published_at=observed_at,
                    last_seen=observed_at,
                    title=item["title"],
                    price=item["price"],
                    currency=item["currency"],
                    flooring_m_squared=item["flooring_m_squared"],
                    location=item.get("location"),
                    source_url=item.get("listing_url"),
                    crawl_id=crawl_id,
                )
                description = Description(text=listing_id, record=record)
                session.add(record)
                session.add(description)
                inserted += 1

            crawl = await session.get(Crawl, crawl_id)
            if crawl:
                crawl.finished_at = now()
            await session.commit()
            logger.info(
                "Target=%s parsed=%s inserted=%s skipped_existing=%s skipped_in_payload=%s touched_last_seen=%s",
                target_id,
                len(results),
                inserted,
                skipped_existing,
                duplicate_in_payload,
                touched_last_seen,
            )
            if backfilled_fields > 0:
                logger.info(
                    "Target=%s backfilled source_url/location on %s existing record(s).",
                    target_id,
                    backfilled_fields,
                )
    except Exception as e:
        logger.exception(f"Error during crawling target={target_id}: {e!r}")
        if crawl_id is not None:
            await mark_crawl_finished(crawl_id)
        return

    logger.info(
        f"Crawl completed for target={target_id} with {len(results)} records found."
    )


async def run_due_crawls():
    await maybe_seed_targets()
    due_targets = await get_due_targets()
    if not due_targets:
        logger.info("No crawl targets due for execution.")
        return

    logger.info(f"Running {len(due_targets)} due crawl target(s).")
    await asyncio.gather(*(run_crawl(target.id) for target in due_targets))


async def run_target_now(target_id: int):
    await maybe_seed_targets()
    logger.info(f"Running target={target_id} on demand.")
    await run_crawl(target_id=target_id, ignore_disabled=True)


async def run_all_now():
    await maybe_seed_targets()
    async with aget_session() as session:
        stmt = select(CrawlTarget.id).where(CrawlTarget.enabled.is_(True))
        target_ids = list((await session.execute(stmt)).scalars().all())

    if not target_ids:
        logger.info("No enabled crawl targets found.")
        return

    logger.info(f"Running {len(target_ids)} enabled target(s) on demand.")
    await asyncio.gather(*(run_crawl(target_id=target_id) for target_id in target_ids))


def crawl():
    scheduler = Scheduler(
        callback=run_due_crawls,
        callback_kwargs=[{}],
        frequency=FREQUENCY,
    )

    logger.info(
        f"Starting Scheduler with frequency: {FREQUENCY}. Crawls are loaded from crawl_targets table."
    )
    scheduler.run_forever()


def run_once(target_id: int | None = None, all_now: bool = False):
    if all_now:
        asyncio.run(run_all_now())
        return
    if target_id is not None:
        asyncio.run(run_target_now(target_id))
        return
    asyncio.run(run_due_crawls())


def main():
    parser = argparse.ArgumentParser(description="Snatchy crawler runner")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run due crawl targets once and exit.",
    )
    parser.add_argument(
        "--target-id",
        type=int,
        help="Run a specific crawl target ID immediately (ignores due-time checks).",
    )
    parser.add_argument(
        "--all-now",
        action="store_true",
        help="Run all enabled crawl targets immediately (ignores due-time checks).",
    )
    args = parser.parse_args()

    if args.all_now:
        run_once(all_now=True)
        return
    if args.target_id is not None:
        run_once(target_id=args.target_id)
        return
    if args.once:
        run_once()
        return
    crawl()


if __name__ == "__main__":
    main()
