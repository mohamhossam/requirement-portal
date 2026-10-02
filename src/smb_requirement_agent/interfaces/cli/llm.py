"""Local configuration validation and explicit paid-provider/index operations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from smb_requirement_agent.application.errors import KnowledgeGenerationError, ModelTransportError
from smb_requirement_agent.infrastructure.config.options import ConfigurationError
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.interfaces.api.composition.operations import (
    qualify_embedding_tokens,
    smoke_llm_profiles,
)
from smb_requirement_agent.interfaces.api.container import build_container


def validate_launcher(settings: Settings, explicit_provider: str | None) -> None:
    if settings.llm_profiles is not None and explicit_provider is not None:
        raise ConfigurationError(
            "LLM_CONFIG_PATH conflicts with an explicit launcher provider option. "
            "Remove the provider option to use configured profiles."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("check", "smoke", "rebuild", "indexes", "activate", "qualify-tokens")
    )
    parser.add_argument("--samples", help="JSON array of synthetic {case, text} token fixtures")
    parser.add_argument(
        "--input-limit", type=int, default=2048, help="Documented embedding input limit"
    )
    parser.add_argument(
        "--config", help="Profile YAML path; overrides LLM_CONFIG_PATH for this command"
    )
    parser.add_argument(
        "--explicit-provider", help="Used by launchers to reject conflicting selection"
    )
    parser.add_argument("--generation", help="Generation ID to activate or roll back to")
    args = parser.parse_args(argv)
    try:
        settings = Settings.from_env(config_path=args.config)
        validate_launcher(settings, args.explicit_provider)
        if args.command == "check":
            summary = (
                settings.llm_profiles.summary()
                if settings.llm_profiles
                else {
                    "provider": settings.llm_provider.value,
                    "mode": "legacy environment configuration",
                }
            )
            print(json.dumps(summary, indent=2))
            print("Configuration is valid; no paid model requests were made.")
            return 0
        if settings.llm_profiles is None:
            raise ConfigurationError("This command requires LLM_CONFIG_PATH or --config.")
        if args.command == "qualify-tokens":
            if not args.samples:
                raise ConfigurationError(
                    "qualify-tokens requires --samples with synthetic fixtures."
                )
            data = json.loads(Path(args.samples).read_text(encoding="utf-8"))
            if not isinstance(data, list) or not all(
                isinstance(item, dict)
                and isinstance(item.get("case"), str)
                and isinstance(item.get("text"), str)
                for item in data
            ):
                raise ConfigurationError("Token fixtures must be an array of {case, text} objects.")
            result = qualify_embedding_tokens(
                settings,
                tuple((item["case"], item["text"]) for item in data),
                args.input_limit,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return (
                0
                if result["all_within_model_limit"] and result["embedding_requests_accepted"]
                else 1
            )
        if args.command == "smoke":
            print(json.dumps(smoke_llm_profiles(settings), indent=2))
            return 0
        if settings.persistence_provider.value != "postgres":
            raise ConfigurationError("Persistent index commands require PostgreSQL persistence.")
        container = build_container(settings)
        try:
            generations = container.knowledge_index_generations
            rebuild = container.rebuild_knowledge_index
            if generations is None or rebuild is None:
                raise ConfigurationError("Index generations are unavailable.")
            if args.command == "rebuild":
                generation = rebuild.execute()
                print(f"Activated complete generation {generation.id} ({generation.identity}).")
            elif args.command == "activate":
                if not args.generation:
                    raise ConfigurationError("activate requires --generation.")
                generations.activate(args.generation)
                print(f"Activated current generation {args.generation}.")
            else:
                print(
                    json.dumps(
                        [
                            {"id": item.id, "identity": item.identity, "status": item.status}
                            for item in generations.list_generations()
                        ],
                        indent=2,
                    )
                )
        finally:
            container.close_resources()
            container.debug_trace.close()
        return 0
    except (ConfigurationError, ModelTransportError, KnowledgeGenerationError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
