# Baseline RAG

The baseline system indexes organizational knowledge from Confluence, GitHub, Jira, and local files into PostgreSQL + pgvector. Relevant chunks are automatically injected as context into every conversation.

## How it works

1. **Crawlers** pull content from configured sources (Confluence pages, GitHub repos, Jira issues, local docs)
2. **Chunker** splits documents into token-sized overlapping chunks (default: 500 tokens, 50 overlap)
3. **Embedding provider** converts chunks into vectors (OpenAI, Bedrock, or Vertex)
4. **PostgreSQL + pgvector** stores chunks with their embeddings
5. **Retriever** queries by cosine similarity and injects top matches into the LLM conversation

## Configuration

Full reference: `config/baseline.yaml.example`

```yaml
database_url: $(DATABASE_URL)

embedding:
  provider: openai                    # openai | bedrock | vertex
  model: text-embedding-3-small
  dimensions: 1536
  openai:
    api_key: $(EMBEDDING_API_KEY)

sources:
  confluence:
    spaces: [DEV, OPS]               # space keys to crawl
    max_pages: 500                    # safety cap per space
  github:
    repositories: [alpha, beta]       # resolved via default_org in tools.yaml
    include: [readme]                 # what to index: readme, issues
    exclude_patterns:                 # files to skip (secrets, credentials)
      - ".env"
      - "*.pem"
      - "config/secrets/*"
  jira:
    projects: [ALPHA, BETA]
    max_issues: 200
  local:
    paths: [config/baseline/]         # directories with .md/.txt files

chunking:
  chunk_size: 500                     # max tokens per chunk
  overlap: 50                         # overlap between chunks

retrieval:
  top_k: 5                           # max chunks injected per query
  max_tokens: 1000                    # hard cap on injected text (tokens)
  min_score: 0.3                      # similarity threshold (1 - cosine distance)
```

## Indexing

```bash
make index               # index all sources
make index-confluence    # index only Confluence
make index-github        # index only GitHub
make index-jira          # index only Jira
make index-local         # index only local files
make docker-index        # run indexer in Docker
```

## Sensitive file filtering

The `exclude_patterns` list under `sources.github` prevents secrets and credentials from being indexed:

- Patterns **without** `/` match against the **filename** only (e.g. `.env`, `*.pem`)
- Patterns **with** `/` match against the **full file path** (e.g. `config/secrets/*`, `*/secrets/*`)

Default exclusions cover `.env`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `secrets.*`, `credentials.*`, `*.tfvars`, and common vendor/secrets directories.

## File summarization

When `summarizer.enabled` is `true`, the indexer uses a cheap LLM to generate a one-line description for each indexed file. The summary is prepended to the chunk content before embedding, which significantly improves retrieval for structured files like YAML configs.

Each chunk gets a header like:

```
Repository: acme/config
File: src/Resources/config/markets/tui.yml
Summary: Whitelabel market configuration defining three markets (DE, AT, CH) with domains and locales.
```

```yaml
summarizer:
  enabled: false                      # toggle on to activate
  model: gpt-4o-mini                  # cheap, fast model
  api_key: $(EMBEDDING_API_KEY)       # can reuse embedding key
```

Per-repo opt-out is supported via `summarize: false` in the repository config:

```yaml
repositories:
  - config:
      include: [readme, src/Resources/config/markets/*]
      summarize: false
```

## Self-learning

When enabled, successful Q&A pairs are stored in a separate "learned" collection when users react with the learn emoji. These are retrieved alongside baseline chunks in future conversations.

```yaml
learning:
  enabled: false                      # toggle on to activate
```

## Knowledge search tool

When the baseline retriever is configured, a `knowledge_search` tool is auto-registered. This lets the LLM explicitly search the vector DB for indexed content and past conversations saved by users. No entry in `tools.yaml` is needed.
