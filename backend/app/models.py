"""SQLAlchemy ORM models for the Amazon AI Fulfillment Assistant.

Multi-tenant architecture:
- User: individual accounts
- Organization: top-level tenant (client's business)
- OrganizationMember: user↔org mapping with roles
- AmazonAccount: per-tenant Amazon SP-API connection
- FulfillmentOrder: orders scoped to an organization
- InventoryItem: inventory scoped to an organization
- FulfillmentWorkflow: workflows scoped to an organization

Adapted from Digital-FTE's models.py and organizations/models.py patterns.
"""

import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    String, Boolean, DateTime, ForeignKey, Enum, func, Text,
    Integer, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AuthProvider(str, enum.Enum):
    LOCAL = "local"
    GOOGLE = "google"


class MembershipRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Permission(str, enum.Enum):
    # Orders
    ORDERS_READ = "orders:read"
    ORDERS_WRITE = "orders:write"
    ORDERS_CANCEL = "orders:cancel"

    # Inventory
    INVENTORY_READ = "inventory:read"
    INVENTORY_WRITE = "inventory:write"
    INVENTORY_ADJUST = "inventory:adjust"

    # Fulfillment
    FULFILLMENT_READ = "fulfillment:read"
    FULFILLMENT_EXECUTE = "fulfillment:execute"
    FULFILLMENT_APPROVE = "fulfillment:approve"

    # Amazon
    AMAZON_CONNECT = "amazon:connect"
    AMAZON_READ = "amazon:read"
    AMAZON_SYNC = "amazon:sync"

    # Automation
    AUTOMATION_MANAGE = "automation:manage"
    AUTOMATION_EXECUTE = "automation:execute"
    AUTOMATION_APPROVE = "automation:approve"

    # Settings
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"

    # Admin
    ADMIN_USERS = "admin:users"
    ADMIN_ORG = "admin:org"


DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    MembershipRole.OWNER.value: [p.value for p in Permission],
    MembershipRole.ADMIN.value: [
        Permission.ORDERS_READ.value, Permission.ORDERS_WRITE.value, Permission.ORDERS_CANCEL.value,
        Permission.INVENTORY_READ.value, Permission.INVENTORY_WRITE.value, Permission.INVENTORY_ADJUST.value,
        Permission.FULFILLMENT_READ.value, Permission.FULFILLMENT_EXECUTE.value, Permission.FULFILLMENT_APPROVE.value,
        Permission.AMAZON_CONNECT.value, Permission.AMAZON_READ.value, Permission.AMAZON_SYNC.value,
        Permission.AUTOMATION_MANAGE.value, Permission.AUTOMATION_EXECUTE.value, Permission.AUTOMATION_APPROVE.value,
        Permission.SETTINGS_READ.value, Permission.SETTINGS_WRITE.value,
        Permission.ADMIN_USERS.value,
    ],
    MembershipRole.MANAGER.value: [
        Permission.ORDERS_READ.value, Permission.ORDERS_WRITE.value,
        Permission.INVENTORY_READ.value, Permission.INVENTORY_WRITE.value, Permission.INVENTORY_ADJUST.value,
        Permission.FULFILLMENT_READ.value, Permission.FULFILLMENT_EXECUTE.value, Permission.FULFILLMENT_APPROVE.value,
        Permission.AMAZON_READ.value, Permission.AMAZON_SYNC.value,
        Permission.AUTOMATION_MANAGE.value, Permission.AUTOMATION_EXECUTE.value, Permission.AUTOMATION_APPROVE.value,
        Permission.SETTINGS_READ.value,
    ],
    MembershipRole.OPERATOR.value: [
        Permission.ORDERS_READ.value, Permission.ORDERS_WRITE.value,
        Permission.INVENTORY_READ.value, Permission.INVENTORY_WRITE.value,
        Permission.FULFILLMENT_READ.value, Permission.FULFILLMENT_EXECUTE.value,
        Permission.AMAZON_READ.value,
        Permission.AUTOMATION_EXECUTE.value,
    ],
    MembershipRole.VIEWER.value: [
        Permission.ORDERS_READ.value,
        Permission.INVENTORY_READ.value,
        Permission.FULFILLMENT_READ.value,
        Permission.AMAZON_READ.value,
        Permission.SETTINGS_READ.value,
    ],
}


