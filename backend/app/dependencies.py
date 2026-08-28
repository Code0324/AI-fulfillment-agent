"""FastAPI dependencies for authentication and tenant resolution.

Adapted from Digital-FTE's dependencies.py and organizations/dependencies.py patterns.
Provides:
- get_current_user: JWT token validation + user lookup
- get_current_organization: tenant resolution from user membership
- require_permission: RBAC permission checking
"""

import uuid
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, Organization, OrganizationMember
from app.security import decode_access_token

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Protect any route that requires a logged-in user.

    Raises 401 if the token is invalid or the user is inactive.
    """
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


async def get_current_organization(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """Resolve the current user's primary organization (tenant).

    Raises 404 if the user is not a member of any organization.
    """
    result = await db.execute(
        select(Organization)
        .join(OrganizationMember)
        .where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.is_active == True,
            Organization.is_active == True,
        )
        .order_by(OrganizationMember.created_at)
    )
    org = result.scalars().first()

    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of any organization. Create or join one first.",
        )

    return org


def require_permission(required_permission: str):
    """Dependency factory that checks a specific permission.

    Usage:
        @router.get("/orders", dependencies=[Depends(require_permission("orders:read"))])
        async def list_orders(...): ...
    """
    async def _check_permission(
        org: Organization = Depends(get_current_organization),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> bool:
        result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.user_id == user.id,
                OrganizationMember.is_active == True,
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this organization",
            )
        permissions = member.get_permissions()
        if required_permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {required_permission}",
            )
        return True

    return _check_permission
