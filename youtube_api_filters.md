# YouTube Data API v3 검색 필터 옵션

YouTube API는 다양한 필터링 옵션을 제공합니다.

## 검색 엔드포인트

```
GET https://www.googleapis.com/youtube/v3/search
```

## 주요 필터 파라미터

### 날짜/시간 필터

| 파라미터 | 설명 | 예시 |
|---------|------|------|
| `publishedAfter` | 특정 날짜 이후 영상 | `2024-01-01T00:00:00Z` |
| `publishedBefore` | 특정 날짜 이전 영상 | `2025-01-01T00:00:00Z` |

### 영상 특성 필터

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| `videoDuration` | `short` | 4분 미만 |
| | `medium` | 4~20분 |
| | `long` | 20분 초과 |
| `videoDefinition` | `high` | HD 영상만 |
| | `standard` | SD 영상만 |
| `type` | `video` | 영상만 (채널, 플레이리스트 제외) |
| `order` | `date`, `rating`, `viewCount`, `relevance` | 정렬 기준 |

### 콘텐츠 필터

| 파라미터 | 설명 |
|---------|------|
| `videoCategoryId` | 카테고리 (10=음악, 24=엔터테인먼트 등) |
| `regionCode` | 국가 코드 (`KR`, `US` 등) |
| `relevanceLanguage` | 언어 우선순위 (`ko`, `en` 등) |
| `safeSearch` | `none`, `moderate`, `strict` |

---

## 예시: 1년 이내 음악 영상 검색

```python
from datetime import datetime, timedelta
from googleapiclient.discovery import build

def search_recent_videos(api_key, query, days=365):
    youtube = build('youtube', 'v3', developerKey=api_key)

    # 1년 전 날짜 계산
    after_date = (datetime.now() - timedelta(days=days)).isoformat() + 'Z'

    request = youtube.search().list(
        part='snippet',
        q=query,
        type='video',
        publishedAfter=after_date,      # 1년 이내
        videoDuration='medium',          # 4~20분
        videoCategoryId='10',            # 음악 카테고리
        regionCode='KR',                 # 한국
        order='viewCount',               # 조회수 순
        maxResults=10
    )

    response = request.execute()
    return response['items']
```

---

## 음악 카테고리 ID 참고

| ID | 카테고리 |
|----|---------|
| 10 | 음악 |
| 24 | 엔터테인먼트 |
| 22 | 인물/블로그 |
| 23 | 코미디 |
| 25 | 뉴스/정치 |
| 27 | 교육 |

---

## 제한사항

- **할당량**: 검색 1회 = 100 units (일 10,000 units 무료)
- **maxResults**: 최대 50개
- **조합 불가**: 일부 필터는 `type=video`일 때만 작동
