from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.core.security import utcnow
from app.db.enums import PlanType
from app.db.rls import set_tenant
from app.db.session import AsyncSessionLocal
from app.db.tenant import TenantContext
from app.integrations import razorpay
from app.models.ai_job import AIJob
from app.models.case import Case
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.services.payment_service import _find_tenant_for
from app.services.plans import PLANS, get_plan


async def get_or_create_subscription(session: AsyncSession, tenant_id: UUID) -> Subscription:
    row = (
        await session.execute(select(Subscription).where(Subscription.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if row is None:
        row = Subscription(tenant_id=tenant_id, plan=PlanType.FREE, status="active")
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def get_usage(session: AsyncSession, tenant_id: UUID) -> dict:
    cases = (await session.execute(select(func.count()).select_from(Case).where(Case.tenant_id == tenant_id))).scalar_one()
    since = utcnow() - timedelta(days=1)
    ai_jobs = (
        await session.execute(
            select(func.count()).select_from(AIJob).where(AIJob.tenant_id == tenant_id).where(AIJob.created_at >= since)
        )
    ).scalar_one()
    return {"cases": cases, "ai_jobs_today": ai_jobs}


async def checkout(session: AsyncSession, tenant: TenantContext, *, plan_id: str, cycle: str) -> dict:
    if plan_id not in PLANS or plan_id == PlanType.FREE.value:
        raise ValidationException("plan_id must be a paid plan.", details={"allowed": ["basic", "pro", "enterprise"]})

    plan = get_plan(plan_id)
    razorpay_plan = plan.razorpay_plan_id_yearly if cycle == "yearly" else plan.razorpay_plan_id_monthly
    result = await razorpay.create_subscription(plan_razorpay_id=razorpay_plan or f"plan_{plan_id}_{cycle}")

    sub = await get_or_create_subscription(session, tenant.tenant_id)
    sub.plan, sub.cycle, sub.status = PlanType(plan_id), cycle, "pending_activation"
    sub.razorpay_subscription_id = result["id"]
    await session.commit()
    return {"razorpay_subscription_id": result["id"], "checkout_url": result["short_url"]}


async def activate_subscription(razorpay_subscription_id: str) -> None:
    """Webhook-driven (no tenant context): resolves the tenant, then activates within its RLS scope."""
    tenant_id = await _find_tenant_for(Subscription.razorpay_subscription_id, razorpay_subscription_id)
    if tenant_id is None:
        return
    async with AsyncSessionLocal() as session:
        await set_tenant(session, str(tenant_id))
        sub = (
            await session.execute(
                select(Subscription).where(Subscription.razorpay_subscription_id == razorpay_subscription_id)
            )
        ).scalar_one_or_none()
        if sub is None:
            return
        sub.status = "active"
        sub.current_period_end = utcnow().date() + timedelta(days=365 if sub.cycle == "yearly" else 30)
        tenant = (await session.execute(select(Tenant).where(Tenant.id == sub.tenant_id))).scalar_one_or_none()
        if tenant is not None:
            tenant.plan = sub.plan
        await session.commit()


async def cancel_subscription(session: AsyncSession, sub: Subscription) -> Subscription:
    """Contract B.14: downgrade/cancel takes effect at cycle end."""
    sub.cancel_at_period_end = True
    await session.commit()
    await session.refresh(sub)
    return sub


async def downgrade_expired_cancellations(session: AsyncSession) -> int:
    """Cycle-end job body: flips elapsed cancellations back to the free plan."""
    expired = list(
        (
            await session.execute(
                select(Subscription)
                .where(Subscription.cancel_at_period_end.is_(True))
                .where(Subscription.current_period_end.is_not(None))
                .where(Subscription.current_period_end <= utcnow().date())
                .where(Subscription.status != "cancelled")
            )
        ).scalars().all()
    )
    for sub in expired:
        sub.plan, sub.status, sub.cancel_at_period_end = PlanType.FREE, "cancelled", False
        tenant = (await session.execute(select(Tenant).where(Tenant.id == sub.tenant_id))).scalar_one_or_none()
        if tenant is not None:
            tenant.plan = PlanType.FREE
    if expired:
        await session.commit()
    return len(expired)
