"""Print the knowledge service the API will call, for the launchers' ready banner (ADR-0099).

The same rule as the API: the knowledge service is called only with both
KNOWLEDGE_API_BASE_URL and REQUIREMENT_SERVICE_TOKEN; otherwise offline
stand-ins answer. Prints one line and never a token. It never fails a launch:
a configuration it cannot read is reported as unknown.
"""

from smb_requirement_agent.infrastructure.config.options import ConfigurationError
from smb_requirement_agent.infrastructure.config.settings import Settings

OFFLINE = "offline stand-ins (set KNOWLEDGE_API_BASE_URL and REQUIREMENT_SERVICE_TOKEN to connect)"


def describe() -> str:
    try:
        url = Settings.from_env().knowledge_service_url
    except ConfigurationError:
        return "unknown (the configuration did not load)"
    return url if url is not None else OFFLINE


def main() -> None:
    print(describe())


if __name__ == "__main__":
    main()
