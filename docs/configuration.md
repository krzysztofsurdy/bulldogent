# Configuration

All configuration follows the same pattern: YAML files define structure and env var names, `.env` provides the actual secrets. Only configure what you need -- unconfigured platforms, providers, and tools are silently skipped.

## Environment variables (`.env`)

All secrets and runtime values live here. Copy `.env.example` to `.env` and fill in only what you need. Variables follow a naming convention:

- `PLATFORM_<NAME>_*` -- messaging platform credentials
- `PROVIDER_<NAME>_*` -- LLM provider credentials
- `TOOL_<NAME>_*` -- tool integration credentials
- `EMBEDDING_*` -- embedding provider credentials

### Platforms

| Variable | Description |
|----------|-------------|
| `PLATFORM_SLACK_LLM_PROVIDER` | Provider name: `openai`, `bedrock`, or `vertex` |
| `PLATFORM_SLACK_BOT_TOKEN` | Slack bot token (`xoxb-...`) |
| `PLATFORM_SLACK_APP_TOKEN` | Slack app-level token (`xapp-...`) |

### LLM providers

| Variable | Description |
|----------|-------------|
| `PROVIDER_OPENAI_MODEL` | Model name (e.g. `gpt-4o`) |
| `PROVIDER_OPENAI_API_KEY` | OpenAI API key |
| `PROVIDER_OPENAI_TEMPERATURE` | Sampling temperature (e.g. `0.7`) |
| `PROVIDER_OPENAI_MAX_TOKENS` | Max response tokens (default `2000`) |
| `PROVIDER_OPENAI_API_URL` | Optional custom endpoint (LiteLLM, Ollama, etc.) |
| `PROVIDER_BEDROCK_MODEL` | e.g. `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| `PROVIDER_BEDROCK_REGION` | AWS region (e.g. `us-east-1`) |
| `PROVIDER_BEDROCK_ANTHROPIC_VERSION` | API version (e.g. `bedrock-2023-05-31`) |
| `PROVIDER_VERTEX_MODEL` | e.g. `gemini-1.5-pro` |
| `PROVIDER_VERTEX_PROJECT_ID` | GCP project ID |
| `PROVIDER_VERTEX_LOCATION` | GCP region (e.g. `us-central1`) |

### Tools

| Variable | Description |
|----------|-------------|
| `TOOL_JIRA_URL` | Jira instance URL (e.g. `https://your-domain.atlassian.net`) |
| `TOOL_JIRA_USERNAME` | Jira username / email |
| `TOOL_JIRA_API_TOKEN` | Jira API token |
| `TOOL_CONFLUENCE_URL` | Confluence instance URL |
| `TOOL_CONFLUENCE_USERNAME` | Confluence username / email |
| `TOOL_CONFLUENCE_API_TOKEN` | Confluence API token |
| `TOOL_GITHUB_TOKEN` | GitHub personal access token |

### Database and embedding

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (e.g. `postgresql+psycopg://user:pass@host:5432/db`) |
| `EMBEDDING_API_KEY` | Embedding provider API key (can reuse `PROVIDER_OPENAI_API_KEY`) |
| `EMBEDDING_API_URL` | Optional custom embedding endpoint (LiteLLM, Ollama) |
| `EMBEDDING_BEDROCK_REGION` | AWS region for Bedrock embeddings |
| `EMBEDDING_VERTEX_PROJECT_ID` | GCP project ID for Vertex embeddings |
| `EMBEDDING_VERTEX_LOCATION` | GCP region for Vertex embeddings |

---

## Platforms (`config/platforms.yaml`)

Each platform block ties together a chat service, its credentials, and the LLM provider it should use. Each platform can use a different LLM provider.

See `config/platforms.yaml.example` for the full annotated reference with required/optional markers.

