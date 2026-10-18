"""Benchmark synthetic subtitle preparation and FFmpeg rendering without ASR.

Run from a checkout with ``python -m scripts.benchmark_rendering --help``.
Media and logs stay in a fresh directory below the explicitly selected output.
The portable summary contains timings, commands, versions, and validation only.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import random
import re
import shutil
import statistics
import subprocess
import tempfile
import time
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from typing import Any
from unittest.mock import patch

import ffmpeg

from multisubs import __version__, build_subtitle_config
from multisubs import text_segmentation as segmentation
from multisubs.font_catalog import bundled_filesystem_directory
from multisubs.models import SubtitleConfig, TranscriptDocument
from multisubs.subtitler import _build_output_stream, probe_video_geometry
from multisubs.transcriber import (
    _build_subtitle_segments,
    write_transcription_artifacts,
)

STYLES = ("default", "yellow-static", "yellow-pop", "neon-magenta-pulse")


@dataclass(frozen=True)
class Case:
    name: str
    kind: str
    style: str | None = None
    options: tuple[str, ...] = ()
    global_options: tuple[str, ...] = ()


def _config(style: str) -> SubtitleConfig:
    return build_subtitle_config(
        template="yellow-pop" if style == "yellow-static" else style,
        overrides={"disable_word_animations": True} if style == "yellow-static" else {},
    )


def synthetic_segments(duration: float) -> list[dict[str, Any]]:
    """Create explicitly artificial alignment; never use it as ASR evidence."""
    segments = []
    for index in range(math.ceil(duration / 3)):
        start, end = index * 3.0, min((index + 1) * 3.0, duration)
        text = f"Teste {index + 1}: medimos legendas e renderização neste vídeo."
        tokens = text.split()
        step = (end - start) / len(tokens)
        words = [
            {
                "word": token if position == 0 else " " + token,
                "start": start + position * step,
                "end": start + (position + 0.9) * step,
            }
            for position, token in enumerate(tokens)
        ]
        segments.append({"start": start, "end": end, "text": text, "words": words})
    return segments


def _run(command: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def _checked(command: list[str]) -> subprocess.CompletedProcess:
    result = _run(command)
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:])
    return result


def _summary(samples: list[float]) -> dict[str, Any]:
    return {
        "samples": samples,
        "median": statistics.median(samples),
        "min": min(samples),
        "max": max(samples),
    }


def _probe(path: Path, executable: str) -> dict[str, Any]:
    return json.loads(
        _checked(
            [
                executable,
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ]
        ).stdout
    )


def _audio_hash(path: Path, executable: str) -> str:
    return _checked(
        [
            executable,
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-c:a",
            "copy",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ]
    ).stdout.strip()


def _prepare(
    destination: Path,
    source: Path,
    duration: float,
    style: str,
    repetitions: int,
    *,
    boundary_cache: bool = False,
) -> tuple[Path, dict[str, Any]]:
    geometry = probe_video_geometry(source)
    source_segments = synthetic_segments(duration)
    config = _config(style)
    semantic_times, artifact_times = [], []
    for iteration in range(repetitions + 1):
        started = time.perf_counter()
        cues = _build_subtitle_segments(source_segments, language="pt")
        semantic_seconds = time.perf_counter() - started
        document = TranscriptDocument(
            source_path=source,
            language="pt",
            task="transcribe",
            model_name="synthetic-no-asr",
            asr_backend="synthetic",
            full_text=" ".join(segment["text"] for segment in source_segments),
            segments=tuple(cues),
        )
        cached_boundaries = lru_cache(maxsize=4096)(segmentation.line_break_boundaries)
        cache_context = (
            patch.object(segmentation, "line_break_boundaries", cached_boundaries)
            if boundary_cache
            else nullcontext()
        )
        with cache_context:
            started = time.perf_counter()
            artifacts = write_transcription_artifacts(
                document,
                destination / f"{style}-{duration:g}-{iteration}",
                config,
                geometry=geometry,
                verify_font_coverage=True,
            )
            artifact_seconds = time.perf_counter() - started
        cache_counts = cached_boundaries.cache_info()._asdict()
        cached_boundaries.cache_clear()
        if iteration:
            semantic_times.append(semantic_seconds)
            artifact_times.append(artifact_seconds)
    ass = Path(artifacts[2])
    lines = ass.read_text(encoding="utf-8").splitlines()
    metadata = json.loads(Path(artifacts[0]).read_text(encoding="utf-8"))["metadata"]
    return ass, {
        "style": style,
        "timeline_seconds": duration,
        "source_segments": len(source_segments),
        "semantic_cues": len(cues),
        "semantic_seconds": _summary(semantic_times),
        "artifact_seconds": _summary(artifact_times),
        "ass_bytes": ass.stat().st_size,
        "ass_dialogues": sum(line.startswith("Dialogue:") for line in lines),
        "experimental_line_break_cache": boundary_cache,
        "last_cache_counts": cache_counts if boundary_cache else None,
        "metadata": metadata,
    }


def _cases(nvenc: bool) -> list[Case]:
    cases = [Case("decode", "null")]
    cases += [Case(f"filter-{style}", "null", style) for style in STYLES]
    cases += [Case("encode-no-subs", "encode")]
    cases += [Case(f"current-{style}", "encode", style) for style in STYLES]
    for preset in ("fast", "veryfast", "ultrafast"):
        cases.append(
            Case(
                f"x264-{preset}",
                "encode",
                "yellow-pop",
                ("-c:v", "libx264", "-preset", preset, "-crf", "23"),
            )
        )
    cases.append(
        Case(
            "x264-threads8-filter1",
            "encode",
            "yellow-pop",
            ("-c:v", "libx264", "-preset", "medium", "-crf", "23", "-threads", "8"),
            ("-filter_complex_threads", "1"),
        )
    )
    if nvenc:
        for preset, quality in (("p4", 23), ("p7", 23), ("p4", 28), ("p4", 30)):
            name = f"nvenc-{preset}"
            if quality != 23:
                name += f"-cq{quality}"
            cases.append(
                Case(
                    name,
                    "encode",
                    "yellow-pop",
                    (
                        "-c:v",
                        "h264_nvenc",
                        "-preset",
                        preset,
                        "-rc",
                        "vbr",
                        "-cq",
                        str(quality),
                        "-b:v",
                        "0",
                    ),
                )
            )
    return cases


def _command(
    case: Case,
    source: Path,
    ass_files: dict[str, Path],
    output: Path,
    executable: str,
) -> list[str]:
    geometry = probe_video_geometry(source)
    input_stream = ffmpeg.input(str(source))
    if case.style:
        fonts = bundled_filesystem_directory(_config(case.style).style.typography.font)
        graph = _build_output_stream(
            ffmpeg,
            source,
            ass_files[case.style],
            output,
            geometry,
            fonts,
        )
        if case.kind == "null":
            options = {
                "filename": str(ass_files[case.style]),
                "original_size": geometry.original_size,
            }
            if fonts:
                options["fontsdir"] = str(fonts)
            video = input_stream["0"].filter("subtitles", **options)
            graph = ffmpeg.output(video, "-", format="null", vcodec="wrapped_avframe")
    elif case.kind == "null":
        graph = ffmpeg.output(
            input_stream["0"],
            "-",
            format="null",
            vcodec="wrapped_avframe",
        )
    else:
        graph = ffmpeg.output(
            input_stream["0"], input_stream["a?"], str(output), acodec="copy"
        )
    compiled = ffmpeg.compile(graph, cmd=executable)
    return [
        compiled[0],
        "-nostdin",
        "-hide_banner",
        "-benchmark",
        "-y",
        *case.global_options,
        *compiled[1:-1],
        *case.options,
        compiled[-1],
    ]


def _quality(
    source: Path,
    output: Path,
    ass: Path,
    style: str,
    executable: str,
) -> dict[str, float]:
    result = {}
    fonts = bundled_filesystem_directory(_config(style).style.typography.font)
    options = {
        "filename": str(ass),
        "original_size": probe_video_geometry(source).original_size,
    }
    if fonts:
        options["fontsdir"] = str(fonts)
    for label, crop in (("ssim_full", False), ("ssim_bottom35pct", True)):
        reference = ffmpeg.input(str(source)).video.filter("subtitles", **options)
        encoded = ffmpeg.input(str(output)).video
        if crop:
            reference = reference.filter("crop", "iw", "trunc(ih*0.35/2)*2", 0, "ih-oh")
            encoded = encoded.filter("crop", "iw", "trunc(ih*0.35/2)*2", 0, "ih-oh")
        graph = ffmpeg.output(
            ffmpeg.filter([encoded, reference], "ssim"), "-", format="null"
        )
        checked = _checked(ffmpeg.compile(graph, cmd=executable))
        matched = re.search(r"All:([0-9.]+)", checked.stderr)
        if matched is None:
            raise RuntimeError("FFmpeg did not report SSIM")
        result[label] = float(matched[1])
    return result


def benchmark(args: argparse.Namespace) -> Path:
    executable = shutil.which(args.ffmpeg)
    probe_executable = shutil.which(args.ffprobe)
    if executable is None or probe_executable is None:
        raise RuntimeError("FFmpeg and ffprobe must be available")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="render-bench-", dir=args.output_dir))
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": _checked(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "multisubs": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "logical_cpus": os.cpu_count(),
        "cpu": next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            ),
            None,
        ),
        "ffmpeg": _checked([executable, "-version"]).stdout,
        "ffprobe": _checked([probe_executable, "-version"]).stdout.splitlines()[0],
        "packages": {
            package: version(package)
            for package in ("Pillow", "ffmpeg-python", "fonttools", "uniseg")
        },
        "parameters": {
            "duration": args.duration,
            "fps": args.fps,
            "repetitions": args.repetitions,
            "sizes": args.sizes,
            "warmups": 1,
            "seed": 20261018,
            "quality": args.quality,
            "cases": args.cases,
            "preparation_only": args.preparation_only,
            "experimental_line_break_cache": args.experimental_line_break_cache,
        },
        "preparation": [],
        "cases": [],
    }
    gpu = shutil.which("nvidia-smi")
    if gpu:
        result = _run(
            [
                gpu,
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader",
            ]
        )
        evidence["gpu"] = (result.stdout or result.stderr).strip()

    def save() -> None:
        # Keep machine-local paths out of the portable summary.
        serialized = json.dumps(evidence, indent=2, ensure_ascii=False)
        serialized = serialized.replace(str(destination.resolve()), "<run>")
        serialized = serialized.replace(str(destination), "<run>")
        serialized = serialized.replace(str(Path.cwd()), "<repo>")
        serialized = serialized.replace(str(Path.home()), "<home>")
        (destination / "summary.json").write_text(serialized + "\n", encoding="utf-8")

    for size in args.sizes:
        width, height = map(int, size.split("x"))
        source = destination / f"source-{size}.mp4"
        print(f"Generating {size}, {args.duration:g}s at {args.fps} fps", flush=True)
        _checked(
            [
                executable,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"testsrc2=size={size}:rate={args.fps}",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:sample_rate=48000",
                "-t",
                str(args.duration),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                str(source),
            ]
        )
        evidence.setdefault("sources", {})[size] = _probe(source, probe_executable)
        source_hash = _audio_hash(source, executable)
        ass_files = {}
        for style in STYLES:
            ass, preparation = _prepare(
                destination,
                source,
                args.duration,
                style,
                args.repetitions,
                boundary_cache=args.experimental_line_break_cache,
            )
            ass_files[style] = ass
            evidence["preparation"].append({"size": size, **preparation})
        if size == args.sizes[0]:
            for timeline in args.preparation_seconds:
                _, preparation = _prepare(
                    destination,
                    source,
                    timeline,
                    "yellow-pop",
                    args.repetitions,
                    boundary_cache=args.experimental_line_break_cache,
                )
                evidence["preparation"].append({"size": size, **preparation})
        if args.preparation_only:
            save()
            continue
        cases = _cases(args.nvenc)
        if args.cases:
            cases = [case for case in cases if case.name in args.cases]
        outputs = {case.name: destination / f"{size}-{case.name}.mp4" for case in cases}
        commands = {
            case.name: _command(case, source, ass_files, outputs[case.name], executable)
            for case in cases
        }
        records = {
            case.name: {
                "size": size,
                "name": case.name,
                "kind": case.kind,
                "style": case.style,
                "command": commands[case.name],
                "samples": [],
            }
            for case in cases
        }
        evidence["cases"].extend(records.values())
        generator = random.Random(20261018)
        for iteration in range(args.repetitions + 1):
            order = cases.copy()
            generator.shuffle(order)
            for case in order:
                record = records[case.name]
                if record.get("status") == "failed":
                    continue
                started = time.perf_counter()
                result = _run(commands[case.name])
                wall = time.perf_counter() - started
                (destination / f"{size}-{case.name}-{iteration}.log").write_text(
                    result.stderr, encoding="utf-8"
                )
                if result.returncode:
                    record.update(status="failed", error=result.stderr[-2000:])
                    print(f"  {case.name}: FAILED (see log)", flush=True)
                    save()
                    continue
                if iteration:
                    cpu = re.search(r"utime=([\d.]+)s stime=([\d.]+)s", result.stderr)
                    rss = re.search(r"maxrss=(\d+)(?:KiB|kB)", result.stderr)
                    record["samples"].append(
                        {
                            "wall_seconds": wall,
                            "cpu_seconds": float(cpu[1]) + float(cpu[2])
                            if cpu
                            else None,
                            "max_rss_kib": int(rss[1]) if rss else None,
                        }
                    )
                print(
                    f"  {size} {case.name} "
                    f"{'warmup' if iteration == 0 else iteration}: {wall:.3f}s",
                    flush=True,
                )
                save()
        for case in cases:
            record = records[case.name]
            if record.get("status") == "failed":
                continue
            record["status"] = "ok"
            record["wall_seconds"] = _summary(
                [sample["wall_seconds"] for sample in record["samples"]]
            )
            record["speed_realtime"] = args.duration / record["wall_seconds"]["median"]
            record["fps"] = args.duration * args.fps / record["wall_seconds"]["median"]
            if case.kind == "encode":
                output = outputs[case.name]
                details = _probe(output, probe_executable)
                video = next(
                    stream
                    for stream in details["streams"]
                    if stream["codec_type"] == "video"
                )
                audio_copied = _audio_hash(output, executable) == source_hash
                record["output"] = {
                    "bytes": output.stat().st_size,
                    "codec": video["codec_name"],
                    "width": video["width"],
                    "height": video["height"],
                    "frames": int(video["nb_frames"]),
                    "pixel_format": video["pix_fmt"],
                    "duration": float(details["format"]["duration"]),
                    "audio_bitstream_identical": audio_copied,
                }
                source_video = next(
                    stream
                    for stream in evidence["sources"][size]["streams"]
                    if stream["codec_type"] == "video"
                )
                duration_matches = (
                    abs(float(details["format"]["duration"]) - args.duration)
                    <= 1 / args.fps + 0.1
                )
                if (
                    (video["width"], video["height"], int(video["nb_frames"]))
                    != (width, height, int(source_video["nb_frames"]))
                    or not audio_copied
                    or not duration_matches
                ):
                    raise RuntimeError(f"Output validation failed: {case.name}")
                if args.quality and case.style == "yellow-pop":
                    record["quality"] = _quality(
                        source, output, ass_files[case.style], case.style, executable
                    )
        save()
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--sizes", nargs="+", default=["1080x1920", "1920x1080"])
    parser.add_argument("--duration", type=float, default=12)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--preparation-only", action="store_true")
    parser.add_argument(
        "--experimental-line-break-cache",
        action="store_true",
        help="Benchmark a bounded, per-artifact in-memory Unicode boundary cache",
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        choices=[case.name for case in _cases(True)],
        help="Run only selected cases, retaining their normal warmup and validation",
    )
    parser.add_argument(
        "--preparation-seconds", nargs="*", type=float, default=[60, 300]
    )
    parser.add_argument(
        "--nvenc",
        action="store_true",
        help="Try p4/p7 and p4 CQ 28/30; record failures without CPU fallback",
    )
    parser.add_argument(
        "--quality",
        action="store_true",
        help="Measure full-frame and bottom-band SSIM against the uncompressed burn",
    )
    args = parser.parse_args()
    if (
        args.cases
        and any(name.startswith("nvenc-") for name in args.cases)
        and not args.nvenc
    ):
        parser.error("NVENC cases require --nvenc")
    if (
        not 0 < args.duration <= 60
        or not 1 <= args.fps <= 60
        or not 1 <= args.repetitions <= 10
    ):
        parser.error("Use duration (0, 60], fps [1, 60], repetitions [1, 10]")
    for size in args.sizes:
        if not re.fullmatch(r"\d{2,4}x\d{2,4}", size) or any(
            not 64 <= int(part) <= 4096 or int(part) % 2 for part in size.split("x")
        ):
            parser.error("Sizes must have even dimensions from 64 through 4096")
    if any(
        not math.isfinite(value) or not 0 < value <= 3600
        for value in args.preparation_seconds
    ):
        parser.error("Preparation timelines must be finite seconds in (0, 3600]")
    print(f"Results: {benchmark(args)}", flush=True)


if __name__ == "__main__":
    main()
