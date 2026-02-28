from unittest.mock import MagicMock, patch

from bulldogent.baseline.config import RetrievalConfig
from bulldogent.baseline.retriever import BaselineRetriever
from bulldogent.baseline.types import RetrievalResult


def _make_row(
    source: str = "confluence",
    title: str = "Doc",
    content: str = "some content",
    url: str = "http://example.com",
    similarity: float = 0.8,
) -> MagicMock:
    row = MagicMock()
    row.source = source
    row.title = title
    row.content = content
    row.url = url
    row.similarity = similarity
    return row


class TestBaselineRetriever:
    def test_retrieve_returns_results_above_threshold(self) -> None:
        embedding_provider = MagicMock()
        embedding_provider.embed_query.return_value = [0.1, 0.2, 0.3]

        config = RetrievalConfig(top_k=5, min_score=0.5)
        retriever = BaselineRetriever(
            embedding_provider=embedding_provider,
            retrieval_config=config,
        )

        rows = [
            _make_row(title="Good", similarity=0.9),
            _make_row(title="Also good", similarity=0.6),
            _make_row(title="Below threshold", similarity=0.3),
        ]

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = rows

        with patch("bulldogent.baseline.retriever.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            results = retriever.retrieve("test query")

        assert len(results) == 2
        assert results[0].title == "Good"
        assert results[0].score == 0.9
        assert results[1].title == "Also good"
        assert results[1].score == 0.6

    def test_retrieve_uses_custom_top_k_and_min_score(self) -> None:
        embedding_provider = MagicMock()
        embedding_provider.embed_query.return_value = [0.1, 0.2]

        config = RetrievalConfig(top_k=10, min_score=0.5)
        retriever = BaselineRetriever(
            embedding_provider=embedding_provider,
            retrieval_config=config,
        )

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [
            _make_row(similarity=0.7),
        ]

        with patch("bulldogent.baseline.retriever.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            results = retriever.retrieve("query", top_k=3, min_score=0.6)

        # Check the SQL parameters passed
        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["top_k"] == 3
        assert len(results) == 1

    def test_retrieve_returns_empty_when_no_results(self) -> None:
        embedding_provider = MagicMock()
        embedding_provider.embed_query.return_value = [0.1]

        config = RetrievalConfig(top_k=5, min_score=0.5)
        retriever = BaselineRetriever(
            embedding_provider=embedding_provider,
            retrieval_config=config,
        )

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = []

        with patch("bulldogent.baseline.retriever.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            results = retriever.retrieve("nothing here")

        assert results == []

    def test_retrieve_maps_row_fields_to_retrieval_result(self) -> None:
        embedding_provider = MagicMock()
        embedding_provider.embed_query.return_value = [0.5]

        config = RetrievalConfig(top_k=5, min_score=0.0)
        retriever = BaselineRetriever(
            embedding_provider=embedding_provider,
            retrieval_config=config,
        )

        row = _make_row(
            source="github",
            title="README",
            content="Install instructions",
            url="https://github.com/repo",
            similarity=0.95,
        )

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [row]

        with patch("bulldogent.baseline.retriever.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            results = retriever.retrieve("install")

        assert len(results) == 1
        r = results[0]
        assert isinstance(r, RetrievalResult)
        assert r.source == "github"
        assert r.title == "README"
        assert r.content == "Install instructions"
        assert r.url == "https://github.com/repo"
        assert r.score == 0.95

    def test_retrieve_calls_embed_query_with_input(self) -> None:
        embedding_provider = MagicMock()
        embedding_provider.embed_query.return_value = [0.1]

        config = RetrievalConfig(top_k=5, min_score=0.5)
        retriever = BaselineRetriever(
            embedding_provider=embedding_provider,
            retrieval_config=config,
        )

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = []

        with patch("bulldogent.baseline.retriever.get_session") as mock_get_session:
            mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

            retriever.retrieve("my search query")

        embedding_provider.embed_query.assert_called_once_with("my search query")
