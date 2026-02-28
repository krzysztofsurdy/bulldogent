from unittest.mock import MagicMock, patch

from github import GithubException

from bulldogent.baseline.config import (
    GitHubRepoConfig,
    GitHubSourceConfig,
    _parse_github_config,
    _parse_summarizer,
)
from bulldogent.baseline.crawlers.github import GitHubCrawler, _is_sensitive


def _make_content_file(
    path: str, text: str, html_url: str = "https://github.com/org/repo", file_type: str = "file"
) -> MagicMock:
    cf = MagicMock()
    cf.path = path
    cf.decoded_content = text.encode()
    cf.html_url = html_url
    cf.type = file_type
    return cf


def _make_crawler(
    source_config: GitHubSourceConfig,
    token: str = "test-token",  # noqa: S107
    default_org: str = "org",
    summarizer: MagicMock | None = None,
) -> GitHubCrawler:
    chunker = MagicMock()
    chunker.chunk_text.side_effect = lambda text, source, title, url, metadata: [
        MagicMock(content=text, source=source, title=title, url=url, metadata=metadata)
    ]
    tool_config = {"github": {"token": token, "default_org": default_org}}
    return GitHubCrawler(
        source_config=source_config,
        tool_config=tool_config,
        chunker=chunker,
        summarizer=summarizer,
    )


class TestParseGithubConfig:
    def test_string_repos_use_global_include(self) -> None:
        raw = {
            "repositories": ["repo-a", "repo-b"],
            "include": ["readme"],
        }
        config = _parse_github_config(raw)

        assert len(config.repositories) == 2
        assert config.repositories[0].name == "repo-a"
        assert config.repositories[0].include == []
        assert config.include == ["readme"]

    def test_dict_repo_with_per_repo_include(self) -> None:
        raw = {
            "repositories": [
                "repo-a",
                {"config": {"include": ["readme", "src/config.yml"]}},
            ],
            "include": ["readme"],
        }
        config = _parse_github_config(raw)

        assert len(config.repositories) == 2
        assert config.repositories[0].name == "repo-a"
        assert config.repositories[0].include == []
        assert config.repositories[1].name == "config"
        assert config.repositories[1].include == ["readme", "src/config.yml"]

    def test_dict_repo_without_include_gets_empty_list(self) -> None:
        raw = {
            "repositories": [{"my-repo": {}}],
            "include": ["readme"],
        }
        config = _parse_github_config(raw)

        assert config.repositories[0].name == "my-repo"
        assert config.repositories[0].include == []

    def test_empty_repositories(self) -> None:
        config = _parse_github_config({})
        assert config.repositories == []
        assert config.include == ["readme"]

    def test_glob_in_per_repo_include(self) -> None:
        raw = {
            "repositories": [
                {"config": {"include": ["readme", "src/markets/*"]}},
            ],
        }
        config = _parse_github_config(raw)
        assert config.repositories[0].include == ["readme", "src/markets/*"]


