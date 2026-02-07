#!/usr/bin/env python3
"""
YouTube 영상 다운로드 및 이메일 전송 자동화 스크립트
- 팟캐스트/토크 영상을 YouTube에서 검색하여 MP3로 다운로드
- Naver 이메일로 MP3 파일 전송
- 25MB 초과 시 Google Drive에 업로드 후 링크 전송
"""

import os
import glob
import smtplib
import configparser
import random
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import yt_dlp

# Google Drive API
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Cloud Storage (Cloud Run 환경에서 download_history.json 영속화)
try:
    from google.cloud import storage as gcs_storage
except ImportError:
    gcs_storage = None

SCOPES = ['https://www.googleapis.com/auth/drive.file']

# 쿠키 파일 경로 (Cloud Run: /cookies/cookies.txt, 로컬: ./cookies.txt)
_cookies_candidate = os.environ.get('COOKIES_PATH', '/cookies/cookies.txt')
if os.path.exists(_cookies_candidate):
    COOKIES_PATH = _cookies_candidate
    print(f"[쿠키] 쿠키 파일 발견: {COOKIES_PATH}")
else:
    COOKIES_PATH = None
    print(f"[쿠키] 쿠키 파일 없음: {_cookies_candidate}")


def load_download_history(history_path: str) -> dict:
    """
    다운로드 기록을 로드합니다.

    Returns:
        dict: {channel: [video_id, ...], ...}
    """
    if os.path.exists(history_path):
        with open(history_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_download_history(history_path: str, history: dict):
    """다운로드 기록을 저장합니다."""
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def load_download_history_gcs(bucket_name: str, blob_name: str = 'download_history.json') -> dict:
    """Cloud Storage에서 다운로드 기록을 로드합니다."""
    client = gcs_storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    if blob.exists():
        return json.loads(blob.download_as_text())
    return {}


def save_download_history_gcs(bucket_name: str, history: dict, blob_name: str = 'download_history.json'):
    """Cloud Storage에 다운로드 기록을 저장합니다."""
    client = gcs_storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(
        json.dumps(history, ensure_ascii=False, indent=2),
        content_type='application/json'
    )


def format_duration(seconds) -> str:
    """
    초 단위 시간을 [X분 Y초] 형식으로 변환합니다.

    Args:
        seconds: 초 단위 시간

    Returns:
        str: 포맷된 시간 문자열
    """
    if seconds is None:
        return ""

    # 정수로 변환
    seconds = int(seconds)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"[{hours}시간 {minutes}분 {secs}초]"
    elif minutes > 0:
        return f"[{minutes}분 {secs}초]"
    else:
        return f"[{secs}초]"


def is_video_accessible(video_url: str) -> bool:
    """
    영상이 다운로드 가능한지 확인합니다. (멤버십 전용 등 제외)

    Args:
        video_url: YouTube 영상 URL

    Returns:
        bool: 다운로드 가능 여부
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    if COOKIES_PATH:
        ydl_opts['cookiefile'] = COOKIES_PATH

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(video_url, download=False)
        return True
    except Exception as e:
        error_msg = str(e).lower()
        # 멤버십 전용, 비공개, 연령 제한 등 확인
        if any(keyword in error_msg for keyword in ['member', 'private', 'unavailable', 'age', 'sign in']):
            return False
        return False


def get_random_video_from_channel(channel: str, downloaded_ids: list = None, max_attempts: int = 10) -> dict:
    """
    특정 채널에서 랜덤으로 영상 하나를 선택하여 반환합니다.
    멤버십 전용 영상과 이미 다운로드한 영상은 제외합니다.

    Args:
        channel: 채널명 (@로 시작) 또는 채널 ID
        downloaded_ids: 이미 다운로드한 영상 ID 목록
        max_attempts: 최대 시도 횟수

    Returns:
        dict: 영상 정보 (url, title, channel, duration, video_id)
    """
    if downloaded_ids is None:
        downloaded_ids = []

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'playlistend': 50,  # 더 많은 영상을 가져와서 선택 폭을 넓힘
    }
    if COOKIES_PATH:
        ydl_opts['cookiefile'] = COOKIES_PATH

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # 채널 URL 구성
        if channel.startswith('@'):
            channel_url = f"https://www.youtube.com/{channel}/videos"
        else:
            channel_url = f"https://www.youtube.com/channel/{channel}/videos"

        result = ydl.extract_info(channel_url, download=False)

        if result and 'entries' in result:
            # None이 아닌 유효한 영상만 필터링
            valid_videos = [v for v in result['entries'] if v is not None]

            # 이미 다운로드한 영상 제외
            new_videos = [v for v in valid_videos if v['id'] not in downloaded_ids]

            if not new_videos:
                print(f"    (모든 영상을 이미 다운로드함, 기록 초기화)")
                new_videos = valid_videos

            if new_videos:
                # 영상 목록을 셔플하여 랜덤 순서로 시도
                random.shuffle(new_videos)

                for attempt, video in enumerate(new_videos[:max_attempts]):
                    video_id = video['id']
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    title = video.get('title', 'Unknown')

                    # 영상 접근 가능 여부 확인
                    if not is_video_accessible(video_url):
                        print(f"    (멤버십/비공개 영상 건너뜀: {title[:30]}...)")
                        continue

                    # 영상 길이 가져오기
                    duration = video.get('duration')
                    duration_str = format_duration(duration)

                    return {
                        'url': video_url,
                        'title': title,
                        'channel': channel,
                        'duration': duration_str,
                        'video_id': video_id
                    }

    raise Exception(f"채널 '{channel}'에서 다운로드 가능한 영상을 찾을 수 없습니다.")


def get_videos_from_all_channels(channels: list, history: dict) -> list:
    """
    모든 채널에서 각각 랜덤으로 영상 하나씩을 가져옵니다.
    이미 다운로드한 영상은 제외합니다.

    Args:
        channels: 채널 목록
        history: 다운로드 기록 {channel: [video_id, ...], ...}

    Returns:
        list: 영상 정보 목록 [{url, title, channel, video_id}, ...]
    """
    if not channels:
        raise Exception("채널 목록이 비어있습니다. config.ini에 채널을 추가해주세요.")

    videos = []
    for channel in channels:
        try:
            print(f"  채널 '{channel}'에서 영상 선택 중...")
            downloaded_ids = history.get(channel, [])
            video = get_random_video_from_channel(channel, downloaded_ids)
            videos.append(video)
            duration_info = f" {video['duration']}" if video.get('duration') else ""
            print(f"    → {video['title']}{duration_info}")
        except Exception as e:
            print(f"    → 오류: {e}")

    if not videos:
        raise Exception("어떤 채널에서도 영상을 가져오지 못했습니다.")

    return videos


def download_mp3(youtube_url: str, output_path: str) -> tuple:
    """
    YouTube 영상을 MP3로 다운로드합니다.

    Args:
        youtube_url: YouTube 영상 URL
        output_path: 저장할 디렉토리 경로

    Returns:
        tuple: (파일 경로, 영상 제목)
    """
    os.makedirs(output_path, exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'quiet': False,
        'no_warnings': False,
    }
    if COOKIES_PATH:
        ydl_opts['cookiefile'] = COOKIES_PATH

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        title = info.get('title', 'Unknown')

        # 다운로드된 MP3 파일 찾기
        mp3_files = glob.glob(f"{output_path}/*.mp3")
        if mp3_files:
            # 가장 최근 파일 반환
            latest_file = max(mp3_files, key=os.path.getctime)
            return latest_file, title

    raise Exception("MP3 파일 다운로드에 실패했습니다.")


def get_drive_service():
    """Google Drive API 서비스를 가져옵니다. (ADC 사용)"""
    creds, _ = google.auth.default(scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)


def upload_to_drive(file_path: str) -> str:
    """
    파일을 Google Drive에 업로드하고 공유 링크를 반환합니다.

    Args:
        file_path: 업로드할 파일 경로

    Returns:
        str: 공유 링크 URL
    """
    service = get_drive_service()
    filename = os.path.basename(file_path)

    file_metadata = {'name': filename}
    media = MediaFileUpload(file_path, mimetype='audio/mpeg', resumable=True)

    print(f"  Google Drive에 업로드 중: {filename}")
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    file_id = file.get('id')

    # 링크가 있는 사람은 누구나 볼 수 있도록 권한 설정
    service.permissions().create(
        fileId=file_id,
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()

    share_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
    print(f"  업로드 완료! 링크: {share_link}")

    return share_link


def send_email(file_path: str, recipient_email: str, video_title: str, config: dict, drive_link: str = None) -> bool:
    """
    MP3 파일을 이메일로 전송합니다.
    drive_link가 있으면 파일 첨부 대신 링크를 본문에 포함합니다.

    Args:
        file_path: MP3 파일 경로
        recipient_email: 수신자 이메일
        video_title: 영상 제목
        config: 이메일 설정 정보
        drive_link: Google Drive 공유 링크 (25MB 초과 시)

    Returns:
        bool: 전송 성공 여부
    """
    sender_email = config['sender_email']
    sender_password = config['sender_password']
    smtp_server = config['smtp_server']
    smtp_port = int(config['smtp_port'])

    # 이메일 메시지 생성
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = f"[mp3 영상]{video_title}"

    # 본문 작성 (링크 유무에 따라 다르게)
    if drive_link:
        body = f"""안녕하세요,

영상 제목: {video_title}

파일이 25MB를 초과하여 Google Drive에 업로드되었습니다.
아래 링크에서 다운로드하세요:

{drive_link}

이 이메일은 자동으로 생성되었습니다.
"""
    else:
        body = f"""안녕하세요,

영상 제목: {video_title}

이 이메일은 자동으로 생성되었습니다.
"""
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    # 파일 첨부 (drive_link가 없을 때만)
    if not drive_link:
        try:
            with open(file_path, 'rb') as attachment:
                part = MIMEBase('audio', 'mpeg')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)

                # 영문 파일명 사용 (호환성)
                safe_filename = 'youtube_podcast.mp3'
                part.add_header(
                    'Content-Disposition',
                    'attachment',
                    filename=safe_filename
                )
                msg.attach(part)
        except Exception as e:
            print(f"파일 첨부 오류: {e}")
            return False

    # 이메일 전송
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        print("이메일 전송 성공!")
        return True
    except Exception as e:
        print(f"이메일 전송 오류: {e}")
        return False


def load_config(config_path: str = "config.ini") -> dict:
    """
    설정 파일을 로드합니다.

    Args:
        config_path: 설정 파일 경로

    Returns:
        dict: 설정 정보
    """
    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')

    # 채널 목록 파싱 (쉼표로 구분)
    channels_str = config.get('YOUTUBE', 'channels', fallback='')
    channels = [ch.strip() for ch in channels_str.split(',') if ch.strip()]

    return {
        'channels': channels,
        'sender_email': config.get('EMAIL', 'sender_email'),
        'sender_password': config.get('EMAIL', 'sender_password'),
        'smtp_server': config.get('EMAIL', 'smtp_server'),
        'smtp_port': config.get('EMAIL', 'smtp_port'),
        'recipient_email': config.get('EMAIL', 'recipient_email'),
        'output_path': config.get('DOWNLOAD', 'output_path', fallback='./downloads'),
    }


def main():
    """
    전체 프로세스를 실행합니다.
    각 채널에서 랜덤으로 영상 1개씩 다운로드하여 이메일로 전송합니다.
    """
    print("=" * 50)
    print("YouTube 영상 다운로드 및 이메일 전송 자동화")
    print("=" * 50)

    try:
        # 설정 로드
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.environ.get('CONFIG_PATH', os.path.join(script_dir, 'config.ini'))
        history_path = os.path.join(script_dir, 'download_history.json')
        gcs_bucket = os.environ.get('GCS_BUCKET')

        print("\n[1단계] 설정 파일 로드 중...")
        config = load_config(config_path)
        if gcs_bucket and gcs_storage:
            print(f"  Cloud Storage 모드: gs://{gcs_bucket}")
            history = load_download_history_gcs(gcs_bucket)
        else:
            history = load_download_history(history_path)
        num_channels = len(config['channels'])
        print(f"  등록된 채널: {num_channels}개")
        for ch in config['channels']:
            downloaded_count = len(history.get(ch, []))
            print(f"    - {ch} (기록: {downloaded_count}개)")
        print(f"  수신자: {config['recipient_email']}")

        # 2단계: 각 채널에서 영상 선택
        print(f"\n[2단계] 각 채널에서 영상 선택 중...")
        videos = get_videos_from_all_channels(config['channels'], history)
        print(f"\n  총 {len(videos)}개 영상 선택됨")

        # 이메일 설정
        email_config = {
            'sender_email': config['sender_email'],
            'sender_password': config['sender_password'],
            'smtp_server': config['smtp_server'],
            'smtp_port': config['smtp_port'],
        }
        output_path = os.path.join(script_dir, config['output_path'])

        # 3단계: 각 영상별로 다운로드 및 이메일 전송
        success_count = 0
        for i, video_info in enumerate(videos, 1):
            duration_info = f" {video_info['duration']}" if video_info.get('duration') else ""
            print(f"\n{'='*50}")
            print(f"[{i}/{len(videos)}] {video_info['channel']}")
            print(f"{'='*50}")
            print(f"  영상: {video_info['title']}{duration_info}")
            print(f"  URL: {video_info['url']}")

            try:
                # MP3 다운로드
                print(f"\n  다운로드 중...")
                mp3_file, title = download_mp3(video_info['url'], output_path)
                print(f"  다운로드 완료: {mp3_file}")

                # 파일 크기 확인
                file_size = os.path.getsize(mp3_file) / (1024 * 1024)  # MB
                print(f"  파일 크기: {file_size:.2f} MB")

                # 25MB 초과 시 Google Drive 업로드
                drive_link = None
                if file_size > 25:
                    print(f"  파일이 25MB를 초과하여 Google Drive에 업로드합니다...")
                    try:
                        drive_link = upload_to_drive(mp3_file)
                    except FileNotFoundError as e:
                        print(f"  오류: {e}")
                        print("  Google Drive 업로드를 건너뛰고 로컬 파일로 저장됩니다.")
                    except Exception as e:
                        print(f"  Google Drive 업로드 오류: {e}")
                        print("  로컬 파일로 저장됩니다.")

                # 이메일 전송
                print(f"  이메일 전송 중...")
                email_title = f"[{video_info['channel']}] {video_info['title']}{duration_info}"
                success = send_email(
                    mp3_file,
                    config['recipient_email'],
                    email_title,
                    email_config,
                    drive_link
                )

                if success:
                    success_count += 1
                    # 다운로드 기록에 추가
                    channel = video_info['channel']
                    video_id = video_info.get('video_id')
                    if video_id:
                        if channel not in history:
                            history[channel] = []
                        if video_id not in history[channel]:
                            history[channel].append(video_id)
                        if gcs_bucket and gcs_storage:
                            save_download_history_gcs(gcs_bucket, history)
                        else:
                            save_download_history(history_path, history)
                    print(f"  ✓ 완료!")
                else:
                    print(f"  ✗ 이메일 전송 실패")
                    print(f"  다운로드된 파일: {mp3_file}")

            except Exception as e:
                print(f"  ✗ 오류 발생: {str(e)}")

        # 최종 결과
        print("\n" + "=" * 50)
        print(f"작업 완료: {success_count}/{len(videos)}개 성공")
        print("=" * 50)

    except FileNotFoundError:
        print("\n오류: config.ini 파일을 찾을 수 없습니다.")
        print("config.ini 파일을 생성하고 이메일 설정을 입력해주세요.")
    except Exception as e:
        print(f"\n오류 발생: {str(e)}")


if __name__ == "__main__":
    main()
