"""Organization management API routes.

Provides endpoints for creating, listing, and joining organizations.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.auth.schemas import CreateOrganizationRequest, OrganizationOut
from app.auth import service

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: CreateOrganizationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new organization. The creating user becomes the OWNER."""
    org = await service.create_organization(
        db, name=payload.name, slug=payload.slug,
        owner_id=user.id, description=payload.description,
    )
    return OrganizationOut.model_validate(org)


@router.get("", response_model=list[OrganizationOut])
async def list_my_organizations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all organizations the current user belongs to."""
    orgs = await service.get_user_organizations(db, user.id)
    return [OrganizationOut.model_validate(o) for o in orgs]
