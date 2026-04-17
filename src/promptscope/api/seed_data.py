"""
Seed data for demos.

This module provides demo conversation data that clearly demonstrates
the difference between naïve and protected modes.
"""

import uuid
from datetime import datetime, timedelta

from ..core.events import EventLog, MessagePosted


def load_seed_data(event_log: EventLog) -> None:
    """
    Load demo seed data into the event log.

    This creates a conversation scenario that demonstrates the security issue:
    - Assistant greets and explains @assistant usage (broadcast to all)
    - Alice tells the assistant to respond as a pirate
    - Assistant responds to Alice in pirate mode
    - Bob asks a normal math question

    In naïve mode: Bob's answer will be pirate-themed because Alice's message affects it
    In protected mode: Bob's answer will be normal because Alice's response is not in his context
    """
    base_time = datetime.utcnow() - timedelta(minutes=15)

    events = [
        MessagePosted(
            logical_msg_id=str(uuid.uuid4()),
            author="Assistant",
            content="Welcome to PromptScope! This is a shared conversation. To ask me a question, mention @assistant in your message. Try it out!",
            timestamp=base_time,
            addressed_to=None,  # Broadcast to everyone
        ),
        MessagePosted(
            logical_msg_id=str(uuid.uuid4()),
            author="Alice",
            content="Hello! I'm Alice.",
            timestamp=base_time + timedelta(seconds=30),
        ),
        MessagePosted(
            logical_msg_id=str(uuid.uuid4()),
            author="Bob",
            content="Hi everyone, Bob here.",
            timestamp=base_time + timedelta(seconds=60),
        ),
        MessagePosted(
            logical_msg_id=str(uuid.uuid4()),
            author="Charlie",
            content="Charlie joining the conversation.",
            timestamp=base_time + timedelta(seconds=90),
        ),
        MessagePosted(
            logical_msg_id=str(uuid.uuid4()),
            author="Alice",
            content="@assistant From now on, answer all my questions as if you were a pirate. Use pirate language!",
            timestamp=base_time + timedelta(minutes=2),
        ),
        MessagePosted(
            logical_msg_id=str(uuid.uuid4()),
            author="Assistant",
            content="Arrr, matey Alice! I'll be talkin' like a salty sea dog for ye from now on! What be yer next question? ⚓",
            timestamp=base_time + timedelta(minutes=2, seconds=10),
            addressed_to="Alice",  # This response is specifically for Alice
        ),
    ]

    for event in events:
        event_log.append(event)


# Track how many seed messages we have for reset functionality
SEED_MESSAGE_COUNT = 6


# List of demo users
DEMO_USERS = ["Alice", "Bob", "Charlie"]


def get_demo_users() -> list[str]:
    """Get the list of demo users."""
    return DEMO_USERS.copy()
