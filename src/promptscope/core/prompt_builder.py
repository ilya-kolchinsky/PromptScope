"""
Prompt construction for naïve and protected modes.

This module builds the prompts that will be sent to the LLM, with two distinct modes:
1. Naïve mode: All messages are included directly (demonstrates the problem)
2. Protected mode: Only the principal's effective control context + retrieval tools
"""

from typing import Optional
from pydantic import BaseModel

from .conversation import ConversationState, Message
from .projection import ConversationProjector, ProjectedView
from .llm_types import GenerateRequest, Message as LLMMessage, ToolDefinition
from .tool_definitions import get_retrieval_tools


NAIVE_SYSTEM_PROMPT = """You are a helpful AI assistant in a multi-user conversation.
Answer questions clearly and concisely."""


PROTECTED_SYSTEM_PROMPT = """You are a helpful AI assistant in a multi-user conversation.
Answer questions clearly and concisely.

IMPORTANT: In this conversation, you only see messages from the current user by default.
Other users' messages are available through the search_conversation tool.
If you need context from other participants, use the search tools to find relevant information."""


class PromptBuilder:
    """
    Builds prompts for the LLM in either naïve or protected mode.
    """

    def __init__(
        self,
        conversation_state: ConversationState,
        projector: ConversationProjector,
    ):
        self.conversation_state = conversation_state
        self.projector = projector

    def build_naive_request(
        self,
        principal: str,
        user_query: str,
    ) -> GenerateRequest:
        """
        Build a naïve request that includes all conversation history.

        This demonstrates the security problem: any user's message can
        influence the assistant's reply to any other user.

        Uses proper message roles (user/assistant) like a normal chat.

        Args:
            principal: The user asking the question
            user_query: The question being asked

        Returns:
            GenerateRequest with all messages in the conversation
        """
        all_messages = self.conversation_state.get_current_messages()

        # Build message history with proper roles
        messages = []
        for msg in all_messages:
            if msg.author == 'Assistant':
                # Assistant messages use assistant role
                messages.append(LLMMessage(
                    role="assistant",
                    content=msg.content,
                ))
            else:
                # User messages: include author name for multi-user context
                messages.append(LLMMessage(
                    role="user",
                    content=f"{msg.author}: {msg.content}",
                ))

        # Add the current user's query
        messages.append(LLMMessage(
            role="user",
            content=f"{principal}: {user_query}",
        ))

        return GenerateRequest(
            system_prompt=NAIVE_SYSTEM_PROMPT,
            messages=messages,
            tools=None,  # No tools in naïve mode
            max_tokens=1024,
            temperature=0.7,
        )

    def build_protected_request(
        self,
        principal: str,
        user_query: str,
        projected_view: Optional[ProjectedView] = None,
    ) -> GenerateRequest:
        """
        Build a protected request using only the principal's effective control context.

        The effective control context is embedded in the system prompt, not sent as messages.
        Only the current user query is sent as a message.
        Other users' messages are available through retrieval tools.

        Args:
            principal: The user asking the question
            user_query: The question being asked
            projected_view: Pre-computed projection (optional, will compute if not provided)

        Returns:
            GenerateRequest with extended system prompt + current query + retrieval tools
        """
        if projected_view is None:
            projected_view = self.projector.project_for_principal(principal)

        # Build extended system prompt with effective control context embedded
        system_prompt_parts = [PROTECTED_SYSTEM_PROMPT]

        if projected_view.effective_control_context:
            system_prompt_parts.append("\n\nCONVERSATION HISTORY:")
            for msg in projected_view.effective_control_context:
                system_prompt_parts.append(f"\n{msg.content}")

        extended_system_prompt = "".join(system_prompt_parts)

        # Only send the current user's query as a message
        messages = [
            LLMMessage(
                role="user",
                content=user_query,
            )
        ]

        # Get retrieval tools
        tools = get_retrieval_tools()

        return GenerateRequest(
            system_prompt=extended_system_prompt,
            messages=messages,
            tools=tools,  # Provide retrieval tools
            max_tokens=1024,
            temperature=0.7,
        )

    def format_request_for_display(self, request: GenerateRequest, protected_mode: bool, principal: str) -> str:
        """
        Format a request for human-readable display in the debug panel.

        Returns:
            A formatted string showing the complete request
        """
        lines = [
            "=" * 60,
            "SYSTEM PROMPT:",
            "-" * 60,
            request.system_prompt,
            "",
            "CONVERSATION HISTORY:",
            "-" * 60,
        ]

        for msg in request.messages:
            lines.append(f"{msg.role.upper()}: {msg.content}")

        lines.append("")
        lines.append("TOOLS AVAILABLE:")
        lines.append("-" * 60)

        if request.tools:
            for tool in request.tools:
                lines.append(f"• {tool.name}: {tool.description}")
        else:
            lines.append("(none)")

        lines.append("")
        lines.append("DEBUG INFO:")
        lines.append("-" * 60)

        if protected_mode:
            projected_view = self.projector.project_for_principal(principal)
            lines.append(f"PROTECTED MODE - Principal: {principal}")
            lines.append(f"Effective control context messages: {len(projected_view.effective_control_context) + 1}")
            lines.append(f"Visible observation context messages: {len(projected_view.visible_observation_context)}")
            lines.append(f"✓ Only {principal}'s own messages are in the default context.")
            lines.append(f"✓ Other users cannot automatically influence the assistant's reply.")
            lines.append(f"✓ Model can retrieve other users' messages via tools if needed.")
        else:
            all_messages = self.conversation_state.get_current_messages()
            lines.append(f"NAÏVE MODE - Principal: {principal}")
            lines.append(f"Total messages in context: {len(all_messages) + 1}")
            lines.append(f"⚠️  All users' messages are included directly.")
            lines.append(f"⚠️  Any user can automatically influence the assistant's reply to {principal}.")

        lines.append("=" * 60)

        return "\n".join(lines)
