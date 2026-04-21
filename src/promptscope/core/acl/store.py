"""
Storage interfaces and implementations for ACL data.
"""

from abc import ABC, abstractmethod
from typing import Optional
from .models import PermissionGrant, PermissionType, User, Group


class PermissionStore(ABC):
    """Abstract interface for permission storage."""

    @abstractmethod
    def grant_permission(self, grant: PermissionGrant) -> PermissionGrant:
        """Store a permission grant."""
        pass

    @abstractmethod
    def revoke_permission(self, grant_id: str) -> bool:
        """Revoke a permission grant."""
        pass

    @abstractmethod
    def get_grants(
        self,
        subject: Optional[str] = None,
        object: Optional[str] = None,
        permission_type: Optional[PermissionType] = None,
    ) -> list[PermissionGrant]:
        """Query permission grants."""
        pass

    @abstractmethod
    def get_grant_by_id(self, grant_id: str) -> Optional[PermissionGrant]:
        """Get a specific grant by ID."""
        pass


class InMemoryPermissionStore(PermissionStore):
    """In-memory implementation for development."""

    def __init__(self):
        self._grants: dict[str, PermissionGrant] = {}

    def grant_permission(self, grant: PermissionGrant) -> PermissionGrant:
        self._grants[grant.id] = grant
        return grant

    def revoke_permission(self, grant_id: str) -> bool:
        if grant_id in self._grants:
            del self._grants[grant_id]
            return True
        return False

    def get_grants(
        self,
        subject: Optional[str] = None,
        object: Optional[str] = None,
        permission_type: Optional[PermissionType] = None,
    ) -> list[PermissionGrant]:
        grants = list(self._grants.values())

        if subject:
            grants = [g for g in grants if g.subject == subject]
        if object:
            grants = [g for g in grants if g.object == object]
        if permission_type:
            grants = [g for g in grants if g.permission_type == permission_type]

        return grants

    def get_grant_by_id(self, grant_id: str) -> Optional[PermissionGrant]:
        return self._grants.get(grant_id)


class UserStore(ABC):
    """Abstract interface for user and group storage."""

    @abstractmethod
    def create_user(self, user: User) -> User:
        """Create a new user."""
        pass

    @abstractmethod
    def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        pass

    @abstractmethod
    def update_user(self, user: User) -> User:
        """Update a user."""
        pass

    @abstractmethod
    def get_all_users(self) -> list[User]:
        """Get all users."""
        pass

    @abstractmethod
    def create_group(self, group: Group) -> Group:
        """Create a new group."""
        pass

    @abstractmethod
    def get_group(self, group_id: str) -> Optional[Group]:
        """Get a group by ID."""
        pass

    @abstractmethod
    def update_group(self, group: Group) -> Group:
        """Update a group."""
        pass

    @abstractmethod
    def get_all_groups(self) -> list[Group]:
        """Get all groups."""
        pass

    @abstractmethod
    def get_user_groups(self, user_id: str) -> list[str]:
        """Get all group IDs a user belongs to (including transitive)."""
        pass

    @abstractmethod
    def add_user_to_group(self, user_id: str, group_id: str) -> bool:
        """Add a user to a group."""
        pass

    @abstractmethod
    def remove_user_from_group(self, user_id: str, group_id: str) -> bool:
        """Remove a user from a group."""
        pass


class InMemoryUserStore(UserStore):
    """In-memory implementation for development."""

    def __init__(self):
        self._users: dict[str, User] = {}
        self._groups: dict[str, Group] = {}

    def create_user(self, user: User) -> User:
        self._users[user.id] = user
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def update_user(self, user: User) -> User:
        self._users[user.id] = user
        return user

    def get_all_users(self) -> list[User]:
        return list(self._users.values())

    def create_group(self, group: Group) -> Group:
        self._groups[group.id] = group
        return group

    def get_group(self, group_id: str) -> Optional[Group]:
        return self._groups.get(group_id)

    def update_group(self, group: Group) -> Group:
        self._groups[group.id] = group
        return group

    def get_all_groups(self) -> list[Group]:
        return list(self._groups.values())

    def get_user_groups(self, user_id: str) -> list[str]:
        """Get all group IDs a user belongs to (direct membership only for now)."""
        user = self.get_user(user_id)
        if not user:
            return []
        return user.groups

    def add_user_to_group(self, user_id: str, group_id: str) -> bool:
        """Add a user to a group."""
        user = self.get_user(user_id)
        group = self.get_group(group_id)

        if not user or not group:
            return False

        # Add to user's groups list
        if group_id not in user.groups:
            user.groups.append(group_id)
            self.update_user(user)

        # Add to group's members list
        if user_id not in group.members:
            group.members.append(user_id)
            self.update_group(group)

        return True

    def remove_user_from_group(self, user_id: str, group_id: str) -> bool:
        """Remove a user from a group."""
        user = self.get_user(user_id)
        group = self.get_group(group_id)

        if not user or not group:
            return False

        # Remove from user's groups list
        if group_id in user.groups:
            user.groups.remove(group_id)
            self.update_user(user)

        # Remove from group's members list
        if user_id in group.members:
            group.members.remove(user_id)
            self.update_group(group)

        return True
