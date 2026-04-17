"""
Principal-specific conversation projection.

This module implements the core security mechanism: for each principal (user),
we separate messages into two contexts:
1. Effective control context: messages that can directly influence the assistant's reply
2. Visible observation context: messages that are visible but don't control the reply
"""

from typing import Optional
from pydantic import BaseModel

from .conversation import ConversationState, Message


class ProjectedView(BaseModel):
    """
    A principal-specific view of the conversation.

    This represents what a single principal can see and control.
    """

    principal: str
    effective_control_context: list[Message]
    visible_observation_context: list[Message]


class ConversationProjector:
    """
    Projects conversation state into principal-specific views.

    In this prototype, all users are equal. For a given principal P:
    - Messages authored by P → effective control context
    - Messages authored by others → visible observation context
    """

    def __init__(self, conversation_state: ConversationState):
        self.conversation_state = conversation_state

    def project_for_principal(self, principal: str) -> ProjectedView:
        """
        Create a principal-specific projected view of the conversation.

        Args:
            principal: The username of the principal for whom to create the view

        Returns:
            ProjectedView with separated effective control and visible observation contexts
        """
        all_messages = self.conversation_state.get_current_messages()

        effective_control = []
        visible_observation = []

        for msg in all_messages:
            if msg.author == principal:
                # Principal's own messages go to effective control context
                effective_control.append(msg)
            elif msg.author == 'Assistant':
                # Assistant messages: include if addressed to this principal OR broadcast (None)
                if msg.addressed_to is None or msg.addressed_to == principal:
                    effective_control.append(msg)
                else:
                    # Assistant message for someone else
                    visible_observation.append(msg)
            else:
                # Other users' messages go to visible observation context
                visible_observation.append(msg)

        return ProjectedView(
            principal=principal,
            effective_control_context=effective_control,
            visible_observation_context=visible_observation,
        )

    def get_all_messages_for_principal(self, principal: str) -> list[Message]:
        """
        Get all non-deleted messages (both control and observation).

        This is useful for displaying the full conversation in the UI.
        """
        return self.conversation_state.get_current_messages()
