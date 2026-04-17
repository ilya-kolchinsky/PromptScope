"""
Simple retrieval over visible observation context.

This module implements basic keyword search over other users' messages.
No advanced vector search - just simple, reliable full-text matching.
"""

from typing import Optional
from pydantic import BaseModel

from .conversation import Message
from .projection import ConversationProjector


class SearchHit(BaseModel):
    """A single search result."""

    message: Message
    snippet: str
    match_positions: list[int]


class SearchResults(BaseModel):
    """Results from a search query."""

    query: str
    principal: str
    hits: list[SearchHit]
    total_searched: int


class ConversationRetrieval:
    """
    Simple keyword-based retrieval over visible observation context.

    For a given principal, searches only through other users' messages
    (the visible observation context).
    """

    def __init__(self, projector: ConversationProjector):
        self.projector = projector

    def search(
        self,
        principal: str,
        query: str,
        context_chars: int = 100,
    ) -> SearchResults:
        """
        Search the visible observation context for a keyword or phrase.

        Args:
            principal: The user performing the search
            query: The search query (case-insensitive substring match)
            context_chars: Number of characters to include around matches in snippets

        Returns:
            SearchResults with matching messages and snippets
        """
        projected_view = self.projector.project_for_principal(principal)
        visible_messages = projected_view.visible_observation_context

        hits = []
        query_lower = query.lower()

        for msg in visible_messages:
            content_lower = msg.content.lower()

            # Simple substring search
            if query_lower in content_lower:
                # Find all match positions
                match_positions = []
                start = 0
                while True:
                    pos = content_lower.find(query_lower, start)
                    if pos == -1:
                        break
                    match_positions.append(pos)
                    start = pos + 1

                # Create a snippet around the first match
                if match_positions:
                    first_match = match_positions[0]
                    snippet_start = max(0, first_match - context_chars)
                    snippet_end = min(len(msg.content), first_match + len(query) + context_chars)

                    snippet = msg.content[snippet_start:snippet_end]

                    # Add ellipsis if truncated
                    if snippet_start > 0:
                        snippet = "..." + snippet
                    if snippet_end < len(msg.content):
                        snippet = snippet + "..."

                    hits.append(SearchHit(
                        message=msg,
                        snippet=snippet,
                        match_positions=match_positions,
                    ))

        return SearchResults(
            query=query,
            principal=principal,
            hits=hits,
            total_searched=len(visible_messages),
        )

    def get_message_context(
        self,
        principal: str,
        logical_msg_id: str,
        before: int = 2,
        after: int = 2,
    ) -> list[Message]:
        """
        Get surrounding context for a specific message.

        Args:
            principal: The user requesting context
            logical_msg_id: The message ID to get context for
            before: Number of messages before to include
            after: Number of messages after to include

        Returns:
            List of messages including the target and its context
        """
        all_messages = self.projector.get_all_messages_for_principal(principal)

        # Find the target message index
        target_idx = None
        for i, msg in enumerate(all_messages):
            if msg.logical_msg_id == logical_msg_id:
                target_idx = i
                break

        if target_idx is None:
            return []

        # Get surrounding messages
        start_idx = max(0, target_idx - before)
        end_idx = min(len(all_messages), target_idx + after + 1)

        return all_messages[start_idx:end_idx]
