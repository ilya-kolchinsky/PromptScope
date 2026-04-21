"""
Data models for the ACL system.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class PermissionType(str, Enum):
    """
    Registry of all supported permission types.

    This enum is extensible - new permission types can be added as needed.
    """

    INFLUENCE = "INFLUENCE"  # Messages appear in effective control context

    # Future permissions (examples):
    # PRIORITY = "PRIORITY"     # Influence message ordering/ranking
    # MODERATE = "MODERATE"     # Can filter/block messages
    # DELEGATE = "DELEGATE"     # Can grant permissions on behalf of target
    # OVERRIDE = "OVERRIDE"     # Can bypass other ACL rules
    # AUDIT = "AUDIT"           # Can view permission evaluation logs


class User(BaseModel):
    """A user in the system."""

    id: str = Field(description="Unique user identifier")
    username: str = Field(description="Display name")
    groups: list[str] = Field(default_factory=list, description="Group IDs this user belongs to")
    manager_id: Optional[str] = Field(default=None, description="Manager's user ID (for hierarchy)")
    metadata: dict = Field(default_factory=dict, description="Extensible metadata")


class Group(BaseModel):
    """A group of users."""

    id: str = Field(description="Unique group identifier")
    name: str = Field(description="Display name")
    parent_groups: list[str] = Field(default_factory=list, description="Parent group IDs (for nested groups)")
    members: list[str] = Field(default_factory=list, description="User IDs in this group")
    metadata: dict = Field(default_factory=dict, description="Extensible metadata")


class PermissionGrant(BaseModel):
    """A single permission grant."""

    id: str = Field(description="Unique grant identifier")
    permission_type: PermissionType = Field(description="Type of permission being granted")
    subject: str = Field(description="User ID or group ID that has the permission")
    object: str = Field(description="Target user/resource ID that the permission applies to")
    scope: Optional[dict] = Field(default=None, description="Permission-specific constraints")
    granted_by: str = Field(description="User ID of who granted this permission")
    granted_at: datetime = Field(default_factory=datetime.utcnow, description="When permission was granted")
    expires_at: Optional[datetime] = Field(default=None, description="Optional expiration time")
    metadata: Optional[dict] = Field(default=None, description="Extensible metadata")
