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
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import yt_dlp

# Google Drive API
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']


def get_recommended_video(search_query: str = "podcast talk show korean") -> dict:
    """
    YouTube에서 팟캐스트/토크 영상을 검색하여 첫 번째 결과를 반환합니다.

    Args:
        search_query: 검색 키워드

    Returns:
        dict: 영상 정보 (url, title)
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'default_search': 'ytsearch5',  # 상위 5개 결과 검색
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(f"ytsearch5:{search_query}", download=False)

        if result and 'entries' in result and len(result['entries']) > 0:
            video = result['entries'][0]
            return {
                'url': f"https://www.youtube.com/watch?v={video['id']}",
                'title': video.get('title', 'Unknown Title')
            }

    raise Exception("추천 영상을 찾을 수 없습니다.")


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
    """
    Google Drive API 서비스를 가져옵니다.
    첫 실행 시 브라우저에서 인증이 필요합니다.
    """
    creds = None
    script_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(script_dir, 'token.json')
    credentials_path = os.path.join(script_dir, 'credentials.json')

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    "credentials.json 파일이 없습니다.\n"
                    "Google Cloud Console에서 OAuth 클라이언트 ID를 생성하고\n"
                    "credentials.json 파일을 다운로드해주세요."
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, 'w') as token:
            token.write(creds.to_json())

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
    msg['Subject'] = f"[YouTube 자동 다운로드] {video_title}"

    # 본문 작성 (링크 유무에 따라 다르게)
    if drive_link:
        body = f"""안녕하세요,

YouTube에서 자동 다운로드된 영상입니다.

영상 제목: {video_title}

파일이 25MB를 초과하여 Google Drive에 업로드되었습니다.
아래 링크에서 다운로드하세요:

{drive_link}

이 이메일은 자동으로 생성되었습니다.
"""
    else:
        body = f"""안녕하세요,

YouTube에서 자동 다운로드된 영상입니다.

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

    return {
        'search_query': config.get('YOUTUBE', 'search_query', fallback='korean podcast talk'),
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
    """
    print("=" * 50)
    print("YouTube 영상 다운로드 및 이메일 전송 자동화")
    print("=" * 50)

    try:
        # 설정 로드
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, 'config.ini')

        print("\n[1/4] 설정 파일 로드 중...")
        config = load_config(config_path)
        print(f"  검색 키워드: {config['search_query']}")
        print(f"  수신자: {config['recipient_email']}")

        # 1단계: YouTube 추천 영상 가져오기
        print("\n[2/4] YouTube에서 추천 영상을 검색 중...")
        video_info = get_recommended_video(config['search_query'])
        print(f"  선택된 영상: {video_info['title']}")
        print(f"  URL: {video_info['url']}")

        # 2단계: MP3 다운로드
        print("\n[3/4] MP3 파일 다운로드 중...")
        output_path = os.path.join(script_dir, config['output_path'])
        mp3_file, title = download_mp3(video_info['url'], output_path)
        print(f"  다운로드 완료: {mp3_file}")

        # 파일 크기 확인
        file_size = os.path.getsize(mp3_file) / (1024 * 1024)  # MB
        print(f"  파일 크기: {file_size:.2f} MB")

        # 3단계: 25MB 초과 시 Google Drive 업로드
        drive_link = None
        if file_size > 25:
            print(f"\n[4/5] 파일이 25MB를 초과하여 Google Drive에 업로드합니다...")
            try:
                drive_link = upload_to_drive(mp3_file)
            except FileNotFoundError as e:
                print(f"  오류: {e}")
                print("  Google Drive 업로드를 건너뛰고 로컬 파일로 저장됩니다.")
            except Exception as e:
                print(f"  Google Drive 업로드 오류: {e}")
                print("  로컬 파일로 저장됩니다.")

        # 4단계: 이메일 전송
        step = "[5/5]" if file_size > 25 else "[4/4]"
        print(f"\n{step} 이메일 전송 중...")
        email_config = {
            'sender_email': config['sender_email'],
            'sender_password': config['sender_password'],
            'smtp_server': config['smtp_server'],
            'smtp_port': config['smtp_port'],
        }

        success = send_email(
            mp3_file,
            config['recipient_email'],
            video_info['title'],
            email_config,
            drive_link
        )

        if success:
            print("\n" + "=" * 50)
            print("모든 작업이 성공적으로 완료되었습니다!")
            print("=" * 50)
        else:
            print("\n이메일 전송에 실패했습니다.")
            print(f"다운로드된 파일은 여기에 저장되어 있습니다: {mp3_file}")

    except FileNotFoundError:
        print("\n오류: config.ini 파일을 찾을 수 없습니다.")
        print("config.ini 파일을 생성하고 이메일 설정을 입력해주세요.")
    except Exception as e:
        print(f"\n오류 발생: {str(e)}")


if __name__ == "__main__":
    main()
