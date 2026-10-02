"""API startup lifecycle regression coverage."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.infrastructure.observability.metrics import Metrics
from smb_requirement_agent.interfaces.api import main as api_main


@dataclass(frozen=True)
class LifecycleSettings:
    """The settings the lifespan reads; recorded by the startup trace event."""

    api_background_workers: bool = True
    metrics_port: int | None = None
    metrics_host: str = "127.0.0.1"
    request_max_body_bytes: int = 2 * 1024 * 1024
    document_max_file_bytes: int = 10 * 1024 * 1024


class DocumentWorker:
    healthy = True

    def start(self) -> None:
        pass

    def stop(self) -> bool:
        return True

    def wait_until_stopped(self) -> None:
        pass


def _container(
    ai_job_worker: object,
    *,
    settings: LifecycleSettings | None = None,
    **fields: object,
) -> SimpleNamespace:
    """A lifecycle-only graph whose workers are keyed like the real container's."""
    index_worker, document_worker = DocumentWorker(), DocumentWorker()
    return SimpleNamespace(
        background_workers={
            "requirement_index_worker": index_worker,
            "workers": ai_job_worker,
            "document_worker": document_worker,
        },
        settings=settings or LifecycleSettings(),
        metrics=Metrics(),
        **fields,
    )


def test_lifespan_and_dependencies_share_the_factory_container() -> None:
    events: list[str] = []

    class Trace:
        def record(self, event: str, **fields: object) -> None:
            pass

        def close(self) -> None:
            pass

    class Worker:
        def start(self) -> None:
            events.append("worker-start")

        def stop(self) -> bool:
            events.append("worker-stop")
            return True

        def wait_until_stopped(self) -> None:
            events.append("worker-wait")

    container = _container(
        Worker(),
        debug_trace=Trace(),
        close_resources=lambda: events.append("resources-close"),
    )
    app = api_main.create_app(lambda: cast(Any, container))

    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            assert app.state.container is container
            events.append("serving")

    asyncio.run(run_lifespan())

    assert events == ["worker-start", "serving", "worker-stop", "resources-close"]


def test_lifespan_does_not_close_resources_until_fenced_workers_return() -> None:
    release_worker = threading.Event()
    resources_closed = threading.Event()

    class Trace:
        def record(self, event: str, **fields: object) -> None:
            del event, fields

        def close(self) -> None:
            return None

    class Worker:
        def start(self) -> None:
            return None

        def stop(self) -> bool:
            return False

        def wait_until_stopped(self) -> None:
            release_worker.wait(timeout=2)

    container = _container(Worker(), debug_trace=Trace(), close_resources=resources_closed.set)
    application = api_main.create_app(lambda: cast(Any, container))

    async def run_lifespan() -> None:
        async with application.router.lifespan_context(application):
            return None

    asyncio.run(run_lifespan())
    assert resources_closed.is_set() is False

    release_worker.set()
    assert resources_closed.wait(timeout=1)


def test_worker_start_failure_closes_resources_without_serving_requests() -> None:
    events: list[str] = []

    class Worker:
        def start(self) -> None:
            raise RuntimeError("worker could not start")

        def stop(self) -> bool:
            events.append("stopped")
            return True

    container = _container(
        Worker(),
        debug_trace=SimpleNamespace(
            record=lambda *args, **kwargs: None,
            close=lambda: events.append("trace closed"),
        ),
        close_resources=lambda: events.append("resources closed"),
    )
    application = api_main.create_app(lambda: cast(Any, container))

    async def start() -> None:
        async with application.router.lifespan_context(application):
            pytest.fail("A failed worker startup must never start serving.")

    with pytest.raises(RuntimeError, match="worker could not start"):
        asyncio.run(start())
    assert application.state.accepting_requests is False
    assert events == ["stopped", "resources closed", "trace closed"]


def test_worker_that_fails_to_stop_keeps_resources_open_and_others_still_stop() -> None:
    events: list[str] = []
    resources_closed = threading.Event()

    class BrokenStop:
        healthy = True

        def start(self) -> None:
            return None

        def stop(self) -> bool:
            raise RuntimeError("stop failed")

        def wait_until_stopped(self) -> None:
            events.append("waited for broken worker")

    class Recorded(DocumentWorker):
        def stop(self) -> bool:
            events.append("other worker stopped")
            return True

    container = _container(
        BrokenStop(),
        debug_trace=SimpleNamespace(record=lambda *args, **kwargs: None, close=lambda: None),
        close_resources=resources_closed.set,
    )
    container.background_workers["requirement_index_worker"] = Recorded()
    application = api_main.create_app(lambda: cast(Any, container))

    async def run_lifespan() -> None:
        async with application.router.lifespan_context(application):
            return None

    asyncio.run(run_lifespan())

    # Resources close only on the cleanup thread, after the broken worker returned.
    assert resources_closed.wait(timeout=1)
    assert events == ["other worker stopped", "waited for broken worker"]


def test_readiness_tracks_persistence_and_worker_health_without_provider_calls() -> None:
    class Worker:
        healthy = True

        def start(self) -> None:
            return None

        def stop(self) -> bool:
            return True

    worker = Worker()
    persistence_ready = True
    container = _container(
        worker,
        debug_trace=SimpleNamespace(record=lambda *args, **kwargs: None, close=lambda: None),
        close_resources=lambda: None,
        readiness_check=lambda: persistence_ready,
    )
    # This graph deliberately has no provider. Readiness must not need one.
    application = api_main.create_app(lambda: cast(Any, container))
    with TestClient(application) as client:
        assert client.get("/ready").status_code == 200
        persistence_ready = False
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json()["checks"]["persistence"] is False
        persistence_ready = True
        worker.healthy = False
        assert client.get("/ready").status_code == 503
        assert client.get("/health").status_code == 200
        worker.healthy = True
        container.background_workers["document_worker"].healthy = False
        assert client.get("/ready").json()["checks"]["document_worker"] is False
        container.background_workers["document_worker"].healthy = True
        container.background_workers["requirement_index_worker"].healthy = False
        assert client.get("/ready").json()["checks"]["requirement_index_worker"] is False


def test_http_only_replica_neither_starts_nor_reports_background_workers() -> None:
    class NeverStarted(DocumentWorker):
        healthy = False

        def start(self) -> None:
            pytest.fail("API_BACKGROUND_WORKERS=false must not start workers.")

        def stop(self) -> bool:
            pytest.fail("Workers this process never started must not be stopped.")

    container = _container(
        NeverStarted(),
        settings=LifecycleSettings(api_background_workers=False),
        debug_trace=SimpleNamespace(record=lambda *args, **kwargs: None, close=lambda: None),
        close_resources=lambda: None,
        readiness_check=lambda: True,
    )
    for name in ("requirement_index_worker", "document_worker"):
        container.background_workers[name] = NeverStarted()
    application = api_main.create_app(lambda: cast(Any, container))

    with TestClient(application) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["checks"] == {"accepting_requests": True, "persistence": True}
