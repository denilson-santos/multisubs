import os
import json
from datetime import datetime
import torch
import whisperx
from .config import DEFAULT_STYLE
from .utils import get_unique_path

WHISPER_MODELS = (
    "tiny.en", "tiny", "base.en", "base", "small.en", "small",
    "medium.en", "medium", "large", "turbo",
)

MAX_CHARS_PER_LINE = 42
# Two lines are the hard cue limit.  The line limit itself is a target: a
# small overflow is preferable to splitting a syntactic unit at an awkward
# point.
MAX_CHARS_PER_CUE = MAX_CHARS_PER_LINE * 2
MAX_LINE_OVERFLOW = 6
MIN_CHARS_PER_LINE = 15
MAX_CUE_DURATION = 6.0
PAUSE_BREAK_THRESHOLD = 0.45


def generate_transcriptions(
    input_path,
    output_dir,
    style_options=None,
    lang='en',
    task='transcribe',
    model_name='turbo',
):
    """
    Generates transcriptions for a video file using WhisperX.
    Creates JSON, SRT, and ASS files simultaneously.

    Args:
        input_path (str): Path to the video file.
        output_dir (str): Directory to save the transcription files.
        style_options (dict, optional): Options to customize the subtitle style. Defaults to None.
        lang (str, optional): Language for transcription. Defaults to 'en'.
        task (str, optional): Transcribe, or translate speech to English. Defaults to 'transcribe'.
        model_name (str, optional): Whisper model name. Defaults to 'turbo'.

    Returns:
        tuple: (json_path, srt_path, ass_path)
    """
    file_name, file_ext = os.path.splitext(os.path.basename(input_path))
    print(f"Generating video transcripts '{file_name+file_ext}' for folder '{output_dir}'...\n")
    os.makedirs(output_dir, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"

    print(f"Loading WhisperX model '{model_name}' on {device} ({compute_type})...")
    model = whisperx.load_model(
        model_name,
        device,
        compute_type=compute_type,
        language=lang or None,
        task=task,
        # Avoid WhisperX's default Pyannote VAD, which requires a PyTorch/
        # cuDNN build compatible with the installed Pyannote checkpoint.
        vad_method="silero",
    )

    print("Transcribing audio...")
    audio = whisperx.load_audio(input_path)
    result = model.transcribe(audio)

    print("Aligning words for subtitle timing...")
    align_model, align_metadata = whisperx.load_align_model(
        language_code=result.get('language', lang),
        device=device,
    )
    aligned_result = whisperx.align(
        result['segments'],
        align_model,
        align_metadata,
        audio,
        device,
        return_char_alignments=False,
    )
    segments = _build_subtitle_segments(aligned_result['segments'])

    full_text = result.get('text') or ' '.join(
        segment['text'].strip() for segment in segments if segment['text'].strip()
    )

    # Generate all output files
    json_path = _save_transcription_json(
        full_text, segments, output_dir, file_name, lang, input_path, task, model_name
    )
    print("Completed JSON transcript!\n")

    srt_path = _generate_srt_file(segments, output_dir, file_name, lang)
    print("Completed SRT transcript!\n")

    ass_path = _generate_ass_file(segments, output_dir, file_name, lang, style_options)
    print("Completed ASS transcript!\n")

    return json_path, srt_path, ass_path


def _build_subtitle_segments(aligned_segments):
    """Build readable subtitle cues from WhisperX word timestamps.

    Words from consecutive WhisperX segments are considered together.  Cue
    boundaries are preferred at sentence punctuation and meaningful pauses;
    character and duration limits are used as fallbacks when no semantic
    boundary is available.
    """
    cues = []
    pending_words = []

    for segment in aligned_segments:
        words = _timed_words(segment)
        if words:
            # WhisperX may split one grammatical sentence into multiple ASR
            # segments.  Keeping the words in one stream lets the subtitle
            # logic choose a better boundary than the ASR segmentation.
            pending_words.extend(words)
            continue

        # Alignment can occasionally return a segment without word-level
        # timestamps.  Flush the aligned stream before using its coarse
        # segment as a safe fallback.
        if pending_words:
            cues.extend(_build_cues_from_words(pending_words))
            pending_words = []
        _append_cue(
            cues,
            segment.get('text', ''),
            segment.get('start', 0.0),
            segment.get('end', 0.0),
            [],
        )

    if pending_words:
        cues.extend(_build_cues_from_words(pending_words))

    for idx, cue in enumerate(cues):
        cue['id'] = idx
    return cues


def _timed_words(segment):
    """Return usable word timestamps from an aligned WhisperX segment."""
    return [
        word for word in segment.get('words', [])
        if word.get('word', '').strip()
        and word.get('start') is not None
        and word.get('end') is not None
    ]


def _build_cues_from_words(words):
    """Create cues from one continuous, chronologically ordered word stream."""
    cues = []
    current_words = []

    for word in words:
        if current_words and _has_significant_pause(current_words[-1], word):
            _append_words_cue(cues, current_words)
            current_words = []

        current_words.append(word)

        # A long sentence can require more than one cue.  When that happens,
        # split at the best available boundary and keep the remaining words
        # in the next cue instead of cutting immediately before `word`.
        while current_words and _cue_exceeds_limits(current_words):
            if len(current_words) == 1:
                # An unusually long word cannot be split without damaging the
                # transcription.  Keep it intact as a last resort.
                _append_words_cue(cues, current_words)
                current_words = []
                break

            break_at = _find_best_cue_break(current_words)
            if break_at <= 0 or break_at >= len(current_words):
                break_at = len(current_words) - 1

            _append_words_cue(cues, current_words[:break_at])
            current_words = current_words[break_at:]

        # Sentence punctuation is a stronger boundary than line balance.  A
        # short sentence should not be forced to share a cue with the next
        # sentence merely because it has fewer than 42 characters.
        if current_words and _ends_sentence(current_words[-1].get('word', '')):
            _append_words_cue(cues, current_words)
            current_words = []

    if current_words:
        _append_words_cue(cues, current_words)

    return cues


def _append_words_cue(cues, words):
    """Append a cue whose timing is derived from its first and last word."""
    if not words:
        return
    _append_cue(
        cues,
        _words_to_text(words),
        words[0]['start'],
        words[-1]['end'],
        words,
    )


def _cue_exceeds_limits(words):
    return (
        len(_words_to_text(words)) > MAX_CHARS_PER_CUE
        or _words_duration(words) > MAX_CUE_DURATION
    )


def _words_duration(words):
    return words[-1]['end'] - words[0]['start']


def _find_best_cue_break(words):
    """Find the best word boundary before the cue's hard limits.

    Semantic priority is the first criterion.  Distance from the character
    and duration targets only decides between boundaries of equal quality.
    """
    candidates = [
        index for index in range(1, len(words))
        if not _cue_exceeds_limits(words[:index])
    ]
    if not candidates:
        return 1

    def key(index):
        prefix = words[:index]
        character_distance = abs(MAX_CHARS_PER_CUE - len(_words_to_text(prefix)))
        duration_distance = abs(MAX_CUE_DURATION - _words_duration(prefix))
        distance = (
            character_distance / MAX_CHARS_PER_CUE
            + duration_distance / MAX_CUE_DURATION
        )
        return _boundary_priority(words, index), -distance

    return max(candidates, key=key)


def _append_cue(cues, text, start, end, words):
    text = text.strip()
    if not text:
        return
    cues.append({
        'id': len(cues),
        'start': start,
        'end': end,
        'text': _wrap_subtitle_text(text, words),
        'words': words,
    })


def _words_to_text(words):
    return ' '.join(word['word'].strip() for word in words).strip()


def _ends_sentence(word):
    return word.rstrip().endswith(('.', '!', '?', '…'))


def _ends_clause(word):
    return word.rstrip().endswith((',', ';', ':', '—', '–'))


def _has_significant_pause(previous_word, next_word):
    previous_end = previous_word.get('end')
    next_start = next_word.get('start')
    if previous_end is None or next_start is None:
        return False
    return next_start - previous_end >= PAUSE_BREAK_THRESHOLD


def _boundary_priority(words, index):
    """Return the language-independent priority of a word boundary."""
    previous_word = words[index - 1]
    next_word = words[index]
    previous_text = previous_word.get('word', '')

    if _ends_sentence(previous_text):
        return 3
    if _ends_clause(previous_text):
        return 2
    if _has_significant_pause(previous_word, next_word):
        return 1
    return 0


def _wrap_subtitle_text(text, words=None):
    """Wrap a cue at a semantic word boundary, producing at most two lines.

    Forty-two characters is treated as the preferred line length.  A small
    overflow is allowed when it preserves a punctuation-, pause-, or
    phrase-friendly boundary.  When boundaries are equally suitable, the
    first line is filled as much as possible without leaving a short second
    line.
    """
    if len(text) <= MAX_CHARS_PER_LINE:
        return text

    if words:
        line_words = [word for word in words if word.get('word', '').strip()]
    else:
        line_words = [{'word': word} for word in text.split()]

    if len(line_words) < 2:
        return text

    def key(index):
        left = _words_to_text(line_words[:index])
        right = _words_to_text(line_words[index:])
        left_overflow = max(0, len(left) - MAX_CHARS_PER_LINE)
        right_overflow = max(0, len(right) - MAX_CHARS_PER_LINE)
        hard_overflow = max(
            0,
            left_overflow - MAX_LINE_OVERFLOW,
        ) + max(
            0,
            right_overflow - MAX_LINE_OVERFLOW,
        )
        shortest_line = min(len(left), len(right))
        short_line_penalty = max(0, MIN_CHARS_PER_LINE - shortest_line) ** 2

        # First protect the hard overflow and very short lines.  Then fill
        # the first line as much as possible; punctuation and pauses resolve
        # ties between equally well-sized candidates.
        return (
            hard_overflow,
            short_line_penalty,
            left_overflow + right_overflow,
            -len(left),
            -_boundary_priority(line_words, index),
            abs(len(left) - len(right)),
        )

    break_at = min(range(1, len(line_words)), key=key)
    left = _words_to_text(line_words[:break_at])
    right = _words_to_text(line_words[break_at:])
    return f"{left}\n{right}"


def _save_transcription_json(full_text, segments, output_dir, file_name, lang, input_path, task, model_name):
    """
    Saves the transcription result as a JSON file with metadata.

    Args:
        full_text (str): Complete transcription text.
        segments (list): List of transcription segments with timestamps.
        output_dir (str): Directory to save the JSON file.
        file_name (str): Base name of the video file.
        lang (str): Language code.
        input_path (str): Original video file path.
        task (str): Task type (transcribe or translate).
        model_name (str): Whisper model used for the transcription.

    Returns:
        str: Path to the saved JSON file.
    """
    json_data = {
        'metadata': {
            'file_name': file_name,
            'original_path': input_path,
            'language': lang,
            'task': task,
            'created_at': datetime.now().isoformat(),
            'model': model_name,
            'duration': segments[-1]['end'] if segments else 0.0,
            'num_segments': len(segments)
        },
        'transcription': {
            'text': full_text,
            'segments': segments
        }
    }

    json_path = get_unique_path(os.path.join(output_dir, f"{file_name}-{lang}.json"))

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    return json_path


def _generate_srt_file(segments, output_dir, file_name, lang):
    """
    Generates SRT file from transcription segments.

    Args:
        segments (list): List of transcription segments with timestamps.
        output_dir (str): Directory to save the SRT file.
        file_name (str): Base name of the video file.
        lang (str): Language code.

    Returns:
        str: Path to the generated SRT file.
    """
    def format_time_srt(seconds):
        """Format time for SRT format: HH:MM:SS,mmm"""
        total_millis = round((seconds or 0.0) * 1000)
        hours, remainder = divmod(total_millis, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        secs, millis = divmod(remainder, 1_000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    srt_path = get_unique_path(os.path.join(output_dir, f"{file_name}-{lang}.srt"))

    with open(srt_path, 'w', encoding='utf-8') as f:
        for idx, segment in enumerate(segments, start=1):
            start_time = format_time_srt(segment['start'])
            end_time = format_time_srt(segment['end'])
            text = segment['text'].strip()

            f.write(f"{idx}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{text}\n\n")

    return srt_path


def _generate_ass_file(segments, output_dir, file_name, lang, style_options=None):
    """
    Generates ASS file from transcription segments.

    Args:
        segments (list): List of transcription segments with timestamps.
        output_dir (str): Directory to save the ASS file.
        file_name (str): Base name of the video file.
        lang (str): Language code.
        style_options (dict, optional): Style customization options.

    Returns:
        str: Path to the generated ASS file.
    """
    def format_time_ass(seconds):
        """Format time for ASS format: H:MM:SS.cc"""
        if seconds is None:
            seconds = 0.0
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"

    style = DEFAULT_STYLE.copy()
    if style_options:
        style.update(style_options)

    ass_path = get_unique_path(os.path.join(output_dir, f"{file_name}-{lang}.ass"))

    with open(ass_path, 'w', encoding='utf-8') as f:
        # Write header
        f.write("[Script Info]\n")
        f.write(f"Title: {file_name}\n")
        f.write("ScriptType: v4.00+\n\n")

        # Write styles
        f.write("[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        f.write(
            f"Style: Default,{style['font']},{style['font_size']},{style['primary_color']},"
            f"{style['secondary_color']},{style['outline_color']},{style['back_color']},"
            f"{style['bold']},{style['italic']},{style['underline']},{style['strikeout']},"
            f"{style['scale_x']},{style['scale_y']},{style['spacing']},{style['angle']},"
            f"{style['border_style']},{style['outline_weight']},{style['shadow_weight']},"
            f"{style['alignment']},{style['margin_l']},{style['margin_r']},{style['margin_v']},1\n\n"
        )

        # Write events
        f.write("[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")

        for segment in segments:
            start = format_time_ass(segment['start'])
            end = format_time_ass(segment['end'])
            text = segment['text'].strip().replace('\n', '\\N')
            f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")

    return ass_path
