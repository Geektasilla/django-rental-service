from typing import Callable, Optional, TypeVar

from django.core.management.base import CommandError

T = TypeVar("T")


def top_up(
    existing: list[T],
    target_count: int,
    create_one: Callable[[], T],
    *,
    max_attempts_per_target: int = 10,
    label: str = "items",
    on_error: Optional[Callable[[Exception], None]] = None,
) -> None:
    """
    Grow `existing` in place up to target_count by repeatedly calling create_one().

    Used for resumable/checkpointed data generation (e.g. seed_data): callers pass in
    whatever already exists (from a previous run), and only the missing amount gets created.

    :param existing: list to top up in place; its current length counts toward the target.
    :param target_count: desired final length of `existing`.
    :param create_one: zero-arg callable that creates and returns one item, or raises on
        failure. Any side effects beyond the returned item (e.g. updating other tracking
        lists) must be handled inside it.
    :param max_attempts_per_target: retry budget per still-missing item before giving up -
        covers occasional transient/random failures without looping forever on a systematic one.
    :param label: noun used in the error message if the attempt budget is exhausted.
    :param on_error: optional callback invoked with the exception each time create_one() fails,
        e.g. to log a warning. Failures are otherwise swallowed and retried.
    :raises CommandError: if attempts exceed (remaining * max_attempts_per_target) without
        reaching target_count.
    """
    remaining = target_count - len(existing)
    max_attempts = max(remaining, 0) * max_attempts_per_target
    attempts = 0

    while len(existing) < target_count:
        attempts += 1
        if attempts > max_attempts:
            raise CommandError(
                f"Gave up creating {label} after {attempts} attempts "
                f"({len(existing)}/{target_count} created) - check the errors above."
            )
        try:
            item = create_one()
        except Exception as exc:
            if on_error:
                on_error(exc)
            continue
        existing.append(item)
