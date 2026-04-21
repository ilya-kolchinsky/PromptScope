"""
PromptScope: A proof-of-concept library for safe multi-user LLM chats.

This library provides the core functionality for implementing secure multi-user
LLM interactions with tool-based context retrieval and hierarchical access control.

For a demo application, see the demo/ directory.
"""

__version__ = "0.1.0"

# Export core classes for convenient importing
from .core.events import EventLog, MessagePosted, MessageEdited, MessageDeleted
from .core.conversation import ConversationState, Message
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
    # Events
    "EventLog",
    "MessagePosted",
    "MessageEdited",
    "MessageDeleted",
    # Conversation
    "ConversationState",
    "Message",
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
