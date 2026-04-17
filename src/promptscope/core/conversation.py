"""
Conversation state management.

This module projects the event log into the current state of the conversation.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .events import EventLog, ConversationEvent, MessagePosted, MessageEdited, MessageDeleted


class Message(BaseModel):
    """Current state of a message in the conversation."""

    logical_msg_id: str
    author: str
    content: str
    created_at: datetime
    last_modified_at: datetime
    is_deleted: bool = False
    addressed_to: Optional[str] = None  # For assistant messages: which principal it's for


class ConversationState:
    """
    Represents the current state of a conversation by projecting the event log.

    This class computes the current view of messages from the append-only event log.
    """

    def __init__(self, event_log: EventLog):
        self.event_log = event_log

    def get_current_messages(self) -> list[Message]:
        """
        Project the event log into the current state of messages.

        Returns a list of non-deleted messages in chronological order.
        """
        messages_dict: dict[str, Message] = {}

        # Replay all events to build current state
        for event in self.event_log.get_all_events():
            if isinstance(event, MessagePosted):
                messages_dict[event.logical_msg_id] = Message(
                    logical_msg_id=event.logical_msg_id,
                    author=event.author,
                    content=event.content,
                    created_at=event.timestamp,
                    last_modified_at=event.timestamp,
                    is_deleted=False,
                    addressed_to=event.addressed_to,
                )

            elif isinstance(event, MessageEdited):
                if event.logical_msg_id in messages_dict:
                    msg = messages_dict[event.logical_msg_id]
                    msg.content = event.new_content
                    msg.last_modified_at = event.timestamp

            elif isinstance(event, MessageDeleted):
                if event.logical_msg_id in messages_dict:
                    messages_dict[event.logical_msg_id].is_deleted = True

        # Filter out deleted messages and sort by creation time
        active_messages = [msg for msg in messages_dict.values() if not msg.is_deleted]
        active_messages.sort(key=lambda m: m.created_at)

        return active_messages

    def get_all_messages_including_deleted(self) -> list[Message]:
        """
        Get all messages including deleted ones.

        Useful for debugging and showing full history.
        """
        messages_dict: dict[str, Message] = {}

        for event in self.event_log.get_all_events():
            if isinstance(event, MessagePosted):
                messages_dict[event.logical_msg_id] = Message(
                    logical_msg_id=event.logical_msg_id,
                    author=event.author,
                    content=event.content,
                    created_at=event.timestamp,
                    last_modified_at=event.timestamp,
                    is_deleted=False,
                    addressed_to=event.addressed_to,
                )

            elif isinstance(event, MessageEdited):
                if event.logical_msg_id in messages_dict:
                    msg = messages_dict[event.logical_msg_id]
                    msg.content = event.new_content
                    msg.last_modified_at = event.timestamp

            elif isinstance(event, MessageDeleted):
                if event.logical_msg_id in messages_dict:
                    messages_dict[event.logical_msg_id].is_deleted = True

        messages = list(messages_dict.values())
        messages.sort(key=lambda m: m.created_at)
        return messages

    def get_message_by_id(self, logical_msg_id: str) -> Optional[Message]:
        """Get a specific message by ID."""
        messages = self.get_all_messages_including_deleted()
        for msg in messages:
            if msg.logical_msg_id == logical_msg_id:
                return msg
        return None
