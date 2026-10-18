# Real-footage encoding validation — 2026-10-18

This follow-up evaluates the four recommended encoding profiles on the local
`test-horizontal-3.mp4` and `test-horizontal-5.mp4` files selected by the user.
It complements the [synthetic investigation](2026-10-18-rendering.md).
The measurements below predate the subsequent default decision: explicit NVENC
now defaults to `p4 / CQ 28`, while x264 stays at `medium / CRF 23` and omitted
encoder selection stays with FFmpeg. See the [current defaults](../../README.md#video-encoding).
The measured profiles all set their quality explicitly, so their settings and
results are unchanged.

On these three 30 second samples, `veryfast / CRF 23` reduced rendering time by
19–46% relative to `medium / CRF 23`, with lower SSIM in every sample. NVENC
`p4 / CQ 28` reduced time by 43–75% and process CPU work by 77–96%; its output
size ranged from 7% smaller to 77% larger than medium. These results support
explicit CPU/NVIDIA profiles, while keeping a quality tradeoff visible before
selecting a new general default.

## Inputs and reproduction

| Clip label | Source | Selected interval | Source video | Subtitle events |
| --- | --- | --- | --- | --- |
| `animation` | `test-horizontal-3.mp4` | 15–45 s | H.264, 1920 × 1080, 24000/1001 fps | 140 |
| `screen` | `test-horizontal-5.mp4` | 60–90 s | AV1, 1920 × 1080, 60000/1001 fps | 800 |
| `talking-head` | `test-horizontal-5.mp4` | 610–640 s | AV1, 1920 × 1080, 60000/1001 fps | 862 |

The first clip contains animated action; the second contains browser text,
screen content, and an inset person; the third contains a person speaking
against a detailed background. The latter two share a source file and decoder,
so they are separate content samples, not independent codec/hardware samples.
Both originals have square pixels, no rotation, and one Opus audio stream.

Use the repository virtual environment and the same bundled Montserrat fonts:

```bash
python -m scripts.benchmark_real_rendering \
  --output-dir data/benchmarks --duration 30 --repetitions 3 \
  --clip multisubs/data/test-horizontal-3.mp4 15 animation \
  --clip multisubs/data/test-horizontal-5.mp4 60 screen \
  --clip multisubs/data/test-horizontal-5.mp4 610 talking-head
```

The matching existing ASS defaults to
`SOURCE_WITHOUT_SUFFIX/subtitles/SOURCE_STEM-pt.ass`. Both selected ASS files
use `yellow-pop` with word pop/highlight effects. The harness retains the
existing events that intersect the clip, shifts their absolute start/end
times, and clips events at the selected boundaries. Every profile uses that
same retimed ASS. It does not regenerate recognition, alignment, layout, or
subtitle animations. A cue crossing the initial cut can have a different
animation phase from the full original, equally for every comparison.

The harness uses `VideoEncodingConfig` and the production
`subtitler._build_output_stream()` graph. Seeking and a 30 second input limit
are added to select the sample; neither is a new public CLI feature. Source
resolution/frame rate, software decoding, libass filtering, and copied audio
remain in use. NVENC accelerates encoding only.

## Method and environment

The host is the same Ryzen 7 5700X / RTX 3070 used for the synthetic follow-up,
with NVIDIA driver 617.42 and primary FFmpeg
`n9.0.2-17-g2a571b6068-20260930`. Python is 3.10.12. The portable evidence
records source/ASS hashes, code hashes for the uncommitted implementation,
compiled commands, and all measured samples.

Each of the 12 clip/profile combinations has one excluded full warmup and
three measured executions, for 36 measured encodes and 12 warmups. Order is
shuffled deterministically within each round. Only one benchmark FFmpeg job
runs at a time. Background desktop/host activity is uncontrolled; medians and
ranges describe this session rather than a hardware-wide performance promise.

Timed rendering includes process startup, seeking/decoding, subtitle filtering,
encoding, copied audio, and MP4 muxing. ASR, ASS preparation, explicit encoder
preflight, quality checks, and screenshots are excluded. The separately observed
one-frame preflight took about 0.016 s for x264 and 0.51–0.56 s for NVENC after
earlier smoke checks. These are not cold-start or complete CLI latency results.

CPU seconds sum work across process threads and can exceed wall time. Peak RSS
is a per-execution FFmpeg counter; the tables show the median of those peaks.
File size includes video, copied audio, and the MP4 container.

SSIM compares each complete decoded output against the same decoded source
with the identical ASS burn before lossy output encoding. Both sides start at
zero presentation time. Full-frame and bottom-35%-of-frame SSIM are collected,
along with per-frame minima and fifth percentiles in the JSON. The harness
checks that every reference/output/SSIM pass has the same frame count. These
scores measure additional encoding loss, not source quality or ASR accuracy.

Audio validation compares SHA-256 hashes of every compressed output packet
against an identical contiguous sequence in the original audio. This handles
negative-timestamp Opus preroll retained during seeking and stream copy;
hashing an independently trimmed audio-only command would select a different
packet range. The original audio payload is preserved without re-encoding.

## Results

Times are seconds; sizes and RSS are MiB. Each time entry is the median and
observed range. SSIM is measured on the retained final execution for each
profile, not averaged across repeated encodes.

### Animated action — H.264, about 24 fps

| Profile | Wall time (range) | CPU seconds | Peak RSS | Output | SSIM full | SSIM bottom 35% |
| --- | --- | --- | --- | --- | --- | --- |
| x264 medium / CRF 23 | 9.749 (9.617–10.108) | 107.465 | 1,165 | 13.08 | 0.995358 | 0.995650 |
| x264 veryfast / CRF 23 | 5.299 (4.997–5.370) | 42.122 | 905 | 13.24 | 0.994313 | 0.994574 |
| NVENC p4 / CQ 28 | 2.452 (2.437–2.543) | 4.833 | 367 | 12.15 | 0.994658 | 0.994823 |
| NVENC p4 / CQ 23 | 2.449 (2.437–2.536) | 4.942 | 369 | 19.89 | 0.996567 | 0.996734 |

Veryfast saves 46% of elapsed time, with almost the same file size and lower
similarity. NVENC CQ 28 saves 75% of elapsed time and 96% of CPU work, while
producing a 7% smaller file than medium. CQ 28 has higher SSIM than veryfast
but lower SSIM than medium. CQ 23 increases similarity and file size.

### Screen content — AV1, about 60 fps

| Profile | Wall time (range) | CPU seconds | Peak RSS | Output | SSIM full | SSIM bottom 35% |
| --- | --- | --- | --- | --- | --- | --- |
| x264 medium / CRF 23 | 9.799 (9.542–9.828) | 95.625 | 1,167 | 5.39 | 0.995623 | 0.995883 |
| x264 veryfast / CRF 23 | 7.892 (7.719–8.279) | 57.927 | 909 | 4.68 | 0.993249 | 0.993079 |
| NVENC p4 / CQ 28 | 5.595 (5.576–5.728) | 22.232 | 365 | 9.51 | 0.996728 | 0.997132 |
| NVENC p4 / CQ 23 | 5.577 (5.515–5.641) | 21.629 | 366 | 15.71 | 0.998193 | 0.998592 |

Veryfast saves 19% of elapsed time and 13% of bytes, with lower SSIM. NVENC
CQ 28 saves 43% of elapsed time, with higher SSIM than medium but 77% more
bytes. CQ 23 is about 2.9 times medium's output size. The similar CQ 23/28
times do not establish a meaningful speed difference between those settings.

### Person speaking — AV1, about 60 fps

| Profile | Wall time (range) | CPU seconds | Peak RSS | Output | SSIM full | SSIM bottom 35% |
| --- | --- | --- | --- | --- | --- | --- |
| x264 medium / CRF 23 | 14.716 (14.694–15.075) | 166.476 | 1,158 | 11.18 | 0.990507 | 0.991131 |
| x264 veryfast / CRF 23 | 9.301 (9.257–10.100) | 76.602 | 900 | 8.35 | 0.987011 | 0.987758 |
| NVENC p4 / CQ 28 | 5.356 (5.348–5.468) | 26.098 | 368 | 15.18 | 0.992054 | 0.992547 |
| NVENC p4 / CQ 23 | 5.396 (5.317–5.469) | 26.115 | 365 | 27.88 | 0.994574 | 0.994908 |

Veryfast saves 37% of elapsed time and 25% of bytes; its SSIM loss is the
largest of these samples. NVENC CQ 28 saves 64% of elapsed time and 84% of CPU
work, with higher SSIM than medium and 36% more bytes. CQ 23 spends another
84% of bytes relative to CQ 28 for less measured encoding loss.

## Remaining rendering costs

Separate video-only null-output runs have their own warmup and three measured
executions per clip/mode, with shuffled order. They omit audio muxing and video
encoding and are diagnostics rather than an additive decomposition of the
render times above.

| Clip | Decode to null | Decode + identical subtitles to null | NVENC p4 / CQ 28 render |
| --- | --- | --- | --- |
| Animated action | 0.591 s | 0.719 s | 2.452 s |
| Screen content | 2.406 s | 2.831 s | 5.595 s |
| Person speaking | 2.624 s | 3.131 s | 5.356 s |

AV1 decoding at about 60 fps is already a multi-second task in these samples;
subtitle filtering adds work too. Codec, frame rate, content, and subtitle
density differ between clips, so these comparisons cannot attribute the
difference to AV1 alone. The next optimization experiment should profile
decoding and frame-transfer costs before changing the render graph. These null
runs do not establish that GPU decoding would improve complete render latency.

## Recommendation and default decision

- Use `libx264 / veryfast / CRF 23` as the explicit CPU speed profile. Its
  19–46% time reduction comes with lower similarity; the smaller screen/face
  outputs are not evidence of equal quality at lower cost.
- Use `h264_nvenc / p4 / CQ 28` as the starting profile on the tested NVIDIA
  setup. It gives the strongest speed/CPU benefit of these profiles, with a
  file-size tradeoff that depends on the content. Keep CQ 23 available when
  higher fidelity justifies the additional bytes.
- Keep NVENC opt-in. A general default cannot depend on this GPU/driver, and
  equal CRF/CQ numbers do not mean equal quality or equivalent file sizes.
- Keep `medium / CRF 23` as the explicit CPU default. Caption edges and facial
  texture show additional softening in inspected veryfast crops; `veryfast`
  remains an optional speed profile. Use `p4 / CQ 28` as the explicit NVENC
  default, with CQ 23 available as a fidelity override. This subsequent product
  decision does not alter the measurements or their captured code hashes.

## Local visual comparison

Generated videos, original-size PNGs at 5/15/25 seconds, full logs, retimed ASS,
and `summary.json` remain under the ignored run directory:

```text
data/benchmarks/real-render-anj1s7tx/
```

`comparison.html` in that directory provides a profile/clip selector, a wipe
comparison against the uncompressed burn, a 1:1 inspection mode, and a video
player. Caption/detail comparison sheets also remain local. These files contain
the user's media and subtitles and are not part of the portable evidence.

Static crops can establish that text is visible and aligned at the inspected
instants, but do not prove perceptual equivalence in motion. The complete
30 second outputs are provided for that assessment.

Inspection covered the animation caption at clip second 5 and screen/face
details at second 15. Glyphs and positions remained readable and aligned in
those crops; fine edge/texture differences are visible between encoders and
presets. This is a limited static inspection, not a claim that every frame or
motion artifact has been visually reviewed.

## Evidence and verification

- [All 12 real-footage encoding cases](results/2026-10-18/real-footage.json).
- [Decode/filter diagnostics](results/2026-10-18/real-footage-diagnostics.json).

All 12 outputs match their decoded reference: 720 frames for animated action
and 1,799 frames for each 60 fps sample. Dimensions are 1920 × 1080, output
frame rates match the originals, and durations are within two frames plus
0.1 seconds of the selected interval. Every compressed audio output is an
identical contiguous source packet sequence, with its original relative
presentation timing. Both SSIM passes cover every expected frame.

Original media and ASS hashes were checked again after the runs. All 45 PNG
snapshots and 12 output videos exist, and the local comparison references those
files. Generated user media, subtitle text, and verbose logs stay ignored;
portable records include only measurements, hashes, commands with sanitized
paths, and relevant codec/geometry properties.
