import json
from typing import Any, Dict, List
from bs4 import BeautifulSoup
import re


class BezRealitkyParser:
    @staticmethod
    def _extract_location_from_title(title: str | None) -> str | None:
        if not title:
            return None
        # Typical format already carries precise location:
        # "Street, City - District"
        location = title.replace("\xa0", " ").strip()
        return location or None

    @staticmethod
    def parse_one(card) -> Dict[str, Any]:
        item = {
            "title": None,
            "price": None,
            "currency": "CZK",
            "flooring_m_squared": None,
            "location": None,
            "description": None,
            "listing_url": None,
        }

        # Extract from html
        title_elem = card.find(class_="PropertyCard_propertyCardAddress__hNqyR")
        price_elem = card.find(class_="PropertyPrice_propertyPriceAmount__WdEE1")
        ppm_elem = card.find(class_="PropertyPrice_propertyPricePerMeter__IfhGa")
        if h2_elem := card.find("h2"):  # Extract the ID from offering URL
            if (a_elem := h2_elem.find("a")) and a_elem.has_attr("href"):
                href = a_elem["href"]
                if href.startswith("http://") or href.startswith("https://"):
                    item["listing_url"] = href
                elif href.startswith("/"):
                    item["listing_url"] = f"https://www.bezrealitky.cz{href}"
                match = re.search(r"/(\d+)-", a_elem["href"])
                if match:
                    item["description"] = match.group(1)

        # Save extracted data to item
        if title_elem:
            item["title"] = title_elem.get_text(strip=True)
            item["location"] = BezRealitkyParser._extract_location_from_title(
                item["title"]
            )
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_text = re.sub(r"[^\d]", "", price_text)
            try:
                item["price"] = int(price_text)
            except ValueError:
                pass
        if ppm_elem:
            ppm_text = ppm_elem.get_text(strip=True)
            ppm_text = re.sub(r"[^\d]", "", ppm_text)
            try:
                ppm = int(ppm_text)
                item["flooring_m_squared"] = item["price"] / ppm
            except (ValueError, ZeroDivisionError):
                pass

        return item

    @classmethod
    def parse(cls, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")

        return [
            cls.parse_one(card)
            for card in soup.find_all(class_="PropertyCard_propertyCardContent__osPAM")
        ]


class SrealityParser:
    AREA_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*m(?:2|\u00b2)", re.IGNORECASE)
    DETAIL_URL_PATTERN = re.compile(r"/detail/[^?#]*/(\d+)(?:[/?#]|$)", re.IGNORECASE)

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            if value is None:
                return None
            parsed = int(value)
            return parsed if parsed > 0 else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _parse_area_from_title(cls, title: str | None) -> float | None:
        if not title:
            return None
        normalized_title = title.replace("\xa0", " ").replace("\u00c2\u00b2", "\u00b2")
        match = cls.AREA_PATTERN.search(normalized_title)
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            return None

    @classmethod
    def _extract_results(cls, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        next_data = soup.find("script", id="__NEXT_DATA__")
        if not next_data or not next_data.string:
            return []

        try:
            payload = json.loads(next_data.string)
        except json.JSONDecodeError:
            return []

        queries = (
            payload.get("props", {})
            .get("pageProps", {})
            .get("dehydratedState", {})
            .get("queries", [])
        )

        for query in queries:
            query_key = query.get("queryKey")
            if isinstance(query_key, list) and query_key and query_key[0] == "estatesSearch":
                results = query.get("state", {}).get("data", {}).get("results", [])
                return results if isinstance(results, list) else []
        return []

    @classmethod
    def _extract_listing_urls(cls, html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        listing_urls: dict[str, str] = {}
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            match = cls.DETAIL_URL_PATTERN.search(href)
            if not match:
                continue
            estate_id = match.group(1)
            if estate_id in listing_urls:
                continue
            if href.startswith("http://") or href.startswith("https://"):
                listing_urls[estate_id] = href
            else:
                listing_urls[estate_id] = f"https://www.sreality.cz{href}"
        return listing_urls

    @classmethod
    def _normalize_location(cls, locality: Any) -> str | None:
        if locality is None:
            return None
        if isinstance(locality, str):
            text = locality.strip()
            return text or None
        if isinstance(locality, dict):
            street = str(locality.get("street") or "").strip()
            street_number = str(locality.get("streetNumber") or "").strip()
            city = str(locality.get("city") or "").strip()
            city_part = str(locality.get("cityPart") or "").strip()
            district = str(locality.get("district") or "").strip()
            street_bits = " ".join(part for part in [street, street_number] if part).strip()
            area_bits = " - ".join(part for part in [city, city_part] if part).strip()

            if street_bits and area_bits:
                return f"{street_bits}, {area_bits}"
            if street_bits:
                return street_bits
            if area_bits:
                return area_bits
            if district:
                return district
        return None

    @classmethod
    def _parse_one(
        cls, estate: dict[str, Any], listing_urls_by_id: dict[str, str]
    ) -> Dict[str, Any]:
        title = estate.get("name")
        location = cls._normalize_location(estate.get("locality"))
        price = cls._safe_int(estate.get("priceSummaryCzk")) or cls._safe_int(
            estate.get("priceCzk")
        )
        price_per_meter = cls._safe_int(estate.get("priceCzkPerSqM"))

        area = None
        if price is not None and price_per_meter is not None and price_per_meter > 0:
            area = round(price / price_per_meter, 2)
        else:
            area = cls._parse_area_from_title(title)

        estate_id = estate.get("id")
        estate_id_str = str(estate_id) if estate_id is not None else ""
        listing_url = listing_urls_by_id.get(estate_id_str)

        return {
            "title": title,
            "price": price,
            "currency": "CZK" if price is not None else None,
            "flooring_m_squared": area,
            "location": location,
            "description": estate_id_str,
            "listing_url": listing_url,
        }

    @classmethod
    def parse(cls, html: str) -> List[Dict[str, Any]]:
        results = cls._extract_results(html)
        listing_urls_by_id = cls._extract_listing_urls(html)
        return [cls._parse_one(estate, listing_urls_by_id) for estate in results]

