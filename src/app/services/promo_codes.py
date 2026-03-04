from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from generated.models.error_code import ErrorCode
from generated.models.promo_code_create import PromoCodeCreate

from ..errors import ApiError
from ..models import PromoCode, DiscountType


async def create_promo_code(session: AsyncSession, role: str, data: PromoCodeCreate) -> PromoCode:
    if role == "USER":
        raise ApiError(ErrorCode.ACCESS_DENIED, "Access denied", 403)
    promo = PromoCode(
        code=data.code,
        discount_type=DiscountType(data.discount_type),
        discount_value=data.discount_value,
        min_order_amount=data.min_order_amount,
        max_uses=data.max_uses,
        valid_from=data.valid_from.astimezone(timezone.utc).replace(tzinfo=None),
        valid_until=data.valid_until.astimezone(timezone.utc).replace(tzinfo=None),
        active=data.active,
    )
    session.add(promo)
    await session.commit()
    await session.refresh(promo)
    return promo
