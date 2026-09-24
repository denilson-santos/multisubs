"""Subtitle file serializers shared by ASR and timed-cue input."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from numbers import Real
from pathlib import Path
from typing import Any

from .errors import ArtifactError
from .utils import atomic_write_text


def write_srt(path: Path, cues: Sequence[Mapping[str, Any]]) -> None:
    """Serialize displayed cues in input order as an SRT file."""
    blocks: list[str] = []
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            "\n".join(
                (
                    str(index),
                    f"{format_srt_time(cue['start'])} --> "
                    f"{format_srt_time(cue['end'])}",
                    str(cue["text"]).strip(),
                )
            )
        )
    atomic_write_text(path, "\n\n".join(blocks) + ("\n\n" if blocks else ""))


def format_srt_time(seconds: object) -> str:
    """Format a finite nonnegative second value at SRT millisecond precision."""
    if isinstance(seconds, bool) or not isinstance(seconds, Real):
        raise ArtifactError("SRT timestamp must be a finite, non-negative number")
    try:
        value = float(seconds)
    except OverflowError as exc:
        raise ArtifactError(
            "SRT timestamp must be a finite, non-negative number"
        ) from exc
    if not math.isfinite(value) or value < 0:
        raise ArtifactError("SRT timestamp must be a finite, non-negative number")
    total_millis = round(value * 1000)
    hours, remainder = divmod(total_millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{millis:03d}"
