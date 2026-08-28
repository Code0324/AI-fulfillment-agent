"""Authentication and user management service.

Adapted from Digital-FTE's auth/service.py and organizations/service.py patterns.
Handles user registration, login, organization creation, and membership.
"""

import uuid
import logging
from typing import Optional

from fastapi import HTTPException, status, Request
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    User, LoginRecord, Organization, OrganizationMember,
    MembershipRole, AuthProvider,
)
from app.auth.schemas import SignupRequest
from app.security import hash_password, verify_password

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------

async def create_local_user(db: AsyncSession, data: SignupRequest) -> User:
    """Register a new local user."""
    existing = await db.execute(
        select(User).where(or_(User.email == data.email, User.username == data.username))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered",
        )

    user = User(
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        auth_provider=AuthProvider.LOCAL,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_local_user(db: AsyncSession, email: str, password: str) -> User:
    """Authenticate a user by email and password."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    return user


async def log_login(db: AsyncSession, user: User, method: str, request: Request) -> None:
    """Record a login event for audit purposes."""
    log_entry = LoginRecord(
        user_id=user.id,
        method=method,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(log_entry)
    await db.commit()


# ---------------------------------------------------------------------------
# Organization operations
# ---------------------------------------------------------------------------

async def create_organization(
    db: AsyncSession,
    name: str,
    slug: str,
    owner_id: uuid.UUID,
    description: Optional[str] = None,
) -> Organization:
    """Create a new organization with the creator as OWNER."""
    org = Organization(name=name, slug=slug, description=description)
    db.add(org)
    await db.flush()

    member = OrganizationMember(
        organization_id=org.id,
        user_id=owner_id,
        role=MembershipRole.OWNER,
    )
    db.add(member)
    await db.commit()
    await db.refresh(org)
    return org


async def get_user_organizations(db: AsyncSession, user_id: uuid.UUID) -> list[Organization]:
    """Get all organizations a user belongs to."""
    result = await db.execute(
        select(Organization)
        .join(OrganizationMember)
        .where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.is_active == True,
            Organization.is_active == True,
        )
    )
    return list(result.scalars().all())


async def get_organization(db: AsyncSession, org_id: uuid.UUID) -> Optional[Organization]:
    """Get an organization by ID."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    return result.scalar_one_or_none()


async def get_member_permissions(
    db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID
) -> list[str]:
    """Get the effective permissions for a user in an organization."""
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.is_active == True,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        return []
    return member.get_permissions()


async def user_has_permission(
    db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID, permission: str
) -> bool:
    """Check if a user has a specific permission in an organization."""
    permissions = await get_member_permissions(db, user_id, org_id)
    return permission in permissions
