FROM python:3.11

WORKDIR /usr/app

RUN apt-get update -y \
  && apt-get install -y ffmpeg \ 
  && pip install -U openai-whisper

CMD ["tail", "-f", "/dev/null"]