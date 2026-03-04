import uuid
from typing import Sequence

from fastapi import APIRouter, Depends, Query, Response, Security, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from generated.models.error_code import ErrorCode

from generated.models.create_order_request import CreateOrderRequest
from generated.models.login_request import LoginRequest
from generated.models.order_entity import OrderEntity
from generated.models.order_item_entity import OrderItemEntity
from generated.models.order_response import OrderResponse
from generated.models.product_create import ProductCreate
from generated.models.product_entity import ProductEntity
from generated.models.product_status import ProductStatus
from generated.models.product_update import ProductUpdate
from generated.models.products_page import ProductsPage
from generated.models.promo_code_create import PromoCodeCreate
from generated.models.promo_code_entity import PromoCodeEntity
from generated.models.refresh_request import RefreshRequest
from generated.models.register_request import RegisterRequest
from generated.models.token_pair import TokenPair
from generated.models.update_order_request import UpdateOrderRequest

from .auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from .db import get_session
from .errors import ApiError
from .models import Order, OrderItem, Product, PromoCode, User
from .security import Principal, get_principal
from .services.orders import cancel_order, create_order, update_order
from .services.products import archive_product, create_product, get_product, update_product
from .services.promo_codes import create_promo_code
from .services.users import get_user_by_email

router = APIRouter(tags=["default"])


def _as_token_pair(user_id: str, role: str) -> TokenPair:
    access_token, expires_in = create_access_token(user_id, role)
    refresh_token = create_refresh_token(user_id, role)
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=expires_in,
    )


