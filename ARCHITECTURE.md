# Architecture — Agentic LLM with Tool Calling

## Design Decisions

### 1. MCP-Style Tool Calling vs Simple RAG

**Chosen Approach:** LLM as orchestrator with tool calling (like MCP servers)

**Why:** More efficient, smarter, follows modern AI agent patterns, better for ML/DL learning

### 2. Multi-Provider LLM Layer

**Chosen Approach:** Provider-agnostic LLM abstraction with factory/registry pattern

**Providers:** OpenAI, AWS Bedrock (Claude), Google Vertex AI — all with tool calling support

**Pattern:** `AbstractProviderConfig` → `ProviderConfigGenerator` → `ProviderFactory` → `ProviderRegistry`

### 3. Messaging Platform Abstraction

**Chosen Approach:** Platform-agnostic messaging layer with adapter/factory/registry pattern

**Platforms:** Slack (full), Teams/Discord/Telegram (stubs)

**Design:** All enabled platforms run simultaneously, each selects its own LLM provider

---

## Architecture Overview

```
┌─────────────┐
│   User      │
│  @mentions  │
│   bot in    │
│   Slack     │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│                    Slack Bot                             │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Event Handler (@app.event)                        │ │
│  │  - Receives mention                                │ │
│  │  - Extracts user message + thread context          │ │
│  │  - Starts agentic loop                             │ │
│  └────────────┬───────────────────────────────────────┘ │
│               │                                          │
│               ▼                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Agentic Loop (Tool Execution Loop)                │ │
│  │                                                     │ │
│  │  1. Send messages + tools to LLM                   │ │
│  │  2. LLM decides: answer or use tools?              │ │
│  │  3. If tool use: execute tools, add results        │ │
│  │  4. Loop back to step 1                            │ │
│  │  5. If end_turn: reply to user                     │ │
│  └────────────┬───────────────────────────────────────┘ │
└───────────────┼──────────────────────────────────────────┘
                │
                ▼
    ┌───────────────────────┐
    │   LLM Provider        │
    │   (via Registry)      │
    │                       │
    │   - complete()        │
    │   - Tool definitions  │
    │   - Tool use support  │
    └───────────┬───────────┘
                │
         ┌──────┼──────┐
         ▼      ▼      ▼
      OpenAI Bedrock Vertex
                (Claude)
                ▲
                │
                │ Can request tools:
                ├─ search_confluence
                ├─ search_jira
                ├─ search_github
                ├─ search_slack_history
                └─ (more tools as needed)

    Tools executed by bot ──────┐
                                 │
                                 ▼
                ┌────────────────────────────────┐
                │   Knowledge Sources (Tools)    │
                ├────────────────────────────────┤
                │  ConfluenceSource              │
                │  JiraSource                    │
                │  GitHubSource                  │
                │  SlackHistorySource            │
                └────────────────────────────────┘
```

---

## How It Works: Example Flow

### User Question
```
User: "@bot what's the status of PROJECT-123?"
```

### Step 1: Bot receives mention
- Extracts message: "what's the status of PROJECT-123?"
- Fetches thread context (if in a thread)
- Prepares initial messages for LLM

### Step 2: First LLM call (with tools available)
```python
messages = [
    {"role": "user", "content": "what's the status of PROJECT-123?"}
]

tools = [
    search_confluence_tool,
    search_jira_tool,
    search_github_tool,
    search_slack_history_tool
]

response = llm_provider.complete(messages, tools=tools)
```

### Step 3: LLM decides to use tools
```python
# LLM response:
{
    "stop_reason": "tool_use",
    "tool_calls": [
        {
            "id": "call_1",
            "name": "search_jira",
            "input": {"query": "PROJECT-123"}
        }
    ]
}
```

**Why this tool?** LLM recognized "PROJECT-123" as a Jira ticket ID.

### Step 4: Bot executes tool
```python
jira_result = jira_source.search("PROJECT-123")
# Returns: {
#   "title": "PROJECT-123: Fix login bug",
#   "status": "In Progress",
#   "assignee": "John Doe",
#   "description": "..."
# }
```