```yaml
slack:
  llm_provider: $(PLATFORM_SLACK_LLM_PROVIDER)   # required -- openai, bedrock, or vertex
  bot_token: $(PLATFORM_SLACK_BOT_TOKEN)          # required
  app_token: $(PLATFORM_SLACK_APP_TOKEN)          # required
  reaction_handling: dog                           # optional -- emoji when processing
  reaction_error: x                                # optional -- emoji on failure
  reaction_approval: white_check_mark              # optional -- emoji for approvals
  reaction_learn: bone                             # optional -- emoji to save Q&A
  approval_groups:                                 # optional -- named groups for approvals
    devops: [alice_smith, bob_jones]                #   user IDs from teams.yaml
    project-leads: [backend.leads]                 #   team.group references
```

The `approval_groups` map group names to platform-specific user IDs -- these are referenced by the approval rules (see below).

### Platform bot permissions

Each platform requires specific bot permissions/scopes to function fully. The bot supports both @mentions in channels and direct messages.

**Slack** -- Bot Token Scopes (OAuth & Permissions):
- `app_mentions:read` -- respond to @mentions in channels
- `im:history` -- read DM messages sent to the bot
- `im:read` -- access DM channel info
- `im:write` -- open DM conversations with users
- `chat:write` -- send messages and replies
- `reactions:read` -- listen for approval reactions
- `reactions:write` -- add/remove processing/error reactions
- `channels:history` -- read thread history in public channels
- `groups:history` -- read thread history in private channels

Subscribe to bot events: `app_mention`, `message.im`, `reaction_added`.


---

## LLM providers (`config/providers.yaml`)

Keep only the providers you use. Each one reads its settings from env vars.

See `config/providers.yaml.example` for the full annotated reference.

```yaml
openai:
  model: $(PROVIDER_OPENAI_MODEL)                  # required
  api_key: $(PROVIDER_OPENAI_API_KEY)              # required
  temperature: $(PROVIDER_OPENAI_TEMPERATURE)       # optional
  max_tokens: $(PROVIDER_OPENAI_MAX_TOKENS)         # optional (default: 2000)
  api_url: $(PROVIDER_OPENAI_API_URL)               # optional -- LiteLLM, Ollama, etc.
```

The optional `api_url` lets you point any provider at a custom endpoint -- useful for LiteLLM proxies, Ollama, LocalStack, or any OpenAI-compatible server.

---

## Tools (`config/tools.yaml`)

Each tool block defines connection credentials and metadata that the LLM sees in its system prompt. Project names, descriptions, and aliases help the bot pick the right target without asking the user.

See `config/tools.yaml.example` for the full annotated reference.

Only tools present in `tools.yaml` with valid credentials are registered. Remove a block entirely to disable that tool.

### Jira

```yaml
jira:
  url: $(TOOL_JIRA_URL)             # required
  username: $(TOOL_JIRA_USERNAME)    # required
  api_token: $(TOOL_JIRA_API_TOKEN)  # required
  cloud: true                        # optional (default: true)
  projects:                          # optional -- metadata shown to LLM
    - prefix: ALPHA                  #   required per entry
      name: Project Alpha            #   optional
      description: "Backend API"     #   optional
      aliases: [backend]             #   optional
```

### Confluence

```yaml
confluence:
  url: $(TOOL_CONFLUENCE_URL)                 # required
  username: $(TOOL_CONFLUENCE_USERNAME)        # optional (required for Cloud)
  api_token: $(TOOL_CONFLUENCE_API_TOKEN)      # optional (required for Cloud)
  cloud: true                                  # optional (default: true)
  spaces:                                      # optional -- metadata shown to LLM
    - key: DEV                                 #   required per entry
      name: Development                        #   optional
      description: "Engineering docs"          #   optional
```

### GitHub

```yaml
github:
  token: $(TOOL_GITHUB_TOKEN)          # required
  default_org: your-org                # optional -- short names resolve to <org>/<repo>
  repositories:                        # optional -- metadata shown to LLM
    - name: your-repo                  #   required per entry
      description: "Main repository"   #   optional
```