def _as_product_entity(product: Product) -> ProductEntity:
    return ProductEntity(
        id=str(product.id),
        name=product.name,
        description=product.description,
        price=float(product.price),
        stock=product.stock,
        category=product.category,
        status=product.status,
        seller_id=str(product.seller_id) if product.seller_id else None,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def _as_promo_entity(promo: PromoCode | None) -> PromoCodeEntity | None:
    if promo is None:
        return None
    return PromoCodeEntity(
        id=str(promo.id),
        code=promo.code,
        discount_type=promo.discount_type,
        discount_value=float(promo.discount_value),
        min_order_amount=float(promo.min_order_amount),
        max_uses=promo.max_uses,
        current_uses=promo.current_uses,
        valid_from=promo.valid_from,
        valid_until=promo.valid_until,
        active=promo.active,
    )


def _as_order_response(order: Order, items: Sequence[OrderItem], promo: PromoCode | None) -> OrderResponse:
    return OrderResponse(
        order=OrderEntity(
            id=str(order.id),
            user_id=str(order.user_id),
            status=order.status,
            promo_code_id=str(order.promo_code_id) if order.promo_code_id else None,
            total_amount=float(order.total_amount),
            discount_amount=float(order.discount_amount),
            created_at=order.created_at,
            updated_at=order.updated_at,
        ),
        items=[
            OrderItemEntity(
                id=str(item.id),
                order_id=str(item.order_id),
                product_id=str(item.product_id),
                quantity=item.quantity,
                price_at_order=float(item.price_at_order),
            )
            for item in items
        ],
        promo_code=_as_promo_entity(promo),
    )


@router.post("/auth/register", response_model=TokenPair)
async def register(
    register_request: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    existing = await get_user_by_email(session, register_request.email)
    if existing:
        raise ApiError(ErrorCode.USER_ALREADY_EXISTS, "User already exists", 409)
    user = User(
        email=register_request.email,
        password_hash=hash_password(register_request.password),
        role=register_request.role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return _as_token_pair(str(user.id), user.role.value)


@router.post("/auth/login", response_model=TokenPair)
async def login(
    login_request: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    user = await get_user_by_email(session, login_request.email)
    if user is None or not verify_password(login_request.password, user.password_hash):
        raise ApiError(ErrorCode.INVALID_CREDENTIALS, "Invalid credentials", 401)
    return _as_token_pair(str(user.id), user.role.value)


@router.post("/auth/refresh", response_model=TokenPair)
async def auth_refresh_post(refresh_request: RefreshRequest) -> TokenPair:
    payload = decode_token(refresh_request.refresh_token, expected_type="refresh")
    return _as_token_pair(payload["sub"], payload["role"])


@router.get("/products", response_model=ProductsPage)
async def products_get(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1),
    status_filter: ProductStatus | None = Query(None),
    category: str | None = Query(None),
    _: Principal = Security(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProductsPage:
    filters = []
    if status_filter is not None:
        filters.append(Product.status == status_filter)
    if category is not None:
        filters.append(Product.category == category)

    total = (
        await session.execute(select(func.count(Product.id)).where(*filters))
    ).scalar_one()
    items = (
        await session.execute(
            select(Product)
            .where(*filters)
            .order_by(Product.created_at.desc())
            .offset(page * size)
            .limit(size)
        )
    ).scalars().all()
    return ProductsPage(
        items=[_as_product_entity(product) for product in items],
        total_elements=total,
        page=page,
        size=size,
    )


@router.post("/products", response_model=ProductEntity, status_code=status.HTTP_201_CREATED)
async def products_post(
    product_create: ProductCreate,
    principal: Principal = Security(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProductEntity:
    product = await create_product(
        session,
        principal.role,
        principal.user_id,
        product_create.model_dump(),
    )
    return _as_product_entity(product)


@router.get("/products/{id}", response_model=ProductEntity)
async def products_id_get(
    id: uuid.UUID,
    _: Principal = Security(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProductEntity:
    product = await get_product(session, str(id))
    if not product:
        raise ApiError(ErrorCode.PRODUCT_NOT_FOUND, "Product not found", 404)
    return _as_product_entity(product)


@router.put("/products/{id}", response_model=ProductEntity)
async def products_id_put(
    id: uuid.UUID,
    product_update: ProductUpdate,
    principal: Principal = Security(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProductEntity:
    product = await update_product(
        session,
        principal.role,
        principal.user_id,
        str(id),
        product_update.model_dump(),
    )
    return _as_product_entity(product)


@router.delete("/products/{id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def products_id_delete(
    id: uuid.UUID,
    principal: Principal = Security(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await archive_product(session, principal.role, principal.user_id, str(id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/promo-codes", response_model=PromoCodeEntity, status_code=status.HTTP_201_CREATED)
async def promo_codes_post(
    promo_code_create: PromoCodeCreate,
    principal: Principal = Security(get_principal),
    session: AsyncSession = Depends(get_session),
) -> PromoCodeEntity:
    promo = await create_promo_code(
        session,
        principal.role,
        promo_code_create,
    )
    return _as_promo_entity(promo)


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def orders_post(
    create_order_request: CreateOrderRequest,
    principal: Principal = Security(get_principal),
    session: AsyncSession = Depends(get_session),
) -> OrderResponse:
    order, promo = await create_order(
        session,
        principal.user_id,
        [(item.product_id, item.quantity) for item in create_order_request.items],
        create_order_request.promo_code,
    )
    await session.refresh(order)
    items = (
        await session.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    ).scalars().all()
    return _as_order_response(order, items, promo)


@router.put("/orders/{id}", response_model=OrderResponse)
async def orders_id_put(
    id: uuid.UUID,
    update_order_request: UpdateOrderRequest,
    principal: Principal = Security(get_principal),
    session: AsyncSession = Depends(get_session),
) -> OrderResponse:
    order, promo = await update_order(
        session,
        principal.user_id,
        str(id),
        [(item.product_id, item.quantity) for item in update_order_request.items],
    )
    await session.refresh(order)
    items = (
        await session.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    ).scalars().all()
    return _as_order_response(order, items, promo)


@router.post("/orders/{id}/cancel", response_model=OrderResponse)
async def orders_id_cancel_post(
    id: uuid.UUID,
    principal: Principal = Security(get_principal),
    session: AsyncSession = Depends(get_session),
) -> OrderResponse:
    order = await cancel_order(session, principal.user_id, str(id))
    await session.refresh(order)
    items = (
        await session.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    ).scalars().all()
    promo = None
    if order.promo_code_id is not None:
        promo = (
            await session.execute(
                select(PromoCode).where(PromoCode.id == uuid.UUID(str(order.promo_code_id)))
            )
        ).scalar_one_or_none()
    return _as_order_response(order, items, promo)
