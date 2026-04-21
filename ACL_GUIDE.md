# PromptScope ACL (Access Control List) Guide

This guide explains how to configure and manage hierarchical permissions in PromptScope.

## Table of Contents

- [Overview](#overview)
- [Core Concepts](#core-concepts)
- [Permission Types](#permission-types)
- [Managing Users and Groups](#managing-users-and-groups)
- [API Reference](#api-reference)
- [Usage Examples](#usage-examples)
- [Extending the System](#extending-the-system)

## Overview

The ACL system in PromptScope provides **hierarchical access control** for multi-user LLM interactions. It allows you to define which users' messages can influence other users' LLM responses, enabling organizational structures like:

- **Admins** setting policies that affect all users
- **Managers** influencing their team members
- **Security teams** injecting compliance guidelines
- **Team leads** providing context to their teams

**Key Design Principle**: In a shared conversation, all messages are visible to all participants (that's the platform's job). PromptScope's ACL controls **which visible messages automatically influence the LLM's responses** vs. which ones require explicit retrieval via tools.

## Core Concepts

### Users

A **User** represents a principal in the system. Each user has:

- `id`: Unique identifier (e.g., "alice@company.com")
- `username`: Display name (e.g., "Alice")
- `groups`: List of group IDs the user belongs to
- `manager_id`: Optional reference to their manager (for hierarchical policies)
- `metadata`: Extensible metadata dictionary

### Groups

A **Group** is a collection of users. Groups are used to grant permissions to multiple users at once:

- `id`: Unique identifier (e.g., "admins", "engineering")
- `name`: Display name (e.g., "Administrators")
- `members`: List of user IDs in this group
- `parent_groups`: Optional list of parent group IDs (for nested groups)
- `metadata`: Extensible metadata dictionary

### Permission Grants

A **PermissionGrant** links a subject (user/group) to an object (user/resource) with a specific permission type:

- `id`: Unique grant identifier
- `permission_type`: Type of permission (e.g., INFLUENCE)
- `subject`: User ID or group ID that has the permission
- `object`: Target user/resource ID
- `granted_by`: User ID who granted this permission
- `granted_at`: Timestamp
- `expires_at`: Optional expiration time
- `scope`: Optional constraints (topic-based, time-based, etc.)
- `metadata`: Extensible metadata

### Projection with ACL

When building a projection for a principal, the system determines which messages go into which context:

```
For Principal P viewing Message M:

IF M.author == P:
    → Effective Control Context (always)

ELSE IF M.author has INFLUENCE permission on P:
    → Effective Control Context (hierarchical influence)

ELSE:
    → Visible Observation Context (retrievable via tools only)
```

## Permission Types

The system uses an **extensible permission registry**. Currently implemented:

### INFLUENCE

**Purpose**: Allows a user's/group's messages to appear in another user's effective control context.

**Effect**: When Alice has INFLUENCE permission on Bob:
- Alice's messages appear in Bob's effective control context
- Bob's LLM responses are automatically affected by Alice's instructions
- This works even in Protected Mode

**Use Cases**:
- Managers influencing their direct reports
- Admin groups setting global policies
- Security teams injecting compliance rules
- Team leads providing team-wide context

**Self-Permission**: ✅ Users always have INFLUENCE permission on themselves

### Future Permission Types

The architecture supports adding new permissions easily:

```python
class PermissionType(str, Enum):
    INFLUENCE = "INFLUENCE"     # Current
    
    # Potential future additions:
    # PRIORITY = "PRIORITY"     # Control message ranking/ordering
    # MODERATE = "MODERATE"     # Filter/block messages
    # DELEGATE = "DELEGATE"     # Grant permissions on behalf of target
    # AUDIT = "AUDIT"           # View permission logs
```

See [Extending the System](#extending-the-system) for details.

## Managing Users and Groups

### Via Web UI

The web interface includes an **Admin Group Management** panel:

1. **View current state**: See all users and their admin status
2. **Promote to Admin**: Click "Promote to Admin" to add user to admins group
3. **Demote from Admin**: Click "Demote" to remove user from admins group
4. **Visual feedback**: Admins are highlighted with green background and badge

### Via API

#### List Users

```bash
curl http://localhost:8000/api/acl/users
```

Response:
```json
{
  "users": [
    {
      "id": "Alice",
      "username": "Alice",
      "groups": ["admins"],
      "manager_id": null
    }
  ]
}
```

#### List Groups

```bash
curl http://localhost:8000/api/acl/groups
```

Response:
```json
{
  "groups": [
    {
      "id": "admins",
      "name": "Admins",
      "members": ["Alice"]
    }
  ]
}
```

#### Add User to Group

```bash
curl -X POST http://localhost:8000/api/acl/groups/admins/members/Alice
```

Response:
```json
{
  "status": "success",
  "user_id": "Alice",
  "group_id": "admins",
  "action": "added"
}
```

#### Remove User from Group

```bash
curl -X DELETE http://localhost:8000/api/acl/groups/admins/members/Alice
```

Response:
```json
{
  "status": "success",
  "user_id": "Alice",
  "group_id": "admins",
  "action": "removed"
}
```

#### Check Influence Set

Get all users who can influence a specific principal:

```bash
curl http://localhost:8000/api/acl/influence/Bob
```

Response:
```json
{
  "principal": "Bob",
  "influencers": ["Bob", "Alice"]
}
```

### Via Python Code

#### Creating Users and Groups

```python
from promptscope.core.acl import User, Group, InMemoryUserStore

# Initialize store
user_store = InMemoryUserStore()

# Create users
alice = user_store.create_user(User(
    id="alice@company.com",
    username="Alice",
    groups=[],
))

bob = user_store.create_user(User(
    id="bob@company.com",
    username="Bob",
    groups=[],
))

# Create group
admins = user_store.create_group(Group(
    id="admins",
    name="Administrators",
    members=[],
))

# Add user to group
user_store.add_user_to_group("alice@company.com", "admins")
```

#### Granting Permissions

```python
from promptscope.core.acl import PermissionGrant, PermissionType
from promptscope.core.acl import InMemoryPermissionStore
from datetime import datetime, timedelta

# Initialize store
permission_store = InMemoryPermissionStore()

# Grant INFLUENCE permission: admins group can influence Bob
grant = permission_store.grant_permission(PermissionGrant(
    id="admin-influence-bob",
    permission_type=PermissionType.INFLUENCE,
    subject="admins",           # The admins group
    object="bob@company.com",   # Can influence Bob
    granted_by="system",
    granted_at=datetime.utcnow(),
))

# Grant with expiration (temporary influence)
temp_grant = permission_store.grant_permission(PermissionGrant(
    id="temp-influence",
    permission_type=PermissionType.INFLUENCE,
    subject="alice@company.com",
    object="charlie@company.com",
    granted_by="admin@company.com",
    granted_at=datetime.utcnow(),
    expires_at=datetime.utcnow() + timedelta(hours=2),  # Expires in 2 hours
))
```

#### Checking Permissions

```python
from promptscope.core.acl import ACLEvaluator

# Initialize evaluator
acl_evaluator = ACLEvaluator(permission_store, user_store)

# Check if Alice can influence Bob
can_influence = acl_evaluator.can_influence("alice@company.com", "bob@company.com")
print(f"Alice can influence Bob: {can_influence}")

# Get all users who can influence Bob
influencers = acl_evaluator.get_influence_set("bob@company.com")
print(f"Users who can influence Bob: {influencers}")
```

## API Reference

### Endpoints

#### `GET /api/acl/users`

Get all users in the system.

**Response:**
```json
{
  "users": [
    {
      "id": "alice",
      "username": "Alice",
      "groups": ["admins"],
      "manager_id": null
    }
  ]
}
```

#### `GET /api/acl/groups`

Get all groups in the system.

**Response:**
```json
{
  "groups": [
    {
      "id": "admins",
      "name": "Admins",
      "members": ["alice"]
    }
  ]
}
```

#### `POST /api/acl/groups/{group_id}/members/{user_id}`

Add a user to a group.

**Parameters:**
- `group_id`: Group identifier (path)
- `user_id`: User identifier (path)

**Response:**
```json
{
  "status": "success",
  "user_id": "alice",
  "group_id": "admins",
  "action": "added"
}
```

**Error Codes:**
- `404`: User or group not found

#### `DELETE /api/acl/groups/{group_id}/members/{user_id}`

Remove a user from a group.

**Parameters:**
- `group_id`: Group identifier (path)
- `user_id`: User identifier (path)

**Response:**
```json
{
  "status": "success",
  "user_id": "alice",
  "group_id": "admins",
  "action": "removed"
}
```

**Error Codes:**
- `404`: User or group not found

#### `GET /api/acl/influence/{principal}`

Get all users who can influence a specific principal.

**Parameters:**
- `principal`: User identifier (path)

**Response:**
```json
{
  "principal": "bob",
  "influencers": ["bob", "alice"]
}
```

### Python API

#### ACLEvaluator

Main authorization service.

```python
class ACLEvaluator:
    def has_permission(
        self,
        subject: str,
        object: str,
        permission_type: PermissionType,
        context: Optional[dict] = None,
    ) -> bool:
        """Check if subject has permission_type on object."""
        
    def can_influence(
        self, 
        subject: str, 
        object: str, 
        context: Optional[dict] = None
    ) -> bool:
        """Convenience method for checking INFLUENCE permission."""
        
    def get_influence_set(self, principal: str) -> set[str]:
        """Get all users who can influence this principal."""
```

#### UserStore

Manages users and groups.

```python
class UserStore:
    def create_user(self, user: User) -> User: ...
    def get_user(self, user_id: str) -> Optional[User]: ...
    def update_user(self, user: User) -> User: ...
    def get_all_users(self) -> list[User]: ...
    
    def create_group(self, group: Group) -> Group: ...
    def get_group(self, group_id: str) -> Optional[Group]: ...
    def update_group(self, group: Group) -> Group: ...
    def get_all_groups(self) -> list[Group]: ...
    
    def add_user_to_group(self, user_id: str, group_id: str) -> bool: ...
    def remove_user_from_group(self, user_id: str, group_id: str) -> bool: ...
```

#### PermissionStore

Manages permission grants.

```python
class PermissionStore:
    def grant_permission(self, grant: PermissionGrant) -> PermissionGrant: ...
    def revoke_permission(self, grant_id: str) -> bool: ...
    def get_grants(
        self,
        subject: Optional[str] = None,
        object: Optional[str] = None,
        permission_type: Optional[PermissionType] = None,
    ) -> list[PermissionGrant]: ...
```

## Usage Examples

### Example 1: Admin Group Influences All Users

**Scenario**: Create an "admins" group whose members can influence all users.

```python
# Create users
user_store.create_user(User(id="alice", username="Alice"))
user_store.create_user(User(id="bob", username="Bob"))
user_store.create_user(User(id="charlie", username="Charlie"))

# Create admins group
user_store.create_group(Group(id="admins", name="Administrators"))

# Grant permission: admins can influence everyone
for user_id in ["alice", "bob", "charlie"]:
    permission_store.grant_permission(PermissionGrant(
        id=f"admin-influence-{user_id}",
        permission_type=PermissionType.INFLUENCE,
        subject="admins",  # The group
        object=user_id,    # Each user
        granted_by="system",
        granted_at=datetime.utcnow(),
    ))

# Add Alice to admins
user_store.add_user_to_group("alice", "admins")

# Now Alice can influence Bob and Charlie
# Alice's messages appear in their effective control context
```

### Example 2: Manager-Team Hierarchy

**Scenario**: Managers can influence their direct reports.

```python
# Create users with manager relationships
alice = user_store.create_user(User(
    id="alice",
    username="Alice (Manager)",
    manager_id=None,
))

bob = user_store.create_user(User(
    id="bob",
    username="Bob",
    manager_id="alice",  # Alice is Bob's manager
))

charlie = user_store.create_user(User(
    id="charlie",
    username="Charlie",
    manager_id="alice",  # Alice is Charlie's manager
))

# Grant permission: Alice can influence her reports
permission_store.grant_permission(PermissionGrant(
    id="alice-influence-bob",
    permission_type=PermissionType.INFLUENCE,
    subject="alice",
    object="bob",
    granted_by="hr-system",
    granted_at=datetime.utcnow(),
))

permission_store.grant_permission(PermissionGrant(
    id="alice-influence-charlie",
    permission_type=PermissionType.INFLUENCE,
    subject="alice",
    object="charlie",
    granted_by="hr-system",
    granted_at=datetime.utcnow(),
))
```

### Example 3: Temporary Security Override

**Scenario**: During a security incident, allow security team to influence all users for 2 hours.

```python
# Create security group
user_store.create_group(Group(id="security", name="Security Team"))
user_store.add_user_to_group("security-alice", "security")

# Grant temporary influence
all_users = user_store.get_all_users()
expiration = datetime.utcnow() + timedelta(hours=2)

for user in all_users:
    permission_store.grant_permission(PermissionGrant(
        id=f"security-emergency-{user.id}",
        permission_type=PermissionType.INFLUENCE,
        subject="security",
        object=user.id,
        granted_by="security-lead",
        granted_at=datetime.utcnow(),
        expires_at=expiration,  # Auto-expires in 2 hours
        metadata={"reason": "security-incident-2024-001"},
    ))
```

### Example 4: Topic-Scoped Permissions (Future)

**Scenario**: Alice can influence Bob only on "deployment" topics.

```python
# This demonstrates future capability with scope constraints
permission_store.grant_permission(PermissionGrant(
    id="alice-deploy-influence",
    permission_type=PermissionType.INFLUENCE,
    subject="alice",
    object="bob",
    granted_by="admin",
    granted_at=datetime.utcnow(),
    scope={
        "topics": ["deployment", "infrastructure"],
        "exclude_topics": ["hr", "personal"],
    },
))

# Evaluator would check scope when evaluating permissions
# (Requires custom evaluator implementation)
```

## Extending the System

### Adding New Permission Types

1. **Define the permission** in `src/promptscope/core/acl/models.py`:

```python
class PermissionType(str, Enum):
    INFLUENCE = "INFLUENCE"
    MODERATE = "MODERATE"  # New permission
```

2. **Update self-permission logic** in `src/promptscope/core/acl/evaluator.py`:

```python
def _allow_self_permission(self, perm_type: PermissionType) -> bool:
    self_allowed = {
        PermissionType.INFLUENCE,
        PermissionType.MODERATE,  # Add here if self-permission allowed
    }
    return perm_type in self_allowed
```

3. **Add convenience method** (optional):

```python
def can_moderate(self, subject: str, object: str) -> bool:
    """Check MODERATE permission specifically."""
    return self.has_permission(subject, object, PermissionType.MODERATE)
```

4. **Use in application logic**:

```python
if acl_evaluator.can_moderate(current_user, target_message):
    # Allow message moderation
    pass
```

### Creating Custom Evaluators

For complex permission logic (e.g., policy-based, ML-based), implement a custom evaluator:

```python
from promptscope.core.acl.evaluator import PermissionEvaluator

class PolicyBasedEvaluator(PermissionEvaluator):
    """Custom evaluator using policy rules."""
    
    def __init__(self, user_store, policy_engine):
        self.user_store = user_store
        self.policy_engine = policy_engine
    
    def evaluate(self, subject: str, object: str, context: dict) -> bool:
        # Load user context
        subject_user = self.user_store.get_user(subject)
        object_user = self.user_store.get_user(object)
        
        # Evaluate custom policies
        return self.policy_engine.evaluate(
            subject=subject_user,
            object=object_user,
            context=context,
        )

# Register custom evaluator
acl_evaluator.register_evaluator(
    PermissionType.INFLUENCE,
    PolicyBasedEvaluator(user_store, policy_engine)
)
```

### Persistent Storage

The current implementation uses in-memory stores. For production, implement persistent storage:

```python
from promptscope.core.acl.store import UserStore, PermissionStore

class DatabaseUserStore(UserStore):
    """PostgreSQL-backed user store."""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def create_user(self, user: User) -> User:
        # INSERT INTO users ...
        pass
    
    # Implement other methods...

class DatabasePermissionStore(PermissionStore):
    """PostgreSQL-backed permission store."""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def grant_permission(self, grant: PermissionGrant) -> PermissionGrant:
        # INSERT INTO permission_grants ...
        pass
    
    # Implement other methods...
```

Then initialize with database-backed stores:

```python
db = create_database_connection()
user_store = DatabaseUserStore(db)
permission_store = DatabasePermissionStore(db)
acl_evaluator = ACLEvaluator(permission_store, user_store)
```

## Best Practices

### Security

1. **Audit Permission Changes**: Log all grant/revoke operations
2. **Principle of Least Privilege**: Grant minimum necessary permissions
3. **Regular Review**: Periodically audit permission grants
4. **Expiration by Default**: Consider time-limited permissions for sensitive operations
5. **Separation of Duties**: Don't allow users to grant themselves elevated permissions

### Performance

1. **Cache Permission Checks**: Cache `get_influence_set()` results
2. **Index by Subject/Object**: Optimize permission lookups
3. **Lazy Evaluation**: Don't compute permissions until needed
4. **Pre-compute Influence Sets**: Calculate and cache for frequently accessed users

### Organization

1. **Use Groups**: Prefer group-based permissions over individual grants
2. **Naming Conventions**: Use clear, consistent IDs (e.g., "team-engineering", "role-admin")
3. **Documentation**: Document permission grants with metadata
4. **Hierarchical Groups**: Structure groups to match your org chart

### Testing

1. **Test Permission Changes**: Verify grants/revokes work correctly
2. **Test Projections**: Ensure ACL affects projections as expected
3. **Test Expiration**: Verify time-based permissions expire correctly
4. **Test Edge Cases**: Self-permissions, circular groups, etc.

## Troubleshooting

### User not being influenced despite being in admin group

**Check:**
1. Permission grant exists: `GET /api/acl/influence/{user_id}`
2. User is actually in the group: `GET /api/acl/users`
3. Permission hasn't expired
4. ACL evaluator is initialized in projector

### Changes not reflected in UI

**Fix:**
1. Refresh the page
2. Check browser console for errors
3. Verify API endpoints return updated data

### Permission denied errors

**Check:**
1. User/group exists in the system
2. Permission grant exists in database
3. Grant hasn't expired
4. ACL evaluator is properly configured

## Further Reading

- **Main README**: [README.md](README.md) - Overview and quick start
- **Architecture**: See "Architecture" section in README
- **API Reference**: See "API Endpoints" section in README
- **Source Code**: `src/promptscope/core/acl/` - Full implementation

---

**Questions?** Open an issue on GitHub or refer to the code examples in `src/promptscope/api/seed_data.py`.
