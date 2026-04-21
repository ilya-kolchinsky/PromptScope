"""
ACL evaluation logic.
"""

from datetime import datetime
from typing import Optional
from .models import PermissionType
from .store import PermissionStore, UserStore


class ACLEvaluator:
    """
    Central authorization service with extensible permission evaluation.

    This class provides the core logic for determining whether a subject
    has a specific permission on an object.
    """

    def __init__(self, permission_store: PermissionStore, user_store: UserStore):
        self.permission_store = permission_store
        self.user_store = user_store

    def has_permission(
        self,
        subject: str,
        object: str,
        permission_type: PermissionType,
        context: Optional[dict] = None,
    ) -> bool:
        """
        Check if subject has permission_type on object.

        This is the main entry point - permission-type agnostic.

        Args:
            subject: User ID or group ID that might have the permission
            object: Target user/resource ID
            permission_type: Type of permission to check
            context: Optional context for permission evaluation

        Returns:
            True if permission is granted, False otherwise
        """
        # Self-permissions (configurable per permission type)
        if subject == object and self._allow_self_permission(permission_type):
            return True

        # Check direct grants
        if self._has_direct_grant(subject, object, permission_type):
            return True

        # Check group-based grants
        if self._has_group_grant(subject, object, permission_type):
            return True

        return False

    def can_influence(self, subject: str, object: str, context: Optional[dict] = None) -> bool:
        """
        Check INFLUENCE permission specifically.

        This is a convenience method for the most common permission check.

        Args:
            subject: User ID who might have influence
            object: Target user ID who might be influenced
            context: Optional context

        Returns:
            True if subject can influence object
        """
        return self.has_permission(subject, object, PermissionType.INFLUENCE, context)

    def _has_direct_grant(self, subject: str, object: str, perm_type: PermissionType) -> bool:
        """Check for direct permission grants."""
        grants = self.permission_store.get_grants(
            subject=subject,
            object=object,
            permission_type=perm_type,
        )

        # Check if any non-expired grant exists
        now = datetime.utcnow()
        for grant in grants:
            if grant.expires_at is None or grant.expires_at > now:
                return True

        return False

    def _has_group_grant(self, subject: str, object: str, perm_type: PermissionType) -> bool:
        """Check for group-based permission grants."""
        # Get groups for subject and object
        subject_groups = self.user_store.get_user_groups(subject)
        object_groups = self.user_store.get_user_groups(object)

        # Check if any subject group has permission on any object group
        for sg in subject_groups:
            for og in object_groups:
                if self._has_direct_grant(sg, og, perm_type):
                    return True

        # Also check if subject's groups have permission on the object directly
        for sg in subject_groups:
            if self._has_direct_grant(sg, object, perm_type):
                return True

        return False

    def _allow_self_permission(self, perm_type: PermissionType) -> bool:
        """Determine if self-permission is allowed for this type."""
        # Configuration: which permissions are self-granted by default
        self_allowed = {
            PermissionType.INFLUENCE,  # You can always influence yourself
        }
        return perm_type in self_allowed

    def get_influence_set(self, principal: str) -> set[str]:
        """
        Get all users/groups that can influence this principal.

        Useful for debugging and displaying influence relationships.

        Args:
            principal: User ID to check

        Returns:
            Set of user IDs that can influence this principal
        """
        influencers = {principal}  # Principal always influences themselves

        # Check all users
        for user in self.user_store.get_all_users():
            if user.id != principal and self.can_influence(user.id, principal):
                influencers.add(user.id)

        # Check all groups
        for group in self.user_store.get_all_groups():
            if self.can_influence(group.id, principal):
                # Add all members of the group
                for member_id in group.members:
                    influencers.add(member_id)

        return influencers
