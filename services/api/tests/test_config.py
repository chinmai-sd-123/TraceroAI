from app.core.config import Settings


def test_an_empty_variable_overrides_the_env_file(tmp_path, monkeypatch) -> None:
    # Blanking a variable in the shell must switch the service off even when
    # .env sets it: local runs rely on this to keep away from real services.
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TRACEROAI_OPENAI_API_KEY=sk-from-dotenv\n"
        "TRACEROAI_REDIS_URL=rediss://production.example:6379\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TRACEROAI_OPENAI_API_KEY", "")
    monkeypatch.setenv("TRACEROAI_REDIS_URL", "")

    settings = Settings(_env_file=env_file)

    assert not settings.openai_api_key
    assert not settings.redis_url


def test_compose_defaults_parse(monkeypatch) -> None:
    # infra/docker-compose.yml passes these when the variables are unset.
    monkeypatch.setenv("TRACEROAI_PROJECT_API_KEYS", "{}")
    monkeypatch.setenv("TRACEROAI_ADMIN_API_KEYS", "[]")
    monkeypatch.setenv("TRACEROAI_OPENAI_API_KEY", "")
    monkeypatch.setenv("TRACEROAI_JUDGE_BASE_URL", "")

    settings = Settings(_env_file=None)

    assert settings.project_api_keys == {}
    assert settings.admin_api_keys == []
    assert not settings.openai_api_key
    assert settings.judge_base_url is None


def test_json_settings_parse_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("TRACEROAI_PROJECT_API_KEYS", '{"key": "my-app"}')
    monkeypatch.setenv("TRACEROAI_ADMIN_API_KEYS", '["admin"]')

    settings = Settings(_env_file=None)

    assert settings.project_api_keys == {"key": "my-app"}
    assert settings.admin_api_keys == ["admin"]
