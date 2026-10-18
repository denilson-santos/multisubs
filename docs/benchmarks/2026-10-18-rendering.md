# Rendering performance investigation — 2026-10-18

This investigation measures the rendering pipeline and candidate FFmpeg
settings. The implementation follow-up below adds explicit encoding controls
and reuses subtitle layout work while preserving existing defaults, timing,
and output contracts. Results are specific to the synthetic fixtures and host
below; they do not establish a production speed or quality guarantee.

**Subsequent default decision:** after the real-footage validation, explicit
NVENC defaults to `p4 / CQ 28`; x264 retains `medium / CRF 23` and omitted
encoder selection stays with FFmpeg. The measurements and earlier implementation
notes below are historical; see the [current defaults](../../README.md#video-encoding).

**Driver update:** NVIDIA 617.42 resolves the primary FFmpeg's observed NVENC
initialization failure. The follow-up section records fresh CPU/GPU comparisons
on that build, preserving the initial 560.94 measurements as historical data.

## Reproduction

Use the existing core/development virtual environment; no ASR extra or model
download is needed:

```bash
python -m scripts.benchmark_rendering \
  --output-dir data/benchmarks \
  --sizes 1080x1920 1920x1080 \
  --duration 12 --repetitions 3 \
  --preparation-seconds 60 300 --quality
```

The optional NVIDIA comparison uses a separately selected build and its own
CPU baseline:

```bash
python -m scripts.benchmark_rendering \
  --output-dir data/benchmarks \
  --ffmpeg /usr/bin/ffmpeg --ffprobe /usr/bin/ffprobe \
  --sizes 1080x1920 --duration 12 --repetitions 3 \
  --preparation-seconds --nvenc --quality
```

The 4K subset and Unicode-cache experiment can be reproduced separately:

```bash
python -m scripts.benchmark_rendering \
  --output-dir data/benchmarks \
  --ffmpeg /usr/bin/ffmpeg --ffprobe /usr/bin/ffprobe \
  --sizes 3840x2160 --duration 6 --repetitions 3 \
  --preparation-seconds --nvenc --quality \
  --cases decode filter-yellow-pop current-yellow-pop x264-veryfast nvenc-p4 nvenc-p7

python -m scripts.benchmark_rendering \
  --output-dir data/benchmarks --sizes 1080x1920 \
  --duration 12 --repetitions 3 --preparation-seconds 60 300 \
  --preparation-only --experimental-line-break-cache
```

`--cases` selects a smaller matrix. The default NVIDIA matrix also includes
p4 at CQ 28 and 30; historically those two cases were collected in a separate
invocation with `--cases nvenc-p4-cq28 nvenc-p4-cq30` and the same 1080p settings.
The cache flag changes only this benchmark process, restores the original
function after each artifact generation, and clears its bounded cache after
each measurement. It is a prototype, not a shipped runtime optimization.

Each invocation creates a fresh directory containing source/output videos,
synthetic JSON/SRT/ASS, FFmpeg logs, and `summary.json`. The directory is under
ignored `data/`; generated media and subtitle artifacts must remain untracked.
The portable summary replaces checkout, home, and run paths with placeholders.

## Host and baseline

- Source: multisubs 5.1.0, commit
  `55a86e352a77157ee2e43957319bba4aa1d6f966`.
- Linux under WSL2; AMD Ryzen 7 5700X, 8 cores / 16 logical CPUs; approximately
  15 GiB of guest RAM.
- NVIDIA GeForce RTX 3070, 8 GiB VRAM, driver 560.94 for the initial runs;
  the later primary-build follow-up uses the user-installed 617.42 driver.
- Python 3.10.12, Pillow 12.3.0, ffmpeg-python 0.2.0.
- Primary FFmpeg: `n9.0.2-17-g2a571b6068-20260930`, libass 0.17.5.
- Alternate FFmpeg: Ubuntu `4.4.2-0ubuntu0.22.04.1`.

`subtitler._build_output_stream()` currently selects the subtitle filter and
copies audio but leaves video codec, preset, rate control, and threads to
FFmpeg. For these MP4 runs, the primary build chose libx264 with medium settings,
CRF 23, and 24 encoder threads. That observation describes this build/container;
it is not an explicit multisubs guarantee for every input extension or build.

With driver 560.94, the primary FFmpeg's NVENC smoke test failed with
`Required: 13.1 Found: 12.2`
and reported a minimum driver of 610.00. The alternate build successfully
encoded synthetic frames on the same GPU. The blocker concerns the FFmpeg
build/driver interface, rather than evidence of a defective GPU. NVIDIA
documents the need to match the build's Video Codec SDK with a compatible
[driver](https://docs.nvidia.com/video-technologies/video-codec-sdk/13.1/ffmpeg-with-nvidia-gpu/index.html).
The user subsequently installed driver 617.42; a fresh NVENC smoke test with
the unchanged primary FFmpeg passed. The benchmark changed no system packages
or driver installation. The follow-up below records the new compatibility and
CPU/GPU comparison separately from the initial runs.

## Method

The fixture is an animated `testsrc2` source, H.264/yuv420p at CRF 18, with a
48 kHz AAC sine track. Generation is excluded from timings. Subtitle text is
synthetic Portuguese, with explicitly artificial word intervals and a new cue
every three seconds. No speech recognition, forced alignment, private media,
network downloads, or transcription-quality assessment is involved.

For each case, one complete warmup is excluded, followed by three measured
executions. Case order is shuffled deterministically in each round. FFmpeg
jobs run sequentially; quality checks run after timed encoding. Wall time
includes process startup and final MP4 muxing. Results report medians and retain
every sample and range. FFmpeg's `-benchmark` also records process CPU time and
peak RSS. Host activity and thermal state are uncontrolled.

The measurements separate:

1. Source mapping and semantic cue construction with
   `_build_subtitle_segments()`.
2. Font coverage, layout, animation preparation, and JSON/SRT/ASS generation
   with `write_transcription_artifacts()`.
3. Decode to the null sink, then decode plus subtitle filtering to the same
   sink, without video encoding or audio output.
4. The existing production render graph and candidate encoding settings,
   including copied audio and a real MP4 output.

`yellow-static` is precisely `yellow-pop` with word animations disabled;
typography and geometry remain equal. Comparing these isolates the word effect
more closely than comparing unrelated templates. `default` and
`neon-magenta-pulse` broaden the style sample but also change typography.

Candidate CPU presets use libx264 at CRF 23. NVIDIA cases use H.264 NVENC,
presets p4/p7, VBR, CQ 23/28/30, and no target bitrate. CRF 23 and CQ 23 are different
controls and must not be interpreted as equal quality. The preset and CRF
controls are documented by
[FFmpeg](https://ffmpeg.org/ffmpeg-codecs.html#libx264_002c-libx264rgb).

Successful encodes are checked with ffprobe for dimensions, frame count, and
duration. Compressed audio payload hashes must match the source. SSIM compares
the decoded output against the same source decoded and burned with the same
ASS/filter/font settings, before lossy output encoding. A second SSIM samples
the bottom 35% of the frame to give subtitles more weight. Neither score proves
readability, temporal fidelity, or perceptual equivalence on real footage.

Preparation timings use an already imported process, a probed geometry, and a
selected configuration. They include no CLI startup, recognition, source
transcript validation, final publication, or FFmpeg encoding. The 60/300 second
preparation samples extend the synthetic subtitle timeline only; they do not
render longer media. Subtracting separate null/encode wall times gives a rough
cost comparison, not an additive profiler breakdown of concurrent FFmpeg work.

## Primary build: 1080p rendering

All rows use the same `yellow-pop` ASS and source, except the row explicitly
without subtitles. Times are seconds for a 12 second / 360 frame video.

| Setting | Portrait median (range) | Landscape median (range) | Portrait output | Portrait peak RSS |
| --- | --- | --- | --- | --- |
| Current implicit medium/CRF 23 | 2.586 (2.448–2.652) | 2.428 (2.423–2.902) | 8.59 MiB | 1,177 MiB |
| x264 fast / CRF 23 | 2.276 (2.259–2.440) | 2.289 (2.285–2.302) | 8.61 MiB | 1,059 MiB |
| x264 veryfast / CRF 23 | 1.719 (1.710–1.806) | 1.744 (1.653–1.759) | 7.46 MiB | 915 MiB |
| x264 ultrafast / CRF 23 | 0.888 (0.882–0.924) | 0.924 (0.884–0.926) | 21.39 MiB | 526 MiB |
| Medium, encoder threads 8 + filter threads 1 | 3.675 (3.594–3.692) | 3.753 (3.682–3.797) | 8.65 MiB | 801 MiB |
| Current encoding, no subtitles | 2.256 (2.201–2.296) | 2.364 (2.322–2.653) | 8.26 MiB | 1,152 MiB |

`veryfast` reduces measured render time by 28–34% (1.39–1.50× throughput),
while the largest CPU improvement is `ultrafast`: 62–66% less time
(2.63–2.91× throughput). Its portrait file is 2.49× the baseline size.
`veryfast` happens to produce a smaller file on this fixture; neither relative
size nor relative quality is guaranteed at equal CRF across presets.

The combined thread limit trades lower memory and CPU consumption for worse
latency: portrait median rises 42%, landscape 55%. It does not justify adopting
that combination. This experiment does not isolate the effect of encoder
threads from filter threads, or test throughput under concurrent jobs.

### Quality observations

| Portrait setting | SSIM full frame | SSIM bottom 35% |
| --- | --- | --- |
| Current implicit medium | 0.995336 | 0.989292 |
| fast | 0.995205 | 0.988995 |
| veryfast | 0.993877 | 0.985950 |
| ultrafast | 0.998310 | 0.996772 |

`ultrafast` has the highest SSIM here while spending substantially more bytes.
That is a measured compression tradeoff, rather than evidence that the fastest
preset offers the best general quality. `veryfast` gives up some measured
similarity. Real clips and human inspection remain necessary before selecting
a default or promising equal quality. Small timing differences, such as `fast`
versus medium, deserve longer runs because some samples vary by roughly 20%.

## Subtitle preparation and effect cost

Preparation results below use the portrait geometry. Artifact time includes
coverage/metrics, layout, animation compilation, and all three subtitle files.

| Style / synthetic timeline | Semantic cues | Cue construction | Artifact generation | ASS dialogues |
| --- | --- | --- | --- | --- |
| default / 12 s | 4 | 0.021 s | 0.203 s | 28 |
| yellow-static / 12 s | 4 | 0.021 s | 0.148 s | 12 |
| yellow-pop / 12 s | 4 | 0.020 s | 0.165 s | 232 |
| neon-magenta-pulse / 12 s | 4 | 0.020 s | 0.158 s | 208 |
| yellow-pop / 60 s | 20 | 0.104 s | 0.707 s | 1,160 |
| yellow-pop / 300 s | 100 | 0.549 s | 3.412 s | 5,800 |

These bounded fixtures show approximately linear preparation growth. The
300 second transcript is prepared without rendering 300 seconds of video.
Repeated structure and warm process caches limit how well this predicts varied
production transcripts or cold CLI invocations.

| Primary-build FFmpeg operation, 12 s portrait | Median wall time |
| --- | --- |
| Decode to null, no subtitles | 0.324 s |
| Decode + default subtitles to null | 0.602 s |
| Decode + yellow-static to null | 0.560 s |
| Decode + yellow-pop to null | 0.453 s |
| Decode + neon-magenta-pulse to null | 0.548 s |
| Encode current yellow-static | 2.377 s |
| Encode current yellow-pop | 2.586 s |
| Encode current neon-magenta-pulse | 2.705 s |

Encoding alone already costs most of the current render time. For example,
portrait yellow-pop uses 22.672 process CPU seconds with encoding, versus
2.367 CPU seconds for decode/filter/null. Removing word effects saves only
about 8% of portrait render wall time and gives no median improvement in the
landscape sample. All tested word-effect styles have zero word-effect fallback
cues, so the effect comparisons do exercise their requested animation.

The much larger ASS event count does not translate into a similarly large
full-render penalty on these short, non-overlapping cues. Null-sink results are
not monotonic with style complexity, and separate executions cannot isolate
libass cache behavior or scheduler effects. This evidence prioritizes encoding
configuration ahead of replacing the subtitle engine or simplifying animation.

## NVIDIA and resolution comparison

The following rows all use FFmpeg 4.4.2. Compare within each resolution and
build; the primary-build 2.586 second baseline is not the GPU reference.
CPU seconds measure process work summed across threads, rather than elapsed
time. RSS is host RAM and does not include GPU VRAM.

| Setting, same yellow-pop subtitles | 1080×1920, 12 s median (range) | Output | CPU seconds | Peak RSS |
| --- | --- | --- | --- | --- |
| Current implicit medium | 2.331 (2.183–2.343) | 8.61 MiB | 21.487 | 1,193 MiB |
| x264 veryfast / CRF 23 | 1.672 (1.637–1.682) | 7.47 MiB | 11.136 | 911 MiB |
| NVENC p4 / CQ 23 | 1.534 (1.527–1.543) | 16.69 MiB | 2.278 | 389 MiB |
| NVENC p7 / CQ 23 | 2.379 (2.378–2.413) | 17.01 MiB | 2.451 | 515 MiB |
| NVENC p4 / CQ 28 | 1.501 (1.478–1.551) | 10.21 MiB | 2.329 | 388 MiB |
| NVENC p4 / CQ 30 | 1.467 (1.438–1.487) | 7.74 MiB | 2.272 | 388 MiB |

At 1080p, p4/CQ 23 is 1.52× faster than this build's current CPU baseline;
p7 is slightly slower. The clearest GPU advantage is freeing CPU capacity:
p4 uses approximately 89% fewer process CPU seconds than medium, while still
running software decoding and subtitle filtering. It is only about 8% faster
than x264 veryfast at CQ 23, with a much larger file. These graphs test GPU
encoding, not a pipeline where every stage runs on the GPU.

| FFmpeg 4.4.2 portrait setting | SSIM full frame | SSIM bottom 35% |
| --- | --- | --- |
| Current medium / CRF 23 | 0.995397 | 0.989474 |
| veryfast / CRF 23 | 0.993855 | 0.985991 |
| NVENC p4 / CQ 23 | 0.998375 | 0.996634 |
| NVENC p7 / CQ 23 | 0.998572 | 0.997138 |
| NVENC p4 / CQ 28 | 0.995219 | 0.989589 |
| NVENC p4 / CQ 30 | 0.992162 | 0.982445 |

CQ 28 brings the measured similarity close to medium on this fixture, with
about 19% more bytes and 36% less elapsed time. CQ 30 approaches medium's
file size but has lower similarity than both medium and veryfast. This small
sweep illustrates why matching the numeric CRF/CQ value is an unsuitable
comparison of encoding quality.

| Setting, 3840×2160, 6 s / 180 frames | Median (range) | Output | CPU seconds | Peak RSS |
| --- | --- | --- | --- | --- |
| Current implicit medium | 4.625 (4.251–4.894) | 13.97 MiB | 46.403 | 3,872 MiB |
| x264 veryfast / CRF 23 | 2.920 (2.720–3.145) | 11.93 MiB | 24.669 | 2,865 MiB |
| NVENC p4 / CQ 23 | 2.674 (2.673–2.712) | 31.08 MiB | 4.604 | 862 MiB |
| NVENC p7 / CQ 23 | 4.288 (4.260–4.400) | 32.39 MiB | 4.699 | 1,171 MiB |

At 4K, veryfast reduces latency by 37% and p4/CQ 23 by 42%. GPU p4 is only
about 8% faster than veryfast here as well. Medium's peak process RAM reaches
3.78 GiB for this short clip, which matters when considering concurrent jobs.
The 4K decode/null and decode/subtitle/null medians are 0.574 and 0.875 seconds,
respectively. CQ 28/30 were not tested at 4K.

## Unicode boundary reuse experiment

A separate, instrumented 300 second preparation call is recorded in the
[cProfile trace](results/2026-10-18/preparation-profile.txt). It makes 400 calls
to `line_break_boundaries()` for 100 source segments: layout recomputes source
boundaries when deriving multiple visual subdivisions.
Unicode line breaking accounts for 5.658 of 6.989 cumulative seconds inside
that profiled call. Instrumentation changes timings; these values must not be
substituted for the unprofiled benchmark.

The experiment wraps only `text_segmentation.line_break_boundaries()` in an
LRU cache of at most 4,096 entries for one artifact-writing call, and clears
it afterwards. It reuses the existing Unicode implementation without changing
any boundary rule, storing text on disk, or changing production modules.

| Portrait preparation | Baseline artifact median | Cache prototype median | Reduction |
| --- | --- | --- | --- |
| default / 12 s | 0.203 s | 0.111 s | 45% |
| yellow-static / 12 s | 0.148 s | 0.068 s | 54% |
| yellow-pop / 12 s | 0.165 s | 0.090 s | 46% |
| neon-magenta-pulse / 12 s | 0.158 s | 0.092 s | 42% |
| yellow-pop / 60 s | 0.707 s | 0.306 s | 57% |
| yellow-pop / 300 s | 3.412 s | 1.407 s | 59% |

The 300 second case records 300 cache hits and 100 misses; each unique source
text includes its segment number. Thus the benefit comes from repeated work
on the same source inside one render, rather than repeating identical captions
throughout a video. The baseline and cached matrix were collected in separate
invocations on the same host, rather than interleaved matched pairs.

All four executions of all six configurations, including warmups, preserve
48 ASS/SRT files byte for byte. All 24 JSON pairs preserve transcription and
rendering data; timestamps and source paths were excluded from JSON equality.
The [equivalence evidence](results/2026-10-18/cache-equivalence.json) records
the file hashes. This verifies the Portuguese fixtures used here; it is not
coverage of CJK segmentation, bidirectional shaping, custom transforms, or
cache lifetime/concurrency in a production implementation.

## Follow-up: primary FFmpeg with NVIDIA driver 617.42

After the user updated the driver from 560.94 to 617.42, the two-frame NVENC
smoke test succeeded with the unchanged primary FFmpeg
`n9.0.2-17-g2a571b6068-20260930`. This resolves the observed NVENC 13.1
initialization failure for this build/GPU/driver combination.

The CPU/NVIDIA comparisons were repeated on the primary build, with fresh CPU
baselines in the same invocation. Each case again has one excluded warmup and
three measured runs. Source generation, subtitles, settings, SSIM comparisons,
and output checks follow the original method. No Unicode cache prototype is
enabled in these follow-up runs.

```bash
python -m scripts.benchmark_rendering \
  --output-dir data/benchmarks --sizes 1080x1920 --duration 12 \
  --repetitions 3 --preparation-seconds --nvenc --quality \
  --cases current-yellow-pop x264-veryfast nvenc-p4 nvenc-p7 nvenc-p4-cq28 nvenc-p4-cq30

python -m scripts.benchmark_rendering \
  --output-dir data/benchmarks --sizes 3840x2160 --duration 6 \
  --repetitions 3 --preparation-seconds --nvenc --quality \
  --cases current-yellow-pop x264-veryfast nvenc-p4 nvenc-p7 nvenc-p4-cq28 nvenc-p4-cq30
```

### 1080p portrait, 12 seconds / 360 frames

| Setting | Median (range) | Output | CPU seconds | Peak RSS | SSIM full / bottom 35% |
| --- | --- | --- | --- | --- | --- |
| Current medium / CRF 23 | 2.429 (2.363–2.569) | 8.59 MiB | 22.319 | 1,197 MiB | 0.995336 / 0.989292 |
| x264 veryfast / CRF 23 | 1.758 (1.736–1.763) | 7.46 MiB | 11.474 | 918 MiB | 0.993877 / 0.985950 |
| NVENC p4 / CQ 23 | 1.611 (1.570–1.619) | 15.60 MiB | 2.844 | 406 MiB | 0.998166 / 0.996147 |
| NVENC p7 / CQ 23 | 2.755 (2.649–2.839) | 16.63 MiB | 2.796 | 536 MiB | 0.998485 / 0.996957 |
| NVENC p4 / CQ 28 | 1.609 (1.578–1.613) | 9.42 MiB | 2.598 | 409 MiB | 0.994156 / 0.987134 |
| NVENC p4 / CQ 30 | 1.596 (1.571–1.641) | 7.32 MiB | 2.673 | 408 MiB | 0.991381 / 0.980680 |

At CQ 23, p4 reduces elapsed time by 34% and process CPU work by 87% relative
to the fresh medium baseline. It is 8% faster than veryfast while producing
a file about twice as large. P7 is 13% slower than medium in this sample.
CQ 28 has slightly higher SSIM than veryfast with 26% more bytes; its measured
SSIM is below medium. CQ 30 approaches veryfast's size but has lower SSIM.

These are comparisons within the updated environment. The initial successful
GPU runs used FFmpeg 4.4.2, so differences between those runs and this follow-up
cannot be attributed to the driver alone. Numeric quality settings should be
evaluated on the selected FFmpeg build as well as the selected encoder.

### 4K landscape, 6 seconds / 180 frames

| Setting | Median (range) | Output | CPU seconds | Peak RSS | SSIM full / bottom 35% |
| --- | --- | --- | --- | --- | --- |
| Current medium / CRF 23 | 5.154 (4.689–5.192) | 14.08 MiB | 48.163 | 3,859 MiB | 0.995117 / 0.988057 |
| x264 veryfast / CRF 23 | 2.992 (2.930–3.482) | 11.91 MiB | 25.257 | 2,913 MiB | 0.993605 / 0.984299 |
| NVENC p4 / CQ 23 | 2.699 (2.663–2.788) | 29.20 MiB | 5.055 | 913 MiB | 0.998621 / 0.996804 |
| NVENC p7 / CQ 23 | 5.122 (5.057–5.138) | 31.62 MiB | 5.400 | 1,219 MiB | 0.998799 / 0.997336 |
| NVENC p4 / CQ 28 | 2.753 (2.731–2.760) | 17.55 MiB | 5.702 | 910 MiB | 0.995786 / 0.990091 |
| NVENC p4 / CQ 30 | 2.822 (2.780–2.889) | 13.53 MiB | 5.660 | 924 MiB | 0.993371 / 0.984254 |

At 4K, p4/CQ 23 reduces elapsed time by 48% and process CPU work by 90%
relative to medium. It is 10% faster than veryfast, with a file 2.45 times as
large. CQ 28 has higher SSIM than medium on this fixture, about 25% more bytes,
and 47% less elapsed time. CQ 30 approaches medium's size with lower SSIM.

The compatibility blocker is resolved. The measured strategy remains to expose
explicit encoder/preset/quality controls and evaluate the quality/size tradeoff
on real footage. The default production render graph still delegates encoder
selection to FFmpeg; the implementation also permits explicit NVENC selection.

## Implementation follow-up

The local implementation adds `--video-encoder`, `--video-preset`, and
`--video-quality` plus the immutable public Python `VideoEncodingConfig`.
Normal rendering, existing SRT/ASS rendering, and animated previews share the
same encoding boundary. Explicit encoder initialization is checked on one
synthetic frame before transcription/deferred generation, with bounded
diagnostics and a 30 second timeout. Default rendering adds no preflight.
These checks add process/device initialization time to explicit high-level
requests; earlier encoder-only timings exclude that overhead.
See the [current usage and defaults](../../README.md#video-encoding).

For Unicode work, the implementation reuses the partitioned display units when
reconstructing linguistic groups for subdivisions. It eliminates the repeated
source analysis directly, rather than shipping the benchmark's cache wrapper.
No global or persisted transcript cache is involved.

The existing preparation harness was repeated with the new implementation,
with the cache prototype disabled, one excluded warmup, and three samples:

| Portrait preparation | Original artifact median | Implemented reuse median | Reduction |
| --- | --- | --- | --- |
| default / 12 s | 0.203 s | 0.115 s | 43% |
| yellow-static / 12 s | 0.148 s | 0.072 s | 51% |
| yellow-pop / 12 s | 0.165 s | 0.092 s | 44% |
| neon-magenta-pulse / 12 s | 0.158 s | 0.082 s | 48% |
| yellow-pop / 60 s | 0.707 s | 0.314 s | 56% |
| yellow-pop / 300 s | 3.412 s | 1.449 s | 58% |

The 48 ASS/SRT files are byte-identical to the initial baseline. All 24 JSON
pairs are identical after removing creation timestamps and source paths.
The [preparation measurements](results/2026-10-18/implementation-preparation.json)
include hashes of the local implementation sources; the
[equivalence checks](results/2026-10-18/implementation-equivalence.json)
record the subtitle hashes. Separate regression cases compare reconstructed
and reused units for combining accents, case expansion, Japanese, Chinese,
and Arabic.

The benchmark directory exposed setuptools' automatic namespace discovery
including generated directories. Distribution discovery now selects only
regular `multisubs` Python packages and explicitly inventoried assets. An
isolated wheel/sdist build verifies that generated media is absent while all
bundled font/template resource bytes remain intact. An editable install and
the console entry point were verified with `.venv` activated.

## Optimization priorities

| Priority | Candidate | Evidence and next decision |
| --- | --- | --- |
| 1 | Explicit CPU encoder, preset, and quality controls | Implemented locally through typed requests, Python APIs and CLI flags, preserving defaults. veryfast cuts encoder-only 1080p latency 28–34% in the initial samples; real-footage quality/size assessment remains useful. |
| 2 | Reuse Unicode/layout work within cue processing | Implemented by reusing partitioned display units. The repeated 300 second preparation is 58% faster with identical measured artifacts and multilingual/source-offset regression coverage. |
| 3 | Opt-in NVENC with initialization preflight and explicit quality/preset settings | Implemented locally. Driver 617.42 initializes the primary build; CPU/NVIDIA media tests preserve audio, subtitle visibility, and collision behavior. Initial encoder-only latency gains remain distinct from full-request latency including the preflight. |
| 4 | Measure controlled job concurrency after choosing per-job settings | Current medium uses almost 3.8 GiB host RAM in the 4K case. CPU seconds and RSS suggest useful tradeoffs, but this investigation measures individual jobs and cannot select safe parallelism or predict batch throughput. |
| 5 | Instrument ASR and full API/CLI latency on representative speech, separately from rendering | This investigation intentionally loads no ASR. The existing source-transcript API already permits transcription reuse for styling variants; no inference-speed improvement is claimed here. |

Lossy encoding and repeated Unicode work offer the clearest initial targets
while retaining the existing renderer, animation, timing, resolution, and
output contracts. The subtitle-filter measurements provide a baseline for
revisiting that stage after the first improvements.

The next evidence should use non-sensitive 30–60 second clips covering a
talking head, a screen recording, and high motion/detail. Compare configurations
on a similar quality/size frontier, inspect caption edges and motion, and
include 1080p/4K, source codecs, cold versus warm startup, audio preservation,
rotation, and multilingual layouts. Short synthetic results should guide which
candidates to evaluate, rather than set a universal speed target.

The [real-footage follow-up](2026-10-18-real-rendering.md) now covers three
30 second 1080p samples from the user-selected videos: animated action, screen
content, and a person speaking. It records 36 measured encodes, quality/size
comparisons, and separate decode/filter diagnostics. Its results supplement the
synthetic counts below; product defaults remain unchanged.

## Evidence and verification

The initial matrices contain 52 FFmpeg scenarios; the driver-617.42 follow-up
adds 12. Combined, these are 64 scenarios, 192 measured executions and 64
excluded warmups, in addition to preparation, quality, and profiling calls.
All 47 encoded-output cases retain the expected frame count and dimensions,
match the requested duration within 0.1 seconds, and preserve the compressed
audio payload hash. The portable records contain every measured sample,
compiled command, encoder output size, CPU/RSS observation, and quality score:

- [Primary FFmpeg, portrait/landscape](results/2026-10-18/cpu-ffmpeg9.json).
- [Alternate FFmpeg, CPU/NVIDIA](results/2026-10-18/gpu-ffmpeg4.json).
- [Alternate FFmpeg, 4K subset](results/2026-10-18/gpu-4k-ffmpeg4.json).
- [NVIDIA quality sweep](results/2026-10-18/gpu-cq-ffmpeg4.json).
- [Unicode cache prototype](results/2026-10-18/line-break-cache.json).
- [Primary FFmpeg, driver 617.42, 1080p follow-up](results/2026-10-18/gpu-primary-driver617-1080p.json).
- [Primary FFmpeg, driver 617.42, 4K follow-up](results/2026-10-18/gpu-primary-driver617-4k.json).
- [Implemented layout reuse, preparation](results/2026-10-18/implementation-preparation.json).
- [Implemented layout reuse, artifact equivalence](results/2026-10-18/implementation-equivalence.json).

These records omit verbose container/transcript metadata; full local logs and
generated fixtures remain in ignored `data/benchmarks`. FFmpeg 4.4 labels its
Linux peak-RSS counter `kB`, while FFmpeg 9 labels it `KiB`; the portable export
recovers the older label from the same per-execution logs. Initial cache
experiments remain confined to the benchmark script; the production changes
are described separately in the implementation follow-up above.

Initial verification: 1,313 hermetic tests passed, with 88 integration tests deselected;
the synthetic benchmark itself exercised FFmpeg/libass/audio boundaries.
Compilation, Ruff formatting/lint, script type checking, and CLI/script help
passed with the repository virtual-environment interpreter. The bare global
`multisubs --help` executable uses a different interpreter and failed to import
Typer's `_click`; `python -m multisubs.cli --help` passed in the project
environment. This existing global-install mismatch was left outside the
benchmark scope.

Post-update verification: the primary NVENC smoke test and all 12 follow-up
encode cases passed. The harness validated frame counts, dimensions, durations,
and copied audio, and collected both SSIM regions. Report links and portable
JSON evidence were checked. That driver-only follow-up updated documentation
and evidence; production code and the harness were unchanged at that stage.

Implementation verification: 1,353 hermetic tests passed. The 94 FFmpeg/media
integration cases passed on the primary FFmpeg, including all three opt-in
NVIDIA cases. The new wheel/sdist isolation test also passed (95 integration
cases total), and the six new CPU/NVIDIA media cases passed separately on the
system FFmpeg 4.4.2. Both builds preserve two copied audio streams, subtitle
visibility, output geometry, and collision safety through the CLI/API checks.
Ruff formatting/lint, Pyright, compilation, editable installation, console
help/version with `.venv` activated, and portable-evidence checks passed.
