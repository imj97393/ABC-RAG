import csv
import time
import random
import sys

from scrapling import Fetcher

Fetchers = Fetcher
BASE_URL = "https://www.yes24.com"
TARGET_URL = "https://www.yes24.com/product/category/bestseller?categoryNumber=001001003&pageNumber={page}&pageSize=24"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.yes24.com",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

OUTPUT_FILE = "yes24_it_mobile_bestseller.csv"


def css_first(element, selector):
    results = element.css(selector)
    return results[0] if results else None


def get_total_pages():
    first_url = TARGET_URL.format(page=1)
    fetcher = Fetchers()
    resp = fetcher.get(first_url, headers=HEADERS)

    end_link = css_first(resp, "a.bgYUI.end")
    if end_link:
        total = int(end_link.attrib.get("title", "1"))
        print(f"[INFO] 총 페이지 수: {total}")
        return total

    page_links = resp.css("div.sGoodsPagen div.yesUI_pagen a.num")
    if page_links:
        last = max(int(a.text.strip()) for a in page_links)
        print(f"[INFO] 총 페이지 수: {last}")
        return last

    print("[WARN] 페이지 수를 확인할 수 없습니다. 1페이지만 수집합니다.")
    return 1


def parse_page(page_num, fetcher):
    url = TARGET_URL.format(page=page_num)
    resp = fetcher.get(url, headers=HEADERS)

    books = []
    items = resp.css("#yesBestList > li")

    for item in items:
        try:
            rank_el = css_first(item, "em.ico.rank")
            rank = rank_el.text.strip() if rank_el else ""

            title_el = css_first(item, "a.gd_name")
            title = title_el.text.strip() if title_el else ""
            link = ""
            if title_el and "href" in title_el.attrib:
                href = title_el.attrib["href"]
                link = href if href.startswith("http") else BASE_URL + href

            author_el = css_first(item, "span.authPub.info_auth")
            author = ""
            if author_el:
                author_a = css_first(author_el, "a")
                author = author_a.text.strip() if author_a else author_el.text.strip().replace(" 저", "").strip()

            publisher_el = css_first(item, "span.authPub.info_pub")
            publisher = ""
            if publisher_el:
                pub_a = css_first(publisher_el, "a")
                publisher = pub_a.text.strip() if pub_a else publisher_el.text.strip()

            date_el = css_first(item, "span.authPub.info_date")
            pub_date = date_el.text.strip() if date_el else ""

            sale_price_el = css_first(item, "strong.txt_num em.yes_b")
            sale_price = sale_price_el.text.strip() if sale_price_el else ""

            original_price_el = css_first(item, "span.txt_num.dash em.yes_m")
            original_price = original_price_el.text.strip() if original_price_el else ""

            discount_el = css_first(item, "span.txt_sale em.num")
            discount = discount_el.text.strip() if discount_el else ""

            img_el = css_first(item, "img[data-original]")
            img_url = ""
            if img_el:
                img_url = img_el.attrib.get("data-original", "")
                if img_url and not img_url.startswith("http"):
                    img_url = "https:" + img_url if img_url.startswith("//") else BASE_URL + img_url

            books.append({
                "순위": rank,
                "제목": title,
                "저자": author,
                "출판사": publisher,
                "출간일": pub_date,
                "판매가": sale_price,
                "정가": original_price,
                "할인율": discount,
                "링크": link,
                "이미지": img_url,
            })
        except Exception as e:
            print(f"[WARN] 항목 파싱 오류: {e}")
            continue

    return books


def main():
    total_pages = get_total_pages()
    all_books = []
    fetcher = Fetchers()

    for page in range(1, total_pages + 1):
        print(f"[{page}/{total_pages}] 페이지 수집 중...", end=" ")
        try:
            books = parse_page(page, fetcher)
            all_books.extend(books)
            print(f"{len(books)}권 수집 완료")
        except Exception as e:
            print(f"오류 발생: {e}")

        if page < total_pages:
            delay = random.uniform(1.5, 3.0)
            time.sleep(delay)

    if all_books:
        fieldnames = ["순위", "제목", "저자", "출판사", "출간일", "판매가", "정가", "할인율", "링크", "이미지"]
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_books)
        print(f"\n[DONE] 총 {len(all_books)}권을 '{OUTPUT_FILE}'에 저장했습니다.")
    else:
        print("[ERROR] 수집된 데이터가 없습니다.")


if __name__ == "__main__":
    main()
