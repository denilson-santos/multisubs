import os
import whisper
from .config import DEFAULT_STYLE
from .utils import get_unique_path
from whisper.utils import get_writer

def generate_transcriptions(input_path, output_dir, style_options=None, lang='en', task='transcribe'):
  """
  Generates srt and ass transcriptions for a video file.

  Args:
      input_path (str): Path to the video file.
      output_dir (str): Directory to save the transcription files.
      style_options (dict, optional): Options to customize the subtitle style. Defaults to None.
      lang (str, optional): Language for transcription. Defaults to 'en'.
      task (str, optional): Transcribe or translate task. Defaults to 'transcribe'.
  """
  file_name = os.path.splitext(os.path.basename(input_path))[0]
  print(f"Generating video transcripts '{file_name}' for folder '{output_dir}'...\n")
  os.makedirs(output_dir, exist_ok=True)

  model = whisper.load_model('turbo')
  result = model.transcribe(input_path, language=lang, task=task)
  writer = get_writer('srt', output_dir)
  srt_path = get_unique_path(os.path.join(output_dir, f"{file_name}-{lang}.srt"))

  writer(result, srt_path)
  print("Completed srt transcript!\n")

  def format_time_ass(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}".replace('.', ':')

  ass_subtitles = []
  for segment in result['segments']:
    start = format_time_ass(segment['start'])
    end = format_time_ass(segment['end'])
    text = segment['text'].strip().replace('\n', '\\N')
    ass_subtitles.append((start, end, text))

  style = DEFAULT_STYLE.copy()
  if style_options:
    style.update(style_options)

  subtitles_path = get_unique_path(os.path.join(output_dir, f"{file_name}-{lang}.ass"))

  with open(subtitles_path, 'w', encoding='utf-8') as f:
    f.write("[Script Info]\n")
    f.write(f"Title: {file_name}\n")
    f.write("ScriptType: v4.00+\n\n")
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
    f.write("[Events]\n")
    f.write("Format: Marked, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    for start, end, text in ass_subtitles:
      f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")

  print("Completed ass transcript!\n")
  return subtitles_path

