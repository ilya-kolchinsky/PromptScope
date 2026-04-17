# Installation Guide

PromptScope uses `pyproject.toml` for dependency management with optional extras for different LLM providers.

## Installation Options

### 1. Core Only (Mock Mode)

For demos and development without any LLM API calls:

```bash
pip install -e .
```

**Includes:**
- FastAPI web server
- Mock LLM client
- All core functionality
- UI

**Use when:**
- Testing the UI and projection logic
- Demonstrating the concept without API costs
- Developing new features

### 2. With Anthropic (Claude)

For using Claude models with tool calling:

```bash
pip install -e ".[anthropic]"
```

**Includes:**
- Core dependencies
- `anthropic` SDK

**Configure:**
```bash
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=your_key_here
```

### 3. With OpenAI (GPT-4)

For using GPT-4 models with function calling:

```bash
pip install -e ".[openai]"
```

**Includes:**
- Core dependencies
- `openai` SDK

**Configure:**
```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=your_key_here
```

### 4. All Providers

For development or testing with multiple providers:

```bash
pip install -e ".[all]"
```

**Includes:**
- Core dependencies
- `anthropic` SDK
- `openai` SDK

### 5. Development Setup

For contributing or running tests:

```bash
pip install -e ".[dev,all]"
```

**Includes:**
- All providers
- pytest
- black
- ruff

## Using vLLM or Ollama

These use OpenAI-compatible APIs, so install the OpenAI extra:

```bash
pip install -e ".[openai]"
```

**For vLLM:**
```bash
export LLM_PROVIDER=vllm
export VLLM_BASE_URL=http://localhost:8000/v1
export VLLM_MODEL=your_model
```

**For Ollama:**
```bash
export LLM_PROVIDER=ollama
export OLLAMA_BASE_URL=http://localhost:11434/v1
export OLLAMA_MODEL=llama3
```

## Backwards Compatibility

A `requirements.txt` file is included for compatibility with older tools:

```bash
pip install -r requirements.txt
```

However, this only installs core dependencies. For LLM providers, you still need to install them manually or use the pyproject.toml approach.

## Verification

After installation, verify it works:

```bash
# Test core functionality
python scripts/verify_tools.py

# Start the server
python run.py
```

## Common Issues

**ImportError: No module named 'anthropic'**
- You're using `LLM_PROVIDER=anthropic` but didn't install the extra
- Fix: `pip install -e ".[anthropic]"`

**ImportError: No module named 'openai'**
- You're using `LLM_PROVIDER=openai` (or vllm/ollama) but didn't install the extra
- Fix: `pip install -e ".[openai]"`

**No error but mock responses in protected mode**
- The mock provider doesn't support tool calling
- Switch to a real provider: `LLM_PROVIDER=anthropic` or `openai`
- Make sure you have the API key configured
