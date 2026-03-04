"""init schema

Revision ID: 0001_init_schema
Revises: 
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_init_schema"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # enums
    op.execute("""
    DO $$
    BEGIN
        CREATE TYPE role_type AS ENUM ('USER','SELLER','ADMIN');
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END
    $$;
    """)
    op.execute("""
    DO $$
    BEGIN
        CREATE TYPE product_status AS ENUM ('ACTIVE','INACTIVE','ARCHIVED');
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END
    $$;
    """)
    op.execute("""
    DO $$
    BEGIN
        CREATE TYPE order_status AS ENUM ('CREATED','PAYMENT_PENDING','PAID','SHIPPED','COMPLETED','CANCELED');
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END
    $$;
    """)
    op.execute("""
    DO $$
    BEGIN
        CREATE TYPE discount_type AS ENUM ('PERCENTAGE','FIXED_AMOUNT');
    EXCEPTION
        WHEN duplicate_object THEN NULL;
    END
    $$;
    """)

    role_type_enum = postgresql.ENUM(name="role_type", create_type=False)
    product_status_enum = postgresql.ENUM(name="product_status", create_type=False)
    order_status_enum = postgresql.ENUM(name="order_status", create_type=False)
    discount_type_enum = postgresql.ENUM(name="discount_type", create_type=False)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", role_type_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=4000)),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("status", product_status_enum, nullable=False),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_products_status", "products", ["status"], unique=False)

    op.create_table(
        "promo_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=20), nullable=False, unique=True),
        sa.Column("discount_type", discount_type_enum, nullable=False),
        sa.Column("discount_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("min_order_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("current_uses", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("valid_from", sa.DateTime(), nullable=False),
        sa.Column("valid_until", sa.DateTime(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", order_status_enum, nullable=False),
        sa.Column("promo_code_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("promo_codes.id"), nullable=True),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price_at_order", sa.Numeric(12, 2), nullable=False),
    )

    op.create_table(
        "user_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("operation_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

def downgrade() -> None:
    op.drop_table("user_operations")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("promo_codes")
    op.drop_index("idx_products_status", table_name="products")
    op.drop_table("products")
    op.drop_table("users")

    op.execute("DROP TYPE discount_type")
    op.execute("DROP TYPE order_status")
    op.execute("DROP TYPE product_status")
    op.execute("DROP TYPE role_type")
