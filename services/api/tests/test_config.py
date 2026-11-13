from app.core.config import Settings


def test_empty_environment_variables_fall_back_to_defaults(monkeypatch) -> None:
    # Docker Compose passes an unset ${VAR:-} as an empty string. For the JSON
    # settings that used to be a parse error, so the API wouldn't start.
    for name in (
        "TRACEROAI_PROJECT_API_KEYS",
        "TRACEROAI_ADMIN_API_KEYS",
        "TRACEROAI_PUBLIC_READ_PROJECTS",
        "TRACEROAI_CORS_ORIGINS",
        "TRACEROAI_OPENAI_API_KEY",
        "TRACEROAI_JUDGE_BASE_URL",
        "TRACEROAI_REQUIRE_API_KEY",
    ):
        monkeypatch.setenv(name, "")

    settings = Settings(_env_file=None)

    assert settings.project_api_keys == {}
    assert settings.admin_api_keys == []
    assert settings.public_read_projects == []
    assert settings.cors_origins == []
    assert settings.openai_api_key is None
    assert settings.judge_base_url is None
    assert settings.require_api_key is None


def test_json_settings_parse_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("TRACEROAI_PROJECT_API_KEYS", '{"key": "my-app"}')
    monkeypatch.setenv("TRACEROAI_ADMIN_API_KEYS", '["admin"]')

    settings = Settings(_env_file=None)

    assert settings.project_api_keys == {"key": "my-app"}
    assert settings.admin_api_keys == ["admin"]
