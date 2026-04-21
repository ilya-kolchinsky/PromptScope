"""
Multi-user LLM session with protection against context pollution.

This module provides the main public API for PromptScope.
"""

import uuid
from datetime import datetime
from typing import Optional, Literal
from pathlib import Path
import json

from .core.events import EventLog, MessagePosted, MessageEdited, MessageDeleted
from .core.conversation import ConversationState
from .core.projection import ConversationProjector
from .core.prompt_builder import PromptBuilder
from .core.retrieval_tools import ConversationTools, SearchFilters
from .core.llm_client import create_llm_client, LLMClient
from .core.acl import (
    User,
    Group,
    PermissionGrant,
    PermissionType,
    ACLEvaluator,
    InMemoryPermissionStore,
    InMemoryUserStore,
)
from .core.acl.store import PermissionStore, UserStore

from .types import Message, Projection, Response
from .exceptions import (
    ConfigurationError,
    ValidationError,
    SecurityError,
    NotFoundError,
    SerializationError,
)


class MultiUserSession:
    """
    A multi-user LLM conversation with protection against context pollution.

    This is the main entry point for using PromptScope. It manages a conversation
    where multiple users can interact with an LLM while maintaining security
    through principal-based projection and optional access control.

    Examples:
        Basic usage:
        >>> session = MultiUserSession()
        >>> session.post("Alice", "Hello everyone!")
        >>> response = session.ask("Bob", "What is 2 + 2?")
        >>> print(response.content)

        With real LLM:
        >>> session = MultiUserSession(
        ...     llm_provider="anthropic",
        ...     api_key="sk-ant-...",
        ...     protected_mode=True
        ... )

        With ACL:
        >>> session = MultiUserSession()
        >>> session.create_user("alice", username="Alice")
        >>> session.create_user("bob", username="Bob")
        >>> session.create_group("admins")
        >>> session.add_to_group("alice", "admins")
        >>> session.grant_influence(subject="admins", target="bob")

    Attributes:
        protected_mode: Default protection mode for LLM requests
        enable_acl: Whether access control is enabled
    """

    def __init__(
        self,
        llm_provider: Literal["mock", "anthropic", "openai", "vllm", "ollama"] = "mock",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        protected_mode: bool = True,
        enable_acl: bool = True,
        event_log: Optional[EventLog] = None,
        user_store: Optional[UserStore] = None,
        permission_store: Optional[PermissionStore] = None,
    ):
        """
        Initialize a new multi-user session.

        Args:
            llm_provider: LLM provider to use (default: "mock" for testing)
            api_key: API key for the LLM provider (if required)
            model: Model name (provider-specific)
            protected_mode: Whether to use protected mode by default
            enable_acl: Whether to enable access control
            event_log: Optional custom event log (for advanced use or loading)
            user_store: Optional custom user store (for advanced use or loading)
            permission_store: Optional custom permission store (for advanced use or loading)

        Raises:
            ConfigurationError: If LLM configuration is invalid
        """
        self.protected_mode = protected_mode
        self.enable_acl = enable_acl

        # Initialize event log
        self._event_log = event_log if event_log is not None else EventLog()

        # Initialize ACL stores
        self._user_store = user_store if user_store is not None else InMemoryUserStore()
        self._permission_store = (
            permission_store if permission_store is not None else InMemoryPermissionStore()
        )

        # Initialize core components
        self._conversation_state = ConversationState(self._event_log)

        if self.enable_acl:
            self._acl_evaluator = ACLEvaluator(self._permission_store, self._user_store)
            self._projector = ConversationProjector(self._conversation_state, self._acl_evaluator)
        else:
            self._acl_evaluator = None
            self._projector = ConversationProjector(self._conversation_state, acl_evaluator=None)

        self._prompt_builder = PromptBuilder(self._conversation_state, self._projector)
        self._conversation_tools = ConversationTools(
            self._event_log, self._conversation_state, self._projector
        )

        # Initialize LLM client
        self._llm_provider = llm_provider
        self._api_key = api_key
        self._model = model
        self._llm_client: Optional[LLMClient] = None

    def _get_llm_client(self) -> LLMClient:
        """Lazy initialization of LLM client."""
        if self._llm_client is None:
            try:
                # Set environment variables if provided
                import os
                if self._api_key:
                    if self._llm_provider == "anthropic":
                        os.environ["ANTHROPIC_API_KEY"] = self._api_key
                    elif self._llm_provider == "openai":
                        os.environ["OPENAI_API_KEY"] = self._api_key

                if self._model:
                    if self._llm_provider == "anthropic":
                        os.environ["ANTHROPIC_MODEL"] = self._model
                    elif self._llm_provider == "openai":
                        os.environ["OPENAI_MODEL"] = self._model

                os.environ["LLM_PROVIDER"] = self._llm_provider
                self._llm_client = create_llm_client()
            except Exception as e:
                raise ConfigurationError(f"Failed to initialize LLM client: {e}") from e

        return self._llm_client

    # ========== Message Operations ==========

    def post(self, author: str, content: str, addressed_to: Optional[str] = None) -> Message:
        """
        Post a new message to the conversation.

        Args:
            author: Username of the message author
            content: Message text content
            addressed_to: If this is an assistant response, which principal it's for

        Returns:
            The posted Message object

        Raises:
            ValidationError: If author or content is empty

        Examples:
            >>> msg = session.post("Alice", "Hello everyone!")
            >>> print(msg.id, msg.author, msg.content)
        """
        if not author or not author.strip():
            raise ValidationError("Author cannot be empty")
        if not content or not content.strip():
            raise ValidationError("Content cannot be empty")

        message_id = str(uuid.uuid4())
        event = MessagePosted(
            logical_msg_id=message_id,
            author=author,
            content=content,
            timestamp=datetime.utcnow(),
            addressed_to=addressed_to,
        )
        self._event_log.append(event)

        # Convert internal message to public Message
        internal_msg = self._conversation_state.get_message_by_id(message_id)
        if internal_msg is None:
            raise SecurityError(f"Message {message_id} not found after posting")

        return self._to_public_message(internal_msg)

    def edit_message(self, message_id: str, new_content: str, editor: str) -> Message:
        """
        Edit an existing message.

        Args:
            message_id: ID of the message to edit
            new_content: New content for the message
            editor: Username of the user editing the message

        Returns:
            The updated Message object

        Raises:
            ValidationError: If new_content or editor is empty
            NotFoundError: If message_id is not found

        Examples:
            >>> msg = session.edit_message(msg_id, "Updated content!", "Alice")
        """
        if not new_content or not new_content.strip():
            raise ValidationError("New content cannot be empty")
        if not editor or not editor.strip():
            raise ValidationError("Editor cannot be empty")

        # Verify message exists
        existing = self._conversation_state.get_message_by_id(message_id)
        if existing is None:
            raise NotFoundError(f"Message {message_id} not found")

        event = MessageEdited(
            logical_msg_id=message_id,
            editor=editor,
            new_content=new_content,
            timestamp=datetime.utcnow(),
        )
        self._event_log.append(event)

        # Get updated message
        updated_msg = self._conversation_state.get_message_by_id(message_id)
        if updated_msg is None:
            raise SecurityError(f"Message {message_id} not found after editing")

        return self._to_public_message(updated_msg)

    def delete_message(self, message_id: str, deleter: str) -> None:
        """
        Delete a message from the conversation.

        Args:
            message_id: ID of the message to delete
            deleter: Username of the user deleting the message

        Raises:
            ValidationError: If deleter is empty
            NotFoundError: If message_id is not found

        Examples:
            >>> session.delete_message(msg_id, "Alice")
        """
        if not deleter or not deleter.strip():
            raise ValidationError("Deleter cannot be empty")

        # Verify message exists
        existing = self._conversation_state.get_message_by_id(message_id)
        if existing is None:
            raise NotFoundError(f"Message {message_id} not found")

        event = MessageDeleted(
            logical_msg_id=message_id,
            deleter=deleter,
            timestamp=datetime.utcnow(),
        )
        self._event_log.append(event)

    def get_messages(
        self,
        author: Optional[str] = None,
        include_deleted: bool = False,
    ) -> list[Message]:
        """
        Get messages from the conversation.

        Args:
            author: Filter by author (default: all authors)
            include_deleted: Whether to include deleted messages

        Returns:
            List of Message objects

        Examples:
            >>> all_msgs = session.get_messages()
            >>> alice_msgs = session.get_messages(author="Alice")
        """
        if include_deleted:
            messages = self._conversation_state.get_all_messages_including_deleted()
        else:
            messages = self._conversation_state.get_current_messages()

        if author:
            messages = [msg for msg in messages if msg.author == author]

        return [self._to_public_message(msg) for msg in messages]

    # ========== LLM Interaction ==========

    def ask(
        self,
        principal: str,
        query: str,
        protected_mode: Optional[bool] = None,
        include_debug_info: bool = False,
    ) -> Response:
        """
        Ask the LLM a question on behalf of a principal.

        Args:
            principal: The user asking the question
            query: The question to ask
            protected_mode: Override the default protected mode setting
            include_debug_info: Whether to include debug information in the response

        Returns:
            Response object with the LLM's answer

        Raises:
            ValidationError: If principal or query is empty
            SecurityError: If protected mode fails to engage when expected

        Examples:
            >>> response = session.ask("Bob", "What is 2 + 2?")
            >>> print(response.content)
        """
        if not principal or not principal.strip():
            raise ValidationError("Principal cannot be empty")
        if not query or not query.strip():
            raise ValidationError("Query cannot be empty")

        # Determine protection mode
        use_protected_mode = protected_mode if protected_mode is not None else self.protected_mode

        # Build the LLM request
        if use_protected_mode:
            projected_view = self._projector.project_for_principal(principal)
            llm_request = self._prompt_builder.build_protected_request(
                principal, query, projected_view
            )

            # Security check: ensure tools are present in protected mode
            if not llm_request.tools:
                raise SecurityError(
                    "Protected mode request has no retrieval tools - this is a security violation"
                )
        else:
            llm_request = self._prompt_builder.build_naive_request(principal, query)

        # Create tool executor
        tool_calls_made = []

        def tool_executor(tool_name: str, tool_args: dict):
            """Execute a retrieval tool."""
            tool_calls_made.append({"tool": tool_name, "args": tool_args})

            if tool_name == "search_conversation":
                filters = None
                if any(k in tool_args for k in ["speakers", "time_range_start", "time_range_end"]):
                    filters = SearchFilters(
                        speakers=tool_args.get("speakers"),
                        time_range_start=(
                            datetime.fromisoformat(tool_args["time_range_start"])
                            if tool_args.get("time_range_start")
                            else None
                        ),
                        time_range_end=(
                            datetime.fromisoformat(tool_args["time_range_end"])
                            if tool_args.get("time_range_end")
                            else None
                        ),
                    )

                result = self._conversation_tools.search_conversation(
                    principal=principal,
                    query=tool_args["query"],
                    filters=filters,
                )
                return result.model_dump()

            elif tool_name == "expand_local_context":
                result = self._conversation_tools.expand_local_context(
                    principal=principal,
                    hit_id=tool_args["hit_id"],
                    window=tool_args.get("window", 2),
                )
                return result.model_dump()

            elif tool_name == "get_exact_event":
                result = self._conversation_tools.get_exact_event(
                    principal=principal,
                    event_id=tool_args["event_id"],
                )
                if result:
                    return result.model_dump()
                return {"error": "Event not found"}

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        # Get LLM response
        client = self._get_llm_client()

        if use_protected_mode and llm_request.tools:
            llm_response = client.generate_with_tools(llm_request, tool_executor)
        else:
            llm_response = client.generate(llm_request)

        # Build response object
        debug_info = None
        if include_debug_info:
            debug_info = {
                "system_prompt": llm_request.system_prompt,
                "messages": [{"role": m.role, "content": m.content} for m in llm_request.messages],
                "tools_available": len(llm_request.tools) if llm_request.tools else 0,
            }

        return Response(
            content=llm_response.content,
            principal=principal,
            query=query,
            protected_mode=use_protected_mode,
            tool_calls=tool_calls_made,
            debug_info=debug_info,
        )

    async def ask_async(
        self,
        principal: str,
        query: str,
        protected_mode: Optional[bool] = None,
        include_debug_info: bool = False,
    ) -> Response:
        """
        Ask the LLM a question asynchronously (STUB - NOT YET IMPLEMENTED).

        This is a placeholder for future async support. Asynchronous execution
        introduces several challenges that need to be addressed:

        1. **Event Log Consistency**: Multiple concurrent asks could create race
           conditions in the event log if responses are posted back.

        2. **Projection Staleness**: If the conversation changes during an async
           request, the projection may be stale when the response arrives.

        3. **ACL Changes**: Permission changes during async execution could cause
           inconsistencies between request time and response time.

        4. **Resource Management**: LLM client connections need proper async handling.

        Future implementation will need to address these issues, potentially through:
        - Snapshot isolation for projections
        - Optimistic concurrency control for event log writes
        - Clear semantics for when ACL checks are performed
        - Proper async LLM client implementation

        Args:
            principal: The user asking the question
            query: The question to ask
            protected_mode: Override the default protected mode setting
            include_debug_info: Whether to include debug information in the response

        Returns:
            Response object with the LLM's answer

        Raises:
            NotImplementedError: This method is not yet implemented
        """
        raise NotImplementedError(
            "Async support is planned but not yet implemented. "
            "See method docstring for challenges that need to be addressed."
        )

    # ========== Projection Access ==========

    def get_projection(self, principal: str) -> Projection:
        """
        Get the conversation projection for a specific principal.

        This shows what messages are in the principal's effective control context
        (directly influence LLM) vs. visible observation context (retrievable via tools).

        Args:
            principal: The user for whom to generate the projection

        Returns:
            Projection object

        Raises:
            ValidationError: If principal is empty

        Examples:
            >>> proj = session.get_projection("Bob")
            >>> print(f"Control: {len(proj.effective_control)}")
            >>> print(f"Observation: {len(proj.visible_observation)}")
        """
        if not principal or not principal.strip():
            raise ValidationError("Principal cannot be empty")

        internal_projection = self._projector.project_for_principal(principal)

        return Projection(
            principal=internal_projection.principal,
            effective_control=[
                self._to_public_message(msg) for msg in internal_projection.effective_control_context
            ],
            visible_observation=[
                self._to_public_message(msg)
                for msg in internal_projection.visible_observation_context
            ],
        )

    # ========== ACL Methods (Direct on Session) ==========

    def create_user(
        self, user_id: str, username: str, groups: Optional[list[str]] = None, **kwargs
    ) -> User:
        """
        Create a new user in the ACL system.

        Args:
            user_id: Unique user identifier
            username: Display name
            groups: List of group IDs the user belongs to
            **kwargs: Additional metadata (e.g., manager_id)

        Returns:
            The created User object

        Raises:
            ValidationError: If user_id or username is empty
            ConfigurationError: If ACL is not enabled

        Examples:
            >>> session.create_user("alice", username="Alice", groups=["admins"])
        """
        if not self.enable_acl:
            raise ConfigurationError("ACL is not enabled for this session")

        if not user_id or not user_id.strip():
            raise ValidationError("user_id cannot be empty")
        if not username or not username.strip():
            raise ValidationError("username cannot be empty")

        user = User(
            id=user_id,
            username=username,
            groups=groups or [],
            manager_id=kwargs.get("manager_id"),
            metadata=kwargs,
        )
        return self._user_store.create_user(user)

    def get_user(self, user_id: str) -> Optional[User]:
        """
        Get a user by ID.

        Args:
            user_id: User identifier

        Returns:
            User object or None if not found

        Raises:
            ConfigurationError: If ACL is not enabled
        """
        if not self.enable_acl:
            raise ConfigurationError("ACL is not enabled for this session")

        return self._user_store.get_user(user_id)

    def list_users(self) -> list[User]:
        """
        List all users.

        Returns:
            List of User objects

        Raises:
            ConfigurationError: If ACL is not enabled
        """
        if not self.enable_acl:
            raise ConfigurationError("ACL is not enabled for this session")

        return self._user_store.get_all_users()

    def create_group(self, group_id: str, name: str) -> Group:
        """
        Create a new group.

        Args:
            group_id: Unique group identifier
            name: Display name

        Returns:
            The created Group object

        Raises:
            ValidationError: If group_id or name is empty
            ConfigurationError: If ACL is not enabled

        Examples:
            >>> session.create_group("admins", "Administrators")
        """
        if not self.enable_acl:
            raise ConfigurationError("ACL is not enabled for this session")

        if not group_id or not group_id.strip():
            raise ValidationError("group_id cannot be empty")
        if not name or not name.strip():
            raise ValidationError("name cannot be empty")

        group = Group(id=group_id, name=name, members=[])
        return self._user_store.create_group(group)

    def add_to_group(self, user_id: str, group_id: str) -> None:
        """
        Add a user to a group.

        Args:
            user_id: User identifier
            group_id: Group identifier

        Raises:
            ValidationError: If user_id or group_id is empty
            NotFoundError: If user or group doesn't exist
            ConfigurationError: If ACL is not enabled

        Examples:
            >>> session.add_to_group("alice", "admins")
        """
        if not self.enable_acl:
            raise ConfigurationError("ACL is not enabled for this session")

        if not user_id or not user_id.strip():
            raise ValidationError("user_id cannot be empty")
        if not group_id or not group_id.strip():
            raise ValidationError("group_id cannot be empty")

        success = self._user_store.add_user_to_group(user_id, group_id)
        if not success:
            raise NotFoundError(f"User {user_id} or group {group_id} not found")

    def remove_from_group(self, user_id: str, group_id: str) -> None:
        """
        Remove a user from a group.

        Args:
            user_id: User identifier
            group_id: Group identifier

        Raises:
            ValidationError: If user_id or group_id is empty
            NotFoundError: If user or group doesn't exist
            ConfigurationError: If ACL is not enabled

        Examples:
            >>> session.remove_from_group("alice", "admins")
        """
        if not self.enable_acl:
            raise ConfigurationError("ACL is not enabled for this session")

        if not user_id or not user_id.strip():
            raise ValidationError("user_id cannot be empty")
        if not group_id or not group_id.strip():
            raise ValidationError("group_id cannot be empty")

        success = self._user_store.remove_user_from_group(user_id, group_id)
        if not success:
            raise NotFoundError(f"User {user_id} or group {group_id} not found")

    def grant_influence(self, subject: str, target: str, granted_by: str = "system") -> None:
        """
        Grant INFLUENCE permission from subject to target.

        This allows the subject's messages to appear in the target's effective
        control context, even in protected mode.

        Args:
            subject: User or group ID that will have influence
            target: User ID that will be influenced
            granted_by: Who is granting this permission (default: "system")

        Raises:
            ValidationError: If subject or target is empty
            ConfigurationError: If ACL is not enabled

        Examples:
            >>> session.grant_influence(subject="admins", target="bob")
            >>> session.grant_influence(subject="alice", target="bob", granted_by="admin")
        """
        if not self.enable_acl:
            raise ConfigurationError("ACL is not enabled for this session")

        if not subject or not subject.strip():
            raise ValidationError("subject cannot be empty")
        if not target or not target.strip():
            raise ValidationError("target cannot be empty")

        grant = PermissionGrant(
            id=f"{subject}-influence-{target}-{uuid.uuid4().hex[:8]}",
            permission_type=PermissionType.INFLUENCE,
            subject=subject,
            object=target,
            granted_by=granted_by,
            granted_at=datetime.utcnow(),
        )
        self._permission_store.grant_permission(grant)

    def revoke_influence(self, subject: str, target: str) -> None:
        """
        Revoke INFLUENCE permission from subject to target.

        Args:
            subject: User or group ID to revoke influence from
            target: User ID that will no longer be influenced

        Raises:
            ValidationError: If subject or target is empty
            ConfigurationError: If ACL is not enabled
            NotFoundError: If no such permission grant exists

        Examples:
            >>> session.revoke_influence(subject="alice", target="bob")
        """
        if not self.enable_acl:
            raise ConfigurationError("ACL is not enabled for this session")

        if not subject or not subject.strip():
            raise ValidationError("subject cannot be empty")
        if not target or not target.strip():
            raise ValidationError("target cannot be empty")

        # Find and revoke the grant
        grants = self._permission_store.get_grants(
            subject=subject, object=target, permission_type=PermissionType.INFLUENCE
        )

        if not grants:
            raise NotFoundError(f"No INFLUENCE permission from {subject} to {target}")

        # Revoke all matching grants
        for grant in grants:
            self._permission_store.revoke_permission(grant.id)

    def can_influence(self, subject: str, target: str) -> bool:
        """
        Check if subject can influence target.

        Args:
            subject: User or group ID to check
            target: Target user ID

        Returns:
            True if subject can influence target, False otherwise

        Raises:
            ConfigurationError: If ACL is not enabled

        Examples:
            >>> if session.can_influence("alice", "bob"):
            ...     print("Alice can influence Bob")
        """
        if not self.enable_acl:
            raise ConfigurationError("ACL is not enabled for this session")

        if self._acl_evaluator is None:
            return False

        return self._acl_evaluator.can_influence(subject, target)

    def get_influencers(self, principal: str) -> list[str]:
        """
        Get all users who can influence a principal.

        Args:
            principal: User ID to check

        Returns:
            List of user IDs that can influence the principal

        Raises:
            ConfigurationError: If ACL is not enabled

        Examples:
            >>> influencers = session.get_influencers("bob")
            >>> print(f"Bob is influenced by: {influencers}")
        """
        if not self.enable_acl:
            raise ConfigurationError("ACL is not enabled for this session")

        if self._acl_evaluator is None:
            return [principal]  # Only self-influence

        return list(self._acl_evaluator.get_influence_set(principal))

    # ========== Serialization ==========

    def save(self, path: str) -> None:
        """
        Save the session state to a file.

        This serializes:
        - Event log (complete conversation history)
        - Users and groups (if ACL is enabled)
        - Permission grants (if ACL is enabled)

        Args:
            path: File path to save to

        Raises:
            SerializationError: If serialization fails

        Examples:
            >>> session.save("my_session.json")
        """
        try:
            data = {
                "version": "1.0",
                "protected_mode": self.protected_mode,
                "enable_acl": self.enable_acl,
                "llm_provider": self._llm_provider,
                "model": self._model,
                "events": [],
                "users": [],
                "groups": [],
                "permissions": [],
            }

            # Serialize event log
            for event in self._event_log.get_all_events():
                event_data = {
                    "event_type": event.event_type,
                    **event.model_dump(exclude={"event_type"}),
                }
                # Convert datetime to ISO format
                if "timestamp" in event_data:
                    event_data["timestamp"] = event_data["timestamp"].isoformat()
                data["events"].append(event_data)

            # Serialize ACL data if enabled
            if self.enable_acl:
                for user in self._user_store.get_all_users():
                    data["users"].append(user.model_dump())

                for group in self._user_store.get_all_groups():
                    data["groups"].append(group.model_dump())

                # Get all permissions
                all_grants = self._permission_store.get_grants()
                for grant in all_grants:
                    grant_data = grant.model_dump()
                    # Convert datetime fields
                    if grant_data.get("granted_at"):
                        grant_data["granted_at"] = grant_data["granted_at"].isoformat()
                    if grant_data.get("expires_at"):
                        grant_data["expires_at"] = grant_data["expires_at"].isoformat()
                    data["permissions"].append(grant_data)

            # Write to file
            Path(path).write_text(json.dumps(data, indent=2))

        except Exception as e:
            raise SerializationError(f"Failed to save session: {e}") from e

    @classmethod
    def load(cls, path: str, api_key: Optional[str] = None) -> "MultiUserSession":
        """
        Load a session from a file.

        Args:
            path: File path to load from
            api_key: Optional API key for LLM (if different from saved state)

        Returns:
            Loaded MultiUserSession instance

        Raises:
            SerializationError: If deserialization fails
            NotFoundError: If file doesn't exist

        Examples:
            >>> session = MultiUserSession.load("my_session.json")
            >>> # Or with a different API key:
            >>> session = MultiUserSession.load("my_session.json", api_key="new-key")
        """
        try:
            file_path = Path(path)
            if not file_path.exists():
                raise NotFoundError(f"File not found: {path}")

            data = json.loads(file_path.read_text())

            # Recreate event log
            event_log = EventLog()
            for event_data in data.get("events", []):
                event_type = event_data.pop("event_type")

                # Convert timestamp back to datetime
                if "timestamp" in event_data:
                    event_data["timestamp"] = datetime.fromisoformat(event_data["timestamp"])

                # Create appropriate event object
                if event_type == "MessagePosted":
                    event = MessagePosted(**event_data)
                elif event_type == "MessageEdited":
                    event = MessageEdited(**event_data)
                elif event_type == "MessageDeleted":
                    event = MessageDeleted(**event_data)
                else:
                    continue  # Skip unknown event types

                event_log.append(event)

            # Recreate user and permission stores
            user_store = InMemoryUserStore()
            permission_store = InMemoryPermissionStore()

            enable_acl = data.get("enable_acl", True)

            if enable_acl:
                # Recreate users
                for user_data in data.get("users", []):
                    user_store.create_user(User(**user_data))

                # Recreate groups
                for group_data in data.get("groups", []):
                    user_store.create_group(Group(**group_data))

                # Recreate permissions
                for perm_data in data.get("permissions", []):
                    # Convert datetime fields
                    if perm_data.get("granted_at"):
                        perm_data["granted_at"] = datetime.fromisoformat(perm_data["granted_at"])
                    if perm_data.get("expires_at") and perm_data["expires_at"]:
                        perm_data["expires_at"] = datetime.fromisoformat(perm_data["expires_at"])

                    permission_store.grant_permission(PermissionGrant(**perm_data))

            # Create session
            return cls(
                llm_provider=data.get("llm_provider", "mock"),
                api_key=api_key,  # Use provided or None
                model=data.get("model"),
                protected_mode=data.get("protected_mode", True),
                enable_acl=enable_acl,
                event_log=event_log,
                user_store=user_store,
                permission_store=permission_store,
            )

        except NotFoundError:
            raise
        except Exception as e:
            raise SerializationError(f"Failed to load session: {e}") from e

    # ========== Helper Methods ==========

    def _to_public_message(self, internal_msg) -> Message:
        """Convert internal Message to public Message."""
        return Message(
            id=internal_msg.logical_msg_id,
            author=internal_msg.author,
            content=internal_msg.content,
            created_at=internal_msg.created_at,
            last_modified_at=internal_msg.last_modified_at,
            is_deleted=internal_msg.is_deleted,
            addressed_to=internal_msg.addressed_to,
        )

    # ========== Advanced Access (for power users) ==========

    @property
    def event_log(self) -> EventLog:
        """
        Access to the internal event log (advanced use).

        This provides direct access to the event log for power users who
        need to inspect or manipulate events directly.
        """
        return self._event_log

    @property
    def conversation_state(self) -> ConversationState:
        """
        Access to the internal conversation state (advanced use).

        This provides direct access to the conversation state projection
        for power users.
        """
        return self._conversation_state

    @property
    def projector(self) -> ConversationProjector:
        """
        Access to the internal projector (advanced use).

        This provides direct access to the projection mechanism for
        power users.
        """
        return self._projector
