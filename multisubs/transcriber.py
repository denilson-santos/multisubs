import os
import json
from datetime import datetime
import whisper
from .config import DEFAULT_STYLE
from .utils import get_unique_path

WHISPER_MODELS = (
    "tiny.en", "tiny", "base.en", "base", "small.en", "small",
    "medium.en", "medium", "large", "turbo",
)

def generate_transcriptions(
    input_path,
    output_dir,
    style_options=None,
    lang='en',
    task='transcribe',
    model_name='turbo',
):
    """
    Generates transcriptions for a video file using an OpenAI Whisper model.
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

    print(f"Loading Whisper model '{model_name}'...")
    model = whisper.load_model(model_name)

    print("Transcribing audio...")
    # ``whisper.transcribe`` performs long-form decoding itself. Unlike the
    # Transformers ASR pipeline, it preserves the timestamp offsets between
    # successive 30-second windows.
    result = model.transcribe(
        input_path,
        language=lang or None,
        task=task,
        verbose=False,
    )

    # Process result to create segments with timestamps
    segments = []
    if 'segments' in result:
        for idx, chunk in enumerate(result['segments']):
            segment = {
                'id': idx,
                'start': chunk.get('start', 0.0),
                'end': chunk.get('end', 0.0),
                'text': chunk['text']
            }
            segments.append(segment)
    else:
        # Fallback if no chunks available
        segments.append({
            'id': 0,
            'start': 0.0,
            'end': 0.0,
            'text': result.get('text', '')
        })

    full_text = result.get('text', '')

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
