from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_tenant_scoped_db
from app.core.rbac import require
from app.core.responses import ApiResponse
from app.schemas.subscription import PlanOut, SubscriptionCheckoutIn, SubscriptionCheckoutOut, SubscriptionOut
from app.services import subscription_service
from app.services.plans import PLANS

router = APIRouter(tags=["Subscription"])


def _sub_out(sub, usage: dict) -> SubscriptionOut:
    return SubscriptionOut(
        plan=sub.plan.value if hasattr(sub.plan, "value") else sub.plan,
        cycle=sub.cycle,
        status=sub.status,
        current_period_end=sub.current_period_end,
        cancel_at_period_end=sub.cancel_at_period_end,
        usage=usage,
    )


@router.get("/plans", response_model=ApiResponse[list[PlanOut]])
async def get_plans() -> ApiResponse[list[PlanOut]]:
    return ApiResponse(
        success=True,
        data=[
            PlanOut(
                id=p.id, name=p.name, price_paise_monthly=p.price_paise_monthly,
                price_paise_yearly=p.price_paise_yearly, max_cases=p.max_cases,
                ai_jobs_per_day=p.ai_jobs_per_day, storage_gb=p.storage_gb,
            )
            for p in PLANS.values()
        ],
    )


@router.get("/subscription", response_model=ApiResponse[SubscriptionOut])
async def get_subscription(
    auth: AuthContext = Depends(require("firm.manage")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[SubscriptionOut]:
    tid = auth.tenant_id
    sub = await subscription_service.get_or_create_subscription(session, tid)
    return ApiResponse(success=True, data=_sub_out(sub, await subscription_service.get_usage(session, tid)))


@router.post("/subscription/checkout", response_model=ApiResponse[SubscriptionCheckoutOut])
async def checkout(
    payload: SubscriptionCheckoutIn,
    auth: AuthContext = Depends(require("firm.manage")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[SubscriptionCheckoutOut]:
    result = await subscription_service.checkout(
        session, auth.as_tenant_context(), plan_id=payload.plan_id, cycle=payload.cycle
    )
    return ApiResponse(success=True, data=SubscriptionCheckoutOut(**result))


@router.post("/subscription/cancel", response_model=ApiResponse[SubscriptionOut])
async def cancel(
    auth: AuthContext = Depends(require("firm.manage")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[SubscriptionOut]:
    tid = auth.tenant_id
    sub = await subscription_service.get_or_create_subscription(session, tid)
    sub = await subscription_service.cancel_subscription(session, sub)
    return ApiResponse(success=True, data=_sub_out(sub, await subscription_service.get_usage(session, tid)))
