
import os
import ffmpeg
from .utils import get_unique_path

def embed_subtitles(input_path, ass_path, output_dir, lang='en'):
  """
  Embeds subtitles into a video file.

  Args:
      input_path (str): Path to the video file.
      ass_path (str): Path to the ass subtitle file.
      output_dir (str): Directory to save the subtitled video.
  """
  file_name = os.path.splitext(os.path.basename(input_path))[0]
  print(f"Adicionando legendas ao vídeo '{file_name}' e salvando na pasta '{output_dir}'...\n")
  
  os.makedirs(output_dir, exist_ok=True)
  output_path = get_unique_path(os.path.join(output_dir, f"{file_name}-{lang}.mp4"))

  input_stream = ffmpeg.input(input_path)
  ( 
    ffmpeg
    .output(input_stream, output_path, vf=f'subtitles={ass_path}', acodec='copy')
    .run(overwrite_output=True)
  )

  print("\nLegenda adicionada com sucesso!\n")
  return output_path

# def convert_transcriptions(input_path, output_dir, style_options=None):
#   file_name = os.path.splitext(os.path.basename(input_path))[0]
#   print(f"Convertendo transcrição '{file_name}' de formato '.srt' para '.ass' e salvando na pasta '{output_dir}'...\n")
#   os.makedirs(output_dir, exist_ok=True)

#   def format_time(srt_time):
#     # Ex: 00:01:02,300 => 0:01:02.30 (centésimos de segundo)
#     h, m, s_ms = srt_time.split(':')
#     s, ms = s_ms.split(',')
#     return f"{int(h)}:{int(m):02d}:{int(s):02d}.{int(ms[:2]):02d}"

#   # Loand and split blocks 
#   with open(input_path, 'r', encoding='utf-8') as f:
#     content = f.read()

#   blocks = re.split(r'\n\s*\n', content.strip())
#   subtitles = []

#   for block in blocks:
#     lines = block.strip().splitlines()
#     if len(lines) >= 3:
#       timing = lines[1]
#       start_str, end_str = timing.split(' --> ')
#       start = format_time(start_str.strip())
#       end = format_time(end_str.strip())
#       text = '\\N'.join(line.strip() for line in lines[2:])
#       subtitles.append((start, end, text))

#   # Default style
#   style = {
#     'font': 'Roboto',
#     'font_size': 14,
#     'primary_color': '&H00FFFFFF',
#     'secondary_color': '&H00FFFFFF',
#     'outline_color': '&H66000000',
#     'back_color': '&H66000000',
#     'bold': 0,
#     'italic': 0,
#     'underline': 0,
#     'strikeout': 0,
#     'scale_x': 100,
#     'scale_y': 100,
#     'spacing': 0,
#     'angle': 0,
#     'border_style': 4,
#     'outline_weight': 0,
#     'shadow_weight': 2,
#     'alignment': 2, 
#     'margin_l': 40,
#     'margin_r': 40,
#     'margin_v': 15
#   }

#   if style_options:
#     style.update(style_options)

#   output_path=os.path.join(output_dir, f"{file_name}.ass")

#   with open(output_path, 'w', encoding='utf-8') as f:
#     # Header
#     f.write("[Script Info]\n")
#     f.write("Title: Converted from SRT\n")
#     f.write("ScriptType: v4.00+\n\n")

#     # Styles
#     f.write("[V4+ Styles]\n")
#     f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
#     f.write(
#         f"Style: Default,{style['font']},{style['font_size']},{style['primary_color']},"
#         f"{style['secondary_color']},{style['outline_color']},{style['back_color']},"
#         f"{style['bold']},{style['italic']},{style['underline']},{style['strikeout']},"
#         f"{style['scale_x']},{style['scale_y']},{style['spacing']},{style['angle']},"
#         f"{style['border_style']},{style['outline_weight']},{style['shadow_weight']},"
#         f"{style['alignment']},{style['margin_l']},{style['margin_r']},{style['margin_v']},1\n\n"
#     )

#     # Events
#     f.write("[Events]\n")
#     f.write("Format: Marked, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")

#     for start, end, text in subtitles:
#       f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")

#   print("Conversão de transcrição concluída!\n")