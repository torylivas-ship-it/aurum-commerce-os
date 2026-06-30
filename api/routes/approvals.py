"""
Approval routes — the Human-in-the-Loop gate.
No product launches, ad spend, or price changes happen without approval.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.database.models import ApprovalRequest, ApprovalStatus, Product, ProductStatus
from core.events import event_bus, Events

router = APIRouter(prefix="/approvals")


class ApprovalResponse(BaseModel):
    id: UUID
    request_type: str
    title: str
    description: Optional[str]
    status: str
    data: Optional[dict]
    impact: Optional[str]
    confidence_score: Optional[float]
    risk_assessment: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ApprovalDecision(BaseModel):
    decision: str  # "approve" or "reject"
    reason: Optional[str] = None
    approved_by: str = "admin"


@router.get("", response_model=List[ApprovalResponse])
async def list_approvals(
    status: str = "pending",
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    try:
        status_enum = ApprovalStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    result = await db.execute(
        select(ApprovalRequest)
        .where(ApprovalRequest.status == status_enum)
        .order_by(desc(ApprovalRequest.created_at))
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(approval_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval


@router.post("/{approval_id}/decide")
async def decide_approval(
    approval_id: UUID,
    decision: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Approval is already {approval.status.value}"
        )

    now = datetime.now(timezone.utc)

    if decision.decision == "approve":
        approval.status = ApprovalStatus.APPROVED
        approval.approved_by = decision.approved_by
        approval.approved_at = now

        # Execute the approved action
        if approval.request_type == "product_launch" and approval.product_id:
            prod_result = await db.execute(
                select(Product).where(Product.id == approval.product_id)
            )
            product = prod_result.scalar_one_or_none()
            if product:
                product.status = ProductStatus.APPROVED

        await event_bus.publish(Events.APPROVAL_RECEIVED, {
            "approval_id": str(approval_id),
            "decision": "approve",
            "type": approval.request_type,
        })

    elif decision.decision == "reject":
        approval.status = ApprovalStatus.REJECTED
        approval.rejection_reason = decision.reason
        approval.approved_by = decision.approved_by
        approval.approved_at = now

        if approval.request_type == "product_launch" and approval.product_id:
            prod_result = await db.execute(
                select(Product).where(Product.id == approval.product_id)
            )
            product = prod_result.scalar_one_or_none()
            if product:
                product.status = ProductStatus.REJECTED
                product.rejection_reason = decision.reason
    else:
        raise HTTPException(
            status_code=400,
            detail="Decision must be 'approve' or 'reject'"
        )

    await db.commit()
    return {
        "id": str(approval.id),
        "status": approval.status.value,
        "decided_at": now.isoformat(),
    }
