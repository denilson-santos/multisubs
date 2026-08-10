
import argparse
import os
from . import __version__
from .transcriber import WHISPER_MODELS, generate_transcriptions
from .subtitler import embed_subtitles
from .config import DEFAULT_STYLE
from .utils import get_unique_dir_path

def main():
    parser = argparse.ArgumentParser(
        add_help=False,
        description='Generate and embed subtitles into a video.',
        formatter_class=lambda prog: argparse.RawTextHelpFormatter(prog, max_help_position=30),
    )

    parser.add_argument(
        '-h',
        '--help',
        action='help',
        default=argparse.SUPPRESS,
        help='Show all options.'
    )

    parser.add_argument(
        '-v',
        '--version',
        action='version',
        version=f'%(prog)s {__version__}',
        help='Show package version.'
    )

    parser.add_argument(
        '-i',
        '--input-path',
        required=True,
        default=argparse.SUPPRESS,
        help='Path to the video file. (Required)',
        metavar='*'
    )

    parser.add_argument(
        '-o',
        '--output-dir',
        default='.',
        help='Output directory for the subtitled video. Defaults (current directory).',
        metavar=''
    )

    parser.add_argument(
        '-l',
        '--lang',
        type=str,
        default='en',
        choices=['af', 'am', 'ar', 'as', 'az', 'ba', 'be', 'bg', 'bn', 'bo', 'br', 'bs', 'ca', 'cs', 'cy', 'da', 'de', 'el', 'en', 'es', 'et', 'eu', 'fa', 'fi', 'fo', 'fr', 'gl', 'gu', 'ha', 'haw', 'he', 'hi', 'hr', 'ht', 'hu', 'hy', 'id', 'is', 'it', 'ja', 'jw', 'ka', 'kk', 'km', 'kn', 'ko', 'la', 'lb', 'ln', 'lo', 'lt', 'lv', 'mg', 'mi', 'mk', 'ml', 'mn', 'mr', 'ms', 'mt', 'my', 'ne', 'nl', 'nn', 'no', 'oc', 'pa', 'pl', 'ps', 'pt', 'ro', 'ru', 'sa', 'sd', 'si', 'sk', 'sl', 'sn', 'so', 'sq', 'sr', 'su', 'sv', 'sw', 'ta', 'te', 'tg', 'th', 'tk', 'tl', 'tr', 'tt', 'uk', 'ur', 'uz', 'vi', 'yi', 'yo', 'yue', 'zh'],
        help='Source language. Translation output is always English. Default: "en"',
        metavar=''
    )

    parser.add_argument(
        '-t',
        '--task',
        type=str,
        default='transcribe',
        choices=['transcribe', 'translate'],
        help='Transcribe, or translate speech to English. Turbo models cannot translate. Default: "transcribe"',
        metavar=''
    )

    parser.add_argument(
        '-m',
        '--model',
        default='turbo',
        choices=WHISPER_MODELS,
        help='Whisper model. For translation, use a multilingual non-Turbo model (e.g. medium or large). Default: "turbo"',
        metavar=''
    )

    parser.add_argument(
        '-k',
        '--keep-transcriptions',
        action='store_true',
        help='Keep transcription files (.srt, .ass) in a structured folder.'
    )

    style_group = parser.add_argument_group('Styling', 'Options to customize subtitle style.')
    for key, value in DEFAULT_STYLE.items():
        style_group.add_argument(
            f'--style-{key.replace("_", "-")}',
            type=type(value),
            default=value,
            help=f'Default: "{value}"',
            metavar=''
        )

    args = parser.parse_args()

    if args.task == 'translate' and args.model == 'turbo':
        parser.error(
            f'Model "{args.model}" does not support translation. '
            'Use a multilingual non-Turbo model, such as "medium" or "large". '
            'Whisper translations are always generated in English.'
        )
    if args.task == 'translate' and args.model.endswith('.en'):
        parser.error(
            f'Model "{args.model}" is English-only and cannot translate. '
            'Use a multilingual non-Turbo model, such as "medium" or "large". '
            'Whisper translations are always generated in English.'
        )

    video_path = args.input_path
    output_dir = args.output_dir

    if not os.path.exists(video_path):
        print(f"Error: Video file not found at '{video_path}'")
        return
    
    if os.path.isfile(output_dir):
        print(f"Error: Output path '{output_dir}' is a file, please provide a directory.")
        return

    if output_dir == '.':
        output_dir = os.getcwd()

    style_options = {}
    for key in DEFAULT_STYLE:
        arg_key = f'style_{key}'
        if hasattr(args, arg_key):
            style_options[key] = getattr(args, arg_key)

    video_name = os.path.splitext(os.path.basename(video_path))[0]

    if args.keep_transcriptions:
        final_output_dir = get_unique_dir_path(os.path.join(output_dir, video_name))

        subtitles_dir = os.path.join(final_output_dir, 'subtitles')
        os.makedirs(subtitles_dir, exist_ok=True)

        json_path, srt_path, ass_path = generate_transcriptions(
            video_path, subtitles_dir, style_options, args.lang, args.task, args.model
        )
        output_path = embed_subtitles(video_path, ass_path, final_output_dir, args.lang)
        
        print(f'Files saved in: {final_output_dir}')

    else:
        json_path, srt_path, ass_path = generate_transcriptions(
            video_path, output_dir, style_options, args.lang, args.task, args.model
        )
        output_path = embed_subtitles(video_path, ass_path, output_dir, args.lang)
        
        srt_path = ass_path.replace('.ass', '.srt')
        try:
            os.remove(ass_path)
            os.remove(srt_path)
        except OSError as e:
            print(f"Error removing subtitle files: {e}")
            
        print(f'File saved in: {output_path}')

if __name__ == '__main__':
    main()
