"""ChromaDB 및 klue-bert-base 기반 임베딩 추출/검색 모듈.

이 모듈은 예스24 IT/모바일 베스트셀러 도서 데이터를 벡터화하고,
로컬 ChromaDB에 적재하여 자연어 질의에 대한 유사도 기반 시맨틱 검색 기능을 제공합니다.
"""

import os
import torch
import pandas as pd
from transformers import AutoTokenizer, AutoModel
import chromadb

class EmbeddingManager:
    """klue/bert-base 모델을 사용하여 텍스트 데이터의 임베딩 벡터를 추출하는 클래스입니다."""

    def __init__(self, model_name: str = "klue/bert-base"):
        """모델 및 토크나이저를 초기화하고 사용 가능한 장치(CPU/CUDA)를 설정합니다.

        Args:
            model_name (str): 사용할 허깅페이스 사전학습 모델명 (기본값: "klue/bert-base")
        """
        # CUDA 사용 가능 여부를 판별하여 최적의 장치 할당
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # 한국어 임베딩 전용 모델 및 토크나이저 로드
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device)
        self.model.eval()  # 추론 모드로 전환

    def get_embeddings(self, texts: list) -> list:
        """입력된 텍스트 리스트에 대해 klue/bert-base 모델의 Mean Pooling 임베딩 벡터를 계산합니다.

        Args:
            texts (list): 임베딩을 추출할 문자열들의 리스트

        Returns:
            list: 각 문자열의 768차원 임베딩 벡터 리스트
        """
        embeddings = []
        for text in texts:
            # 입력 텍스트 토크나이징 및 패딩, 트렁케이션 처리 (최대 길이 512)
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
            
            # Mean Pooling: 패딩 토큰을 제외한 어텐션 마스크 영역의 평균 벡터를 구함
            attention_mask = inputs['attention_mask']
            token_embeddings = outputs.last_hidden_state  # [batch_size, sequence_length, hidden_size]
            
            # 차원 맞추기
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
            sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            
            # 평균 풀링된 768차원 벡터 계산
            mean_pooled = sum_embeddings / sum_mask
            
            # 리스트 형태로 변환하여 결과에 추가
            embeddings.append(mean_pooled[0].cpu().tolist())
            
        return embeddings


class ChromaDBManager:
    """ChromaDB 로컬 저장소를 활용하여 도서 데이터를 관리하고 검색하는 클래스입니다."""

    def __init__(self, db_dir: str = None, collection_name: str = "yes24_books"):
        """ChromaDB PersistentClient를 설정하고 컬렉션을 가져오거나 생성합니다.

        Args:
            db_dir (str, optional): DB 저장 경로 (기본값은 프로젝트 root/data/chroma_db)
            collection_name (str): 사용할 컬렉션 이름 (기본값: "yes24_books")
        """
        if db_dir is None:
            # 기본 경로를 패키지 기준의 프로젝트 root/data/chroma_db로 설정
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_dir = os.path.join(project_root, "data", "chroma_db")
        
        self.db_dir = db_dir
        self.collection_name = collection_name
        
        # 디렉터리가 없으면 자동 생성
        os.makedirs(db_dir, exist_ok=True)
        
        # 로컬 영속성(Persistent) 클라이언트 생성
        self.client = chromadb.PersistentClient(path=db_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}  # 코사인 유사도 방식을 사용한 벡터 매칭
        )
        
        # 임베딩 매니저는 실제 임베딩 계산이 발생할 때 최초 1회 지연 초기화(Lazy Loading)
        self.emb_manager = None

    def _init_embedding_manager(self):
        """임베딩 추출기를 메모리에 최초 로딩합니다."""
        if self.emb_manager is None:
            self.emb_manager = EmbeddingManager()

    def has_data(self) -> bool:
        """현재 데이터베이스 컬렉션에 등록된 도서가 존재하는지 확인합니다.

        Returns:
            bool: 도서가 있으면 True, 비어있으면 False
        """
        return self.collection.count() > 0

    def add_books(self, df: pd.DataFrame, progress_callback=None):
        """도서 데이터프레임을 받아 임베딩을 생성한 후 벡터 DB에 추가합니다.

        Args:
            df (pd.DataFrame): 예스24 베스트셀러 도서 데이터프레임
            progress_callback (callable, optional): 진행 상태를 업데이트할 콜백 함수 (현재_진행수, 총_개수, 메시지)
        """
        self._init_embedding_manager()
        
        ids = []
        documents = []
        metadatas = []
        
        total = len(df)
        
        for idx, row in df.iterrows():
            book_id = str(row.get("순위", idx))
            title = str(row.get("도서명", ""))
            author = str(row.get("저자", ""))
            publisher = str(row.get("출판사", ""))
            desc = str(row.get("내용", ""))
            
            # 시맨틱 검색을 최적화하기 위한 임베딩 대상 원문 결합
            combined_text = f"도서명: {title} | 저자: {author} | 출판사: {publisher} | 내용: {desc}"
            
            ids.append(book_id)
            documents.append(combined_text)
            
            # 메타데이터 값 정제 (None 입력 방지 및 문자열 변환)
            metadata = {
                "rank": int(row.get("순위", 0)),
                "title": title,
                "author": author,
                "publisher": publisher,
                "pub_date": str(row.get("출판일", "")),
                "sale_price": int(row.get("판매가", 0)),
                "link": str(row.get("링크", "")),
                "description": desc[:500]  # ChromaDB 메타데이터 크기 초과 방지를 위한 컷오프
            }
            metadatas.append(metadata)
            
            if progress_callback:
                # 임베딩 생성 시작 전 진행률 표기
                progress_callback(idx, total, f"'{title}' 도서 정보 준비 중...")
        
        # 대량의 텍스트에 대한 임베딩 벡터 생성
        embeddings = []
        for i, doc in enumerate(documents):
            emb = self.emb_manager.get_embeddings([doc])[0]
            embeddings.append(emb)
            if progress_callback:
                progress_callback(i + 1, total, f"'{metadatas[i]['title']}' 임베딩 생성 및 분석 완료 ({i+1}/{total})")
        
        # 벡터 DB에 데이터 추가
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

    def search_similar_books(self, query: str, top_n: int = 5) -> list:
        """질문을 임베딩한 후 벡터 DB에서 Cosine 유사도가 가장 높은 상위 N개의 도서 목록을 검색합니다.

        Args:
            query (str): 사용자 검색어 또는 질문
            top_n (int): 반환할 도서의 개수 (기본값: 5)

        Returns:
            list: 유사 도서 메타데이터 딕셔너리 리스트
        """
        self._init_embedding_manager()
        
        # 질의어 임베딩 추출
        query_vector = self.emb_manager.get_embeddings([query])[0]
        
        # 유사 벡터 쿼리 수행
        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_n
        )
        
        books_list = []
        if results and "metadatas" in results and len(results["metadatas"]) > 0:
            # 쿼리 결과에서 첫 번째 질문 결과의 메타데이터 파싱
            for meta in results["metadatas"][0]:
                books_list.append({
                    "순위": meta.get("rank", 0),
                    "도서명": meta.get("title", ""),
                    "저자": meta.get("author", ""),
                    "출판사": meta.get("publisher", ""),
                    "출판일": meta.get("pub_date", ""),
                    "판매가": meta.get("sale_price", 0),
                    "내용": meta.get("description", ""),
                    "링크": meta.get("link", "")
                })
                
        return books_list
