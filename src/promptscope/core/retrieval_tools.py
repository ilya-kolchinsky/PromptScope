"""
Retrieval tools for the LLM to access conversation context.

These tools are provided to the model in protected mode, allowing it to
search and retrieve messages from other users when needed.
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

from .conversation import Message, ConversationState
from .projection import ConversationProjector
from .events import EventLog, ConversationEvent


class SearchFilters(BaseModel):
    """Filters for search_conversation tool."""

    speakers: Optional[list[str]] = Field(
        default=None,
        description="Filter by specific speaker(s). If None, search all speakers."
    )
    time_range_start: Optional[datetime] = Field(
        default=None,
        description="Filter messages after this timestamp"
    )
    time_range_end: Optional[datetime] = Field(
        default=None,
        description="Filter messages before this timestamp"
    )


class SearchHit(BaseModel):
    """A single search result with metadata."""

    hit_id: str = Field(description="Unique identifier for this hit (message ID)")
    speaker: str = Field(description="Who said this")
    content: str = Field(description="The message content")
    timestamp: str = Field(description="When it was said")
    snippet: str = Field(description="Content snippet with context around match")


class SearchResult(BaseModel):
    """Result from search_conversation tool."""

    hits: list[SearchHit]
    total_searched: int
    query: str


class ContextWindow(BaseModel):
    """Result from expand_local_context tool."""

    target_hit_id: str
    window_size: int
    messages: list[dict]  # List of {speaker, content, timestamp, hit_id}


class ExactEvent(BaseModel):
    """Result from get_exact_event tool."""

    event_id: str
    event_type: str
    author: str
    content: str
    timestamp: str
    metadata: dict


class ConversationTools:
    """
    Tools for the LLM to access conversation context in protected mode.

    These tools allow the model to retrieve messages from other users
    (visible observation context) without having them in the default prompt.
    """

    def __init__(
        self,
        event_log: EventLog,
        conversation_state: ConversationState,
        projector: ConversationProjector,
    ):
        self.event_log = event_log
        self.conversation_state = conversation_state
        self.projector = projector

    def search_conversation(
        self,
        principal: str,
        query: str,
        filters: Optional[SearchFilters] = None,
    ) -> SearchResult:
        """
        Search the conversation's visible observation context.

        Args:
            principal: The user performing the search
            query: Search query (case-insensitive substring match)
            filters: Optional filters (speakers, time range, etc.)

        Returns:
            SearchResult with matching messages
        """
        # Get visible observation context for this principal
        projected_view = self.projector.project_for_principal(principal)
        visible_messages = projected_view.visible_observation_context

        # Apply filters
        filtered_messages = visible_messages

        if filters:
            if filters.speakers:
                filtered_messages = [
                    msg for msg in filtered_messages
                    if msg.author in filters.speakers
                ]

            if filters.time_range_start:
                filtered_messages = [
                    msg for msg in filtered_messages
                    if msg.created_at >= filters.time_range_start
                ]

            if filters.time_range_end:
                filtered_messages = [
                    msg for msg in filtered_messages
                    if msg.created_at <= filters.time_range_end
                ]

        # Search within filtered messages
        hits = []
        query_lower = query.lower()

        for msg in filtered_messages:
            content_lower = msg.content.lower()

            if query_lower in content_lower:
                # Find first match position for snippet
                match_pos = content_lower.find(query_lower)

                # Create snippet (50 chars before and after match)
                snippet_start = max(0, match_pos - 50)
                snippet_end = min(len(msg.content), match_pos + len(query) + 50)
                snippet = msg.content[snippet_start:snippet_end]

                if snippet_start > 0:
                    snippet = "..." + snippet
                if snippet_end < len(msg.content):
                    snippet = snippet + "..."

                hits.append(SearchHit(
                    hit_id=msg.logical_msg_id,
                    speaker=msg.author,
                    content=msg.content,
                    timestamp=msg.created_at.isoformat(),
                    snippet=snippet,
                ))

        return SearchResult(
            hits=hits,
            total_searched=len(filtered_messages),
            query=query,
        )

    def expand_local_context(
        self,
        principal: str,
        hit_id: str,
        window: int = 2,
    ) -> ContextWindow:
        """
        Get nearby messages around a specific hit.

        Args:
            principal: The user requesting context
            hit_id: The message ID to get context around
            window: Number of messages before and after (default: 2)

        Returns:
            ContextWindow with surrounding messages
        """
        # Get all messages for context
        all_messages = self.conversation_state.get_current_messages()

        # Find the target message
        target_idx = None
        for i, msg in enumerate(all_messages):
            if msg.logical_msg_id == hit_id:
                target_idx = i
                break

        if target_idx is None:
            return ContextWindow(
                target_hit_id=hit_id,
                window_size=window,
                messages=[],
            )

        # Get surrounding messages
        start_idx = max(0, target_idx - window)
        end_idx = min(len(all_messages), target_idx + window + 1)

        context_messages = []
        for msg in all_messages[start_idx:end_idx]:
            context_messages.append({
                "speaker": msg.author,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat(),
                "hit_id": msg.logical_msg_id,
                "is_target": msg.logical_msg_id == hit_id,
            })

        return ContextWindow(
            target_hit_id=hit_id,
            window_size=window,
            messages=context_messages,
        )

    def get_exact_event(
        self,
        principal: str,
        event_id: str,
    ) -> Optional[ExactEvent]:
        """
        Get the exact event with full metadata.

        Args:
            principal: The user requesting the event
            event_id: The logical message ID (event ID)

        Returns:
            ExactEvent with verbatim content and metadata
        """
        # Find the most recent event for this message
        events = self.event_log.get_all_events()

        # Find all events related to this message ID
        related_events = [
            e for e in events
            if hasattr(e, 'logical_msg_id') and e.logical_msg_id == event_id
        ]

        if not related_events:
            return None

        # Get the most recent state-defining event
        latest_event = related_events[-1]

        # Get current message state to check visibility
        msg = self.conversation_state.get_message_by_id(event_id)
        if msg is None:
            return None

        # Check if this message is visible to the principal
        projected_view = self.projector.project_for_principal(principal)
        all_visible = (
            projected_view.effective_control_context +
            projected_view.visible_observation_context
        )

        if event_id not in [m.logical_msg_id for m in all_visible]:
            return None

        # Build metadata
        metadata = {
            "is_deleted": msg.is_deleted,
            "created_at": msg.created_at.isoformat(),
            "last_modified_at": msg.last_modified_at.isoformat(),
            "edit_count": len([e for e in related_events if e.event_type == "MessageEdited"]),
        }

        return ExactEvent(
            event_id=event_id,
            event_type=latest_event.event_type,
            author=msg.author,
            content=msg.content,
            timestamp=msg.last_modified_at.isoformat(),
            metadata=metadata,
        )