class TestGitHubCrawlerCrawl:
    @patch("github.Github")
    def test_skips_when_no_token(self, _mock_github: MagicMock) -> None:
        config = GitHubSourceConfig(
            repositories=[GitHubRepoConfig(name="repo")],
            include=["readme"],
        )
        crawler = _make_crawler(config, token="")
        assert crawler.crawl() == []

    @patch("github.Github")
    def test_repo_uses_global_include(self, mock_github_cls: MagicMock) -> None:
        readme = _make_content_file("README.md", "# Hello")
        mock_repo = MagicMock()
        mock_repo.get_readme.return_value = readme
        mock_github_cls.return_value.get_repo.return_value = mock_repo

        config = GitHubSourceConfig(
            repositories=[GitHubRepoConfig(name="my-repo")],
            include=["readme"],
        )
        crawler = _make_crawler(config)
        chunks = crawler.crawl()

        assert len(chunks) == 1
        mock_repo.get_readme.assert_called_once()

    @patch("github.Github")
    def test_per_repo_include_overrides_global(self, mock_github_cls: MagicMock) -> None:
        file_content = _make_content_file("src/config.yml", "key: value")
        mock_repo = MagicMock()
        mock_repo.get_contents.return_value = file_content
        mock_github_cls.return_value.get_repo.return_value = mock_repo

        config = GitHubSourceConfig(
            repositories=[
                GitHubRepoConfig(name="config", include=["src/config.yml"]),
            ],
            include=["readme"],
        )
        crawler = _make_crawler(config)
        chunks = crawler.crawl()

        assert len(chunks) == 1
        mock_repo.get_readme.assert_not_called()
        mock_repo.get_contents.assert_called_once_with("src/config.yml")

    @patch("github.Github")
    def test_per_repo_include_with_readme_and_files(self, mock_github_cls: MagicMock) -> None:
        readme = _make_content_file("README.md", "# Readme")
        file_content = _make_content_file("src/config.yml", "key: value")
        mock_repo = MagicMock()
        mock_repo.get_readme.return_value = readme
        mock_repo.get_contents.return_value = file_content
        mock_github_cls.return_value.get_repo.return_value = mock_repo

        config = GitHubSourceConfig(
            repositories=[
                GitHubRepoConfig(name="config", include=["readme", "src/config.yml"]),
            ],
        )
        crawler = _make_crawler(config)
        chunks = crawler.crawl()

        assert len(chunks) == 2
        mock_repo.get_readme.assert_called_once()
        mock_repo.get_contents.assert_called_once_with("src/config.yml")

    @patch("github.Github")
    def test_glob_pattern_indexes_directory_files(self, mock_github_cls: MagicMock) -> None:
        file_a = _make_content_file("src/markets/de.yml", "locale: de")
        file_b = _make_content_file("src/markets/fr.yml", "locale: fr")
        subdir = _make_content_file("src/markets/old", "", file_type="dir")
        mock_repo = MagicMock()
        mock_repo.get_contents.return_value = [file_a, file_b, subdir]
        mock_github_cls.return_value.get_repo.return_value = mock_repo

        config = GitHubSourceConfig(
            repositories=[
                GitHubRepoConfig(name="config", include=["src/markets/*"]),
            ],
        )
        crawler = _make_crawler(config)
        chunks = crawler.crawl()

        assert len(chunks) == 2
        mock_repo.get_contents.assert_called_once_with("src/markets")

    @patch("github.Github")
    def test_glob_skips_subdirectories(self, mock_github_cls: MagicMock) -> None:
        file_a = _make_content_file("src/markets/de.yml", "locale: de")
        subdir = _make_content_file("src/markets/nested", "", file_type="dir")
        mock_repo = MagicMock()
        mock_repo.get_contents.return_value = [file_a, subdir]
        mock_github_cls.return_value.get_repo.return_value = mock_repo

        config = GitHubSourceConfig(
            repositories=[
                GitHubRepoConfig(name="config", include=["src/markets/*"]),
            ],
        )
        crawler = _make_crawler(config)
        chunks = crawler.crawl()

        assert len(chunks) == 1
        assert chunks[0].metadata["file"] == "src/markets/de.yml"

    @patch("github.Github")
    def test_file_not_found_continues(self, mock_github_cls: MagicMock) -> None:
        mock_repo = MagicMock()
        mock_repo.get_contents.side_effect = GithubException(404, "Not Found", None)
        mock_github_cls.return_value.get_repo.return_value = mock_repo

        config = GitHubSourceConfig(
            repositories=[
                GitHubRepoConfig(name="config", include=["missing.yml"]),
            ],
        )
        crawler = _make_crawler(config)
        chunks = crawler.crawl()

        assert chunks == []

    @patch("github.Github")
    def test_repo_not_found_continues(self, mock_github_cls: MagicMock) -> None:
        mock_github_cls.return_value.get_repo.side_effect = GithubException(404, "Not Found", None)

        config = GitHubSourceConfig(
            repositories=[GitHubRepoConfig(name="missing-repo")],
            include=["readme"],
        )
        crawler = _make_crawler(config)
        chunks = crawler.crawl()

        assert chunks == []

    @patch("github.Github")
    def test_default_org_prepended(self, mock_github_cls: MagicMock) -> None:
        readme = _make_content_file("README.md", "# Hello")
        mock_repo = MagicMock()
        mock_repo.get_readme.return_value = readme
        mock_github_cls.return_value.get_repo.return_value = mock_repo

        config = GitHubSourceConfig(
            repositories=[GitHubRepoConfig(name="my-repo")],
            include=["readme"],
        )
        crawler = _make_crawler(config, default_org="my-org")
        crawler.crawl()

        mock_github_cls.return_value.get_repo.assert_called_once_with("my-org/my-repo")


