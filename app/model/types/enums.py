import enum


class RecordType(enum.Enum):
    """Enum for record types."""

    REAL_ESTATE = "real_estate"


class Currency(enum.Enum):
    """Enum for currency types."""

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CZK = "CZK"
