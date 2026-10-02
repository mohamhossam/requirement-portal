"""Background polling of the architecture index/mapping job queue."""

import logging
from threading import Event, Thread

from smb_requirement_agent.application.ports.architecture_jobs import ArchitectureJob
from smb_requirement_agent.application.use_cases.leased_jobs import LeasedJobs

_LOGGER = logging.getLogger(__name__)

# Repositories grant a five-minute lease; renewing every minute leaves four
# missed renewals of slack before another worker may reclaim the job.
LEASE_RENEWAL_SECONDS = 60.0


class ArchitectureJobWorker:
    """Claim and run queued architecture jobs on one background thread.

    The worker keeps each claimed job's lease renewed while it runs; the use
    case renews once more inside the commit, so a job whose renewals stopped
    cannot write. The same worker runs in the API process or a worker process.
    """

    def __init__(
        self,
        jobs: LeasedJobs,
        *,
        poll_interval_seconds: float,
        shutdown_grace_seconds: float,
        lease_renewal_seconds: float = LEASE_RENEWAL_SECONDS,
        name: str = "architecture-jobs",
    ) -> None:
        self._jobs = jobs
        self._name = name
        self._poll_interval = poll_interval_seconds
        self._shutdown_grace = shutdown_grace_seconds
        self._lease_renewal = lease_renewal_seconds
        self._stop = Event()
        self._thread: Thread | None = None

    @property
    def healthy(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._run, name=self._name, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                job = self._jobs.claim_next()
            except Exception:
                _LOGGER.exception("Architecture job polling failed")
                job = None
            if job is None:
                self._stop.wait(self._poll_interval)
                continue
            try:
                self._execute(job)
            except Exception:
                _LOGGER.exception("Architecture job %s could not be run", job.id)

    def _execute(self, job: ArchitectureJob) -> None:
        stop_renewing = Event()

        def renew() -> None:
            while not stop_renewing.wait(self._lease_renewal):
                try:
                    if not self._jobs.renew_lease(job):
                        return
                except Exception:
                    # A missed renewal is recoverable until the lease expires;
                    # the commit-time renewal decides whether this attempt writes.
                    _LOGGER.exception("Architecture job %s lease renewal failed", job.id)

        renewer = Thread(target=renew, name=f"architecture-job-lease-{job.id[:8]}", daemon=True)
        renewer.start()
        try:
            completed = self._jobs.execute_claimed(job)
        finally:
            stop_renewing.set()
            renewer.join(timeout=1)
        _LOGGER.info("Architecture job %s: %s", completed.id, completed.status)

    def stop(self) -> bool:
        """Stop polling; True when an in-flight job finished within the grace period."""
        self._stop.set()
        if self._thread is None:
            return True
        self._thread.join(timeout=self._shutdown_grace)
        return not self._thread.is_alive()

    def wait_until_stopped(self) -> None:
        if self._thread is not None:
            self._thread.join()
