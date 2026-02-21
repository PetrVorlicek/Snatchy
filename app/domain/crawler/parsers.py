from typing import Any, Dict, List
from bs4 import BeautifulSoup
import re


class BezRealitkyParser:
    @staticmethod
    def parse_one(card) -> Dict[str, Any]:
        item = {
            "title": None,
            "price": None,
            "currency": "CZK",
            "flooring_m_squared": None,
            "description": None,
        }

        # Extract from html
        title_elem = card.find(class_="PropertyCard_propertyCardAddress__hNqyR")
        price_elem = card.find(class_="PropertyPrice_propertyPriceAmount__WdEE1")
        ppm_elem = card.find(class_="PropertyPrice_propertyPricePerMeter__IfhGa")
        if h2_elem := card.find("h2"):  # Extract the ID from offering URL
            if (a_elem := h2_elem.find("a")) and a_elem.has_attr("href"):
                match = re.search(r"/(\d+)-", a_elem["href"])
                if match:
                    item["description"] = match.group(1)

        # Save extracted data to item
        if title_elem:
            item["title"] = title_elem.get_text(strip=True)
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
