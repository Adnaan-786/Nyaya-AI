"""
Static SaaS plan catalog (contract B.14). Hardcoded rather than a DB
table: plans change rarely, and it keeps quota enforcement simple.
Move to a DB table if plans ever need to change without a deploy.
"""

from dataclasses import dataclass

from app.db.enums import PlanType


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    price_paise_monthly: int
    price_paise_yearly: int
    max_cases: int  # -1 means unlimited
    ai_jobs_per_day: int
    storage_gb: int
    razorpay_plan_id_monthly: str = ""
    razorpay_plan_id_yearly: str = ""


PLANS: dict[str, Plan] = {
    PlanType.FREE.value: Plan("free", "Free", 0, 0, 10, 5, 1),
    PlanType.BASIC.value: Plan("basic", "Basic", 99900, 999900, 100, 30, 10),
    PlanType.PRO.value: Plan("pro", "Pro", 299900, 2999900, 500, 100, 50),
    PlanType.ENTERPRISE.value: Plan("enterprise", "Enterprise", 999900, 9999900, -1, 500, 500),
}

PLAN_ORDER = [PlanType.FREE.value, PlanType.BASIC.value, PlanType.PRO.value, PlanType.ENTERPRISE.value]


def get_plan(plan_id: str) -> Plan:
    return PLANS.get(plan_id) or PLANS[PlanType.FREE.value]


def next_plan_up(plan_id: str) -> str | None:
    """The plan to suggest in a 402 `details.upgrade_to`; None if already on the top plan."""
    try:
        idx = PLAN_ORDER.index(plan_id)
    except ValueError:
        return PLAN_ORDER[1]
    return PLAN_ORDER[idx + 1] if idx + 1 < len(PLAN_ORDER) else None
