"""
Admin Panel Request Schemas
Pydantic models for admin API requests
"""

from typing import Optional

from pydantic import BaseModel, Field


class BroadcastRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=1000)
    type: str = Field(default="announcement", pattern="^(announcement|system_update)$")


class SetRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(admin|user)$")


class SetMembershipRequest(BaseModel):
    tier: str = Field(..., pattern="^(pro|free)$")
    months: int = Field(default=1, ge=1, le=12)


class SetStatusRequest(BaseModel):
    active: bool
    reason: Optional[str] = None


class PostVisibilityRequest(BaseModel):
    is_hidden: bool


class PostPinRequest(BaseModel):
    is_pinned: bool


class ResolveReportRequest(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$")
    violation_level: Optional[str] = Field(
        None, pattern="^(mild|medium|severe|critical)$"
    )


class UpdateConfigRequest(BaseModel):
    value: str
