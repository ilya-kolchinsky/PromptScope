"""
Public data types for the PromptScope API.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Message:
    """
    A message in a multi-user conversation.

    Attributes:
        id: Unique message identifier
        author: Username of the message author
        content: Message text content
        created_at: When the message was created
        last_modified_at: When the message was last modified
        is_deleted: Whether the message has been deleted
        addressed_to: If this is an assistant response, which principal it's for (None = broadcast)
    """

    id: str
    author: str
    content: str
    created_at: datetime
    last_modified_at: datetime
    is_deleted: bool = False
    addressed_to: Optional[str] = None


@dataclass
class Projection:
    """
    A principal-specific view of the conversation.

    This represents what messages a specific principal can see and which
    ones will directly influence their LLM interactions.

    Attributes:
        principal: The user for whom this projection is generated
        effective_control: Messages that directly influence the LLM (in default context)
        visible_observation: Messages that are visible but don't automatically influence
    """

    principal: str
    effective_control: list[Message]
    visible_observation: list[Message]


@dataclass
class Response:
    """
    An LLM response to a user query.

    Attributes:
        content: The LLM's response text
        principal: The user who asked the question
        query: The original query
        protected_mode: Whether protected mode was used for this response
        tool_calls: List of tool calls made by the LLM (if any)
        debug_info: Optional debug information about the request
    """

    content: str
    principal: str
    query: str
    protected_mode: bool
    tool_calls: list[dict] = field(default_factory=list)
    debug_info: Optional[dict] = None
