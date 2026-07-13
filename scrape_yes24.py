"""예스24 IT 모바일 베스트셀러 도서 목록 크롤링 모듈.

이 모듈은 예스24 사이트에서 IT 모바일 베스트셀러 카테고리의 전체 페이지를
수집하여 CSV 형식으로 저장하는 기능을 제공합니다.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re

def scrape_yes24_bestsellers() -> None:
    """예스24 IT 모바일 종합 베스트셀러 목록의 전체 페이지를 수집하여 CSV로 저장한다.

    실제 브라우저의 요청처럼 보이기 위해 User-Agent를 설정하고 페이징 루프를 돕니다.
    수집 완료 후 'yes24_it_mobile_bestsellers.csv' 파일로 결과를 저장합니다.

    Note:
        - 예스24 서버 부하를 방지하기 위해 요청 사이에 1초의 시간 대기(time.sleep)를 가집니다.
        - 중복 수집을 방지하고 정확한 종료 조건을 맞추기 위해 이미 조회된 도서번호(goods_no)를 캐싱합니다.
    """
    # 실제 브라우저에서 요청하는 것처럼 헤더를 설정합니다.
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.yes24.com/",
        "Connection": "keep-alive"
    }

    base_url = "https://www.yes24.com/product/category/bestseller"
    category_number = "001001003"  # IT 모바일 카테고리 번호
    page_size = 24
    
    books_data = []
    page = 1
    
    # 중복 수집 방지 및 루프 종료를 위해 이미 수집한 상품 번호를 기록합니다.
    seen_goods_nos = set()

    print(f"예스24 IT 모바일 베스트셀러 크롤링을 시작합니다. (카테고리: {category_number})")

    while True:
        url = f"{base_url}?categoryNumber={category_number}&pageNumber={page}&pageSize={page_size}"
        print(f"페이지 {page} 수집 중... URL: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"에러 발생: HTTP 상태 코드 {response.status_code}")
                break
                
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 도서 목록 아이템 찾기 (li 태그 중 data-goods-no 속성이 있는 것)
            items = soup.find_all('li', attrs={'data-goods-no': True})
            
            if not items:
                print("더 이상 도서 아이템이 발견되지 않아 크롤링을 종료합니다.")
                break
                
            # 현재 페이지에서 새로 추가된 도서가 있는지 추적
            new_items_count = 0
            
            for item in items:
                goods_no = item.get('data-goods-no')
                
                # 이미 수집한 상품 번호라면 건너뜁니다. (종종 마지막 페이지 이후에 같은 페이지가 반복되는 현상 방지)
                if goods_no in seen_goods_nos:
                    continue
                
                seen_goods_nos.add(goods_no)
                new_items_count += 1
                
                # 1. 순위
                rank_elem = item.find('em', class_='rank')
                rank = rank_elem.text.strip() if rank_elem else ""
                
                # 2. 도서명
                name_elem = item.find('a', class_='gd_name')
                title = name_elem.text.strip() if name_elem else ""
                
                # 3. 링크
                link = ""
                if name_elem and name_elem.get('href'):
                    href = name_elem.get('href')
                    link = f"https://www.yes24.com{href}" if href.startswith('/') else href
                
                # 4. 저자
                auth_elem = item.find('span', class_='info_auth')
                author = auth_elem.text.strip() if auth_elem else ""
                # "저자 저" -> "저자" 형태로 가공 (옵션)
                author = re.sub(r'\s*저$', '', author).strip()
                
                # 5. 출판사
                pub_elem = item.find('span', class_='info_pub')
                publisher = pub_elem.text.strip() if pub_elem else ""
                
                # 6. 출판일
                date_elem = item.find('span', class_='info_date')
                pub_date = date_elem.text.strip() if date_elem else ""
                
                # 7. 판매가
                price_elem = item.find('strong', class_='txt_num')
                sale_price = ""
                if price_elem:
                    price_em = price_elem.find('em', class_='yes_b')
                    sale_price = price_em.text.strip() if price_em else price_elem.text.strip()
                
                # 8. 정가
                orig_elem = item.find('span', class_='dash')
                original_price = ""
                if orig_elem:
                    orig_em = orig_elem.find('em', class_='yes_m')
                    original_price = orig_em.text.strip() if orig_em else orig_elem.text.strip()
                
                # 9. 할인율
                sale_pct_elem = item.find('span', class_='txt_sale')
                discount_rate = ""
                if sale_pct_elem:
                    sale_pct_num = sale_pct_elem.find('em', class_='num')
                    discount_rate = f"{sale_pct_num.text.strip()}%" if sale_pct_num else sale_pct_elem.text.strip()
                
                # 10. 판매지수
                sale_num_elem = item.find('span', class_='saleNum')
                sale_index = ""
                if sale_num_elem:
                    sale_index = sale_num_elem.text.replace("판매지수", "").strip()
                
                books_data.append({
                    "순위": rank,
                    "도서번호": goods_no,
                    "도서명": title,
                    "링크": link,
                    "저자": author,
                    "출판사": publisher,
                    "출판일": pub_date,
                    "판매가": sale_price,
                    "정가": original_price,
                    "할인율": discount_rate,
                    "판매지수": sale_index
                })
            
            # 새로 추가된 도서가 하나도 없다면 종료 (페이지를 넘겼는데 이전 페이지와 동일할 때)
            if new_items_count == 0:
                print("새로운 도서가 발견되지 않아 크롤링을 종료합니다.")
                break
                
            page += 1
            # 예스24 서버의 부하를 최소화하기 위해 1초 대기합니다.
            time.sleep(1.0)
            
        except Exception as e:
            print(f"페이지 {page} 수집 중 오류 발생: {e}")
            break

    # 데이터를 Pandas DataFrame으로 변환 후 CSV로 저장합니다.
    if books_data:
        df = pd.DataFrame(books_data)
        csv_file_path = "yes24_it_mobile_bestsellers.csv"
        # utf-8-sig 인코딩을 사용하여 엑셀에서 한글이 깨지지 않도록 합니다.
        df.to_csv(csv_file_path, index=False, encoding='utf-8-sig')
        print(f"\n성공적으로 데이터를 수집하여 '{csv_file_path}' 파일로 저장했습니다. (총 {len(books_data)}개 도서)")
    else:
        print("수집된 데이터가 없습니다.")

if __name__ == "__main__":
    scrape_yes24_bestsellers()
