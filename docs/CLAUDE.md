# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**PromptScope** is a proof-of-concept demonstrating **reduction-based security** for multi-user LLM chats.

**Core Problem**: Multi-user context pollution - one user's messages automatically influence the LLM's responses to other users.

**Solution**: Reduce this novel problem to classic prompt injection by:
1. Only including the principal's own messages in default context
2. Moving other users' messages behind a retrieval interface
3. Giving the model tools to search/retrieve when needed

If retrieved content contains malicious instructions, it becomes classic prompt injection (which has known mitigations).

## Running the Application

```bash
# Install dependencies
pip install -e ".[all]"  # All providers
# OR: pip install -e ".[anthropic]"  # Claude only
# OR: pip install -e ".[openai]"     # GPT-4 only
# OR: pip install -e .                # Mock mode only

# Run verification
python scripts/verify_tools.py

# Start server (mock mode, no API key needed)
python run.py

# With real LLM
# Edit .env: LLM_PROVIDER=anthropic (or openai, vllm, ollama)
python run.py
```

Access at: http://localhost:8000

## Architecture

### Core Components (src/promptscope/core/)

**events.py**: Event log system
- `MessagePosted`, `MessageEdited`, `MessageDeleted` events
- `EventLog`: Append-only log (single source of truth)

**conversation.py**: State projection
- `ConversationState`: Projects event log into current message state

**projection.py**: Principal-specific views
- `ConversationProjector.project_for_principal()` - THE CORE SECURITY MECHANISM
- Line 56: `if msg.author == principal` - splits into control vs observation
- `ProjectedView`: effective_control_context + visible_observation_context

**retrieval_tools.py**: Tool implementations for the model
- `ConversationTools.search_conversation()` - Search with filters
- `ConversationTools.expand_local_context()` - Get surrounding messages
- `ConversationTools.get_exact_event()` - Get verbatim event

**tool_definitions.py**: Tool schemas
- Defines the 3 tools the model can call in protected mode

**prompt_builder.py**: Request construction
- `build_naive_request()`: All messages in context, no tools
- `build_protected_request()`: Only principal's messages + retrieval tools

**llm_client.py**: Multi-provider LLM client
- Base class: `LLMClient` with `generate()` and `generate_with_tools()`
- Providers: Mock, Anthropic, OpenAI, vLLM, Ollama
- `generate_with_tools()` implements the tool calling loop

**llm_types.py**: Common types
- `GenerateRequest`, `GenerateResponse`, `ToolDefinition`, `ToolCall`, `ToolResult`

### API Layer (src/promptscope/api/)

**server.py**: FastAPI backend
- Line 227-265: Tool executor maps tool calls to `ConversationTools` methods
- Line 270: `generate_with_tools()` for protected mode with automatic tool handling
- Endpoints: messages, projection, assistant, retrieval, status

**models.py**: Pydantic request/response schemas

**seed_data.py**: Demo data (Alice pirate scenario)

### UI (src/promptscope/ui/static/)

- **index.html**: Main UI
- **style.css**: Styling
- **app.js**: Frontend logic

## Key Design Principles

1. **Reduction-Based Security**: Transform unsolved problem → solved problem
2. **Event Sourcing**: Append-only log as single source of truth
3. **Tool-Based Retrieval**: Model must explicitly call tools to access other users' messages
4. **Multi-Provider**: Works with Anthropic, OpenAI, vLLM, Ollama, mock
5. **Auditable**: Tool calls create visible audit trail

## The Tool Calling Flow

**Protected Mode (with real LLM supporting tools):**
```
1. User asks question
2. Build request: principal's messages + 3 retrieval tools
3. Send to LLM
4. LLM may call search_conversation("relevant keywords")
5. Tool executor runs ConversationTools.search_conversation()
6. Returns results to LLM
7. LLM incorporates and responds
8. (Loop continues if more tool calls)
```

**Tool Executor** (server.py:227-265):
- Maps tool names to `ConversationTools` methods
- Handles argument parsing (including datetime conversion)
- Returns JSON results

**LLM Client** (llm_client.py:45-104):
- `generate_with_tools()` implements the loop
- Adds assistant message with tool calls to conversation
- Executes tools via executor callback
- Adds tool results to conversation
- Continues until final answer or max iterations

## Code Locations for Key Mechanisms

| Mechanism | File | Lines | What It Does |
|-----------|------|-------|--------------|
| **Principal check** | `projection.py` | 56 | `if msg.author == principal` - the security decision |
| **Context separation** | `projection.py` | 52-61 | Splits into control vs observation |
| **Tool definitions** | `tool_definitions.py` | 15-74 | Schemas for 3 retrieval tools |
| **Tool implementation** | `retrieval_tools.py` | 77-287 | search, expand, get_exact |
| **Protected request** | `prompt_builder.py` | 75-120 | Only principal's msgs + tools |
| **Naïve request** | `prompt_builder.py` | 35-73 | All messages, no tools |
| **Tool executor** | `server.py` | 227-265 | Maps tool calls to methods |
| **Tool calling loop** | `llm_client.py` | 45-104 | Automatic multi-turn execution |
| **Anthropic tools** | `llm_client.py` | 139-205 | Anthropic-specific format |
| **OpenAI tools** | `llm_client.py` | 263-338 | OpenAI-specific format |

## Development Workflow

**Add a new retrieval tool:**
1. Add method to `ConversationTools` in `retrieval_tools.py`
2. Add schema to `get_retrieval_tools()` in `tool_definitions.py`
3. Add case in tool executor (server.py:227-265)

**Add a new LLM provider:**
1. Create class extending `LLMClient` in `llm_client.py`
2. Implement `generate()` with provider-specific API
3. Handle tool calling in provider-specific format
4. Add to `create_llm_client()` factory

**Modify projection logic:**
1. Edit `ConversationProjector.project_for_principal()` in `projection.py`
2. Verify in `verify_tools.py`

**Add API endpoints:**
1. Define models in `api/models.py`
2. Add endpoint in `api/server.py`
3. Update UI in `ui/static/app.js`

## Testing

```bash
# Verify core logic and tools
python scripts/verify_tools.py

# Check imports
python -c "import sys; sys.path.insert(0, 'src'); from promptscope.api.server import app"

# Run server
python run.py
```

## Important Invariants

- Event log is append-only
- Projection logic is pure (no side effects)
- Protected mode: only principal's messages in default context
- Protected mode: always provides retrieval tools (if provider supports them)
- Tool executor must validate principal for all tool calls
- Retrieved messages can still contain injection attacks (by design - this is the reduction)

## Configuration

Environment variables (.env):
- `LLM_PROVIDER`: "mock", "anthropic", "openai", "vllm", "ollama"
- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`
- `OPENAI_API_KEY`, `OPENAI_MODEL`
- `VLLM_BASE_URL`, `VLLM_MODEL`
- `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
- `HOST`, `PORT`

## The Core Insight

**Before**: Multi-user pollution (novel, unsolved)
- Alice's message → automatically in Bob's context → affects Bob's response

**After**: Classic prompt injection (known, solvable)
- Alice's message → behind retrieval tool → model calls tool → retrieves Alice's message → affects Bob's response

**Why better**: We can now apply known mitigations:
- Input sanitization on retrieved content
- Sandboxing
- Audit logging of tool calls
- Rate limiting
- Content filtering

## License

Apache License 2.0
