# Ollama Configuration Notes

## Fixed Issues

### 1. Base URL Must Use `/v1` Endpoint

**Wrong:**
```bash
OLLAMA_BASE_URL=http://localhost:11434/api
```

**Correct:**
```bash
OLLAMA_BASE_URL=http://localhost:11434/v1
```

**Why:** Ollama has two API interfaces:
- `/api/*` - Native Ollama API format
- `/v1/*` - OpenAI-compatible API format

Our implementation uses the OpenAI SDK for simplicity, so it needs the `/v1` endpoint.

### 2. Model Names Need Full Tags

**Wrong:**
```bash
OLLAMA_MODEL=qwen3.5
```

**Correct:**
```bash
OLLAMA_MODEL=qwen3.5:latest
```

**Why:** Ollama requires full model tags including the version/quantization suffix.

### 3. Reasoning Models Show Thinking Process

Some Ollama models (like `qwen3.5`) are reasoning models that show their thinking process in the response. This is expected behavior but can be verbose.

**For cleaner responses, use non-reasoning models:**
```bash
OLLAMA_MODEL=llama3.2:3b          # Clean, direct responses
OLLAMA_MODEL=llama3.1:8b          # Larger, more capable
OLLAMA_MODEL=phi:latest           # Smaller, faster
```

## Recommended Configuration

For best demo experience with PromptScope:

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.2:3b
```

## Tool Calling Support

**Note:** Most Ollama models do NOT support tool/function calling natively. This means:
- In **protected mode**, the model won't be able to call the retrieval tools
- The app will still work, but won't demonstrate the tool-based retrieval
- For tool calling demo, use Anthropic or OpenAI providers

## Testing Your Setup

```bash
# Test if Ollama is running
curl http://localhost:11434/api/tags

# Test OpenAI-compatible endpoint
curl http://localhost:11434/v1/models

# Test generation
python -c "
import sys
sys.path.insert(0, 'src')
from dotenv import load_dotenv
load_dotenv()
from promptscope.core.llm_client import create_llm_client
from promptscope.core.llm_types import GenerateRequest, Message as LLMMessage

client = create_llm_client()
request = GenerateRequest(
    system_prompt='You are helpful.',
    messages=[LLMMessage(role='user', content='Say hello')],
    tools=None,
)
response = client.generate(request)
print(response.content)
"
```

## Your Models

Available models on your system:
- `qwen3.5:latest` - Reasoning model (verbose)
- `llama3.2:3b` - Recommended for demo
- `llama3.1:8b` - Larger, more capable
- `phi:latest` - Small and fast
- `codellama:*` - For code generation

Choose based on your needs:
- **Speed**: `phi:latest`
- **Quality + Speed balance**: `llama3.2:3b` ✓ Recommended
- **Quality**: `llama3.1:8b`
- **Reasoning**: `qwen3.5:latest`
