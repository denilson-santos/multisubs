"""Compare CPU/NVIDIA encoding on local footage and existing ASS, without ASR.

Each --clip takes SOURCE, START_SECONDS, and LABEL. The matching ASS defaults
to SOURCE_WITHOUT_SUFFIX/subtitles/SOURCE_STEM-pt.ass. Originals are read only;
outputs, retimed subtitles, diagnostics, and screenshots stay in a fresh run
directory. Only summary.json is suitable for a portable evidence export.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import re
import shutil
import tempfile
import time
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

import ffmpeg

from multisubs.font_catalog import bundled_filesystem_directory
from multisubs.models import VideoEncodingConfig
from multisubs.subtitler import (
    _build_output_stream,
    probe_video_geometry,
    validate_video_encoding_support,
)
from scripts.benchmark_rendering import _checked, _probe, _run, _summary

PROFILES = {
    "x264-medium": VideoEncodingConfig("libx264", "medium", 23),
    "x264-veryfast": VideoEncodingConfig("libx264", "veryfast", 23),
    "nvenc-p4-cq28": VideoEncodingConfig("h264_nvenc", "p4", 28),
    "nvenc-p4-cq23": VideoEncodingConfig("h264_nvenc", "p4", 23),
}


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _audio_packets(path: Path) -> list[dict[str, Any]]:
    result = _checked(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_packets",
            "-show_data_hash",
            "sha256",
            "-show_entries",
            "packet=pts_time,data_hash",
            "-of",
            "json",
            str(path),
        ]
    )
    return json.loads(result.stdout)["packets"]


def _audio_copy_check(
    source: list[dict[str, Any]], output: Path, start: float, duration: float
) -> dict[str, Any]:
    packets = _audio_packets(output)
    hashes = [packet["data_hash"] for packet in packets]
    if not hashes:
        raise RuntimeError("The encoded output has no audio packets")
    for index, packet in enumerate(source):
        timestamp = float(packet["pts_time"])
        if not start - 30 <= timestamp <= start + 0.1:
            continue
        if packet["data_hash"] != hashes[0]:
            continue
        selected = source[index : index + len(hashes)]
        if [packet["data_hash"] for packet in selected] != hashes:
            continue
        if abs(float(selected[-1]["pts_time"]) - (start + duration)) > 0.1:
            continue
        return {
            "compressed_payload_identical": True,
            "contiguous_source_sequence": True,
            "packet_count": len(packets),
            "source_first_packet_seconds": timestamp,
            "source_last_packet_seconds": float(selected[-1]["pts_time"]),
            "output_first_packet_seconds": float(packets[0]["pts_time"]),
            "output_last_packet_seconds": float(packets[-1]["pts_time"]),
        }
    raise RuntimeError("Output audio packets differ from the source clip sequence")


def _ass_time(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _ass_timestamp(value: float) -> str:
    centiseconds = round(value * 100)
    hours, rest = divmod(centiseconds, 360000)
    minutes, rest = divmod(rest, 6000)
    seconds, fraction = divmod(rest, 100)
    return f"{hours}:{minutes:02}:{seconds:02}.{fraction:02}"


def _retime_ass(source: Path, output: Path, start: float, duration: float) -> int:
    lines = []
    count = 0
    for line in source.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("Dialogue:"):
            fields = line.split(",", 9)
            begin, end = _ass_time(fields[1]) - start, _ass_time(fields[2]) - start
            if end <= 0 or begin >= duration:
                continue
            fields[1] = _ass_timestamp(max(0, begin))
            fields[2] = _ass_timestamp(min(duration, end))
            line = ",".join(fields)
            count += 1
        lines.append(line)
    if not count:
        raise ValueError(f"No subtitle events overlap the selected clip: {source}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count


def _reference(source: Path, start: float, duration: float, options: dict[str, str]):
    return (
        ffmpeg.input(str(source), ss=start, t=duration)
        .video.filter("subtitles", **options)
        .filter("setpts", "PTS-STARTPTS")
    )


def _quality(
    source: Path,
    output: Path,
    start: float,
    duration: float,
    options: dict[str, str],
    directory: Path,
    name: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for label, crop in (("full", False), ("bottom35pct", True)):
        reference = _reference(source, start, duration, options)
        encoded = ffmpeg.input(str(output)).video.filter("setpts", "PTS-STARTPTS")
        if crop:
            reference = reference.filter("crop", "iw", "trunc(ih*0.35/2)*2", 0, "ih-oh")
            encoded = encoded.filter("crop", "iw", "trunc(ih*0.35/2)*2", 0, "ih-oh")
        stats = directory / f"{name}-ssim-{label}.txt"
        metric = ffmpeg.filter(
            [encoded, reference], "ssim", shortest=1, stats_file=str(stats)
        )
        checked = _checked(ffmpeg.compile(ffmpeg.output(metric, "-", format="null")))
        match = re.search(r"All:([0-9.]+)", checked.stderr)
        if match is None:
            raise RuntimeError("FFmpeg did not report SSIM")
        result[f"ssim_{label}"] = float(match[1])
        values = [
            float(value) for value in re.findall(r"All:([0-9.]+)", stats.read_text())
        ]
        result[f"ssim_{label}_frames"] = len(values)
        result[f"ssim_{label}_min"] = min(values)
        result[f"ssim_{label}_p05"] = sorted(values)[int(0.05 * (len(values) - 1))]
    return result


def benchmark(args: argparse.Namespace) -> Path:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="real-render-", dir=args.output_dir))
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": _checked(["git", "rev-parse", "HEAD"]).stdout.strip(),
        "working_tree_dirty": bool(_checked(["git", "status", "--porcelain"]).stdout),
        "code_sha256": {
            name: _digest(Path(name))
            for name in (
                "multisubs/subtitler.py",
                "multisubs/config.py",
                "scripts/benchmark_real_rendering.py",
            )
        },
        "ffmpeg": _checked(["ffmpeg", "-version"]).stdout.splitlines()[0],
        "ffprobe": _checked(["ffprobe", "-version"]).stdout.splitlines()[0],
        "python": platform.python_version(),
        "parameters": {
            "duration": args.duration,
            "repetitions": args.repetitions,
            "warmups": 1,
            "seed": 20261018,
        },
        "encoder_preflight_seconds": {},
        "clips": [],
        "notes": [
            "No ASR; existing ASS retimed to each clip and shared by all profiles.",
            "Timed commands use the production graph and VideoEncodingConfig.",
            "Timings include seeking/decoding, libass, encoding, audio copy, muxing.",
            "Timings exclude preflight, artifact preparation, quality checks, images.",
            "One FFmpeg process at a time; one warmup per profile; shuffled rounds.",
            "SSIM references the same decoded source with the same ASS burn.",
            "SSIM and screenshots do not establish perceptual equivalence in motion.",
            "Audio packet payloads must be an identical contiguous source sequence; "
            "negative-timestamp Opus preroll is retained by stream copy.",
        ],
    }
    gpu = shutil.which("nvidia-smi")
    if gpu:
        result = _run(
            [
                gpu,
                "--query-gpu=name,driver_version,memory.total,utilization.gpu",
                "--format=csv,noheader",
            ]
        )
        evidence["gpu_at_start"] = (result.stdout or result.stderr).strip()

    def save() -> None:
        serialized = json.dumps(evidence, indent=2, ensure_ascii=False)
        for original, replacement in (
            (str(destination.resolve()), "<run>"),
            (str(destination), "<run>"),
            (str(Path.cwd()), "<repo>"),
            (str(Path.home()), "<home>"),
        ):
            serialized = serialized.replace(original, replacement)
        (destination / "summary.json").write_text(serialized + "\n", encoding="utf-8")

    print(f"RUN_DIR {destination}", flush=True)
    save()
    for name, config in PROFILES.items():
        started = time.perf_counter()
        validate_video_encoding_support(config)
        evidence["encoder_preflight_seconds"][name] = time.perf_counter() - started
    save()
    audio_packets_cache = {}
    for source_name, start_value, label in args.clip:
        source = Path(source_name).resolve()
        start = float(start_value)
        ass = source.with_suffix("") / "subtitles" / f"{source.stem}-pt.ass"
        directory = destination / label
        directory.mkdir()
        geometry = probe_video_geometry(source)
        if geometry.rotation_degrees or geometry.sample_aspect_ratio != 1:
            raise ValueError("This comparison requires unrotated square-pixel footage")
        if (
            geometry.duration_seconds is None
            or start + args.duration > geometry.duration_seconds
        ):
            raise ValueError("The selected clip extends beyond the source duration")
        families = {
            line.split(",")[1]
            for line in ass.read_text(encoding="utf-8-sig").splitlines()
            if line.startswith("Style:")
        }
        if len(families) != 1:
            raise ValueError("This comparison expects one shared bundled font family")
        fonts = bundled_filesystem_directory(families.pop())
        clipped_ass = directory / "clip.ass"
        dialogues = _retime_ass(ass, clipped_ass, start, args.duration)
        options = {
            "filename": str(clipped_ass),
            "original_size": geometry.original_size,
        }
        if fonts:
            options["fontsdir"] = str(fonts)
        details = _probe(source, "ffprobe")
        video = next(s for s in details["streams"] if s["codec_type"] == "video")
        audio_streams = sum(s["codec_type"] == "audio" for s in details["streams"])
        if audio_streams != 1:
            raise ValueError("This audio comparison expects one source audio stream")
        clip: dict[str, Any] = {
            "label": label,
            "source": source.name,
            "source_sha256": _digest(source),
            "ass_sha256": _digest(ass),
            "start_seconds": start,
            "duration_seconds": args.duration,
            "ass_dialogues": dialogues,
            "source_video": {
                key: video.get(key)
                for key in (
                    "codec_name",
                    "width",
                    "height",
                    "pix_fmt",
                    "avg_frame_rate",
                )
            },
            "audio_streams": audio_streams,
            "cases": [],
        }
        evidence["clips"].append(clip)
        if source not in audio_packets_cache:
            audio_packets_cache[source] = _audio_packets(source)
        audio_reference = audio_packets_cache[source]
        frames_command = ffmpeg.compile(
            ffmpeg.output(
                _reference(source, start, args.duration, options),
                "-",
                format="framemd5",
            )
        )
        frame_rows = _checked(frames_command).stdout.splitlines()
        expected_frames = sum(
            bool(row) and not row.startswith("#") for row in frame_rows
        )
        clip["reference_frames"] = expected_frames
        commands = {}
        records = {}
        for name, config in PROFILES.items():
            output = directory / f"{name}.mp4"
            graph = _build_output_stream(
                ffmpeg,
                source,
                clipped_ass,
                output,
                geometry,
                fonts,
                video_encoding=config,
            )
            command = ffmpeg.compile(graph)
            index = command.index("-i")
            command[index:index] = ["-ss", str(start), "-t", str(args.duration)]
            command[1:1] = ["-nostdin", "-hide_banner", "-benchmark", "-y"]
            commands[name] = command
            records[name] = {
                "name": name,
                "encoder": config.encoder,
                "preset": config.preset,
                "quality_value": config.quality,
                "command": command,
                "samples": [],
            }
            clip["cases"].append(records[name])
        generator = random.Random(20261018)
        for iteration in range(args.repetitions + 1):
            order = list(PROFILES)
            generator.shuffle(order)
            for name in order:
                started = time.perf_counter()
                checked = _checked(commands[name])
                elapsed = time.perf_counter() - started
                (directory / f"{name}-{iteration}.log").write_text(checked.stderr)
                cpu = re.search(r"utime=([\d.]+)s stime=([\d.]+)s", checked.stderr)
                rss = re.search(r"maxrss=(\d+)(?:KiB|kB)", checked.stderr)
                if not cpu or not rss:
                    raise RuntimeError("Missing CPU/RSS counters")
                if iteration:
                    records[name]["samples"].append(
                        {
                            "wall_seconds": elapsed,
                            "cpu_seconds": float(cpu[1]) + float(cpu[2]),
                            "max_rss_kib": int(rss[1]),
                        }
                    )
                print(
                    f"{label} {name} {'warmup' if not iteration else iteration}: "
                    f"{elapsed:.3f}s",
                    flush=True,
                )
                save()
        for name, record in records.items():
            output = directory / f"{name}.mp4"
            encoded = _probe(output, "ffprobe")
            stream = next(s for s in encoded["streams"] if s["codec_type"] == "video")
            frame_count = int(stream["nb_frames"])
            audio_check = _audio_copy_check(
                audio_reference, output, start, args.duration
            )
            clip_fps = float(Fraction(video["avg_frame_rate"]))
            output_duration = float(encoded["format"]["duration"])
            if (
                frame_count != expected_frames
                or (stream["width"], stream["height"])
                != (geometry.render_width, geometry.render_height)
                or abs(output_duration - args.duration) > 2 / clip_fps + 0.1
            ):
                raise RuntimeError(f"Media validation failed: {label} {name}")
            for key in ("wall_seconds", "cpu_seconds", "max_rss_kib"):
                record[key] = _summary([sample[key] for sample in record["samples"]])
            record["output"] = {
                "bytes": output.stat().st_size,
                "frames": frame_count,
                "width": stream["width"],
                "height": stream["height"],
                "duration": output_duration,
                "pixel_format": stream["pix_fmt"],
                "audio_bitstream_identical": audio_check[
                    "compressed_payload_identical"
                ],
                "audio_validation": audio_check,
                "avg_frame_rate": stream["avg_frame_rate"],
            }
            print(f"{label} {name}: measuring SSIM", flush=True)
            record["quality"] = _quality(
                source, output, start, args.duration, options, directory, name
            )
            if any(
                record["quality"][f"ssim_{region}_frames"] != expected_frames
                for region in ("full", "bottom35pct")
            ):
                raise RuntimeError(f"SSIM frame alignment failed: {label} {name}")
            record["status"] = "ok"
            save()
        for second in (5, 15, 25):
            if second >= args.duration:
                continue
            for name, path in [("reference", None)] + [
                (name, directory / f"{name}.mp4") for name in PROFILES
            ]:
                stream = (
                    _reference(source, start, args.duration, options)
                    if path is None
                    else ffmpeg.input(str(path)).video
                )
                stream = stream.filter("select", f"gte(t,{second})")
                target = directory / f"{name}-{second}s.png"
                _checked(ffmpeg.compile(ffmpeg.output(stream, str(target), vframes=1)))
        print(f"{label}: media, audio, SSIM alignment and screenshots OK", flush=True)
    save()
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clip",
        nargs=3,
        action="append",
        required=True,
        metavar=("SOURCE", "START_SECONDS", "LABEL"),
    )
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not math.isfinite(args.duration) or not 25 < args.duration <= 60:
        parser.error("Duration must be greater than 25 and at most 60 seconds")
    if not 1 <= args.repetitions <= 10:
        parser.error("Repetitions must be between 1 and 10")
    labels = set()
    for source, start, label in args.clip:
        if (
            not Path(source).is_file()
            or not math.isfinite(float(start))
            or float(start) < 0
        ):
            parser.error(
                "Each clip requires an existing file and finite nonnegative start"
            )
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", label) or label in labels:
            parser.error("Labels must be unique lowercase kebab-case names")
        labels.add(label)
    print(benchmark(args), flush=True)


if __name__ == "__main__":
    main()
