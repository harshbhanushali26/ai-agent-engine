# 🤖 AI Agent Engine

Autonomous AI agent with deterministic routing, cost tracking, and multi-layer optimization.

Built from scratch in pure Python to demonstrate full control over planning, execution, recovery, and LLM usage.

---

## 🧠 Core Principle

Most agents send every query to the LLM.

This system avoids that.

```
Query → Cache → Pattern Router → LLM (only if required)
```

Deterministic queries are executed locally.
The LLM is used only when reasoning is necessary.

---

## 🚀 What Makes It Strong

### 1. Deterministic Execution Layer (0 LLM Calls)

* Math evaluation via safe Python AST
* Date & time reasoning
* Text transformations (regex + tools)
* Web search via `duckduckgo-search` (DDGS)
* Weather data via Open-Meteo

Local execution is prioritized over model inference.

---

### 2. Cost-Aware Design

* Token tracking per session
* Daily API quota enforcement
* Progressive usage warnings (50%, 80%, 100%)
* Disk-based usage logs
* Smart caching (skips dynamic queries like weather & datetime)

Cost visibility is built into the architecture.

---

### 3. Agent Pipeline (LLM Fallback Layer)

When routing fails:

```
Planner → Validator → Executor → Responder
```

* Structured task decomposition
* Tool validation
* Sequential execution with state tracking
* Automatic retry on transient errors
* Replanning on structural failures

The system is defensive by design.

---

## 💡 Example

```
You: What's 5 + 3?
Agent: 8
⚡ Pattern match — 0 API calls

You: Convert 'hello' to uppercase
Agent: HELLO
⚡ Pattern match — 0 API calls

You: What's the weather in Tokyo?
Agent: Current weather in Tokyo is 15°C...
✗ LLM pipeline triggered
```

---

## 📊 Runtime Output Example

```
💰 Session Usage
Prompt tokens: 6,241
Completion tokens: 171
Total tokens: 6,412
Estimated cost: $0.000481

📈 Session Stats
Total queries: 5
Cache hits: 2
Pattern matches: 2
LLM executions: 1
```

---

## 🏗 Architecture Overview

```
agent_engine/
├── core/        # Planning, execution, routing
├── tools/       # Calculator, datetime, text, weather, web
├── memory/      # Persistent caching
├── infra/       # Logging & environment
├── runtime/     # Logs, telemetry, usage data
├── tests/       # Deterministic layer tests
└── main.py
```

---

## 🛠 Tech Stack

* Python 3.11+
* Gemini API (LLM layer)
* Open-Meteo (weather data)
* DuckDuckGo Search via DDGS
* Local AST parsing for safe math evaluation

---

## 🎯 What This Demonstrates

* Multi-layer agent optimization
* Deterministic routing before LLM invocation
* Cost-aware AI architecture
* Failure recovery strategies
* Structured logging & telemetry
* Clean modular system design

---

## 🚀 Setup

```bash
git clone https://github.com/harshbhanushali26/ai-agent-engine.git
cd ai-agent-engine
pip install -r requirements.txt
cp .env.example .env
# Add GEMINI_API_KEY
python main.py
```

---

## 🛣️ Roadmap

* RAG integration
* Async tool execution
* REST API layer
* Streaming responses

---

## 📝 License

MIT

---

## 👤 Author

Harsh Bhanushali
GitHub: [https://github.com/harshbhanushali26](https://github.com/harshbhanushali26)

---


