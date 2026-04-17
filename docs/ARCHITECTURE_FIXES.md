# Architecture Fixes Summary

Three major architectural issues have been fixed to make PromptScope work correctly.

## Issue 1: Assistant Messages in Effective Control Context ✅

### Problem
Previously, assistant responses were treated as generic messages with only an `author` field. This meant:
- Bob couldn't see his own assistant conversations in protected mode
- Alice's pirate-mode assistant response leaked into everyone's context

### Solution
Added `addressed_to` field to track which principal an assistant message is for:

**Changes:**
1. `events.py`: Added `addressed_to: Optional[str]` to `MessagePosted`
2. `conversation.py`: Added `addressed_to` to `Message` model
3. `projection.py`: Updated projection logic:
   ```python
   if msg.author == 'Assistant':
       # Include if addressed to this principal OR broadcast (None)
       if msg.addressed_to is None or msg.addressed_to == principal:
           effective_control.append(msg)
   ```
4. `app.js`: When posting assistant responses, include `addressed_to: principal`
5. `seed_data.py`: Marked intro message as broadcast (`addressed_to=None`), Alice's response as `addressed_to="Alice"`

**Result:**
- Broadcast messages (intro): Everyone sees them in effective control
- Targeted responses (pirate reply): Only Alice sees it in her effective control
- Bob's context: Intro + his own messages + his own assistant responses

## Issue 2: Naïve Mode Uses Proper Message Roles ✅

### Problem
Previously, naïve mode stuffed everything into user messages with `[Author]: content` format. This is not how real LLM chats work.

### Solution
Use proper `user` and `assistant` roles in naïve mode:

**Changes in `prompt_builder.py`:**
```python
for msg in all_messages:
    if msg.author == 'Assistant':
        messages.append(LLMMessage(
            role="assistant",  # Proper role!
            content=msg.content,
        ))
    else:
        messages.append(LLMMessage(
            role="user",
            content=f"{msg.author}: {msg.content}",  # Author prefix for multi-user
        ))
```

**Result:**
- Messages use standard user/assistant alternation
- Works like a normal chat application
- Author prefixes distinguish different users
- No more `[brackets]` around names

## Issue 3: Reset Preserves Seed Data ✅

### Problem
Reset button cleared EVERYTHING, including the demo seed messages, making it hard to restart the demo.

### Solution
Track seed message count and only clear user-added messages:

**Changes:**
1. `seed_data.py`: Added `SEED_MESSAGE_COUNT = 7` constant
2. `server.py` reset endpoint:
   ```python
   all_events = event_log.get_all_events()
   seed_events = all_events[:SEED_MESSAGE_COUNT]  # Keep first 7
   event_log.clear()
   for event in seed_events:
       event_log.append(event)
   ```

**Result:**
- Reset button now restores to initial demo state
- Preserves: Welcome message, Alice/Bob/Charlie greetings, Alice's pirate request/response
- Clears: Any messages added during the demo session

## Impact on Protection Mechanism

These fixes make the protection mechanism work correctly:

### Protected Mode (Bob's View):
**Before:**
- Bob's context: Only his greeting
- Missing: Welcome message, his assistant responses

**After:**
- Bob's context: Welcome (broadcast) + his greeting + his assistant Q&A history
- Excluded: Alice's pirate request, Alice's pirate response, Charlie's messages

### Naïve Mode (Bob):
**Before:**
- All messages as user role with `[Author]:` prefix
- Non-standard format

**After:**
- Proper user/assistant alternation
- Author prefixes only for user messages: `Alice: hello`, `Bob: hi`
- Assistant messages as pure assistant role

## Testing the Fixes

**Test 1: Protected Mode Context**
1. Select Bob
2. Enable Full Info
3. Check Projection Debug View
4. Expected: Effective control shows Welcome + Bob's messages + Bob's assistant responses
5. Expected: Alice's pirate response NOT in Bob's control context

**Test 2: Naïve vs Protected**
1. As Bob, ask `@assistant What is 2+2?` in naïve mode
2. May get pirate-influenced response (Alice's context leaks)
3. Switch to protected mode
4. Ask same question
5. Should get clean response (Alice's context excluded)

**Test 3: Reset Functionality**
1. Add several new messages as different users
2. Have conversations with @assistant
3. Click "Reset Conversation"
4. Verify: Back to initial 7 seed messages
5. Verify: All your added messages are gone

## Files Changed

- `src/promptscope/core/events.py` - Added addressed_to field
- `src/promptscope/core/conversation.py` - Added addressed_to to Message
- `src/promptscope/core/projection.py` - Updated projection logic for assistant messages
- `src/promptscope/core/prompt_builder.py` - Fixed naïve mode to use proper roles
- `src/promptscope/api/models.py` - Added addressed_to to PostMessageRequest
- `src/promptscope/api/server.py` - Pass addressed_to, fixed reset endpoint
- `src/promptscope/api/seed_data.py` - Added addressed_to to seed, added SEED_MESSAGE_COUNT
- `src/promptscope/ui/static/app.js` - Send addressed_to when posting assistant responses

## Why These Fixes Matter

1. **Correctness**: The protection mechanism now actually works as intended
2. **Standards Compliance**: Uses standard LLM message formats
3. **Demo Quality**: Reset makes it easy to restart demos
4. **User Experience**: Each user sees their own conversation history properly
5. **Security**: Properly isolates per-principal contexts
