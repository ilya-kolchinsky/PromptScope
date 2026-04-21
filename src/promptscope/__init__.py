"""
PromptScope: A library for safe multi-user LLM chats.

This library provides functionality for implementing secure multi-user
LLM interactions with tool-based context retrieval and hierarchical access control.

Quick Start:
    >>> from promptscope import MultiUserSession
    >>> session = MultiUserSession()
    >>> session.post("Alice", "Hello everyone!")
    >>> response = session.ask("Bob", "What is 2 + 2?")
    >>> print(response.content)

For a demo application, see the demo/ directory.
"""

__version__ = "0.1.0"

# ========== Public API ==========
# Main entry point
from .session import MultiUserSession

# Public data types
from .types import Message, Projection, Response

# Exceptions
from .exceptions import (
    PromptScopeError,
    ConfigurationError,
    ValidationError,
    SecurityError,
    NotFoundError,
    PermissionError,
    SerializationError,
)

# ========== Advanced/Core API ==========
# For power users who need direct access to internals
from .core.events import EventLog, MessagePosted, MessageEdited, MessageDeleted
from .core.conversation import ConversationState
from .core.projection import ConversationProjector, ProjectedView
from .core.prompt_builder import PromptBuilder
from .core.retrieval_tools import ConversationTools
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

__all__ = [
    # ===== Public API (most users should use these) =====
    # Main class
    "MultiUserSession",
    # Data types
    "Message",
    "Projection",
    "Response",
    # Exceptions
    "PromptScopeError",
    "ConfigurationError",
    "ValidationError",
    "SecurityError",
    "NotFoundError",
    "PermissionError",
    "SerializationError",
    # ===== Advanced/Core API (for power users) =====
    # Events
    "EventLog",
    "MessagePosted",
    "MessageEdited",
    "MessageDeleted",
    # Conversation
    "ConversationState",
    # Projection
    "ConversationProjector",
    "ProjectedView",
    # Prompt Building
    "PromptBuilder",
    # Retrieval
    "ConversationTools",
    # LLM Client
    "create_llm_client",
    "LLMClient",
    # ACL
    "User",
    "Group",
    "PermissionGrant",
    "PermissionType",
    "ACLEvaluator",
    "InMemoryPermissionStore",
    "InMemoryUserStore",
]
