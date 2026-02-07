FROM python:3.11-slim

# ffmpeg 설치 (MP3 변환에 필요)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 스크립트 복사
COPY youtube_auto_download.py .
COPY config.ini .
COPY credentials.json .
COPY token.json .

# 다운로드 폴더 생성
RUN mkdir -p downloads

# 실행
CMD ["python", "youtube_auto_download.py"]
