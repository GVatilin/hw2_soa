import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from generated.models.error_code import ErrorCode

from ..errors import ApiError
from ..settings import settings
from ..models import (
    Product, ProductStatus,
    Order, OrderItem, OrderStatus,
    UserOperation,
    PromoCode, DiscountType
)


async def _check_rate_limit(session: AsyncSession, user_id: uuid.UUID):
    q = (
        select(UserOperation.created_at)
        .where(UserOperation.user_id == user_id, UserOperation.operation_type == "CREATE_ORDER")
        .order_by(UserOperation.created_at.desc())
        .limit(1)
    )
    last = (await session.execute(q)).scalar_one_or_none()
    if last and (datetime.now(timezone.utc) - last.astimezone(timezone.utc) < timedelta(minutes=settings.order_rate_limit_min)):
        raise ApiError(ErrorCode.ORDER_LIMIT_EXCEEDED, "Order operation rate limit exceeded", 429)


async def _check_has_active_order(session: AsyncSession, user_id: uuid.UUID):
    q = select(Order.id).where(Order.user_id == user_id, Order.status.in_([OrderStatus.CREATED, OrderStatus.PAYMENT_PENDING])).limit(1)
    if (await session.execute(q)).first():
        raise ApiError(ErrorCode.ORDER_HAS_ACTIVE, "User already has an active order", 409)


def _promo_discount(total: Decimal, promo: PromoCode) -> Decimal:
    if promo.discount_type == DiscountType.PERCENTAGE:
        disc = (total * Decimal(str(promo.discount_value)) / Decimal("100")).quantize(Decimal("0.01"))
        cap = (total * Decimal("0.70")).quantize(Decimal("0.01"))
        return min(disc, cap)
    return min(Decimal(str(promo.discount_value)), total)


def _to_uuid(value: str | uuid.UUID) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(value)


async def create_order(
    session: AsyncSession,
    user_id_str: str | uuid.UUID,
    items: list[tuple[str | uuid.UUID, int]],
    promo_code: str | None,
):
    user_id = _to_uuid(user_id_str)
    async with session.begin():
        await _check_rate_limit(session, user_id)
        await _check_has_active_order(session, user_id)

        product_ids = [_to_uuid(pid) for pid, _ in items]
        products = (await session.execute(
            select(Product).where(Product.id.in_(product_ids)).with_for_update()
        )).scalars().all()
        by_id = {p.id: p for p in products}

        insuff = []
        for pid_str, qty in items:
            pid = _to_uuid(pid_str)
            p = by_id.get(pid)
            if not p:
                raise ApiError(ErrorCode.PRODUCT_NOT_FOUND, "Product not found", 404, {"product_id": str(pid_str)})
            if p.status != ProductStatus.ACTIVE:
                raise ApiError(ErrorCode.PRODUCT_INACTIVE, "Product inactive", 409, {"product_id": str(pid_str)})
            if p.stock < qty:
                insuff.append({"product_id": str(pid_str), "requested": qty, "available": p.stock})
        if insuff:
            raise ApiError(ErrorCode.INSUFFICIENT_STOCK, "Insufficient stock", 409, {"items": insuff})

        total = Decimal("0.00")
        for pid_str, qty in items:
            pid = _to_uuid(pid_str)
            p = by_id[pid]
            p.stock -= qty
            total += Decimal(str(p.price)) * Decimal(qty)
        total = total.quantize(Decimal("0.01"))

        discount = Decimal("0.00")
        promo = None
        if promo_code:
            promo = (await session.execute(
                select(PromoCode).where(PromoCode.code == promo_code).with_for_update()
            )).scalar_one_or_none()
            now = datetime.now(timezone.utc)
            if (
                promo is None
                or not promo.active
                or promo.current_uses >= promo.max_uses
                or not (promo.valid_from.astimezone(timezone.utc) <= now <= promo.valid_until.astimezone(timezone.utc))
            ):
                raise ApiError(ErrorCode.PROMO_CODE_INVALID, "Promo code invalid", 422)
            if total < Decimal(str(promo.min_order_amount)):
                raise ApiError(ErrorCode.PROMO_CODE_MIN_AMOUNT, "Order amount below promo minimum", 422)

            discount = _promo_discount(total, promo)
            total = (total - discount).quantize(Decimal("0.01"))
            promo.current_uses += 1

        order = Order(
            user_id=user_id,
            status=OrderStatus.CREATED,
            promo_code_id=promo.id if promo else None,
            total_amount=float(total),
            discount_amount=float(discount),
        )
        session.add(order)
        await session.flush()

        for pid_str, qty in items:
            pid = _to_uuid(pid_str)
            p = by_id[pid]
            session.add(OrderItem(order_id=order.id, product_id=p.id, quantity=qty, price_at_order=float(p.price)))

        session.add(UserOperation(user_id=user_id, operation_type="CREATE_ORDER"))
        await session.flush()
        return order, promo


async def cancel_order(session: AsyncSession, user_id_str: str, order_id_str: str):
    user_id = uuid.UUID(user_id_str)
    order_id = uuid.UUID(order_id_str)
    async with session.begin():
        order = (await session.execute(select(Order).where(Order.id == order_id).with_for_update())).scalar_one_or_none()
        if not order:
            raise ApiError(ErrorCode.ORDER_NOT_FOUND, "Order not found", 404)
        if order.user_id != user_id:
            raise ApiError(ErrorCode.ORDER_OWNERSHIP_VIOLATION, "Order belongs to another user", 403)
        if order.status != OrderStatus.PAYMENT_PENDING and order.status != OrderStatus.CREATED:
            raise ApiError(ErrorCode.INVALID_STATE_TRANSITION, "Order cannot be canceled in this state", 409)

        items = (await session.execute(select(OrderItem).where(OrderItem.order_id == order_id))).scalars().all()
        prod_ids = [it.product_id for it in items]
        prods = (await session.execute(select(Product).where(Product.id.in_(prod_ids)).with_for_update())).scalars().all()
        by_id = {p.id: p for p in prods}

        for it in items:
            by_id[it.product_id].stock += it.quantity

        if order.promo_code_id:
            promo = (await session.execute(select(PromoCode).where(PromoCode.id == order.promo_code_id).with_for_update())).scalar_one_or_none()
            if promo and promo.current_uses > 0:
                promo.current_uses -= 1

        order.status = OrderStatus.CANCELED
        await session.flush()
        return order
