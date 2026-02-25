import structlog
from openai import OpenAI

_logger = structlog.get_logger()

_PROMPT = (
    "You are a technical documentation assistant. "
    "Given a file from a code repository, write a single concise sentence (max 30 words) "
    "that describes what this file contains and its purpose. "
    "Focus on the domain meaning, not the file format. "
    "Do not include the file path or repository name in your response."
)

# Truncate large files to keep summarisation cheap and fast.
_MAX_CONTENT_CHARS = 3000


class FileSummarizer:
    """Generate one-line file summaries using a small, cheap LLM."""

    def __init__(self, api_key: str, model: str, api_url: str | None = None) -> None:
        self._client = OpenAI(
            api_key=api_key,
            base_url=api_url,
        )
        self._model = model

    def summarize(self, content: str, repo: str, path: str) -> str:
        """Return a one-line summary of the file content."""
        truncated = content[:_MAX_CONTENT_CHARS]
        user_msg = f"Repository: {repo}\nFile: {path}\n\n{truncated}"

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _PROMPT},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=60,
            temperature=0.0,
        )
        summary = (response.choices[0].message.content or "").strip()
        _logger.debug("github_file_summarized", repo=repo, path=path, summary=summary)
        return summary
