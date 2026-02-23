CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source VARCHAR(50) NOT NULL,
    title VARCHAR(500) NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    url VARCHAR(1000) NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}',
    embedding vector(1536)
);

CREATE INDEX IF NOT EXISTS ix_knowledge_source ON knowledge (source);
CREATE INDEX IF NOT EXISTS ix_knowledge_embedding ON knowledge
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
