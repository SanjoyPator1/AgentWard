from __future__ import annotations

import pytest

from agentward_harness.model import ModelConfig


class TestModelConfigFromEnv:
    def test_defaults_to_ollama_with_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MODEL_PROVIDER", raising=False)
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

        config = ModelConfig.from_env()

        assert config.provider == "ollama"
        assert config.model == "qwen3:8b"
        assert config.base_url == "http://localhost:11434/v1"
        assert config.api_key == "ollama"

    def test_ollama_reads_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MODEL_PROVIDER", "ollama")
        monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:latest")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://example:11434/v1")

        config = ModelConfig.from_env()

        assert config.model == "qwen2.5:latest"
        assert config.base_url == "http://example:11434/v1"

    def test_gemini_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MODEL_PROVIDER", "gemini")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            ModelConfig.from_env()

    def test_gemini_reads_key_and_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MODEL_PROVIDER", "gemini")
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
        monkeypatch.setenv("GEMINI_MODEL", "gemini-3.7-flash")

        config = ModelConfig.from_env()

        assert config.provider == "gemini"
        assert config.api_key == "test-key-123"
        assert config.model == "gemini-3.7-flash"
        assert config.base_url == "https://generativelanguage.googleapis.com/v1beta/openai/"

    def test_gemini_default_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MODEL_PROVIDER", "gemini")
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
        monkeypatch.delenv("GEMINI_MODEL", raising=False)

        config = ModelConfig.from_env()

        assert config.model == "gemini-3.5-flash-lite"

    def test_groq_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MODEL_PROVIDER", "groq")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        with pytest.raises(ValueError, match="GROQ_API_KEY"):
            ModelConfig.from_env()

    def test_groq_reads_key_and_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MODEL_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "test-key-456")
        monkeypatch.setenv("GROQ_MODEL", "llama-3.1-8b-instant")

        config = ModelConfig.from_env()

        assert config.provider == "groq"
        assert config.api_key == "test-key-456"
        assert config.model == "llama-3.1-8b-instant"
        assert config.base_url == "https://api.groq.com/openai/v1"

    def test_groq_default_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MODEL_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "test-key-456")
        monkeypatch.delenv("GROQ_MODEL", raising=False)

        config = ModelConfig.from_env()

        assert config.model == "openai/gpt-oss-120b"

    def test_unknown_provider_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MODEL_PROVIDER", "bedrock")

        with pytest.raises(ValueError, match="Unknown MODEL_PROVIDER"):
            ModelConfig.from_env()
