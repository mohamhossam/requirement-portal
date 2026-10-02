"""Opt-in HTTP search load measurement. Results are measurements, not release approval.

Only /health, /ready and the read-only POST /knowledge/search/unified are called: the
requirement service's search over Requirements and published library passages. The
library's own search is the knowledge service's to measure (ADR-0099). Supply
representative queries and run against an explicitly selected qualification environment.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from time import perf_counter

import httpx
from pydantic import TypeAdapter, ValidationError

from smb_requirement_agent.application.use_cases.unified_knowledge_search import UnifiedSearchHit


@dataclass(frozen=True)
class SearchSample:
    elapsed_ms: float
    status: int | None
    result_count: int
    error: str | None


def summarize(samples: tuple[SearchSample, ...]) -> dict[str, object]:
    if not samples:
        raise ValueError("At least one measured request is required.")
    successful = sorted(sample.elapsed_ms for sample in samples if sample.error is None)
    errors: dict[str, int] = {}
    for sample in samples:
        if sample.error:
            errors[sample.error] = errors.get(sample.error, 0) + 1
    return {
        "requests": len(samples),
        "successful_requests": len(successful),
        "errors": errors,
        "empty_results": sum(s.error is None and s.result_count == 0 for s in samples),
        "http_search_p50_ms": successful[math.ceil(len(successful) * 0.50) - 1]
        if successful
        else None,
        "http_search_p95_ms": successful[math.ceil(len(successful) * 0.95) - 1]
        if successful
        else None,
        "http_search_max_ms": max(successful) if successful else None,
        "all_requests_succeeded": not errors,
        "capacity_qualified": False,
    }


def measure(
    base_url: str,
    queries: tuple[str, ...],
    users: int,
    requests: int,
    token: str | None,
    timeout: float,
) -> dict[str, object]:
    url = httpx.URL(base_url)
    if url.scheme not in ("http", "https") or url.userinfo or url.query or url.fragment:
        raise ValueError("Supply an HTTP(S) base URL without embedded credentials/query/fragment.")
    if token and url.scheme != "https" and url.host not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Bearer credentials require HTTPS outside loopback.")
    if users < 1 or requests < users or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Supply positive users/timeout and at least one request per user.")
    if not queries or any(not q.strip() or len(q) > 2000 for q in queries):
        raise ValueError("Queries require 1–2,000 characters each.")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with httpx.Client(base_url=base_url, headers=headers, timeout=timeout) as client:
        for path in ("/health", "/ready"):
            client.get(path).raise_for_status()
    barrier = Barrier(users, timeout=timeout)
    codec = TypeAdapter(tuple[UnifiedSearchHit, ...])

    def worker(index: int) -> tuple[SearchSample, ...]:
        samples: list[SearchSample] = []
        with httpx.Client(base_url=base_url, headers=headers, timeout=timeout) as client:
            barrier.wait()
            for position in range(index, requests, users):
                started = perf_counter()
                status = None
                count = 0
                error = None
                try:
                    response = client.post(
                        "/knowledge/search/unified",
                        json={"query": queries[position % len(queries)]},
                    )
                    status = response.status_code
                    response.raise_for_status()
                    count = len(codec.validate_json(response.content))
                except (httpx.HTTPError, ValidationError) as exc:
                    # Never export response bodies, query texts, tokens, or provider messages.
                    error = f"HTTP_{status}" if status and status >= 400 else type(exc).__name__
                samples.append(
                    SearchSample((perf_counter() - started) * 1000, status, count, error)
                )
        return tuple(samples)

    started = perf_counter()
    with ThreadPoolExecutor(max_workers=users) as pool:
        samples = tuple(sample for batch in pool.map(worker, range(users)) for sample in batch)
    seconds = perf_counter() - started
    return {
        "measured_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "concurrent_clients": users,
        "query_count": len(queries),
        "wall_seconds": seconds,
        "requests_per_second": requests / seconds,
        "scope": "HTTP unified search including query embedding; successful response latency only",
        "limits": "Corpus size, database/embedding timing, ingestion fairness and semantic quality "
        "must be qualified separately. Closed-loop clients; no think time; no warmup excluded.",
        **summarize(samples),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--users", type=int, default=25)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    token = args.token_file.read_text(encoding="utf-8").strip() if args.token_file else None
    if args.token_file and not token:
        parser.error("The supplied token file is empty.")
    queries = TypeAdapter(tuple[str, ...]).validate_json(args.queries.read_bytes())
    report = measure(args.base_url, queries, args.users, args.requests, token, args.timeout)
    encoded = json.dumps(report, indent=2)
    args.output.write_text(encoded, encoding="utf-8")
    print(encoded)
    return 0 if report["all_requests_succeeded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
