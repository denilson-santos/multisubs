
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
  file_name, file_ext = os.path.splitext(os.path.basename(input_path))
  print(f"Adding subtitles to video '{file_name+file_ext}' and saving in the folder '{output_dir}'...\n")
  
  os.makedirs(output_dir, exist_ok=True)
  output_path = get_unique_path(os.path.join(output_dir, f"{file_name}-{lang}{file_ext}"))

  input_stream = ffmpeg.input(input_path)
  ( 
    ffmpeg
    .output(input_stream, output_path, vf=f'subtitles={ass_path}', acodec='copy')
    .run(overwrite_output=True)
  )

  print("\nSubtitle added successfully!\n")
  return output_path