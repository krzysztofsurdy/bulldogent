![Bulldogent](./logo.png)

# Bulldogent

**Agentic AI bot that lives in your team chat and gets things done.**

Bulldogent is a multi-platform AI assistant that responds to @mentions across Slack, Discord, Teams, and Telegram. It connects to your team's knowledge sources — Jira, Confluence, GitHub, and the web — through an agentic tool-calling loop where the LLM decides what to search and when. Sensitive operations like creating issues or merging PRs go through a configurable approval workflow before execution.

## Features

- **Multi-platform** — Slack, Discord, Microsoft Teams, Telegram
- **Provider-agnostic LLM** — OpenAI, AWS Bedrock (Claude), Google Vertex AI (Gemini)
- **Agentic tool calling** — LLM autonomously decides which tools to use across multiple reasoning steps
- **Knowledge sources** — Jira, Confluence, GitHub, web search (Tavily)
- **Approval gates** — configurable per-operation and per-project approval groups
- **Thread-aware** — maintains conversation context across message threads

## Architecture

```
                        @mention
                           |
                    +--------------+
                    |     Bot      |      Agentic loop (max 15 steps)
                    |  orchestrator|----+
                    +--------------+    |
                           |            |
              +------------+------------+------------+
              |            |            |            |
        +-----------+ +---------+ +---------+ +-----------+
        | Messaging | |   LLM   | |  Tools  | | Approval  |
        | Platforms | |Providers| |Registry | | Manager   |
        +-----------+ +---------+ +---------+ +-----------+
        | Slack     | | OpenAI  | | Jira    | | Per-op    |
        | Discord   | | Bedrock | | GitHub  | | Per-proj  |
        | Teams     | | Vertex  | | Conflu. | | Reaction  |
        | Telegram  | |         | | Web     | | based     |
        +-----------+ +---------+ +---------+ +-----------+
```

The bot follows a clean, layered design with Protocol-based abstractions. Each layer (messaging, LLM, tools) is independently extensible — add a new platform, provider, or tool by implementing the abstract interface and registering it.

## Tools

| Tool | Library | Operations |
|------|---------|------------|
| **Jira** | `atlassian-python-api` | search issues (structured filters + JQL), get issue, list issue types, create, update (with status transitions), delete |
| **Confluence** | `atlassian-python-api` | search pages (CQL), get page content, get child pages, list spaces |
| **GitHub** | `PyGithub` | issues (list, create), PRs (list, get, files, merge), comments, releases (list, get, publish), workflows (list, runs, jobs) |
| **Web Search** | `tavily-python` | real-time web search with AI summaries |

Tools are YAML-driven — each adapter has an `operations.yaml` that defines parameters and descriptions. The LLM sees these as callable functions.

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Install

```bash
git clone <repo-url> && cd bulldogent
make install
```

### Configure

```bash
cp .env.example .env
cp config/tools.yaml.example config/tools.yaml
cp config/tool_operation_approval.yaml.example config/tool_operation_approval.yaml
```

Edit `.env` with your credentials. You only need to configure the platforms and providers you want to use — unconfigured ones are silently skipped.

**Minimum viable setup** (Slack + OpenAI):
```env
PLATFORM_SLACK_LLM_PROVIDER=openai
PLATFORM_SLACK_BOT_TOKEN=xoxb-...
PLATFORM_SLACK_APP_TOKEN=xapp-...
PROVIDER_OPENAI_API_KEY=sk-...
PROVIDER_OPENAI_MODEL=gpt-4o
```

### Run

```bash
make run
```

## Configuration

All configuration follows the same pattern: YAML files define structure and env var names, environment variables provide the actual secrets.

### Platforms (`config/messaging_platform.yaml`)

Each platform block specifies which LLM provider to use, bot tokens, emoji reactions, and approval groups with user IDs.

### LLM Providers (`config/llm_provider.yaml`)

Model name, temperature, max tokens, and provider-specific settings (region, project ID, etc.) — all via env vars.

### Tools (`config/tools.yaml`)

```yaml
jira:
  url_env: TOOL_JIRA_URL
  username_env: TOOL_JIRA_USERNAME
  api_token_env: TOOL_JIRA_API_TOKEN
  projects:
    - prefix: PROJ
      name: My Project
      aliases: [backend]

confluence:
  url_env: TOOL_CONFLUENCE_URL
  username_env: TOOL_CONFLUENCE_USERNAME
  api_token_env: TOOL_CONFLUENCE_API_TOKEN

github:
  token_env: TOOL_GITHUB_TOKEN
  default_org: my-org
  repositories:
    - name: my-repo
      description: "Main repository"

web_search:
  api_key_env: TOOL_TAVILY_API_KEY
```

### Approval Rules (`config/tool_operation_approval.yaml`)

Two-level hierarchy — per-operation defaults and per-project overrides:

```yaml
jira:
  jira_delete_issue:
    approval_group: jira_admins          # all deletes need admin approval

  jira_create_issue:
    approval_group: jira_admins          # default for creates
    projects:
      ALPHA: alpha_maintainers           # override for ALPHA project
      BETA: ~                            # BETA is exempt (no approval)
```

Unlisted operations execute immediately. When approval is required, the bot posts a message mentioning the approval group members — they approve by reacting with the configured emoji.

## Development

```bash
make lint         # ruff check
make format       # ruff format
make typecheck    # mypy (strict mode)
make test         # pytest with coverage
make check        # all of the above
make fix          # auto-fix lint issues + format
make clean        # remove cache files
```

