"""
Conversation event log system.

This module implements an append-only event log for conversation messages.
Events are never modified or deleted; they are only appended to the log.
"""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class MessagePosted(BaseModel):
    """Event: A user posted a new message to the conversation."""

    event_type: Literal["MessagePosted"] = "MessagePosted"
    logical_msg_id: str = Field(description="Unique identifier for this logical message")
    author: str = Field(description="Username of the message author")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    addressed_to: Optional[str] = Field(
        default=None,
        description="If this is an assistant response, which principal it's for. None = broadcast to all"
    )


class MessageEdited(BaseModel):
    """Event: A user edited an existing message."""

    event_type: Literal["MessageEdited"] = "MessageEdited"
    logical_msg_id: str = Field(description="ID of the message being edited")
    editor: str = Field(description="Username of the editor")
    new_content: str = Field(description="Updated message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MessageDeleted(BaseModel):
    """Event: A user deleted a message."""

    event_type: Literal["MessageDeleted"] = "MessageDeleted"
    logical_msg_id: str = Field(description="ID of the message being deleted")
    deleter: str = Field(description="Username of the user who deleted it")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Union type for all event types
ConversationEvent = MessagePosted | MessageEdited | MessageDeleted


class EventLog:
    """
    Append-only event log for conversation events.

    This is the single source of truth for all conversation state.
    Events are never modified or removed from the log.
    """

    def __init__(self):
        self._events: list[ConversationEvent] = []

    def append(self, event: ConversationEvent) -> None:
        """Append a new event to the log."""
        self._events.append(event)

    def get_all_events(self) -> list[ConversationEvent]:
        """Get all events in chronological order."""
        return list(self._events)

    def clear(self) -> None:
        """Clear all events (for testing/reset only)."""
        self._events.clear()
