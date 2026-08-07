"""Retry policy evaluation: should a terminal job run again, and after how long.

Pure decisions over a :class:`~molq.models.RetryPolicy` and a finished
:class:`~molq.models.JobRecord`.  Actually re-submitting is the Submitor's job;
deciding is this module's.
"""

from __future__ import annotations

from molq.models import JobRecord, RetryPolicy


def should_retry(record: JobRecord, policy: RetryPolicy | None) -> bool:
    """True when *record* is eligible for another attempt under *policy*.

    Three independent gates: attempts remaining, the terminal state being one
    the policy retries, and — when ``retry_on_exit_codes`` is set — the exit
    code matching. ``retry_on_exit_codes=None`` means "any exit code".
    """
    if policy is None:
        return False
    if record.attempt >= policy.max_attempts:
        return False
    if record.state not in policy.retry_on_states:
        return False
    if (
        policy.retry_on_exit_codes is not None
        and record.exit_code not in policy.retry_on_exit_codes
    ):
        return False
    return True


def retry_delay_seconds(policy: RetryPolicy, attempt: int) -> float:
    """Seconds to wait before *attempt*'s successor, capped by the policy.

    ``fixed`` waits the same interval every time; ``exponential`` grows by
    ``factor`` per attempt. Both are clamped to ``maximum_seconds``.
    """
    backoff = policy.backoff
    if backoff.mode == "fixed":
        return min(backoff.initial_seconds, backoff.maximum_seconds)
    delay = backoff.initial_seconds * (backoff.factor ** max(attempt - 1, 0))
    return min(delay, backoff.maximum_seconds)