def get_default_permissions(role: MembershipRole) -> list[str]:
    return DEFAULT_ROLE_PERMISSIONS.get(role.value, [])


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    """Individual user account."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    auth_provider: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider, name="auth_provider_enum"), default=AuthProvider.LOCAL, nullable=False
    )
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    memberships: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    login_records: Mapped[list["LoginRecord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class LoginRecord(Base):
    """Audit trail for login events."""
    __tablename__ = "login_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    method: Mapped[str] = mapped_column(String(20), nullable=False)  # local, google
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logged_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="login_records")


# ---------------------------------------------------------------------------
# Organization (Tenant)
# ---------------------------------------------------------------------------

class Organization(Base):
    """Top-level tenant. Everything is scoped to an organization."""
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Subscription
    subscription_plan: Mapped[str] = mapped_column(String(50), default="free", nullable=False)
    subscription_status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    members: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    amazon_accounts: Mapped[list["AmazonAccount"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    orders: Mapped[list["FulfillmentOrder"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    inventory_items: Mapped[list["InventoryItem"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    fulfillment_workflows: Mapped[list["FulfillmentWorkflow"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class OrganizationMember(Base):
    """Maps a user to an organization with a specific role."""
    __tablename__ = "organization_members"

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    role: Mapped[MembershipRole] = mapped_column(
        Enum(MembershipRole, name="membership_role_enum"), default=MembershipRole.VIEWER, nullable=False
    )
    custom_permissions: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")

    def get_permissions(self) -> list[str]:
        if self.custom_permissions:
            return self.custom_permissions
        return get_default_permissions(self.role)


# ---------------------------------------------------------------------------
# Amazon Account (per-tenant connection)
# ---------------------------------------------------------------------------

class AmazonAccount(Base):
    """Per-tenant Amazon SP-API connection.

    Stores encrypted credentials for each organization's Amazon seller account.
    Supports multiple marketplace connections per organization.
    """
    __tablename__ = "amazon_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Amazon seller identification
    seller_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    marketplace_id: Mapped[str] = mapped_column(String(50), nullable=False, default="ATVPDKIKX0DER")
    marketplace_name: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g. "US", "UK"
    region: Mapped[str] = mapped_column(String(10), nullable=False, default="na")

    # LWA credentials (encrypted at rest in production)
    lwa_client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    lwa_client_secret: Mapped[str] = mapped_column(String(512), nullable=False)
    lwa_refresh_token: Mapped[str] = mapped_column(String(512), nullable=False)

    # Connection state
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active, disconnected, error
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Metadata
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="amazon_accounts")


# ---------------------------------------------------------------------------
# Fulfillment Order (per-tenant)
# ---------------------------------------------------------------------------

class FulfillmentOrder(Base):
    """A fulfillment order scoped to an organization."""
    __tablename__ = "fulfillment_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amazon_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("amazon_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Amazon order reference
    amazon_order_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20), default="MANUAL", nullable=False)  # MANUAL, AMAZON, MOCK_AMAZON

    # Order details
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    shipping_address: Mapped[str] = mapped_column(Text, nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    inventory_reserved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="orders")
    workflows: Mapped[list["FulfillmentWorkflow"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Inventory Item (per-tenant)
# ---------------------------------------------------------------------------

class InventoryItem(Base):
    """An inventory item scoped to an organization."""
    __tablename__ = "inventory_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    sku: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    current_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="inventory_items")

    __table_args__ = (
        UniqueConstraint("organization_id", "sku", name="uq_org_sku"),
    )


# ---------------------------------------------------------------------------
# Fulfillment Workflow (per-tenant)
# ---------------------------------------------------------------------------

class FulfillmentWorkflow(Base):
    """A fulfillment workflow scoped to an organization."""
    __tablename__ = "fulfillment_workflows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fulfillment_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    steps_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # serialized workflow steps
    confirmation_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="fulfillment_workflows")
    order: Mapped["FulfillmentOrder"] = relationship(back_populates="workflows")
