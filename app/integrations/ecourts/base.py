"""
Provider abstraction for eCourts data (plan C.7):

    "Provider abstraction: ECourtsProvider interface with
    lookup_cnr(cnr), case_status(cnr), cause_list(court_id, date).
    Two implementations: NapixProvider (official NIC APIs once
    approved) and CommercialProvider (eCourtsIndia/Surepass). Config
    chooses per-environment; a recorded FixtureProvider serves
    staging/checkpoint determinism."

Every implementation returns/accepts the same normalized shapes below,
so swapping providers is config-only (settings.ecourts_provider),
exactly as required by the plan's Definition of Done for this module.
"""

import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class NormalizedHearing:
    date: datetime.date
    purpose: str | None = None
    outcome_notes: str | None = None


@dataclass
class NormalizedCase:
    """The normalized shape every provider must return from a CNR lookup."""

    cnr: str
    title: str
    court_name: str | None = None
    court_type: str | None = None
    judge_name: str | None = None
    case_type: str | None = None
    stage: str | None = None
    parties: list[str] = field(default_factory=list)
    next_hearing_date: datetime.date | None = None
    history: list[NormalizedHearing] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


class ECourtsProviderError(Exception):
    """Raised by a provider implementation when the upstream call fails."""


class ECourtsProvider(ABC):
    """Abstract interface every eCourts data source must implement."""

    @abstractmethod
    async def lookup_cnr(self, cnr: str) -> NormalizedCase:
        """Fetch full case details for a CNR."""

    @abstractmethod
    async def case_status(self, cnr: str) -> NormalizedCase:
        """
        Cheaper/faster status-only refresh, used by the polling worker.
        Providers that don't distinguish the two calls may just delegate
        to lookup_cnr.
        """

    @abstractmethod
    async def cause_list(self, court_id: str, date: datetime.date) -> list[NormalizedCase]:
        """List of cases listed at a given court on a given date."""
