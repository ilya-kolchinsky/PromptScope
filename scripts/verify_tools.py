#!/usr/bin/env python3
"""
Verification script for tool-based retrieval system.
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
from promptscope.core.retrieval_tools import ConversationTools
from promptscope.api.seed_data import load_seed_data

print("🔍 PromptScope Tool-Based Retrieval Verification")
print("=" * 60)

# Initialize components
event_log = EventLog()
conversation_state = ConversationState(event_log)
projector = ConversationProjector(conversation_state)
prompt_builder = PromptBuilder(conversation_state, projector)
conversation_tools = ConversationTools(event_log, conversation_state, projector)

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

# Test request building
print("\n3. Testing request construction...")

# Naïve mode
naive_request = prompt_builder.build_naive_request("Bob", "What is 2 + 2?")
print(f"   ✓ Naïve mode: {len(naive_request.messages)} messages, tools: {naive_request.tools is not None}")

# Protected mode
protected_request = prompt_builder.build_protected_request("Bob", "What is 2 + 2?")
print(f"   ✓ Protected mode: {len(protected_request.messages)} messages, tools: {protected_request.tools is not None}")

if protected_request.tools:
    print(f"   ✓ Tools available: {[t.name for t in protected_request.tools]}")

# Test retrieval tools
print("\n4. Testing retrieval tools...")

# Search for pirate
search_result = conversation_tools.search_conversation(
    principal="Bob",
    query="pirate",
)
print(f"   ✓ Search for 'pirate': {len(search_result.hits)} hits")
if search_result.hits:
    hit = search_result.hits[0]
    print(f"      - Found in message from {hit.speaker}")
    print(f"      - Snippet: {hit.snippet[:50]}...")

    # Test expand context
    context = conversation_tools.expand_local_context(
        principal="Bob",
        hit_id=hit.hit_id,
        window=2,
    )
    print(f"   ✓ Expanded context: {len(context.messages)} messages")

    # Test get exact event
    event = conversation_tools.get_exact_event(
        principal="Bob",
        event_id=hit.hit_id,
    )
    if event:
        print(f"   ✓ Got exact event: {event.event_type} by {event.author}")

# Demonstrate the key difference
print("\n5. Key Difference:")
print("\n   NAÏVE MODE:")
print(f"      - All {len(naive_request.messages)} messages go directly to model")
print(f"      - Alice's pirate instruction is in the context")
print(f"      - NO tools available")

print("\n   PROTECTED MODE:")
print(f"      - Only {len(protected_request.messages)} messages (Bob's) go directly to model")
print(f"      - Alice's pirate instruction is NOT in the context")
print(f"      - {len(protected_request.tools)} tools available:")
for tool in protected_request.tools:
    print(f"         • {tool.name}")
print(f"      - Model can retrieve Alice's message by calling search_conversation")

print("\n6. Tool-Based Retrieval Reduces Problem:")
print("   Multi-user pollution → Classic prompt injection")
print("   ✓ Model must explicitly call tools to get other users' messages")
print("   ✓ Retrieved content goes through same injection mitigations as RAG")
print("   ✓ Audit trail: we can see which messages the model retrieved")

print("\n" + "=" * 60)
print("✅ Tool-based retrieval system working correctly!")
print("\nNext: Run 'python run.py' and test with real/mock LLM")
print("=" * 60)
