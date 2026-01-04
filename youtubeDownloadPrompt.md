# YouTube 영상 다운로드 및 이메일 전송 자동화 스크립트

## 목적
YouTube에서 추천 영상을 받아 MP3로 다운로드하고 이메일로 전송하는 전체 프로세스를 자동화합니다.

## 요구사항

### 1단계: YouTube 영상 추천 및 링크 가져오기
- YouTube에서 사용자 취향에 맞는 영상을 추천받아 링크를 추출합니다
- 사용자의 관심사/선호 카테고리를 고려하여 영상을 선택합니다
- 영상 URL을 변수에 저장합니다

### 2단계: MP3 다운로드
- 웹사이트: https://notube.net/en/youtube-app-297
- 1단계에서 가져온 YouTube 링크를 사용하여 MP3 파일로 다운로드합니다
- 다운로드 경로: 로컬 노트북 (기본 다운로드 폴더 또는 지정된 경로)

### 3단계: 이메일 전송
- 다운로드된 MP3 파일을 a2527178@naver.com으로 전송합니다
- 이메일 제목과 본문에 영상 제목 정보를 포함합니다

## 구현 방식

다음 기술/라이브러리를 사용하여 Python 스크립트를 작성해주세요:

### 필요한 라이브러리
- `selenium` 또는 `playwright`: 웹 브라우저 자동화
- `requests`: HTTP 요청 (필요시)
- `google-api-python-client`: YouTube API 연동 (추천 영상 가져오기)
- `smtplib` 및 `email`: 이메일 전송
- `time`: 대기 시간 처리

### 주요 기능

#### 1. YouTube 추천 영상 가져오기
```python
def get_recommended_video():
    """
    YouTube에서 추천 영상을 가져옵니다.

    옵션:
    - YouTube API를 사용하여 트렌딩/추천 영상 가져오기
    - 사용자의 선호 카테고리 기반 검색
    - 특정 키워드로 검색 후 상위 결과 선택

    Returns:
        str: YouTube 영상 URL
    """
    pass
```

#### 2. MP3 다운로드
```python
def download_mp3(youtube_url, output_path):
    """
    notube.net을 통해 YouTube 영상을 MP3로 다운로드합니다.

    Args:
        youtube_url (str): YouTube 영상 URL
        output_path (str): MP3 파일을 저장할 경로

    프로세스:
    1. https://notube.net/en/youtube-app-297 페이지 열기
    2. URL 입력 필드에 youtube_url 입력
    3. 다운로드 버튼 클릭
    4. MP3 변환 대기
    5. 다운로드 링크 클릭하여 파일 저장

    Returns:
        str: 다운로드된 파일의 전체 경로
    """
    pass
```

#### 3. 이메일 전송
```python
def send_email(file_path, recipient_email, video_title):
    """
    다운로드된 MP3 파일을 이메일로 전송합니다.

    Args:
        file_path (str): 전송할 MP3 파일 경로
        recipient_email (str): 수신자 이메일 (a2527178@naver.com)
        video_title (str): 영상 제목

    설정 필요:
    - SMTP 서버 설정 (Gmail, Naver 등)
    - 발신자 이메일 및 앱 비밀번호

    Returns:
        bool: 전송 성공 여부
    """
    pass
```

#### 4. 메인 실행 함수
```python
def main():
    """
    전체 프로세스를 실행합니다.
    """
    try:
        # 1단계: YouTube 추천 영상 가져오기
        print("YouTube에서 추천 영상을 가져오는 중...")
        video_url = get_recommended_video()
        print(f"선택된 영상: {video_url}")

        # 2단계: MP3 다운로드
        print("MP3 파일 다운로드 중...")
        output_path = "./downloads/"
        mp3_file = download_mp3(video_url, output_path)
        print(f"다운로드 완료: {mp3_file}")

        # 3단계: 이메일 전송
        print("이메일 전송 중...")
        success = send_email(mp3_file, "a2527178@naver.com", "YouTube 추천 영상")

        if success:
            print("모든 작업이 성공적으로 완료되었습니다!")
        else:
            print("이메일 전송에 실패했습니다.")

    except Exception as e:
        print(f"오류 발생: {str(e)}")
```

## 구현 시 고려사항

### 보안
- 이메일 인증 정보는 환경 변수 또는 별도 설정 파일에 저장
- API 키는 코드에 직접 포함하지 말 것

### 에러 처리
- 네트워크 연결 실패 처리
- 다운로드 실패 시 재시도 로직
- 웹 요소 로딩 대기 시간 충분히 확보

### 웹 스크래핑 주의사항
- notube.net의 이용 약관 확인
- 과도한 요청으로 인한 IP 차단 방지
- 웹 페이지 구조 변경에 대비한 유연한 선택자 사용

### 대안 방법
만약 notube.net 자동화가 어려운 경우:
- `yt-dlp` 라이브러리를 사용하여 직접 다운로드
  ```bash
  pip install yt-dlp
  ```
  ```python
  import yt_dlp

  def download_mp3_with_ytdlp(youtube_url, output_path):
      ydl_opts = {
          'format': 'bestaudio/best',
          'postprocessors': [{
              'key': 'FFmpegExtractAudio',
              'preferredcodec': 'mp3',
              'preferredquality': '192',
          }],
          'outtmpl': f'{output_path}/%(title)s.%(ext)s',
      }

      with yt_dlp.YoutubeDL(ydl_opts) as ydl:
          info = ydl.extract_info(youtube_url, download=True)
          return f"{output_path}/{info['title']}.mp3"
  ```

## 실행 방법

```bash
# 필요한 패키지 설치
pip install selenium webdriver-manager google-api-python-client yt-dlp

# 스크립트 실행
python youtube_auto_download.py
```

## 환경 설정 파일 예시 (config.ini)

```ini
[YOUTUBE]
API_KEY = your_youtube_api_key_here
PREFERRED_CATEGORY = music

[EMAIL]
SMTP_SERVER = smtp.gmail.com
SMTP_PORT = 587
SENDER_EMAIL = your_email@gmail.com
SENDER_PASSWORD = your_app_password_here
RECIPIENT_EMAIL = a2527178@naver.com

[DOWNLOAD]
OUTPUT_PATH = ./downloads/
```

## 추가 기능 제안

1. **스케줄링**: 매일 특정 시간에 자동 실행
2. **로깅**: 실행 내역 및 오류 기록
3. **중복 확인**: 이미 다운로드한 영상 재다운로드 방지
4. **플레이리스트 지원**: 여러 영상 일괄 처리
5. **알림**: 작업 완료 시 알림 전송

---

**참고**: 이 스크립트는 개인적인 용도로만 사용하시고, YouTube 및 notube.net의 이용 약관을 준수해 주세요.
