FROM python:3.13-slim

# ffmpeg 설치 (HLS → MP3 변환용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

WORKDIR /app

RUN pip3 install -r requirements.txt

CMD ["python3", "app.py"]