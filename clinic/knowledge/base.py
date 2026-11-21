from abc import ABC, abstractmethod

from clinic.models import Tenant


class Tab:
    """Tab names in each clinic's Google Sheet."""

    FAQ = "FAQ"
    SERVICES = "Services"
    INFO = "Info"
    ALL = (FAQ, SERVICES, INFO)


class KnowledgeSourceError(Exception):
    """The clinic's knowledge could not be loaded."""


class KnowledgeSource(ABC):
    """Where a clinic's FAQ, prices and info come from."""

    @abstractmethod
    def get_tab(self, tenant: Tenant, name: str) -> list[dict[str, str]]:
        """Rows of one tab. Keys are lowercase column headers, values are strings."""
