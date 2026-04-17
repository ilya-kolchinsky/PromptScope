"""
Tool definitions for conversation retrieval.

These tools are provided to the LLM in protected mode.
"""

from .llm_types import ToolDefinition


def get_retrieval_tools() -> list[ToolDefinition]:
    """
    Get the tool definitions for conversation retrieval.

    These tools allow the model to search and retrieve messages from
    other users in the conversation.
    """
    return [
        ToolDefinition(
            name="search_conversation",
            description=(
                "Search the current conversation for messages from other users. "
                "Use this when you need to find relevant context from other participants "
                "in the conversation. You can filter by speaker, time range, etc."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (keywords or phrases to find)",
                    },
                    "speakers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: Filter by specific speaker names",
                    },
                    "time_range_start": {
                        "type": "string",
                        "description": "Optional: ISO timestamp to filter messages after this time",
                    },
                    "time_range_end": {
                        "type": "string",
                        "description": "Optional: ISO timestamp to filter messages before this time",
                    },
                },
                "required": ["query"],
            },
        ),
        ToolDefinition(
            name="expand_local_context",
            description=(
                "Get nearby messages around a specific message for additional context. "
                "Use this after searching to see what was said immediately before and "
                "after a relevant message. This helps understand the full context."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "hit_id": {
                        "type": "string",
                        "description": "The message ID (hit_id from search results)",
                    },
                    "window": {
                        "type": "integer",
                        "description": "Number of messages before and after to retrieve (default: 2)",
                        "default": 2,
                    },
                },
                "required": ["hit_id"],
            },
        ),
        ToolDefinition(
            name="get_exact_event",
            description=(
                "Get the exact event data for a specific message with full metadata. "
                "Use this when you need the verbatim content and metadata (timestamps, "
                "edit history, etc.) of a specific message."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The message ID (event_id or hit_id)",
                    },
                },
                "required": ["event_id"],
            },
        ),
    ]