### Step 5: Add tool result to conversation
```python
messages.extend([
    {"role": "assistant", "tool_calls": [...]},  # LLM's request
    {"role": "user", "tool_results": [...]}      # Tool execution result
])
```

### Step 6: Second LLM call (with tool results)
```python
response = llm_provider.complete(messages, tools=tools)
```

### Step 7: LLM generates answer
```python
# LLM response:
{
    "stop_reason": "end_turn",
    "content": "PROJECT-123 is currently In Progress, assigned to John Doe.
                It's about fixing a login bug. Would you like more details?"
}
```

### Step 8: Bot replies in Slack
Bot sends the LLM's answer in the thread.

---

## Multi-Step Tool Use (Iterative Reasoning)

LLM can chain multiple tool calls:

### Example: "How do we deploy?"

**First LLM call:**
```
LLM: I should search Confluence for deployment docs
Tool call: search_confluence("deployment production")
```

**Second LLM call (after getting Confluence results):**
```
LLM: The docs mention a GitHub workflow, let me check that
Tool call: search_github("deploy.yml")
```

**Third LLM call (after getting GitHub results):**
```
LLM: Now I have enough context to answer
Response: "To deploy to production, run `npm run deploy:prod`
           which triggers the workflow in .github/workflows/deploy.yml..."
```

---

## Tool Definitions

Each knowledge source is defined as a tool with:
- **name** — function name
- **description** — what it does (LLM reads this to decide when to use it)
- **input_schema** — what parameters it takes

### Example: Confluence Tool

```python
{
    "name": "search_confluence",
    "description": "Search Confluence documentation and wiki pages for company information, technical docs, runbooks, and process documentation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query to find relevant Confluence pages"
            }
        },
        "required": ["query"]
    }
}
```

### Example: Jira Tool

```python
{
    "name": "search_jira",
    "description": "Search Jira for issues, tickets, and project information. Use ticket IDs like PROJECT-123 or search by keywords.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Jira ticket ID (e.g. PROJECT-123) or search keywords"
            }
        },
        "required": ["query"]
    }
}
```

---

## Agentic Loop Implementation

```python
def handle_mention_with_tools(user_message: str, thread_context: list[dict]) -> str:
  """
  Agentic loop: LLM decides what tools to use, bot executes them.
  """
  # Initial conversation with thread context
  messages = thread_context + [
    {"role": "user", "content": user_message}
  ]

  # Available tools
  tools = [
    confluence_tool_definition,
    jira_tool_definition,
    github_tool_definition,
    slack_history_tool_definition
  ]

  max_iterations = 5  # Prevent infinite loops
  iteration = 0

  while iteration < max_iterations:
    # Send to LLM with tools
    response = llm_provider.complete(messages, tools=tools)

    if response.finish_reason == "end_turn":
      # LLM has final answer
      return response.content

    elif response.finish_reason == "tool_use":
      # LLM wants to use tools
      tool_results = []

      for tool_call in response.tool_operation_calls:
        result = execute_tool(tool_call.name, tool_call.input)
        tool_results.append({
          "tool_call_id": tool_call.id,
          "result": result
        })

      # Add to conversation history
      messages.append({
        "role": "assistant",
        "tool_calls": response.tool_operation_calls
      })
      messages.append({
        "role": "user",
        "tool_results": tool_results
      })

      iteration += 1

    else:
      # Unexpected stop reason
      raise Exception(f"Unexpected stop reason: {response.finish_reason}")

  # Max iterations reached
  return "I've gathered a lot of information but need to think about this more. Could you rephrase your question?"


def execute_tool(tool_name: str, tool_input: dict) -> dict:
  """Execute a tool by name."""
  if tool_name == "search_confluence":
    return confluence_source.search(tool_input["query"])
  elif tool_name == "search_jira":
    return jira_source.search(tool_input["query"])
  elif tool_name == "search_github":
    return github_source.search(tool_input["query"])
  elif tool_name == "search_slack_history":
    return slack_history_source.search(tool_input["query"])
  else:
    raise ValueError(f"Unknown tool: {tool_name}")
```

---

## Thread Context & User Differentiation