class TestIsSensitive:
    """Tests for the _is_sensitive filter function."""

    def test_filename_pattern_matches(self) -> None:
        assert _is_sensitive(".env", [".env"]) is True
        assert _is_sensitive("config/.env", [".env"]) is True

    def test_filename_wildcard_matches(self) -> None:
        assert _is_sensitive("server.pem", ["*.pem"]) is True
        assert _is_sensitive("deep/path/cert.pem", ["*.pem"]) is True

    def test_filename_pattern_no_match(self) -> None:
        assert _is_sensitive("config.yml", [".env", "*.pem"]) is False

    def test_dotenv_variants(self) -> None:
        assert _is_sensitive(".env.local", [".env.*"]) is True
        assert _is_sensitive(".env.production", [".env.*"]) is True
        assert _is_sensitive("src/.env.test", [".env.*"]) is True

    def test_path_pattern_matches_full_path(self) -> None:
        assert _is_sensitive("config/secrets/prod.yaml", ["config/secrets/*"]) is True

    def test_path_pattern_no_match_different_dir(self) -> None:
        assert _is_sensitive("other/secrets/prod.yaml", ["config/secrets/*"]) is False

    def test_path_pattern_with_wildcard_dir(self) -> None:
        assert _is_sensitive("deploy/secrets/db.yml", ["*/secrets/*"]) is True
        assert _is_sensitive("k8s/secrets/api.yml", ["*/secrets/*"]) is True

    def test_empty_patterns_matches_nothing(self) -> None:
        assert _is_sensitive(".env", []) is False
        assert _is_sensitive("secrets.yaml", []) is False

    def test_symfony_parameters_yml(self) -> None:
        patterns = ["parameters.yml", "parameters.*.yml"]
        assert _is_sensitive("parameters.yml", patterns) is True
        assert _is_sensitive("parameters.prod.yml", patterns) is True
        assert _is_sensitive("app/parameters.yml", patterns) is True

    def test_vendor_dir_pattern(self) -> None:
        assert _is_sensitive("vendor/autoload.php", ["vendor/*"]) is True
        assert _is_sensitive("src/vendor.php", ["vendor/*"]) is False


