from typing import Callable, Optional, TypeVar

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.management.base import CommandError
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from rest_framework import serializers

T = TypeVar("T")


def as_drf_validation_error(exc: DjangoValidationError) -> serializers.ValidationError:
    """
    :param exc: a Django-core ValidationError raised by Model.full_clean() (e.g. Property.clean()).
    :return: an equivalent DRF ValidationError, preserving field-level detail when available.
    """
    return serializers.ValidationError(
        exc.message_dict if hasattr(exc, "message_dict") else exc.messages
    )


def visible_to_participants(
    queryset: QuerySet, user: AbstractBaseUser, *lookups: str
) -> QuerySet:
    """
    :param queryset: base queryset, already `select_related()`/etc. as needed by the caller.
    :param user: the requesting user; staff bypasses filtering and sees every row.
    :param lookups: field lookup paths compared against ``user``, OR'd together (e.g. "tenant",
        "property__owner") - a row is visible if the user matches at least one.
    :return: the queryset unfiltered for staff, otherwise restricted to rows where the user is
        one of the named participants.
    """
    if user.is_staff:
        return queryset
    condition = Q()
    for lookup in lookups:
        condition |= Q(**{lookup: user})
    return queryset.filter(condition).distinct()


def get_client_ip(request: HttpRequest) -> Optional[str]:
    """
    :param request: the incoming HTTP request.
    :return: the client's IP address, preferring the first hop of X-Forwarded-For (set by a
        reverse proxy/load balancer) over REMOTE_ADDR; None if neither header is present.
    """
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


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
