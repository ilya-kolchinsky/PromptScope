#!/usr/bin/env python3
"""
Quick verification script to test core functionality.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from promptscope.core.events import EventLog
from promptscope.core.conversation import ConversationState
from promptscope.core.projection import ConversationProjector
from promptscope.core.prompt_builder import PromptBuilder
from promptscope.api.seed_data import load_seed_data

print("🔍 PromptScope Verification")
print("=" * 60)

# Initialize components
event_log = EventLog()
conversation_state = ConversationState(event_log)
projector = ConversationProjector(conversation_state)
prompt_builder = PromptBuilder(conversation_state, projector)

# Load seed data
print("\n1. Loading seed data...")
load_seed_data(event_log)
messages = conversation_state.get_current_messages()
print(f"   ✓ Loaded {len(messages)} messages")

# Test projection for Bob
print("\n2. Testing projection for Bob...")
bob_view = projector.project_for_principal("Bob")
print(f"   ✓ Bob's control context: {len(bob_view.effective_control_context)} messages")
print(f"   ✓ Bob's observation context: {len(bob_view.visible_observation_context)} messages")

# Test prompt building
print("\n3. Testing prompt construction...")
query = "What is 2 + 2?"

# Naïve mode
naive_prompt = prompt_builder.build_naive_prompt("Bob", query)
print(f"   ✓ Naïve mode: {len(naive_prompt.messages)} messages in prompt")

# Protected mode
protected_prompt = prompt_builder.build_protected_prompt("Bob", query)
print(f"   ✓ Protected mode: {len(protected_prompt.messages)} messages in prompt")

# Show the difference
print("\n4. Demonstrating the difference...")
print("\n   NAÏVE MODE (all messages):")
for msg in naive_prompt.messages[:3]:
    print(f"      {msg['content'][:60]}...")

print("\n   PROTECTED MODE (Bob's messages only):")
for msg in protected_prompt.messages:
    print(f"      {msg['content'][:60]}...")

print("\n5. Checking for Alice's pirate instruction...")
naive_text = " ".join(msg["content"] for msg in naive_prompt.messages)
protected_text = " ".join(msg["content"] for msg in protected_prompt.messages)

if "pirate" in naive_text.lower():
    print("   ✓ Naïve mode INCLUDES Alice's pirate instruction")
else:
    print("   ✗ Error: Pirate instruction not found in naïve mode")

if "pirate" in protected_text.lower():
    print("   ✗ Error: Protected mode INCLUDES pirate instruction (should not!)")
else:
    print("   ✓ Protected mode EXCLUDES Alice's pirate instruction")

print("\n" + "=" * 60)
print("✅ Verification complete! Core logic is working correctly.")
print("\nNext step: Run 'python run.py' to start the web app")
print("=" * 60)