class TestExcludePatternsCrawl:
    """Tests for exclude_patterns filtering during crawl."""

    @patch("github.Github")
    def test_sensitive_file_skipped(self, mock_github_cls: MagicMock) -> None:
        env_file = _make_content_file(".env", "SECRET=abc")
        config_file = _make_content_file("config.yml", "key: value")
        mock_repo = MagicMock()
        mock_repo.get_contents.return_value = [env_file, config_file]
        mock_github_cls.return_value.get_repo.return_value = mock_repo

        config = GitHubSourceConfig(
            repositories=[GitHubRepoConfig(name="repo", include=["*"])],
            exclude_patterns=[".env"],
        )
        crawler = _make_crawler(config)
        chunks = crawler.crawl()

        assert len(chunks) == 1
        assert chunks[0].metadata["file"] == "config.yml"

    @patch("github.Github")
    def test_path_pattern_excludes_directory(self, mock_github_cls: MagicMock) -> None:
        secret = _make_content_file("config/secrets/prod.yaml", "password: x")
        normal = _make_content_file("config/routes.yaml", "routes: []")
        mock_repo = MagicMock()
        mock_repo.get_contents.side_effect = lambda path: {
            "config/secrets": [secret],
            "config/routes.yaml": normal,
        }[path]
        mock_github_cls.return_value.get_repo.return_value = mock_repo

        config = GitHubSourceConfig(
            repositories=[
                GitHubRepoConfig(
                    name="app",
                    include=["config/secrets/*", "config/routes.yaml"],
                ),
            ],
            exclude_patterns=["config/secrets/*"],
        )
        crawler = _make_crawler(config)
        chunks = crawler.crawl()

        assert len(chunks) == 1
        assert chunks[0].metadata["file"] == "config/routes.yaml"

    @patch("github.Github")
    def test_no_exclude_patterns_indexes_all(self, mock_github_cls: MagicMock) -> None:
        file_a = _make_content_file("a.yml", "a")
        file_b = _make_content_file("b.yml", "b")
        mock_repo = MagicMock()
        mock_repo.get_contents.return_value = [file_a, file_b]
        mock_github_cls.return_value.get_repo.return_value = mock_repo

        config = GitHubSourceConfig(
            repositories=[GitHubRepoConfig(name="repo", include=["*"])],
            exclude_patterns=[],
        )
        crawler = _make_crawler(config)
        chunks = crawler.crawl()

        assert len(chunks) == 2


class TestFileContentHeader:
    """Tests for Repository/File/Summary header prepended to file chunks."""

    @patch("github.Github")
    def test_header_prepended_to_file_content(self, mock_github_cls: MagicMock) -> None:
        content_file = _make_content_file("src/config.yml", "key: value")
        mock_repo = MagicMock()
        mock_repo.get_contents.return_value = content_file
        mock_github_cls.return_value.get_repo.return_value = mock_repo

        config = GitHubSourceConfig(
            repositories=[GitHubRepoConfig(name="repo", include=["src/config.yml"])],
        )
        crawler = _make_crawler(config)
        chunks = crawler.crawl()

        assert "Repository: org/repo" in chunks[0].content
        assert "File: src/config.yml" in chunks[0].content
        assert "key: value" in chunks[0].content

    @patch("github.Github")
    def test_summary_included_when_summarizer_provided(self, mock_github_cls: MagicMock) -> None:
        content_file = _make_content_file("src/config.yml", "key: value")
        mock_repo = MagicMock()
        mock_repo.get_contents.return_value = content_file
        mock_github_cls.return_value.get_repo.return_value = mock_repo

        summarizer = MagicMock()
        summarizer.summarize.return_value = "Application configuration file."

        config = GitHubSourceConfig(
            repositories=[GitHubRepoConfig(name="repo", include=["src/config.yml"])],
        )
        crawler = _make_crawler(config, summarizer=summarizer)
        chunks = crawler.crawl()

        assert "Summary: Application configuration file." in chunks[0].content
        summarizer.summarize.assert_called_once()

    @patch("github.Github")
    def test_no_summary_line_without_summarizer(self, mock_github_cls: MagicMock) -> None:
        content_file = _make_content_file("src/config.yml", "key: value")
        mock_repo = MagicMock()
        mock_repo.get_contents.return_value = content_file
        mock_github_cls.return_value.get_repo.return_value = mock_repo

        config = GitHubSourceConfig(
            repositories=[GitHubRepoConfig(name="repo", include=["src/config.yml"])],
        )
        crawler = _make_crawler(config)
        chunks = crawler.crawl()

        assert "Summary:" not in chunks[0].content

    @patch("github.Github")
    def test_summarizer_error_gracefully_skipped(self, mock_github_cls: MagicMock) -> None:
        content_file = _make_content_file("src/config.yml", "key: value")
        mock_repo = MagicMock()
        mock_repo.get_contents.return_value = content_file
        mock_github_cls.return_value.get_repo.return_value = mock_repo

        summarizer = MagicMock()
        summarizer.summarize.side_effect = RuntimeError("API down")

        config = GitHubSourceConfig(
            repositories=[GitHubRepoConfig(name="repo", include=["src/config.yml"])],
        )
        crawler = _make_crawler(config, summarizer=summarizer)
        chunks = crawler.crawl()

        assert len(chunks) == 1
        assert "Summary:" not in chunks[0].content

    @patch("github.Github")
    def test_summarize_disabled_per_repo(self, mock_github_cls: MagicMock) -> None:
        content_file = _make_content_file("src/config.yml", "key: value")
        mock_repo = MagicMock()
        mock_repo.get_contents.return_value = content_file
        mock_github_cls.return_value.get_repo.return_value = mock_repo

        summarizer = MagicMock()
        summarizer.summarize.return_value = "Should not appear."

        config = GitHubSourceConfig(
            repositories=[
                GitHubRepoConfig(name="repo", include=["src/config.yml"], summarize=False),
            ],
        )
        crawler = _make_crawler(config, summarizer=summarizer)
        chunks = crawler.crawl()

        assert "Summary:" not in chunks[0].content
        summarizer.summarize.assert_not_called()


