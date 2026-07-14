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


def main():
    # 데이터 로드
    df = load_and_preprocess_data(DATA_FILE)

    if df.empty:
        st.error("데이터 파일을 찾을 수 없거나 데이터가 비어 있습니다. 먼저 상세 정보 크롤러를 완료해 주세요.")
        st.info(f"확인 경로: {DATA_FILE}")
        return

    # 대시보드 타이틀
    st.markdown('<div class="main-header">YES24 IT/모바일 베스트셀러 대시보드</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">실시간으로 수집된 예스24 IT/모바일 카테고리의 베스트셀러 데이터를 바탕으로 트렌드를 분석하고 도서를 검색합니다.</div>', unsafe_allow_html=True)

    # 탭 구성 (시각화 분석 / 도서 검색)
    tab1, tab2 = st.tabs(["📊 탐색적 데이터 분석 (EDA)", "🔍 키워드 검색 및 도서 상세"])

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


if __name__ == "__main__":
    main()
