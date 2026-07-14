"""예스24 IT/모바일 베스트셀러 도서 상세 정보 수집 모듈.

이 모듈은 기존에 수집된 베스트셀러 CSV 파일을 로드하여, 각 도서의 상세 페이지 링크를 방문해
책 소개(내용)와 도서 표지 이미지 URL을 크롤링한 후 기존 데이터셋에 반영하여 저장하는 기능을 제공합니다.
Windows 환경의 인코딩 오류를 방지하고 속도 향상을 위해 멀티스레딩을 활용합니다.
"""

import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import pandas as pd
import requests
from bs4 import BeautifulSoup

# Windows 콘솔 출력의 인코딩 에러 방지 (utf-8 설정)
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # reconfigure가 작동하지 않는 예외 상황 대응
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 입출력 파일 경로 정의
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
INPUT_FILE = os.path.join(DATA_DIR, "yes24_it_mobile_bestsellers.csv")

# HTTP 요청 헤더 정의 (실제 브라우저 요청처럼 모방)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.yes24.com/",
    "Connection": "keep-alive"
}

# 멀티스레딩 공유 데이터 및 Lock 정의
csv_lock = threading.Lock()


def scrape_book_details(url: str) -> tuple[str, str]:
    """도서의 상세 페이지 URL에서 책 소개와 이미지 URL을 수집합니다.

    Args:
        url (str): 도서 상세 페이지 URL

    Returns:
        tuple[str, str]: (책 소개(내용), 이미지 URL)
    """
    if not url or pd.isna(url):
        return "", ""

    try:
        # 예스24 서버 부하 방지를 위해 요청 전 스레드별 랜덤 대기 (0.3 ~ 0.8초)
        time.sleep(random.uniform(0.3, 0.8))
        
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            return "", ""

        soup = BeautifulSoup(response.text, "lxml")

        # 1. 이미지 URL 추출 (meta property="og:image" 에서 수집하는 것이 가장 정확함)
        img_url = ""
        og_image = soup.find("meta", property="og:image")
        if og_image:
            img_url = og_image.get("content", "").strip()

        # 2. 책 소개(내용) 추출
        description = ""

        # 상세정보 탭 내의 텍스트 영역 탐색 (일반적인 YES24 책소개 영역 셀렉터)
        detail_wrap = soup.select_one("#infosDetail .infoWrap_txt")
        if detail_wrap:
            description = detail_wrap.get_text(separator="\n", strip=True)

        # 상세정보 영역이 비어있거나 없는 경우, 메타 태그의 description 요약을 대체 사용
        if not description:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                description = meta_desc.get("content", "").strip()

        # 텍스트 내 불필요한 공백 및 '정보 더 보기/감추기' 같은 UI 텍스트 제거 정제
        description = re.sub(r"\n+", "\n", description)
        description = description.replace("정보 더 보기/감추기", "").strip()

        return description, img_url

    except Exception:
        # 개별 요청 오류 시 빈 값 반환하여 전체 프로세스 중단 방지
        return "", ""


def process_row(idx, row, total_books):
    """개별 행을 처리하는 스레드 타겟 함수."""
    title = row.get("도서명", row.get("제목", "알 수 없음"))
    url = row.get("링크", "")

    # 이미 데이터가 채워져 있는 경우 스킵
    if pd.notna(row.get("내용")) and str(row.get("내용")).strip() != "" and pd.notna(row.get("이미지")) and str(row.get("이미지")).strip() != "":
        return idx, None, None

    # 콘솔 인코딩 에러 방지를 위해 에러가 나지 않는 방식으로 제목 출력
    safe_title = title.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
    print(f"[{idx + 1}/{total_books}] '{safe_title}' 수집 중...")
    
    desc, img = scrape_book_details(url)
    return idx, desc, img


def main():
    """메인 실행 함수.

    CSV 데이터를 읽어 상세정보 컬럼을 확보하고 크롤링을 진행한 후 파일로 다시 저장합니다.
    """
    if not os.path.exists(INPUT_FILE):
        print(f"[ERROR] 원본 데이터 파일이 존재하지 않습니다: {INPUT_FILE}")
        return

    print(f"[INFO] 원본 데이터를 불러옵니다: {INPUT_FILE}")
    df = pd.read_csv(INPUT_FILE)

    # 신규 컬럼 정의 (기존에 있으면 유지)
    if "내용" not in df.columns:
        df["내용"] = ""
    if "이미지" not in df.columns:
        df["이미지"] = ""

    # 수집 대상 필터링 (내용과 이미지가 비어있는 것만 수집하도록 최적화)
    to_scrape_indices = df[
        df["내용"].isna() | (df["내용"].astype(str).str.strip() == "") |
        df["이미지"].isna() | (df["이미지"].astype(str).str.strip() == "")
    ].index.tolist()

    total_to_scrape = len(to_scrape_indices)
    total_books = len(df)
    
    print(f"[INFO] 전체 도서 {total_books}권 중 수집 대상 도서: {total_to_scrape}권")

    if total_to_scrape == 0:
        print("[SUCCESS] 이미 모든 도서의 상세 정보 수집이 완료되었습니다.")
        return

    # 빠른 시연을 위해 최대 250권까지만 상세 수집하도록 제한 (전체는 시간이 너무 오래 걸릴 수 있으므로)
    # 상위권 도서 위주로 시각화 및 검색을 먼저 채우고, 대시보드의 유용성을 확보하기 위함입니다.
    max_limit = 250
    if total_to_scrape > max_limit:
        print(f"[INFO] 수집 대기 시간이 너무 길어지는 것을 방지하기 위해 상위 {max_limit}권만 우선 수집합니다.")
        to_scrape_indices = to_scrape_indices[:max_limit]
        total_to_scrape = len(to_scrape_indices)

    # ThreadPoolExecutor를 사용한 멀티스레드 크롤링 (동시성 4)
    # 서버 과부하를 막기 위해 max_workers는 4로 제한합니다.
    completed_count = 0
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(process_row, idx, df.iloc[idx], total_books): idx 
            for idx in to_scrape_indices
        }
        
        for future in as_completed(futures):
            idx, desc, img = future.result()
            
            if desc is not None and img is not None:
                # 데이터프레임 업데이트 (Thread-safe하게 처리)
                with csv_lock:
                    df.at[idx, "내용"] = desc
                    df.at[idx, "이미지"] = img

            completed_count += 1
            
            # 15개 완료될 때마다 파일에 동기화 저장
            if completed_count % 15 == 0 or completed_count == total_to_scrape:
                with csv_lock:
                    df.to_csv(INPUT_FILE, index=False, encoding="utf-8-sig")
                print(f"[INFO] 중간 동기화 완료 ({completed_count}/{total_to_scrape} 완료)")

    print(f"[SUCCESS] 크롤링이 완료되었으며 '{INPUT_FILE}' 파일에 최종 저장되었습니다.")


if __name__ == "__main__":
    main()