When bot is @mentioned in a thread, it fetches all previous messages:

```python
def get_thread_context(channel: str, thread_ts: str) -> list[dict]:
    """Fetch all messages in a thread with user names."""
    messages = slack_client.conversations_replies(
        channel=channel,
        ts=thread_ts
    )

    context = []
    for msg in messages["messages"]:
        user_id = msg.get("user")
        user_name = get_user_name(user_id)  # Fetch from Slack API

        context.append({
            "role": "user" if user_id != bot_user_id else "assistant",
            "content": f"{user_name}: {msg['text']}"
        })

    return context
```

**Result:**
```python
[
    {"role": "user", "content": "Alice: my name is Alice"},
    {"role": "assistant", "content": "Nice to meet you, Alice!"},
    {"role": "user", "content": "Bob: what's Alice's name?"}
]
```

LLM sees **who said what** and can differentiate between users.

---

## Benefits of This Architecture

### 1. Efficiency
- Only searches what's needed (not all sources every time)
- Saves API calls and latency

### 2. Intelligence
- LLM decides the search strategy
- Can combine information from multiple sources
- Can follow up with more searches if needed

### 3. Flexibility
- Easy to add new tools (just define the tool, implement the function)
- LLM automatically learns to use new tools from their descriptions

### 4. Agentic Behavior
- Multi-step reasoning
- Can handle complex queries that require multiple lookups
- Follows modern AI agent patterns (like AutoGPT, LangChain agents, MCP servers)

### 5. ML/DL Learning
- Tool use / function calling is fundamental in AI agents
- Prepares for more advanced agent patterns (ReAct, chain-of-thought, etc.)
- Aligns with how production AI systems work

---

## Messaging Platform Abstraction

### Architecture Pattern: Adapter + Factory + Registry

The messaging layer uses the **Adapter pattern** to isolate platform-specific code behind a common interface, with **Factory** for instantiation and **Registry** for runtime access. Same pattern as LLM providers.

### Structure

```
messaging/platform/
├── types.py             ← PlatformType, PlatformMessage, PlatformUser
├── platform.py          ← AbstractMessagingPlatform (ABC) + PlatformFactory
├── config.py            ← AbstractPlatformConfig + per-platform configs + PlatformConfigGenerator
├── registry.py          ← PlatformRegistry (singleton)
├── __init__.py
└── adapter/
    ├── slack.py         ← SlackPlatform (full implementation)
    ├── teams.py         ← TeamsPlatform (stub)
    ├── discord.py       ← DiscordPlatform (stub)
    └── telegram.py      ← TelegramPlatform (stub)
```

### Config Flow (Environment-Driven)

```
config/platform.yaml          → PlatformConfigGenerator.all()
  (holds env var names)             ↓ yields config objects
                               PlatformFactory.from_config()
                                    ↓ creates adapters
                               PlatformRegistry._build()
                                    ↓ registers enabled platforms
                               PlatformRegistry.get(PlatformType.SLACK)
```

YAML files hold env var **names** only (e.g. `bot_token_env: PLATFORM_SLACK_BOT_TOKEN`).
Actual values come from environment variables / `.env` file.

### AbstractMessagingPlatform (ABC)

```python
class AbstractMessagingPlatform(ABC):
    def __init__(self, config: AbstractPlatformConfig) -> None: ...

    @abstractmethod
    def identify(self) -> PlatformType: ...

    @abstractmethod
    def send_message(self, channel_id: str, text: str, thread_id: str | None = None) -> str: ...

    @abstractmethod
    def add_reaction(self, channel_id: str, message_id: str, emoji: str) -> None: ...

    @abstractmethod
    def on_message(self, handler: Callable[[PlatformMessage], None]) -> None: ...

    @abstractmethod
    def start(self) -> None: ...
```

### Config Hierarchy

```python
@dataclass
class AbstractPlatformConfig(ABC):
    enabled: bool
    llm_provider: str                    # Which LLM provider this platform uses
    reaction_acknowledged: str
    reaction_handled: str
    reaction_error: str

@dataclass
class SlackConfig(AbstractPlatformConfig):
    bot_token: str
    app_token: str

# Similar: TeamsConfig, DiscordConfig, TelegramConfig
```

