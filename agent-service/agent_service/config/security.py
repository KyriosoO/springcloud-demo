from agent_service.config.models import Settings


def load_security_settings() -> Settings:
    settings = Settings()  # type: ignore[call-arg]
    validate_security_settings(settings)
    return settings


def validate_security_settings(settings: Settings) -> None:
    for url in (settings.auth_authorization_url, settings.employee_query_url):
        if url.host not in {"127.0.0.1", "localhost"} and url.scheme != "https":
            raise ValueError("non-local security endpoints must use HTTPS")
