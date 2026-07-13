# 예스24 IT 모바일 베스트셀러 도서 목록 크롤링 구현 계획

이 계획은 예스24의 IT 모바일 종합 베스트 도서 목록의 전체 페이지를 수집하여 CSV 파일로 저장하는 스크립트를 작성하고 실행하는 방법을 정의합니다.

## 제약 사항 및 요구사항
- **언어**: 한국어 답변 및 한국어 코드 주석
- **파이썬 가상환경**: `uv`를 필수적으로 사용하며, 기존 가상환경이 있다면 재사용합니다. (현재 워크스페이스에는 `.venv`가 없음으로 신규 생성)
- **크롤링 방식**: 실제 브라우저 요청처럼 보이도록 User-Agent 등의 헤더 설정 필요.
- **라이브러리**: `requests`, `beautifulsoup4`, `pandas` 등을 활용한 스크래핑 및 CSV 저장.

## 개발 계획

### 1. 환경 설정 및 라이브러리 설치
- `uv venv`를 사용하여 가상환경 `.venv` 생성.
- `uv pip install requests beautifulsoup4 pandas lxml` 패키지 설치.

### 2. 크롤링 스크립트 작성
- **파일명**: `c:\Users\USER\Documents\ABC-RAG\scrape_yes24.py`
- **구현 내용**:
  - `User-Agent` 설정 (실제 브라우저인 것처럼 헤더 구성)
  - `pageNumber`를 1부터 시작하여 루프 수행
  - 각 페이지 URL: `https://www.yes24.com/product/category/bestseller?categoryNumber=001001003&pageNumber={page}&pageSize=24`
  - 페이지 내의 도서 목록(`li` 태그 중 `data-goods-no` 속성을 가진 항목) 파싱
  - 각 도서에서 추출할 정보:
    - **순위 (Rank)**
    - **도서명 (Title)**
    - **상세페이지 링크 (Link)**
    - **저자 (Author)**
    - **출판사 (Publisher)**
    - **출판일 (PubDate)**
    - **판매가 (SalePrice)**
    - **정가 (OriginalPrice)**
    - **할인율 (DiscountRate)**
    - **판매지수 (SaleIndex)**
  - 페이지에 도서 데이터가 없거나 이전 페이지와 동일한 데이터를 불러올 경우(혹은 다음 페이지 버튼이 비활성화되거나 데이터가 없을 때) 크롤링 루프를 종료합니다.
  - 수집된 데이터를 Pandas DataFrame으로 변환한 후 `c:\Users\USER\Documents\ABC-RAG\yes24_it_mobile_bestsellers.csv`로 저장 (UTF-8-SIG 인코딩 사용).

### 3. 검증 계획
- 작성한 스크립트를 실행하여 예외 없이 종료되는지 확인.
- 생성된 `yes24_it_mobile_bestsellers.csv` 파일의 크기 및 내용의 첫 몇 줄을 확인하여 정상적으로 데이터가 수집되었는지 검증.
- `pandas`를 이용하여 전체 행의 개수를 파악하여 전체 페이지가 누락 없이 정상 수집되었는지 확인.

## 사용자 검토 필요 사항
- 특별히 크롤링 대상에서 제외해야 하거나 추가하고 싶은 정보가 있으신가요?
- 예스24 서버의 부하를 줄이기 위해 각 페이지 요청 사이에 약 1초 정도의 대기 시간(time.sleep)을 부여하고자 합니다.

승인해 주시면 구현 및 실행을 진행하겠습니다.