### Multi-Platform Design

All enabled platforms run simultaneously — no "active platform" concept.
Each platform specifies which LLM provider to use via `llm_provider` field.

```
Slack  → uses OpenAI
Teams  → uses Bedrock
Discord → uses Vertex
```

### Current Status

- ✅ Slack fully implemented (slack-bolt, Socket Mode)
- ✅ Teams/Discord/Telegram stubs in place
- ✅ Factory/registry pattern ready for new platforms
- ✅ Per-platform LLM provider selection

---

## Comparison: Simple RAG vs Tool Calling

### Simple RAG (Rejected Approach)

```python
# Always search everything
confluence_results = confluence_source.search(user_message)
jira_results = jira_source.search(user_message)
github_results = github_source.search(user_message)
slack_results = slack_history_source.search(user_message)

# Dump all results into context
context = format_all_results([
    confluence_results,
    jira_results,
    github_results,
    slack_results
])

# LLM gets everything whether it needs it or not
response = llm.complete(
    system=context,
    user=user_message
)
```

**Problems:**
- ❌ Wastes API calls (searches everything every time)
- ❌ Slow (waits for all sources even if only one is needed)
- ❌ Context bloat (LLM gets irrelevant results)
- ❌ No multi-step reasoning

### Tool Calling (Chosen Approach)

```python
# LLM decides what to search
response = llm.complete(
  messages=[{"role": "user", "content": user_message}],
  tools=[confluence_tool, jira_tool, github_tool, slack_tool]
)

if response.tool_operation_calls:
  # Only execute what LLM requested
  for tool_call in response.tool_operation_calls:
    result = execute_tool(tool_call)
    # LLM gets targeted results

  # LLM can request more tools if needed
```

**Benefits:**
- ✅ Efficient (only searches what's needed)
- ✅ Fast (parallel execution of requested tools)
- ✅ Targeted context (LLM gets relevant results)
- ✅ Multi-step reasoning (iterative tool use)

---

## Implementation Roadmap

### Milestone 2: LLM with Tool Use
- ✅ Implement 3 providers: OpenAI, Bedrock, Vertex (all with tool calling)
- ✅ Provider abstraction: config hierarchy, factory, registry
- ✅ Messaging platform abstraction: config, factory, registry, 4 adapters
- Implement agentic loop (tool execution loop) — Ticket 2.3
- Test with a single mock tool

### Milestone 3: First Tool (Confluence)
- Implement `ConfluenceSource`
- Define `search_confluence` tool
- Register tool with LLM provider
- Test end-to-end: mention → LLM requests tool → bot searches Confluence → LLM answers

### Milestone 4: More Tools
- Implement `JiraSource`, `GitHubSource`, `SlackHistorySource`
- Define their tool definitions
- Register all tools
- Test multi-tool scenarios

### Milestone 5: Thread Context
- Fetch thread history with user names
- Include in LLM messages
- Test conversation continuity and user differentiation

---

## Future Enhancements

### Streaming Responses
- Stream LLM responses token-by-token to Slack
- Update message in real-time as LLM generates answer

### Caching
- Cache tool results to avoid redundant searches
- TTL-based invalidation

### Tool Result Ranking
- Score and rank tool results by relevance
- Pass top N results to LLM (not all)

### Advanced Tools
- Tools that create/update (not just search)
  - `create_jira_ticket`
  - `update_confluence_page`
  - `create_github_issue`

### Self-Reflection
- LLM evaluates if it has enough info or needs more tools
- "I found X but I'm not confident, let me search Y too"

---

## Key Takeaways

1. **LLM is the orchestrator** — it decides what information to retrieve
2. **Tools are capabilities** — each knowledge source is a tool the LLM can invoke
3. **Agentic loop** — iterative: LLM thinks → requests tools → receives results → thinks again
4. **Efficient & smart** — only searches what's needed, can do multi-step reasoning
5. **Modern pattern** — aligns with MCP, LangChain agents, AutoGPT, production AI systems