class TestParseGithubConfigNew:
    """Tests for new config parsing features."""

    def test_exclude_patterns_parsed(self) -> None:
        raw = {
            "repositories": ["repo-a"],
            "exclude_patterns": [".env", "*.pem", "config/secrets/*"],
        }
        config = _parse_github_config(raw)

        assert config.exclude_patterns == [".env", "*.pem", "config/secrets/*"]

    def test_exclude_patterns_default_empty(self) -> None:
        config = _parse_github_config({"repositories": ["repo-a"]})
        assert config.exclude_patterns == []

    def test_summarize_per_repo_parsed(self) -> None:
        raw = {
            "repositories": [
                {"repo-a": {"include": ["readme"], "summarize": False}},
                {"repo-b": {"include": ["readme"]}},
            ],
        }
        config = _parse_github_config(raw)

        assert config.repositories[0].summarize is False
        assert config.repositories[1].summarize is True

    def test_summarize_defaults_true(self) -> None:
        raw = {"repositories": ["repo-a"]}
        config = _parse_github_config(raw)
        assert config.repositories[0].summarize is True


class TestParseSummarizerConfig:
    """Tests for _parse_summarizer config parsing."""

    def test_returns_none_when_disabled(self) -> None:
        assert _parse_summarizer({"enabled": False, "model": "m", "api_key": "k"}) is None

    def test_returns_none_when_none(self) -> None:
        assert _parse_summarizer(None) is None

    def test_returns_none_when_empty(self) -> None:
        assert _parse_summarizer({}) is None

    def test_returns_none_when_missing_model(self) -> None:
        assert _parse_summarizer({"enabled": True, "api_key": "k"}) is None

    def test_returns_none_when_missing_api_key(self) -> None:
        assert _parse_summarizer({"enabled": True, "model": "m"}) is None

    def test_returns_config_when_valid(self) -> None:
        result = _parse_summarizer(
            {
                "enabled": True,
                "model": "gpt-4o-mini",
                "api_key": "sk-test",
            }
        )
        assert result is not None
        assert result.model == "gpt-4o-mini"
        assert result.api_key == "sk-test"
        assert result.api_url is None

    def test_includes_api_url(self) -> None:
        result = _parse_summarizer(
            {
                "enabled": True,
                "model": "gpt-4o-mini",
                "api_key": "sk-test",
                "api_url": "https://proxy.example.com",
            }
        )
        assert result is not None
        assert result.api_url == "https://proxy.example.com"
