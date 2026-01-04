# 클라우드 저장소 활용 가이드

## Docker vs 클라우드 저장소

| 개념 | 용도 | 이 프로젝트에서 |
|------|------|----------------|
| **Docker** | 애플리케이션 컨테이너화/배포 | 스크립트를 서버에서 자동 실행할 때 필요 |
| **클라우드 저장소** | 파일 저장 (S3, GCS, Dropbox 등) | MP3 파일 저장에 필요 |

**결론**: 로컬 용량 문제 해결에는 **클라우드 저장소**가 필요합니다. Docker는 선택사항입니다.

---

## 클라우드 저장소 옵션 비교

### 1. Google Drive (권장 - 무료)

| 항목 | 내용 |
|------|------|
| 무료 용량 | 15GB |
| 장점 | 무료, 쉬운 공유, 웹 접근 가능 |
| 단점 | API 할당량 제한 |
| Python 라이브러리 | `google-api-python-client`, `pydrive2` |

```python
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

def upload_to_google_drive(file_path, folder_id=None):
    gauth = GoogleAuth()
    gauth.LocalWebserverAuth()  # 최초 1회 브라우저 인증

    drive = GoogleDrive(gauth)

    file = drive.CreateFile({
        'title': os.path.basename(file_path),
        'parents': [{'id': folder_id}] if folder_id else []
    })
    file.SetContentFile(file_path)
    file.Upload()

    # 공유 링크 생성
    file.InsertPermission({
        'type': 'anyone',
        'value': 'anyone',
        'role': 'reader'
    })

    return file['alternateLink']
```

---

### 2. AWS S3

| 항목 | 내용 |
|------|------|
| 무료 용량 | 5GB (12개월 프리티어) |
| 장점 | 안정적, 대용량 처리 가능, 자동화에 적합 |
| 단점 | 프리티어 이후 유료, 설정 복잡 |
| Python 라이브러리 | `boto3` |

```python
import boto3
from botocore.exceptions import NoCredentialsError

def upload_to_s3(file_path, bucket_name, object_name=None):
    s3_client = boto3.client(
        's3',
        aws_access_key_id='YOUR_ACCESS_KEY',
        aws_secret_access_key='YOUR_SECRET_KEY'
    )

    if object_name is None:
        object_name = os.path.basename(file_path)

    try:
        s3_client.upload_file(file_path, bucket_name, object_name)
        url = f"https://{bucket_name}.s3.amazonaws.com/{object_name}"
        return url
    except NoCredentialsError:
        print("AWS 자격 증명 오류")
        return None
```

---

### 3. Dropbox

| 항목 | 내용 |
|------|------|
| 무료 용량 | 2GB |
| 장점 | 간단한 API, 쉬운 공유 |
| 단점 | 무료 용량 적음 |
| Python 라이브러리 | `dropbox` |

```python
import dropbox

def upload_to_dropbox(file_path, access_token):
    dbx = dropbox.Dropbox(access_token)

    with open(file_path, 'rb') as f:
        file_name = os.path.basename(file_path)
        dbx.files_upload(f.read(), f'/{file_name}')

    # 공유 링크 생성
    shared_link = dbx.sharing_create_shared_link_with_settings(f'/{file_name}')
    return shared_link.url
```

---

## 권장 아키텍처

### 옵션 A: 로컬 실행 + 클라우드 저장 (간단)

```
[로컬 PC]
    │
    ├─ 1. YouTube API로 영상 검색
    ├─ 2. yt-dlp로 MP3 다운로드 (임시 폴더)
    ├─ 3. 클라우드에 업로드
    ├─ 4. 로컬 파일 삭제
    └─ 5. 클라우드 링크를 이메일로 전송
```

**장점**: 설정 간단, Docker 불필요
**단점**: PC가 켜져 있어야 함

---

### 옵션 B: Docker + 클라우드 서버 (자동화)

```
[클라우드 서버 (AWS EC2, GCP 등)]
    │
    └─ [Docker 컨테이너]
           │
           ├─ 1. 스케줄러(cron)로 자동 실행
           ├─ 2. YouTube API로 영상 검색
           ├─ 3. yt-dlp로 MP3 다운로드
           ├─ 4. S3/Google Drive에 업로드
           ├─ 5. 컨테이너 내 파일 삭제
           └─ 6. 이메일로 링크 전송
```

**장점**: 완전 자동화, 24시간 실행 가능
**단점**: 서버 비용 발생, 설정 복잡

---

## Docker 사용 시 구성

### Dockerfile 예시

```dockerfile
FROM python:3.11-slim

# FFmpeg 설치 (MP3 변환용)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 스케줄러로 실행하거나 직접 실행
CMD ["python", "main.py"]
```

### docker-compose.yml 예시

```yaml
version: '3.8'

services:
  youtube-downloader:
    build: .
    environment:
      - YOUTUBE_API_KEY=${YOUTUBE_API_KEY}
      - AWS_ACCESS_KEY=${AWS_ACCESS_KEY}
      - AWS_SECRET_KEY=${AWS_SECRET_KEY}
      - EMAIL_PASSWORD=${EMAIL_PASSWORD}
    volumes:
      - ./downloads:/app/downloads  # 임시 다운로드 폴더
      - ./config:/app/config        # 설정 파일
    restart: unless-stopped
```

---

## 비용 비교

| 서비스 | 무료 범위 | 초과 시 비용 |
|--------|----------|-------------|
| Google Drive | 15GB | 100GB: ₩2,400/월 |
| AWS S3 | 5GB (1년) | ~₩30/GB/월 |
| Dropbox | 2GB | 2TB: $11.99/월 |
| AWS EC2 (t2.micro) | 750시간/월 (1년) | ~₩10,000/월 |

---

## 권장 선택

| 상황 | 권장 |
|------|------|
| 테스트/개인 사용 | **옵션 A** + Google Drive |
| 자동화 필요 | **옵션 B** + Docker + S3 |
| 비용 최소화 | **옵션 A** + Google Drive (무료 15GB) |

---

## 필요한 패키지

```bash
# Google Drive
pip install pydrive2

# AWS S3
pip install boto3

# Dropbox
pip install dropbox
```
