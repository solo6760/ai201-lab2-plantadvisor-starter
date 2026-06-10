# System Design: Plant Advisor Agent

**Status:** Complete — read this before opening any code file.

---

## What You're Building

Plant Advisor is a conversational agent that helps users care for their houseplants. Given a question like "my monstera leaves are turning yellow — what's wrong?", it looks up the plant's care requirements, checks the current seasonal context, and generates a specific, grounded answer.

The infrastructure is complete. The conversation loop, tool schemas, and UI are all built. What's missing is the logic that makes the tools actually work (`tools.py`) and the agent loop that orchestrates them (`agent.py`).

---

## Architecture

```
User
  │
  ▼
app.py  ──────────────────────────────────────────────────────────►  Gradio UI
  │                                                                   (complete)
  │  run_agent(user_message, history)
  ▼
agent.py  ────────────────────────────────────────────────────────►  Groq LLM
  │                                                              (llama-3.3-70b)
  │  Tool call loop:
  │    LLM decides which tool to call
  │    dispatch_tool() routes to the right function
  │    Results go back to the LLM
  │    Loop until LLM stops calling tools
  │
  ├── lookup_plant(plant_name)
  │       └── tools.py  ──────────────────────────────────────►  plants.json
  │
  └── get_seasonal_conditions(season)
          └── tools.py  ──────────────────────────────────────►  seasons.json
```

---

## Key Technical Decisions

### Why a tool-calling agent instead of direct RAG?

Plant care involves two logically separate data sources: plant-specific requirements (watering frequency, light needs) and seasonal context (winter reduces watering for everything). These have different query shapes — one is a plant lookup, the other is a time-based lookup. An agent with two distinct tools can compose these cleanly. A single retrieval step would have to retrieve both kinds of data from a unified index, making it harder to attribute which piece of advice comes from which source.

### Why Groq function calling?

The Groq API supports the OpenAI-compatible tool calling interface, where the model returns structured `tool_calls` objects specifying which function to invoke and with what arguments. This is the industry-standard pattern for tool-using agents. Understanding how to build and consume this interface is a directly transferable skill.

### Why a MAX_TOOL_ROUNDS safety limit?

An agent loop runs until the LLM stops calling tools. Without a limit, a buggy tool or an unusual LLM response could cause an infinite loop. `MAX_TOOL_ROUNDS` (set in `config.py`) caps the number of tool-calling iterations before the agent returns whatever response it has. This is a common production practice — set a reasonable limit and monitor.

### Why separate tool functions from the agent loop?

Tool functions (`tools.py`) are pure data retrieval — they take arguments and return structured data. The agent loop (`agent.py`) handles the conversation protocol. Keeping these separate makes each easier to test independently and mirrors how agent systems are structured in production (tools are often deployed as separate services).

---

## Component Status

| Component | File | Status | Who builds it |
|-----------|------|--------|---------------|
| Gradio UI | `app.py` | ✅ Complete | (built) |
| Config | `config.py` | ✅ Complete | (built) |
| Plant database | `data/plants.json` | ✅ Complete | (built) |
| Seasonal data | `data/seasons.json` | ✅ Complete | (built) |
| Tool definitions (schemas) | `agent.py` | ✅ Complete | (built) |
| Tool dispatch | `agent.py` | ✅ Complete | (built) |
| System prompt | `agent.py` | ✅ Complete | (built) |
| `lookup_plant()` | `tools.py` | 🔲 Student spec + implementation | Milestone 1 |
| `get_seasonal_conditions()` | `tools.py` | 🔲 Student spec + implementation | Milestone 1 |
| `run_agent()` | `agent.py` | 🔲 Student spec + implementation | Milestone 2 |
| Graceful degradation | `tools.py` + `agent.py` | 🔲 Student analysis + improvement | Milestone 3 |

---

## Where to Start

1. Read this document fully.
2. Open `agent.py` and read the tool definitions and system prompt — these describe what the LLM expects from each tool.
3. Open `tools.py` and read the docstrings — they describe what each function should return.
4. Open `specs/tool-functions-spec.md` and complete the blank fields.
5. Implement `lookup_plant()` and `get_seasonal_conditions()`.
6. Then move to `specs/agent-loop-spec.md` and `run_agent()`.

---

## Data Sources

**`data/plants.json`** — 15 common houseplants, each with:
- `display_name`, `scientific_name`, `aliases`
- `difficulty` level
- `watering` (frequency, description, over/underwatering signs)
- `light` (requirement, description, what to avoid)
- `humidity`, `temperature`, `fertilizing`
- `common_issues` list
- `seasonal_notes` (brief per-season adjustments)

**`data/seasons.json`** — 4 seasons (spring/summer/fall/winter), each with:
- `description`, `months`
- `watering`, `fertilizing`, `light`, `repotting`, `pests` guidance
- `general_tip`

---

## How the Groq Tool Calling API Works

When you call `client.chat.completions.create()` with `tools=TOOL_DEFINITIONS`, the LLM may respond with a `tool_calls` list instead of (or before) a text response. Each tool call contains:

```
tool_call.function.name       → the tool name (e.g., "lookup_plant")
tool_call.function.arguments  → a JSON string of the arguments
tool_call.id                  → a unique ID linking this call to its result
```

To feed the tool result back to the LLM, you append two things to the messages list:
1. The assistant message that contained the `tool_calls` (append the message object directly)
2. A tool result message for each tool call: `{"role": "tool", "content": <result string>, "tool_call_id": <id>}`

Then call the LLM again. This is the core of the agent loop.
