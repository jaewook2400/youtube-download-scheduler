기능: 유튜브에 접속해서 특정 기준에 따라 검색된 영상을 mp3 파일로 다운로드하고, 특정 이메일로 전송해줌.

CI/CD 파이프라인: 
1. 로컬 -> Github 로 push
2. Github 업데이트 -> Gcloud 자동 배포
3. Gcloud에선 매일 특정 시간 스케줄러로 자동 실행


적용 과정:

1. YouTube 자동 다운로드 프로젝트를 Google Cloud에 배포하기로 함
2. Dockerfile 수정: 민감 파일(config.ini 등) COPY 제거, Secret Manager로 전환
3. cloudbuild.yaml 생성: GitHub push → Docker 빌드 → Artifact Registry 푸시 → Cloud Run Job 업데이트 파이프라인
4. download_history.json을 Cloud Storage(GCS)에 저장하도록 코드 수정 (컨테이너는 매번 초기화되니까)
5. Google Drive 인증을 OAuth(credentials.json/token.json) → ADC(Application Default Credentials)로 전환
6. Secret Manager에 config.ini 등록 → Cloud Run Job에 볼륨 마운트 설정
7. Cloud Build 트리거 생성 (GitHub main 브랜치 push 시 자동 빌드)
8. Artifact Registry youtube-download 저장소 생성
9. 현재: 트리거 재실행 후 빌드 성공 대기 중 → 성공하면 Cloud Run Job 실행 테스트 예정
10. 아직 남은 것: Cloud Scheduler (매일 오전 7시 KST), GCS 버킷 생성
