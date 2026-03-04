import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from generated.models.error_code import ErrorCode

from ..errors import ApiError
from ..models import Product, ProductStatus


async def create_product(session: AsyncSession, role: str, user_id: str, data: dict) -> Product:
    if role not in ("SELLER","ADMIN"):
        raise ApiError(ErrorCode.ACCESS_DENIED, "Access denied", 403)
    
    seller_id = None if role == "ADMIN" else uuid.UUID(user_id)
    p = Product(
        name=data["name"],
        description=data.get("description"),
        price=data["price"],
        stock=data["stock"],
        category=data["category"],
        status=ProductStatus(data["status"]),
        seller_id=seller_id,
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


async def get_product(session: AsyncSession, product_id: str) -> Product | None:
    res = await session.execute(select(Product).where(Product.id == uuid.UUID(product_id)))
    return res.scalar_one_or_none()


async def update_product(session: AsyncSession, role: str, user_id: str, product_id: str, data: dict) -> Product:
    if role not in ("SELLER","ADMIN"):
        raise ApiError(ErrorCode.ACCESS_DENIED, "Access denied", 403)
    
    p = await get_product(session, product_id)
    if not p:
        raise ApiError(ErrorCode.PRODUCT_NOT_FOUND, "Product not found", 404)
    if role == "SELLER" and (p.seller_id is None or str(p.seller_id) != user_id):
        raise ApiError(ErrorCode.ACCESS_DENIED, "Access denied", 403)

    p.name = data["name"]
    p.description = data.get("description")
    p.price = data["price"]
    p.stock = data["stock"]
    p.category = data["category"]
    p.status = ProductStatus(data["status"])
    await session.commit()
    await session.refresh(p)
    return p


async def archive_product(session: AsyncSession, role: str, user_id: str, product_id: str) -> None:
    p = await get_product(session, product_id)
    if not p:
        raise ApiError(ErrorCode.PRODUCT_NOT_FOUND, "Product not found", 404)
    if role not in ("SELLER","ADMIN"):
        raise ApiError(ErrorCode.ACCESS_DENIED, "Access denied", 403)
    if role == "SELLER" and (p.seller_id is None or str(p.seller_id) != user_id):
        raise ApiError(ErrorCode.ACCESS_DENIED, "Access denied", 403)
    p.status = ProductStatus.ARCHIVED
    await session.commit()
