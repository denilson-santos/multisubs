"""Invocation-local cooperative cancellation for synchronous public APIs."""

from collections.abc import Callable

from .errors import CancelledError, ValidationError

CancellationCheck = Callable[[], bool] | None


def check_cancelled(should_cancel: CancellationCheck) -> None:
    """Raise at a stage boundary without changing any shared cancellation state."""
    if should_cancel is not None:
        if not callable(should_cancel):
            raise ValidationError("should_cancel must be callable or None")
        if should_cancel():
            raise CancelledError("The multisubs operation was cancelled")
