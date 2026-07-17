"""예스24 IT/모바일 베스트셀러 EDA 및 도서 검색 Streamlit 대시보드.

이 애플리케이션은 수집된 도서 데이터를 활용하여 다채로운 데이터 분석 시각화와
책 제목 및 상세 내용(소개)에 대한 다중 키워드 검색 및 다차원 필터링 기능을 제공합니다.
"""

import os
import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from groq import Groq
from vector_db import ChromaDBManager
import json

# 페이지 기본 설정 (와이드 모드, 대시보드 타이틀 및 아이콘)
st.set_page_config(
    page_title="YES24 IT/모바일 베스트셀러 대시보드",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 데이터 파일 경로 설정
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DATA_FILE = os.path.join(DATA_DIR, "yes24_it_mobile_bestsellers.csv")

# 프리미엄 디자인을 위한 커스텀 CSS 주입
st.markdown("""
<style>
    /* 전체 배경 및 폰트 스타일 지정 */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Noto Sans KR', sans-serif;
    }
    
    /* 대시보드 메인 헤더 디자인 */
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A8A;
        background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 2rem;
    }
    
    /* KPI 카드 스타일 */
    .kpi-card {
        background: rgba(255, 255, 255, 0.8);
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        padding: 1.5rem;
        border: 1px solid #E5E7EB;
        text-align: center;
        transition: transform 0.2s ease-in-out;
    }
    .kpi-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    }
    .kpi-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #2563EB;
        margin-top: 0.5rem;
    }
    .kpi-label {
        font-size: 0.9rem;
        color: #6B7280;
        font-weight: 500;
    }
    
    /* 도서 검색 카드 레이아웃 */
    .book-card {
        background: #ffffff;
        border-radius: 12px;
        border: 1px solid #F3F4F6;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        padding: 1.25rem;
        margin-bottom: 1.25rem;
        display: flex;
        gap: 1.5rem;
        transition: border-color 0.2s;
    }
    .book-card:hover {
        border-color: #3B82F6;
    }
    .book-img {
        width: 110px;
        height: 160px;
        object-fit: cover;
        border-radius: 6px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .book-info {
        flex: 1;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .book-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #1F2937;
        margin-bottom: 0.25rem;
    }
    .book-meta {
        font-size: 0.85rem;
        color: #6B7280;
        margin-bottom: 0.75rem;
    }
    .book-description {
        font-size: 0.9rem;
        color: #4B5563;
        line-height: 1.5;
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        margin-bottom: 0.75rem;
    }
    .highlight {
        background-color: #FEF08A; /* 파스텔 연노랑 하이라이트 */
        font-weight: 500;
        padding: 0 2px;
        border-radius: 2px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_and_preprocess_data(filepath: str) -> pd.DataFrame:
    """도서 데이터를 로드하고 전처리합니다.

    - 정가, 판매가: 콤마 제거 및 정수형 변환
    - 할인율: '%' 기호 제거 및 실수형 변환
    - 판매지수: 콤마 제거 및 정수형 변환
    - 출판일: 연도 및 월 정보 추출
    - 내용, 이미지: 결측치 보정
    """
    if not os.path.exists(filepath):
        return pd.DataFrame()

    df = pd.read_csv(filepath)

    # 1. 가격 컬럼 전처리
    for col in ["판매가", "정가"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(",", "")
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # 2. 할인율 컬럼 전처리
    if "할인율" in df.columns:
        df["할인율_값"] = df["할인율"].astype(str).str.replace("%", "")
        df["할인율_값"] = pd.to_numeric(df["할인율_값"], errors="coerce").fillna(0).astype(int)
    else:
        df["할인율_값"] = 0

    # 3. 판매지수 컬럼 전처리
    if "판매지수" in df.columns:
        df["판매지수_값"] = df["판매지수"].astype(str).str.replace(",", "")
        df["판매지수_값"] = pd.to_numeric(df["판매지수_값"], errors="coerce").fillna(0).astype(int)
    else:
        df["판매지수_값"] = 0

    # 4. 출판일 컬럼에서 연도와 월 추출
    if "출판일" in df.columns:
        df["출판연도"] = df["출판일"].astype(str).apply(lambda x: re.search(r"(\d{4})년", x).group(1) if re.search(r"(\d{4})년", x) else "기타")
        df["출판월"] = df["출판일"].astype(str).apply(lambda x: re.search(r"(\d{2})월", x).group(1) if re.search(r"(\d{2})월", x) else "기타")
    elif "출간일" in df.columns:
        # 출간일 컬럼 대응
        df["출판연도"] = df["출간일"].astype(str).apply(lambda x: re.search(r"(\d{4})년", x).group(1) if re.search(r"(\d{4})년", x) else "기타")
        df["출판월"] = df["출간일"].astype(str).apply(lambda x: re.search(r"(\d{2})월", x).group(1) if re.search(r"(\d{2})월", x) else "기타")
        df["출판일"] = df["출간일"]
    else:
        df["출판연도"] = "기타"
        df["출판월"] = "기타"
        df["출판일"] = "기타"

    # 5. 도서명 컬럼 통일
    if "도서명" not in df.columns and "제목" in df.columns:
        df["도서명"] = df["제목"]

    # 6. 내용 및 이미지 결측치 처리
    if "내용" not in df.columns:
        df["내용"] = "책 소개 정보가 없습니다."
    else:
        df["내용"] = df["내용"].fillna("책 소개 정보가 없습니다.")

    if "이미지" not in df.columns:
        df["이미지"] = ""
    else:
        df["이미지"] = df["이미지"].fillna("")

    return df


def highlight_keyword(text: str, keyword: str) -> str:
    """텍스트 내의 특정 키워드를 HTML span 태그로 감싸 하이라이트 처리합니다."""
    if not keyword or not text:
        return text
    # 대소문자 구분 없이 매칭하기 위해 re.compile 사용
    try:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        return pattern.sub(f'<span class="highlight">\\g<0></span>', text)
    except Exception:
        return text


def retrieve_relevant_books(query: str, df: pd.DataFrame, top_n: int = 10) -> list:
    """사용자 질문에서 핵심 키워드를 추출하여 데이터프레임에서 관련성이 높은 도서 목록을 필터링합니다.

    - 불용어를 제외한 키워드들을 추출합니다.
    - 도서명, 내용, 저자, 출판사 등에서 키워드 매칭 여부에 따라 점수를 부과합니다.
    - 점수 기반으로 내림차순 정렬하고 상위 top_n개의 도서를 반환합니다.
    """
    if df.empty or not query:
        return []

    # 1. 사용자 질문 정제 및 키워드 추출
    # 특수문자 제거
    cleaned_query = re.sub(r"[^\w\s]", " ", query)
    words = cleaned_query.split()
    
    # 2글자 미만이거나 불용어에 해당하는 단어 필터링
    stopwords = {
        "추천", "추천해", "추천해줘", "추천해줄래", "추천해주라", "추천한다",
        "알려줘", "알려줄래", "보여줘", "있어", "있니", "있나요", "있습니까", "있을까",
        "어떤", "무슨", "도서", "책", "교재", "분야", "관련", "관련된", "대해", "대해서",
        "대한", "찾아", "찾아줘", "소개", "소개해", "가장", "제일", "요즘", "베스트",
        "셀러", "베스트셀러", "인기", "인기있는", "재미있는", "쉬운", "어려운"
    }
    
    keywords = [w for w in words if len(w) >= 2 and w not in stopwords]
    
    # 만약 불용어를 빼고 남은 키워드가 없다면 원본 단어 중 1글자 이상인 것들을 사용
    if not keywords:
        keywords = [w for w in words if w not in stopwords]
        
    if not keywords:
        # 그래도 없다면 전체 단어 사용
        keywords = words

    # 2. 도서별 점수 계산
    scores = []
    for idx, row in df.iterrows():
        score = 0
        book_title = str(row.get("도서명", "")).lower()
        book_desc = str(row.get("내용", "")).lower()
        book_author = str(row.get("저자", "")).lower()
        book_pub = str(row.get("출판사", "")).lower()
        
        for kw in keywords:
            kw_lower = kw.lower()
            # 제목에 포함 시 가중치 15점
            if kw_lower in book_title:
                score += 15 + (book_title.find(kw_lower) == 0) * 5  # 앞에 나올수록 조금 더 가산점
            # 저자에 포함 시 가중치 8점
            if kw_lower in book_author:
                score += 8
            # 내용에 포함 시 가중치 3점
            if kw_lower in book_desc:
                # 내용에서 키워드가 출현하는 횟수 세기
                count = book_desc.count(kw_lower)
                score += min(count * 3, 15)  # 최대 15점까지만 가산
            # 출판사에 포함 시 가중치 5점
            if kw_lower in book_pub:
                score += 5
                
        # 매칭된 키워드가 있는 경우에만 후보에 추가
        if score > 0:
            # 동점인 경우 판매지수가 높은 책이 우선되도록 미세한 점수 추가
            sales_idx = row.get("판매지수_값", 0)
            score += min(sales_idx / 100000.0, 0.99)  # 최대 0.99점 추가
            scores.append((idx, score))
            
    if not scores:
        return []

    # 3. 점수 높은 순 정렬 및 상위 N개 추출
    scores.sort(key=lambda x: x[1], reverse=True)
    top_indices = [idx for idx, scr in scores[:top_n]]
    top_books_df = df.loc[top_indices]
    
    books_list = []
    for _, row in top_books_df.iterrows():
        books_list.append({
            "순위": row.get("순위", "정보 없음"),
            "도서명": row.get("도서명", "제목 없음"),
            "저자": row.get("저자", "저자 미상"),
            "출판사": row.get("출판사", "출판사 정보 없음"),
            "출판일": row.get("출판일", "날짜 없음"),
            "판매가": row.get("판매가", 0),
            "내용": row.get("내용", "소개 없음"),
            "링크": row.get("링크", "")
        })
    return books_list


def query_books_by_numeric_metrics(
    df: pd.DataFrame,
    min_price: int = None,
    max_price: int = None,
    min_sales: int = None,
    max_sales: int = None,
    sort_by: str = None,
    ascending: bool = False,
    top_n: int = 10
) -> list:
    """사용자가 가격이나 판매지수를 명시했을 때 데이터프레임을 직접 정렬하고 범위를 필터링하여 결과를 반환합니다.

    Args:
        df (pd.DataFrame): 예스24 베스트셀러 도서 데이터프레임
        min_price (int, optional): 최소 가격
        max_price (int, optional): 최대 가격
        min_sales (int, optional): 최소 판매지수
        max_sales (int, optional): 최대 판매지수
        sort_by (str, optional): 정렬 기준 ("판매가" 또는 "판매지수_값")
        ascending (bool): 오름차순 여부 (기본값: False)
        top_n (int): 반환할 도서 개수 (기본값: 10)

    Returns:
        list: 정렬 및 필터링이 완료된 도서 정보 딕셔너리 리스트
    """
    if df.empty:
        return []

    filtered_df = df.copy()

    # 1. 가격 필터링 (판매가 컬럼 기준)
    if min_price is not None:
        filtered_df = filtered_df[filtered_df["판매가"] >= min_price]
    if max_price is not None:
        filtered_df = filtered_df[filtered_df["판매가"] <= max_price]

    # 2. 판매지수 필터링 (판매지수_값 컬럼 기준)
    if min_sales is not None:
        filtered_df = filtered_df[filtered_df["판매지수_값"] >= min_sales]
    if max_sales is not None:
        filtered_df = filtered_df[filtered_df["판매지수_값"] <= max_sales]

    # 3. 정렬 처리
    if sort_by:
        sort_col = None
        if sort_by in ["판매가", "가격"]:
            sort_col = "판매가"
        elif sort_by in ["정가"]:
            sort_col = "정가"
        elif sort_by in ["판매지수", "판매지수_값", "인기"]:
            sort_col = "판매지수_값"
        elif sort_by in ["할인율", "할인율_값"]:
            sort_col = "할인율_값"

        if sort_col and sort_col in filtered_df.columns:
            filtered_df = filtered_df.sort_values(by=sort_col, ascending=ascending)
    else:
        # 특별한 정렬 기준이 지정되지 않았으나 필터링 등이 걸린 경우 판매지수 높은 인기 순을 기본값으로 정렬
        if "판매지수_값" in filtered_df.columns:
            filtered_df = filtered_df.sort_values(by="판매지수_값", ascending=False)

    # 4. 결과 가공
    result_books = []
    for _, row in filtered_df.head(top_n).iterrows():
        result_books.append({
            "순위": row.get("순위", "정보 없음"),
            "도서명": row.get("도서명", "제목 없음"),
            "저자": row.get("저자", "저자 미상"),
            "출판사": row.get("출판사", "출판사 정보 없음"),
            "출판일": row.get("출판일", "날짜 없음"),
            "판매가": row.get("판매가", 0),
            "내용": row.get("내용", "소개 없음"),
            "링크": row.get("링크", "")
        })

    return result_books


def recommend_books_via_groq(query: str, relevant_books: list, api_key: str, model: str, df: pd.DataFrame = None) -> str:
    """Groq API를 사용하여 도서 추천 응답을 생성합니다.

    - 가격이나 판매지수에 관련된 수치 연산 및 정렬이 필요한 경우 Tool Calling을 수행합니다.
    - 일반 질의의 경우 제공된 relevant_books 데이터를 Context로 활용합니다.
    - 추천 시 마크다운 링크 형식 [도서명](링크)을 필수로 포함합니다.
    """
    try:
        client = Groq(api_key=api_key)
    except Exception as e:
        return f"Groq 클라이언트 초기화 실패: {str(e)}"

    # 도서 컨텍스트 구성
    if not relevant_books:
        context_str = "제공된 관련 도서 목록이 비어 있습니다."
    else:
        context_str = "아래는 현재 데이터베이스(IT/모바일 베스트셀러)에서 검색된 관련 도서 목록입니다:\n\n"
        for i, book in enumerate(relevant_books):
            context_str += (
                f"[{i+1}] 도서명: {book['도서명']}\n"
                f"- 순위: {book['순위']}위\n"
                f"- 저자: {book['저자']}\n"
                f"- 출판사: {book['출판사']}\n"
                f"- 출판일: {book['출판일']}\n"
                f"- 판매가: {book['판매가']:,}원\n"
                f"- 소개내용: {book['내용']}\n"
                f"- 상세링크: {book['링크']}\n\n"
            )

    system_prompt = (
        "당신은 예스24 IT/모바일 베스트셀러 도서 데이터를 기반으로 책을 추천하는 전문 AI 어시스턴트입니다.\n"
        "아래 규칙을 엄격히 준수하여 한국어로 답변하세요:\n\n"
        "1. 제공된 [도서 목록] 컨텍스트 또는 도구(Tool) 호출을 통해 가져온 결과만을 기반으로 추천을 수행하십시오.\n"
        "2. 만약 제공된 도서 목록에 사용자가 찾는 분야의 도서가 없거나 질문에 부합하는 도서가 전혀 없다면, "
        "절대 임의로 도서 정보를 지어내거나 외부 도서를 추천하지 마십시오. 반드시 한국어로 '추천할 도서가 없습니다.'라고 명확하게 답변하십시오.\n"
        "3. 책을 추천할 때는 해당 도서의 정보(순위, 저자, 출판사, 판매가, 내용 요약 등)를 친절히 설명하십시오.\n"
        "4. 책을 언급할 때는 반드시 '[도서명](상세링크)' 형식을 적용하여 사용자가 링크를 클릭해 바로 예스24 도서 상세 페이지로 이동할 수 있게 마크다운 링크를 제공하십시오. "
        "예: [Do it! 점프 투 파이썬](https://www.yes24.com/product/goods/119293186)\n"
        "5. 답변에 링크를 작성할 때는 컨텍스트에 주어진 '상세링크' 값을 그대로 사용하십시오. 임의로 도메인을 변경하거나 위조하지 마십시오."
    )

    user_content = (
        f"[도서 목록]\n{context_str}\n\n"
        f"[사용자 질문]\n{query}\n\n"
        f"위 도서 목록 내 또는 도구 호출을 통해 적절한 도서를 추천하고 그 이유를 설명해 주세요. "
        f"만약 조건에 맞는 도서가 전혀 없다면 반드시 '추천할 도서가 없습니다.'라고 답하세요."
    )

    # 수치 분석용 도구(Tool) 정의
    tools = [
        {
            "type": "function",
            "function": {
                "name": "query_books_by_numeric_metrics",
                "description": (
                    "사용자가 도서의 가격대 조건(최소 가격, 최대 가격), 판매지수 범위 조건, "
                    "혹은 수치 정렬(예: 가격 싼 순서, 판매지수 높은 인기 순서 등)을 요구하여 질문했을 때 호출하여 데이터프레임을 직접 정렬/필터링합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "min_price": {
                            "type": "integer",
                            "description": "최소 가격 필터 조건 (원 단위, 예: 10000)"
                        },
                        "max_price": {
                            "type": "integer",
                            "description": "최대 가격 필터 조건 (원 단위, 예: 25000)"
                        },
                        "min_sales": {
                            "type": "integer",
                            "description": "최소 판매지수 조건 (예: 5000)"
                        },
                        "max_sales": {
                            "type": "integer",
                            "description": "최대 판매지수 조건"
                        },
                        "sort_by": {
                            "type": "string",
                            "enum": ["판매가", "판매지수_값"],
                            "description": "정렬 기준 컬럼 ('판매가'는 가격 기준, '판매지수_값'은 인기도/판매량 기준)"
                        },
                        "ascending": {
                            "type": "boolean",
                            "description": "오름차순 여부. True이면 낮은 순(가격 싼 순), False이면 높은 순(가격 비싼 순, 판매지수 높은 인기 순)으로 정렬합니다."
                        }
                    },
                    "required": []
                }
            }
        }
    ]

    try:
        # 1차 호출 (도구 호출 필요 여부 체크)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
            max_tokens=2048
        )
        
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        
        # 도구 호출이 필요하고 데이터프레임이 전달된 경우
        if tool_calls and df is not None:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
                response_message
            ]
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                if function_name == "query_books_by_numeric_metrics":
                    # 인자 파싱
                    min_p = function_args.get("min_price")
                    max_p = function_args.get("max_price")
                    min_s = function_args.get("min_sales")
                    max_s = function_args.get("max_sales")
                    sort_b = function_args.get("sort_by")
                    asc = function_args.get("ascending", False)
                    
                    # 로컬 데이터프레임 정렬/필터링 실행
                    calc_books = query_books_by_numeric_metrics(
                        df=df,
                        min_price=min_p,
                        max_price=max_p,
                        min_sales=min_s,
                        max_sales=max_s,
                        sort_by=sort_b,
                        ascending=asc
                    )
                    
                    # 도구 실행 결과를 LLM용 컨텍스트로 변환
                    if not calc_books:
                        result_str = "조건을 만족하는 도서 목록이 데이터베이스에 없습니다."
                    else:
                        result_str = "수치 범위 필터링 및 정렬 조건으로 데이터베이스에서 직접 연산 및 정렬한 결과입니다:\n\n"
                        for idx, b in enumerate(calc_books):
                            result_str += (
                                f"[{idx+1}] 도서명: {b['도서명']}\n"
                                f"- 순위: {b['순위']}위\n"
                                f"- 저자: {b['저자']}\n"
                                f"- 출판사: {b['출판사']}\n"
                                f"- 출판일: {b['출판일']}\n"
                                f"- 판매가: {b['판매가']:,}원\n"
                                f"- 소개내용: {b['내용']}\n"
                                f"- 상세링크: {b['링크']}\n\n"
                            )
                            
                    # 대화 메시지에 도구 응답 추가
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": result_str
                    })
                    
            # 2차 호출 (최종 답변 생성)
            second_response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
                max_tokens=2048
            )
            return second_response.choices[0].message.content
        else:
            # 도구 호출을 수행하지 않은 경우 일반 응답 텍스트 반환
            return response_message.content

    except Exception as e:
        return f"Groq API 호출(Tool Calling 포함) 중 오류가 발생했습니다: {str(e)}"


def main():
    # 데이터 로드
    df = load_and_preprocess_data(DATA_FILE)

    if df.empty:
        st.error("데이터 파일을 찾을 수 없거나 데이터가 비어 있습니다. 먼저 상세 정보 크롤러를 완료해 주세요.")
        st.info(f"확인 경로: {DATA_FILE}")
        return

    # ChromaDB 매니저 초기화 및 데이터 자동 적재 (RAG 개선)
    db_manager = ChromaDBManager()
    if not db_manager.has_data():
        with st.status("📚 최초 실행: 한국어 klue-bert 모델 기반 벡터 데이터베이스 빌드 중...", expanded=True) as status:
            st.write("사전학습된 `klue/bert-base` 모델 가중치를 다운로드하고 도서 데이터의 고차원 벡터 변환을 시작합니다.")
            progress_bar = st.progress(0.0)
            status_text = st.empty()
            
            def progress_cb(current, total, msg):
                ratio = float(current) / float(total)
                progress_bar.progress(ratio)
                status_text.text(f"[{current}/{total}] {msg}")
                
            try:
                db_manager.add_books(df, progress_callback=progress_cb)
                status.update(label="🎉 벡터 데이터베이스 빌드 완료!", state="complete", expanded=False)
                progress_bar.empty()
                status_text.empty()
                st.toast("RAG 챗봇용 벡터 DB 빌드가 성공적으로 완료되었습니다!", icon="✅")
            except Exception as e:
                status.update(label="❌ 빌드 실패", state="error", expanded=True)
                st.error(f"벡터 데이터베이스 생성 중 오류가 발생했습니다: {str(e)}")
                progress_bar.empty()
                status_text.empty()

    # 사이드바 설정 (Groq API Key 및 모델)
    st.sidebar.title("🔑 AI 추천 설정")
    st.sidebar.markdown("Groq Cloud에서 발급받은 API Key를 입력하여 도서 추천 챗봇을 이용하실 수 있습니다.")
    
    groq_api_key = st.sidebar.text_input("Groq API Key", type="password", help="gsk_로 시작하는 Groq API Key를 입력하세요.")
    
    model_options = [
        "llama-3.3-70b-versatile",
        "llama3-8b-8192",
        "mixtral-8x7b-32768"
    ]
    selected_model = st.sidebar.selectbox("LLM 모델 선택", model_options, index=0)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("[Groq Console 바로가기](https://console.groq.com/keys)")

    # 대시보드 타이틀
    st.markdown('<div class="main-header">YES24 IT/모바일 베스트셀러 대시보드</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">실시간으로 수집된 예스24 IT/모바일 카테고리의 베스트셀러 데이터를 바탕으로 트렌드를 분석하고 도서를 검색합니다.</div>', unsafe_allow_html=True)

    # 탭 구성 (시각화 분석 / 도서 검색 / 챗봇)
    tab1, tab2, tab3 = st.tabs(["📊 탐색적 데이터 분석 (EDA)", "🔍 키워드 검색 및 도서 상세", "🤖 AI 도서 추천 챗봇"])

    # --- 탭 1: 탐색적 데이터 분석 (EDA) ---
    with tab1:
        # KPI 메트릭 영역
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
        
        with kpi_col1:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">총 베스트셀러 도서 수</div>
                <div class="kpi-value">{len(df)}권</div>
            </div>
            """, unsafe_allow_html=True)
            
        with kpi_col2:
            avg_index = int(df["판매지수_값"].mean())
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">평균 판매지수</div>
                <div class="kpi-value">{avg_index:,}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with kpi_col3:
            avg_discount = df["할인율_값"].mean()
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">평균 할인율</div>
                <div class="kpi-value">{avg_discount:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
            
        with kpi_col4:
            avg_price = int(df["판매가"].mean())
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">평균 판매가</div>
                <div class="kpi-value">{avg_price:,}원</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br><hr><br>", unsafe_allow_html=True)

        # 시각화 그래프 영역 - 행 1
        row1_col1, row1_col2 = st.columns(2)

        with row1_col1:
            st.subheader("🏢 출판사별 베스트셀러 도서 수 (Top 10)")
            pub_counts = df["출판사"].value_counts().reset_index()
            pub_counts.columns = ["출판사", "도서수"]
            fig_pub = px.bar(
                pub_counts.head(10),
                x="도서수",
                y="출판사",
                orientation="h",
                text="도서수",
                color="도서수",
                color_continuous_scale="Blues",
                labels={"도서수": "도서 수", "출판사": "출판사 명"}
            )
            fig_pub.update_layout(
                yaxis={"categoryorder": "total ascending"},
                margin=dict(l=20, r=20, t=20, b=20),
                height=350,
                coloraxis_showscale=False
            )
            st.plotly_chart(fig_pub, use_container_width=True)

        with row1_col2:
            st.subheader("📈 판매지수 Top 10 도서")
            top_sales = df.sort_values(by="판매지수_값", ascending=False).head(10)
            fig_sales = px.bar(
                top_sales,
                x="판매지수_값",
                y="도서명",
                orientation="h",
                text="판매지수_값",
                color="판매지수_값",
                color_continuous_scale="Purples",
                labels={"판매지수_값": "판매지수", "도서명": "도서명"}
            )
            fig_sales.update_layout(
                yaxis={"categoryorder": "total ascending"},
                margin=dict(l=20, r=20, t=20, b=20),
                height=350,
                coloraxis_showscale=False
            )
            # 도서명이 길 경우 축에 너무 잘리는 문제 방지
            fig_sales.update_yaxes(ticktext=[name[:18] + '...' if len(name) > 18 else name for name in top_sales["도서명"]],
                                   tickvals=top_sales["도서명"])
            st.plotly_chart(fig_sales, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # 시각화 그래프 영역 - 행 2
        row2_col1, row2_col2 = st.columns(2)

        with row2_col1:
            st.subheader("💰 정가 vs 판매가 가격 분포")
            fig_price = go.Figure()
            fig_price.add_trace(go.Box(y=df["정가"], name="정가", marker_color="#3B82F6", boxpoints="all"))
            fig_price.add_trace(go.Box(y=df["판매가"], name="판매가", marker_color="#10B981", boxpoints="all"))
            fig_price.update_layout(
                margin=dict(l=20, r=20, t=20, b=20),
                height=350,
                yaxis_title="가격 (원)"
            )
            st.plotly_chart(fig_price, use_container_width=True)

        with row2_col2:
            st.subheader("📅 출판 연도별 베스트셀러 분포")
            # '기타' 제외하고 연도별 정렬
            year_df = df[df["출판연도"] != "기타"].copy()
            year_df["출판연도"] = pd.to_numeric(year_df["출판연도"])
            year_counts = year_df["출판연도"].value_counts().reset_index().sort_values(by="출판연도")
            year_counts.columns = ["출판연도", "도서수"]
            
            fig_year = px.line(
                year_counts,
                x="출판연도",
                y="도서수",
                markers=True,
                color_discrete_sequence=["#EF4444"],
                labels={"출판연도": "출판 연도", "도서수": "도서 수"}
            )
            fig_year.update_layout(
                margin=dict(l=20, r=20, t=20, b=20),
                height=350,
                xaxis=dict(tickmode="linear")
            )
            st.plotly_chart(fig_year, use_container_width=True)

    # --- 탭 2: 키워드 검색 및 도서 상세 ---
    with tab2:
        # 검색 및 필터 패널
        st.subheader("🔍 도서 다차원 검색 엔진")
        
        search_col1, search_col2 = st.columns([3, 1])
        
        with search_col1:
            keyword = st.text_input("검색할 키워드를 입력해 주세요 (제목 또는 본문 내용 검색 가능):", placeholder="예: 클로드, 파이썬, 챗GPT, 리액트 등")
            
        with search_col2:
            search_target = st.radio("검색 대상 영역 선택", ["전체(제목+내용)", "제목만", "내용만"], horizontal=True)

        st.markdown("<br>", unsafe_allow_html=True)
        
        # 필터 슬라이더/멀티셀렉트 레이아웃
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        
        with filter_col1:
            all_publishers = sorted(df["출판사"].unique().tolist())
            selected_publishers = st.multiselect("출판사 필터", all_publishers, placeholder="출판사 전체")
            
        with filter_col2:
            max_price = int(df["판매가"].max())
            price_range = st.slider("판매가 범위 설정 (원)", 0, max_price, (0, max_price), step=1000)
            
        with filter_col3:
            min_sales_idx = st.number_input("최소 판매지수 설정", min_value=0, value=0, step=1000)

        # --- 데이터 필터링 적용 ---
        filtered_df = df.copy()

        # 1. 출판사 필터
        if selected_publishers:
            filtered_df = filtered_df[filtered_df["출판사"].isin(selected_publishers)]

        # 2. 판매가 범위 필터
        filtered_df = filtered_df[
            (filtered_df["판매가"] >= price_range[0]) & 
            (filtered_df["판매가"] <= price_range[1])
        ]

        # 3. 최소 판매지수 필터
        filtered_df = filtered_df[filtered_df["판매지수_val"] >= min_sales_idx] if "판매지수_val" in filtered_df.columns else filtered_df[filtered_df["판매지수_값"] >= min_sales_idx]

        # 4. 키워드 검색 필터
        if keyword:
            keyword_clean = keyword.strip()
            if search_target == "제목만":
                filtered_df = filtered_df[filtered_df["도서명"].str.contains(keyword_clean, case=False, na=False)]
            elif search_target == "내용만":
                filtered_df = filtered_df[filtered_df["내용"].str.contains(keyword_clean, case=False, na=False)]
            else:  # 전체
                filtered_df = filtered_df[
                    filtered_df["도서명"].str.contains(keyword_clean, case=False, na=False) |
                    filtered_df["내용"].str.contains(keyword_clean, case=False, na=False)
                ]

        # 검색 결과 렌더링
        st.markdown(f"**검색 결과: 총 {len(filtered_df)}건의 도서가 매칭되었습니다.**")
        st.markdown("<br>", unsafe_allow_html=True)

        if filtered_df.empty:
            st.warning("조건에 부합하는 도서가 없습니다. 검색어나 필터를 변경해 주세요.")
        else:
            for idx, row in filtered_df.iterrows():
                # 제목 및 소개글 하이라이팅 처리
                raw_title = row["도서명"]
                raw_desc = row["내용"]
                
                display_title = highlight_keyword(raw_title, keyword) if keyword else raw_title
                display_desc = highlight_keyword(raw_desc, keyword) if keyword else raw_desc

                # 가격 포맷 설정
                orig_price_fmt = f"{row['정가']:,}원" if row["정가"] > 0 else "정보 없음"
                sale_price_fmt = f"{row['판매가']:,}원" if row["판매가"] > 0 else "정보 없음"
                discount_fmt = f"[{row['할인율_값']}% 할인]" if row["할인율_값"] > 0 else ""

                # 표지 이미지 기본 대체 이미지 처리
                img_src = row["이미지"] if row["이미지"] else "https://via.placeholder.com/110x160?text=No+Cover"

                st.markdown(f"""
                <div class="book-card">
                    <img src="{img_src}" class="book-img" alt="{raw_title} 표지">
                    <div class="book-info">
                        <div>
                            <div class="book-title">[{row['순위']}위] {display_title}</div>
                            <div class="book-meta">
                                저자: <strong>{row['저자']}</strong> | 출판사: <strong>{row['출판사']}</strong> | 출판일: {row['출판일']}
                            </div>
                            <div class="book-description">{display_desc}</div>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem;">
                            <div style="font-size: 0.95rem; color: #111827;">
                                판매가: <strong style="color: #2563EB; font-size: 1.1rem;">{sale_price_fmt}</strong> <span style="text-decoration: line-through; color: #9CA3AF; font-size: 0.85rem; margin-left: 0.25rem;">{orig_price_fmt}</span> <strong style="color: #EF4444; font-size: 0.9rem; margin-left: 0.25rem;">{discount_fmt}</strong>
                                | 판매지수: <span style="font-weight: 500; color: #4B5563;">{row['판매지수_값']:,}</span>
                            </div>
                            <a href="{row['링크']}" target="_blank" style="text-decoration: none;">
                                <button style="background-color: #2563EB; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; font-weight: 500; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                                    YES24 상세 보기 ➔
                                </button>
                            </a>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # --- 탭 3: AI 도서 추천 챗봇 ---
    with tab3:
        st.subheader("🤖 AI 도서 추천 챗봇")
        st.write("질문을 입력하시면 예스24 IT/모바일 베스트셀러 도서 목록 내에서 관련 책을 추천해 드립니다.")
        
        # API Key 검증
        if not groq_api_key:
            st.info("💡 챗봇을 이용하시려면 사이드바에서 **Groq API Key**를 입력해 주세요.")
        else:
            # 챗봇 세션 상태 초기화
            if "messages" not in st.session_state:
                st.session_state.messages = []
                
            # 이전 대화 메시지 출력
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    
            # 사용자 입력 처리
            if user_input := st.chat_input("추천받고 싶은 도서 분야나 키워드를 물어보세요! (예: 파이썬 입문책 추천해줘, 클로드 활용 가이드 있나요?)"):
                # 사용자 메시지 렌더링
                with st.chat_message("user"):
                    st.markdown(user_input)
                # 세션에 저장
                st.session_state.messages.append({"role": "user", "content": user_input})
                
                # AI 답변 생성
                with st.chat_message("assistant"):
                    with st.spinner("관련 도서를 검색하고 추천 답변을 생성하고 있습니다..."):
                        # 1. 관련 도서 검색 (ChromaDB 벡터 검색)
                        try:
                            relevant_books = db_manager.search_similar_books(user_input, top_n=5)
                        except Exception as e:
                            # 벡터 검색 중 예외 발생 시 기존 키워드 기반 필터링으로 복구 (안정성 확보)
                            relevant_books = retrieve_relevant_books(user_input, df)
                        
                        # 2. Groq API 호출을 통한 답변 생성
                        ai_response = recommend_books_via_groq(
                            query=user_input, 
                            relevant_books=relevant_books, 
                            api_key=groq_api_key, 
                            model=selected_model,
                            df=df
                        )
                        st.markdown(ai_response)
                        
                # 세션에 저장
                st.session_state.messages.append({"role": "assistant", "content": ai_response})


if __name__ == "__main__":
    main()
