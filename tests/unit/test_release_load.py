"""Failed or undersized measurements must never become capacity approval."""

import pytest

from tests.release_load import SearchSample, measure, summarize


def test_percentiles_do_not_hide_failed_requests_or_claim_qualification() -> None:
    samples = tuple(SearchSample(float(i), 200, 1, None) for i in range(1, 101))
    report = summarize((*samples, SearchSample(10000, 503, 0, "HTTP_503")))
    assert report["http_search_p95_ms"] == 95
    assert report["errors"] == {"HTTP_503": 1}
    assert report["all_requests_succeeded"] is False
    assert report["capacity_qualified"] is False


def test_total_outage_has_no_successful_latency() -> None:
    report = summarize((SearchSample(30000, None, 0, "ReadTimeout"),))
    assert report["http_search_p95_ms"] is None
    assert report["successful_requests"] == 0
    assert report["all_requests_succeeded"] is False


def test_empty_measurement_is_not_a_pass() -> None:
    with pytest.raises(ValueError, match="one measured request"):
        summarize(())


def test_remote_plaintext_target_cannot_receive_a_bearer_token() -> None:
    with pytest.raises(ValueError, match="require HTTPS"):
        measure("http://example.invalid", ("synthetic",), 1, 1, "test-token", 1)