### Knowledge search

Auto-registered when the baseline RAG retriever is configured (`baseline.yaml`). No entry needed in `tools.yaml`.

---

## Teams (`config/teams.yaml`)

Single source of truth for user and team identity mapping across all systems. Maps people and teams to their tool-specific identities (Jira user IDs) and messaging platform IDs (Slack).

See `config/teams.yaml.example` for the full annotated reference.

If `teams.yaml` is not present, the bot starts normally -- team-based features are silently disabled.

### User mappings

Each user is keyed by a stable ID (e.g. `alice_smith`) and has two namespaced trees:

- `tools:` -- per-tool identities (Jira user_id, etc.)
- `platforms:` -- per-messaging-platform user IDs (Slack)

```yaml
user_mappings:
  alice_smith:
    name: Alice Smith                      # required -- display name
    tools:                                 # optional
      jira:
        user_id: 617bea97bcb5740068b3d930  #   Jira account ID
        username: alice.smith
    platforms:                             # optional
      slack: U0ALICE01
      discord: "123456789"
```

### Teams

Each team defines groups, tool resources, and platform channels. The `default` group is mandatory and lists all members. Additional groups (e.g. `leads`, `on_call`) can be referenced as `<team_id>.<group>` in approval rules.

```yaml
teams:
  backend:
    name: Backend                          # optional (default: team ID)
    aliases: [be, api]                     # optional -- for fuzzy lookup
    groups:                                # required
      default: [alice_smith, bob_jones]    #   required -- all team members
      leads: [alice_smith]                 #   optional -- "backend.leads" in approvals
    tools:                                 # optional -- team resources
      jira:
        projects: [ALPHA]
    platforms:                             # optional
      slack:
        channel_id: C0123456789
```

### Approval integration

Approval groups in `platforms.yaml` can reference:
- Individual user IDs from `teams.yaml`
- `<team>.<group>` references (e.g. `backend.leads`)
- Plain team IDs (resolve to the `default` group)

Platform-specific user IDs are looked up automatically from the user mappings.

---

## Observability (`config/observability.yaml`)

Consolidates logging and event staging configuration.

See `config/observability.yaml.example` for the full annotated reference.

### Logging

```yaml
logging:
  json_output: true     # optional (default: true) -- JSON for structured logging, false for console
  log_level: INFO       # optional (default: INFO) -- DEBUG, INFO, WARNING, ERROR
```

### Event staging

The bot emits structured events for every conversation step. Events are staged in PostgreSQL for observability and analysis.

```yaml
events:
  enabled: false           # optional (default: false)
```

Event types: `message_received`, `baseline_context_injected`, `llm_request`, `tool_calls_requested`, `tool_executed`, `approval_requested`, `approval_granted`, `approval_timed_out`, `llm_response`, `learning_stored`, `error`.

---

## Approval rules (`config/platforms.yaml` -- `approvals` section)

Controls which tool operations require human approval before execution. Two-level hierarchy -- per-operation defaults and per-project overrides.

```yaml
approvals:
  jira:
    jira_delete_issue:
      approval_group: jira_admins             # all deletes need approval

    jira_create_issue:
      approval_group: jira_admins             # default for all projects
      projects:
        ALPHA: alpha_maintainers              # override for ALPHA
        BETA: ~                               # BETA is exempt (no approval)

  github:
    github_merge_pr:
      approval_group: github_admins

    github_publish_release:
      projects:
        acme/alpha: release_managers          # only alpha releases need approval
```

**Resolution order** (most specific wins):
1. Project/repository override (`projects.<KEY>`)
2. Operation default (`approval_group`)
3. Not listed = no approval required

When approval is required, the bot posts a message in the thread mentioning the group members. They approve by reacting with the configured emoji (e.g. `:white_check_mark:`). If no one approves within 5 minutes, the operation is cancelled.

Group names must match keys in the platform's `approval_groups` map.
