# Google Cloud 배포 가이드 (Cloud Build CI/CD)

GitHub push → Cloud Build 자동 빌드 → Cloud Run Job 배포 → Cloud Scheduler 매일 오전 7시 실행

## 아키텍처

```
GitHub (push) → Cloud Build → Artifact Registry → Cloud Run Job
                                                        ↑
                                          Secret Manager (config.ini, credentials.json, token.json)
                                          Cloud Storage  (download_history.json)
                                          Cloud Scheduler (매일 07:00 KST)
```

## 1. 사전 준비

### GCP 프로젝트 설정

Google Cloud Console(https://console.cloud.google.com)에서:

1. 프로젝트 생성 또는 선택
2. 결제 계정 연결

프로젝트 ID를 아래 명령어에서 `YOUR_PROJECT_ID`로 대체하세요.

### API 활성화

Cloud Console > API 및 서비스 > 라이브러리에서 다음 API를 활성화:

- Cloud Build API
- Cloud Run Admin API
- Cloud Scheduler API
- Artifact Registry API
- Secret Manager API
- Cloud Storage API

또는 Cloud Shell에서:
```bash
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com
```

## 2. Artifact Registry 저장소 생성

```bash
gcloud artifacts repositories create youtube-download \
  --repository-format=docker \
  --location=asia-northeast3 \
  --description="YouTube Download Docker Images"
```

## 3. Secret Manager에 민감 파일 등록

로컬의 민감 파일 3개를 Secret Manager에 저장합니다.

```bash
# config.ini
gcloud secrets create config-ini \
  --data-file=config.ini

# credentials.json (Google Drive OAuth 클라이언트)
gcloud secrets create credentials-json \
  --data-file=credentials.json

# token.json (Google Drive OAuth 토큰)
gcloud secrets create token-json \
  --data-file=token.json
```

## 4. Cloud Storage 버킷 생성 (다운로드 기록 저장용)

```bash
gsutil mb -l asia-northeast3 gs://YOUR_PROJECT_ID-youtube-history
```

## 5. Cloud Run Job 생성

초기 생성 시에는 먼저 수동으로 이미지를 한 번 빌드해야 합니다.

```bash
# 첫 이미지 빌드 (Cloud Build로)
gcloud builds submit \
  --tag asia-northeast3-docker.pkg.dev/YOUR_PROJECT_ID/youtube-download/youtube-downloader:latest

# Cloud Run Job 생성
gcloud run jobs create youtube-download-job \
  --image asia-northeast3-docker.pkg.dev/YOUR_PROJECT_ID/youtube-download/youtube-downloader:latest \
  --region asia-northeast3 \
  --memory 1Gi \
  --cpu 1 \
  --max-retries 1 \
  --task-timeout 30m \
  --set-secrets "/app/config.ini=config-ini:latest,/app/credentials.json=credentials-json:latest,/app/token.json=token-json:latest" \
  --set-env-vars "GCS_BUCKET=YOUR_PROJECT_ID-youtube-history"
```

## 6. IAM 권한 설정

Cloud Build 서비스 계정에 Cloud Run 배포 권한을 부여합니다.

```bash
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format='value(projectNumber)')

# Cloud Build → Cloud Run 배포 권한
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/run.developer"

# Cloud Build → Service Account 사용 권한
gcloud iam service-accounts add-iam-policy-binding \
  ${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Cloud Run Job → Secret Manager 접근 권한
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Cloud Run Job → Cloud Storage 접근 권한
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```

## 7. Cloud Build 트리거 설정 (GitHub 연동)

Cloud Console에서 설정하는 것이 가장 편리합니다:

1. **Cloud Build > 트리거** 페이지로 이동
2. **저장소 연결**: GitHub 앱을 설치하고 `jaewook2400/youtube-download-scheduler` 저장소 연결
3. **트리거 만들기**:
   - 이름: `deploy-on-push`
   - 이벤트: 브랜치에 푸시
   - 브랜치: `^main$`
   - 유형: Cloud Build 구성 파일
   - 경로: `cloudbuild.yaml`

## 8. Cloud Scheduler 설정 (매일 오전 7시 KST)

```bash
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format='value(projectNumber)')

# Compute Engine 기본 서비스 계정에 Cloud Run 호출 권한 부여
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/run.invoker"

# 스케줄러 생성
gcloud scheduler jobs create http youtube-download-scheduler \
  --location asia-northeast3 \
  --schedule "0 7 * * *" \
  --time-zone "Asia/Seoul" \
  --uri "https://asia-northeast3-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/YOUR_PROJECT_ID/jobs/youtube-download-job:run" \
  --http-method POST \
  --oauth-service-account-email "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
```

## 9. 테스트

### 수동 실행
```bash
gcloud run jobs execute youtube-download-job --region asia-northeast3
```

### 로그 확인
```bash
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=youtube-download-job" \
  --limit 50 --format="table(timestamp, textPayload)"
```

### CI/CD 테스트
코드를 수정하고 GitHub에 push하면 Cloud Build가 자동으로 빌드 및 배포합니다.

## 운영

### Secret 업데이트 (비밀번호 변경 등)
```bash
gcloud secrets versions add config-ini --data-file=config.ini
```

### 로그 모니터링
```bash
gcloud logging read "resource.type=cloud_run_job" --limit 20
```

### 리소스 삭제
```bash
gcloud scheduler jobs delete youtube-download-scheduler --location asia-northeast3
gcloud run jobs delete youtube-download-job --region asia-northeast3
gcloud artifacts repositories delete youtube-download --location asia-northeast3
```

## 비용 예상

- **Cloud Run Jobs**: 실행 시간당 과금 (월 240,000 vCPU-초 무료)
- **Cloud Scheduler**: 월 3개 작업 무료
- **Cloud Build**: 월 120분 빌드 무료
- **Artifact Registry**: 0.5GB까지 무료
- **Secret Manager**: 월 6개 활성 버전 무료
- **Cloud Storage**: 5GB 무료

**예상 월 비용**: 무료 티어 내 (하루 1번, 약 5분 실행 기준)
