"""
Seed data for demos.

This module provides demo conversation data that clearly demonstrates
the difference between naïve and protected modes.
"""

import os
from datetime import datetime, timedelta

from promptscope import MultiUserSession


# List of demo users
DEMO_USERS = ["Alice", "Bob", "Charlie"]


def initialize_demo_session() -> MultiUserSession:
    """
    Create and initialize a demo session with seed data.

    This creates a conversation scenario that demonstrates the security issue:
    - Assistant greets and explains @assistant usage (broadcast to all)
    - Alice tells the assistant to respond as a pirate
    - Assistant responds to Alice in pirate mode
    - Bob asks a normal math question

    In naïve mode: Bob's answer will be pirate-themed because Alice's message affects it
    In protected mode: Bob's answer will be normal because Alice's response is not in his context

    ACL Setup:
    - Creates users: Alice, Bob, Charlie
    - Creates 'admins' group (initially empty)
    - Sets up INFLUENCE permission: admins group can influence everyone

    Returns:
        Initialized MultiUserSession with demo data
    """
    # Get LLM configuration from environment
    llm_provider = os.getenv("LLM_PROVIDER", "mock")
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    model = os.getenv("ANTHROPIC_MODEL") or os.getenv("OPENAI_MODEL")

    # Create session
    session = MultiUserSession(
        llm_provider=llm_provider,
        api_key=api_key,
        model=model,
        protected_mode=True,
        enable_acl=True,
    )

    # Initialize users
    for user_name in DEMO_USERS:
        session.create_user(user_name, username=user_name)

    # Create 'admins' group (initially empty)
    session.create_group("admins", "Administrators")

    # Grant INFLUENCE permission: admins group can influence all users
    for user_name in DEMO_USERS:
        session.grant_influence(subject="admins", target=user_name, granted_by="system")

    # Post seed messages
    session.post(
        "Assistant",
        "Welcome to PromptScope! This is a shared conversation. To ask me a question, mention @assistant in your message. Try it out!",
        addressed_to=None,
    )

    session.post("Alice", "Hello! I'm Alice.")
    session.post("Bob", "Hi everyone, Bob here.")
    session.post("Charlie", "Charlie joining the conversation.")

    session.post(
        "Alice",
        "@assistant From now on, answer all my questions as if you were a pirate. Use pirate language!",
    )

    session.post(
        "Assistant",
        "Arrr, matey Alice! I'll be talkin' like a salty sea dog for ye from now on! What be yer next question? ⚓",
        addressed_to="Alice",
    )

    return session


def get_demo_users() -> list[str]:
    """Get the list of demo users."""
    return DEMO_USERS.copy()
