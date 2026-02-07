# Google Cloud Run Jobs 배포 가이드

매일 오전 7시 (한국시간)에 YouTube 다운로드 스크립트를 자동 실행합니다.

## 1. 사전 준비

### Google Cloud CLI 설치
```bash
# macOS
brew install google-cloud-sdk

# 로그인
gcloud auth login
```

### 프로젝트 설정
```bash
# 새 프로젝트 생성 또는 기존 프로젝트 사용
gcloud projects create youtube-download-auto --name="YouTube Download Auto"

# 프로젝트 선택
gcloud config set project youtube-download-auto

# 결제 계정 연결 (Cloud Console에서 수동으로 해야 함)
# https://console.cloud.google.com/billing
```

## 2. API 활성화

```bash
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com
```

## 3. Artifact Registry 저장소 생성

```bash
gcloud artifacts repositories create youtube-download \
  --repository-format=docker \
  --location=asia-northeast3 \
  --description="YouTube Download Docker Images"
```

## 4. Docker 이미지 빌드 및 푸시

```bash
cd /Users/jaewook/Desktop/놀이터/youtube_down

# Docker 인증 설정
gcloud auth configure-docker asia-northeast3-docker.pkg.dev

# 이미지 빌드 및 푸시
gcloud builds submit --tag asia-northeast3-docker.pkg.dev/youtube-download-auto/youtube-download/youtube-downloader:latest
```

## 5. Cloud Run Jobs 생성

```bash
gcloud run jobs create youtube-download-job \
  --image asia-northeast3-docker.pkg.dev/youtube-download-auto/youtube-download/youtube-downloader:latest \
  --region asia-northeast3 \
  --memory 1Gi \
  --cpu 1 \
  --max-retries 1 \
  --task-timeout 30m
```

## 6. Cloud Scheduler 설정 (매일 오전 7시 KST)

```bash
# 서비스 계정 권한 부여
gcloud projects add-iam-policy-binding youtube-download-auto \
  --member="serviceAccount:$(gcloud projects describe youtube-download-auto --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
  --role="roles/run.invoker"

# 스케줄러 생성 (매일 오전 7시 한국시간)
gcloud scheduler jobs create http youtube-download-scheduler \
  --location asia-northeast3 \
  --schedule "0 7 * * *" \
  --time-zone "Asia/Seoul" \
  --uri "https://asia-northeast3-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/youtube-download-auto/jobs/youtube-download-job:run" \
  --http-method POST \
  --oauth-service-account-email "$(gcloud projects describe youtube-download-auto --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
```

## 7. 수동 테스트

```bash
# Job 수동 실행
gcloud run jobs execute youtube-download-job --region asia-northeast3

# 로그 확인
gcloud run jobs executions logs youtube-download-job --region asia-northeast3
```

## 8. 환경 변수로 민감 정보 관리 (권장)

config.ini의 이메일 비밀번호 등을 환경 변수로 관리하려면:

```bash
# Secret Manager 사용
gcloud secrets create email-password --data-file=-
# (비밀번호 입력 후 Ctrl+D)

# Job 업데이트
gcloud run jobs update youtube-download-job \
  --region asia-northeast3 \
  --set-secrets EMAIL_PASSWORD=email-password:latest
```

## 비용 예상

- **Cloud Run Jobs**: 실행 시간당 과금 (월 240,000 vCPU-초 무료)
- **Cloud Scheduler**: 월 3개 작업 무료
- **Artifact Registry**: 0.5GB까지 무료

**예상 월 비용**: 무료 티어 내 (하루 1번, 약 5분 실행 기준)

## 문제 해결

### 로그 확인
```bash
gcloud run jobs executions list --job youtube-download-job --region asia-northeast3
gcloud logging read "resource.type=cloud_run_job" --limit 50
```

### Job 삭제
```bash
gcloud scheduler jobs delete youtube-download-scheduler --location asia-northeast3
gcloud run jobs delete youtube-download-job --region asia-northeast3
```
