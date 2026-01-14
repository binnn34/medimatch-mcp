"""카카오 로컬 API 클라이언트"""
import httpx
from typing import Optional, List
from urllib.parse import quote
from .config import (
    KAKAO_REST_API_KEY,
    KAKAO_KEYWORD_SEARCH_URL,
    KAKAO_CATEGORY_SEARCH_URL,
    KAKAO_ADDRESS_SEARCH_URL,
    KAKAO_CATEGORY_CODES,
    DEFAULT_LOCATION,
)


class KakaoLocalAPIClient:
    """카카오 로컬 API 클라이언트

    병원/약국 검색 및 위치 기반 서비스 제공
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or KAKAO_REST_API_KEY
        self.headers = {"Authorization": f"KakaoAK {self.api_key}"}

    async def get_coordinates_from_place(self, place_name: str) -> dict:
        """
        장소명/주소를 좌표로 변환 (다양한 검색 전략 적용)

        Args:
            place_name: 장소명 또는 주소 (예: "홍대", "강남역", "광주 첨단", "서울시 강남구")

        Returns:
            좌표 정보 딕셔너리
        """
        # 검색어 전처리
        normalized_name = self._normalize_place_name(place_name)
        search_queries = self._generate_search_queries(normalized_name)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 1단계: 다양한 검색어로 키워드 검색 시도
                for query in search_queries:
                    response = await client.get(
                        KAKAO_KEYWORD_SEARCH_URL,
                        params={"query": query, "size": 5},
                        headers=self.headers,
                    )
                    response.raise_for_status()
                    data = response.json()

                    documents = data.get("documents", [])
                    if documents:
                        # 가장 적합한 결과 선택 (지역/장소 우선)
                        place = self._select_best_place(documents, normalized_name)
                        return {
                            "success": True,
                            "x": place.get("x"),
                            "y": place.get("y"),
                            "place_name": place.get("place_name", place_name),
                            "address": place.get("address_name", ""),
                            "search_query_used": query,
                        }

                # 2단계: 주소 검색 시도
                for query in search_queries:
                    response = await client.get(
                        KAKAO_ADDRESS_SEARCH_URL,
                        params={"query": query},
                        headers=self.headers,
                    )
                    response.raise_for_status()
                    data = response.json()

                    documents = data.get("documents", [])
                    if documents:
                        addr = documents[0]
                        # address 응답 구조가 다름
                        x = addr.get("x") or addr.get("address", {}).get("x") or addr.get("road_address", {}).get("x")
                        y = addr.get("y") or addr.get("address", {}).get("y") or addr.get("road_address", {}).get("y")

                        if x and y:
                            return {
                                "success": True,
                                "x": x,
                                "y": y,
                                "place_name": place_name,
                                "address": addr.get("address_name", ""),
                                "search_query_used": query,
                            }

                # 3단계: 지역명 매핑 시도
                mapped_location = self._get_region_coordinates(normalized_name)
                if mapped_location:
                    return mapped_location

                return {
                    "success": False,
                    "error": f"'{place_name}'의 위치를 찾을 수 없습니다.",
                    "tried_queries": search_queries,
                    "suggestion": "더 구체적인 장소명을 입력해주세요. (예: '홍대입구역', '광주광역시 첨단동')",
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"좌표 변환 오류: {str(e)}",
            }

    def _normalize_place_name(self, place_name: str) -> str:
        """장소명 정규화"""
        # 공백 정리
        normalized = " ".join(place_name.split())

        # 일반적인 표현 변환
        replacements = {
            "근처": "",
            "주변": "",
            "부근": "",
            "쪽": "",
            "에서": "",
            "동네": "",
        }
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)

        return normalized.strip()

    def _generate_search_queries(self, place_name: str) -> list:
        """다양한 검색 쿼리 생성"""
        queries = [place_name]

        # 지역 매핑 (세부 지역명)
        region_mappings = {
            # 광주
            "광주 첨단": ["광주광역시 첨단동", "광주 첨단지구", "첨단역"],
            "첨단": ["광주광역시 첨단동", "광주 첨단지구", "첨단역"],
            "광주 상무": ["광주광역시 상무지구", "상무역", "광주 상무동"],
            "광주 충장로": ["광주광역시 충장로", "충장로역"],
            "광주 금남로": ["광주광역시 금남로", "금남로역"],

            # 서울
            "홍대": ["홍대입구역", "홍익대학교", "마포구 서교동"],
            "홍대입구": ["홍대입구역", "마포구 서교동"],
            "강남": ["강남역", "강남구청", "서울 강남구"],
            "강남역": ["강남역", "서울 강남구 역삼동"],
            "신촌": ["신촌역", "연세대학교", "서대문구 신촌동"],
            "건대": ["건대입구역", "건국대학교", "광진구 화양동"],
            "혜화": ["혜화역", "대학로", "종로구 혜화동"],
            "이태원": ["이태원역", "용산구 이태원동"],
            "명동": ["명동역", "중구 명동"],
            "종로": ["종로역", "종로구", "서울 종로"],
            "신림": ["신림역", "관악구 신림동"],
            "사당": ["사당역", "동작구 사당동"],
            "잠실": ["잠실역", "송파구 잠실동"],
            "여의도": ["여의도역", "영등포구 여의도동"],
            "영등포": ["영등포역", "영등포구"],
            "왕십리": ["왕십리역", "성동구 왕십리동"],
            "동대문": ["동대문역", "동대문구"],
            "서울역": ["서울역", "중구 남대문로"],
            "용산": ["용산역", "용산구"],

            # 경기
            "판교": ["판교역", "성남시 분당구 판교동"],
            "분당": ["분당구", "성남시 분당구", "서현역"],
            "수원": ["수원역", "수원시청", "경기도 수원시"],
            "일산": ["일산역", "고양시 일산", "일산동구"],
            "부천": ["부천역", "부천시청", "경기도 부천시"],
            "안양": ["안양역", "안양시청", "경기도 안양시"],
            "의정부": ["의정부역", "의정부시청"],
            "평택": ["평택역", "평택시청"],

            # 부산
            "서면": ["서면역", "부산 부산진구 서면"],
            "해운대": ["해운대역", "부산 해운대구"],
            "광안리": ["광안리해수욕장", "부산 수영구 광안리"],
            "부산역": ["부산역", "부산 동구"],
            "센텀시티": ["센텀시티역", "부산 해운대구 우동"],
            "남포동": ["남포역", "부산 중구 남포동"],

            # 대구
            "동성로": ["동성로", "대구 중구 동성로"],
            "대구역": ["대구역", "대구 북구"],
            "수성구": ["수성구청역", "대구 수성구"],

            # 대전
            "둔산": ["둔산동", "대전 서구 둔산동"],
            "대전역": ["대전역", "대전 동구"],
            "유성": ["유성구", "대전 유성구"],

            # 인천
            "부평": ["부평역", "인천 부평구"],
            "송도": ["송도역", "인천 연수구 송도동"],
            "인천역": ["인천역", "인천 중구"],

            # 제주
            "제주시": ["제주시청", "제주특별자치도 제주시"],
            "서귀포": ["서귀포시청", "제주특별자치도 서귀포시"],
            "애월": ["애월읍", "제주시 애월읍"],
        }

        # 매핑된 쿼리 추가
        for key, values in region_mappings.items():
            if key in place_name or place_name in key:
                queries.extend(values)
                break

        # 역 추가 (역이 없으면)
        if "역" not in place_name and len(place_name) <= 4:
            queries.append(f"{place_name}역")

        # 시/구/동 추가
        if not any(suffix in place_name for suffix in ["시", "구", "동", "읍", "면", "리"]):
            queries.append(f"{place_name}동")
            queries.append(f"{place_name}구")

        # 중복 제거하면서 순서 유지
        seen = set()
        unique_queries = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique_queries.append(q)

        return unique_queries

    def _select_best_place(self, documents: list, original_query: str) -> dict:
        """검색 결과에서 가장 적합한 장소 선택"""
        if not documents:
            return {}

        # 우선순위: 지하철역 > 행정구역 > 랜드마크 > 일반장소
        priority_keywords = ["역", "시청", "구청", "동사무소", "터미널", "공원"]

        for keyword in priority_keywords:
            for doc in documents:
                place_name = doc.get("place_name", "")
                category = doc.get("category_name", "")
                if keyword in place_name or "교통" in category or "지하철" in category:
                    return doc

        # 우선순위에 맞는 게 없으면 첫 번째 결과 반환
        return documents[0]

    def _get_region_coordinates(self, place_name: str) -> Optional[dict]:
        """주요 지역의 기본 좌표 반환 (폴백용)"""
        # 광역시/도 및 주요 지역 좌표
        region_coords = {
            # 서울 주요 지역
            "홍대": {"x": "126.9236", "y": "37.5563", "name": "홍대입구역"},
            "강남": {"x": "127.0276", "y": "37.4979", "name": "강남역"},
            "신촌": {"x": "126.9368", "y": "37.5550", "name": "신촌역"},
            "건대": {"x": "127.0702", "y": "37.5403", "name": "건대입구역"},
            "잠실": {"x": "127.1001", "y": "37.5133", "name": "잠실역"},
            "여의도": {"x": "126.9245", "y": "37.5217", "name": "여의도역"},
            "명동": {"x": "126.9857", "y": "37.5636", "name": "명동역"},
            "종로": {"x": "126.9832", "y": "37.5700", "name": "종로역"},
            "서울역": {"x": "126.9725", "y": "37.5547", "name": "서울역"},

            # 광주
            "광주 첨단": {"x": "126.8489", "y": "35.2210", "name": "광주 첨단지구"},
            "첨단": {"x": "126.8489", "y": "35.2210", "name": "광주 첨단지구"},
            "광주 상무": {"x": "126.8595", "y": "35.1527", "name": "광주 상무지구"},
            "광주": {"x": "126.8526", "y": "35.1595", "name": "광주광역시"},

            # 부산
            "서면": {"x": "129.0596", "y": "35.1578", "name": "서면역"},
            "해운대": {"x": "129.1604", "y": "35.1631", "name": "해운대역"},
            "부산": {"x": "129.0756", "y": "35.1796", "name": "부산역"},

            # 대구
            "동성로": {"x": "128.5968", "y": "35.8686", "name": "동성로"},
            "대구": {"x": "128.6014", "y": "35.8714", "name": "대구역"},

            # 대전
            "둔산": {"x": "127.3845", "y": "36.3550", "name": "둔산동"},
            "대전": {"x": "127.4339", "y": "36.3326", "name": "대전역"},

            # 인천
            "부평": {"x": "126.7235", "y": "37.4908", "name": "부평역"},
            "송도": {"x": "126.6568", "y": "37.3863", "name": "송도역"},
            "인천": {"x": "126.7052", "y": "37.4563", "name": "인천역"},

            # 경기
            "판교": {"x": "127.1114", "y": "37.3948", "name": "판교역"},
            "분당": {"x": "127.1284", "y": "37.3780", "name": "서현역"},
            "수원": {"x": "127.0012", "y": "37.2660", "name": "수원역"},
            "일산": {"x": "126.7698", "y": "37.6558", "name": "일산역"},

            # 제주
            "제주": {"x": "126.5312", "y": "33.4996", "name": "제주시청"},
            "서귀포": {"x": "126.5102", "y": "33.2531", "name": "서귀포시청"},
        }

        for key, coords in region_coords.items():
            if key in place_name or place_name in key:
                return {
                    "success": True,
                    "x": coords["x"],
                    "y": coords["y"],
                    "place_name": coords["name"],
                    "address": "",
                    "source": "region_mapping",
                }

        return None

    def get_default_location(self) -> dict:
        """기본 위치(서울 시청) 반환"""
        return {
            "success": True,
            "x": DEFAULT_LOCATION["x"],
            "y": DEFAULT_LOCATION["y"],
            "place_name": DEFAULT_LOCATION["name"],
            "address": "서울특별시 중구 세종대로 110",
        }

    async def search_keyword(
        self,
        query: str,
        x: Optional[str] = None,
        y: Optional[str] = None,
        radius: int = 5000,
        page: int = 1,
        size: int = 15,
        sort: str = "accuracy",
    ) -> dict:
        """
        키워드로 장소 검색

        Args:
            query: 검색 키워드 (예: "아토피 피부과", "강남 내과")
            x: 중심 좌표 경도 (longitude)
            y: 중심 좌표 위도 (latitude)
            radius: 검색 반경 (미터, 최대 20000)
            page: 페이지 번호 (1-45)
            size: 한 페이지 결과 수 (1-15)
            sort: 정렬 기준 (accuracy: 정확도순, distance: 거리순)

        Returns:
            검색 결과 딕셔너리
        """
        params = {
            "query": query,
            "page": page,
            "size": size,
            "sort": sort,
        }

        # 위치 기반 검색
        if x and y:
            params["x"] = x
            params["y"] = y
            params["radius"] = min(radius, 20000)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    KAKAO_KEYWORD_SEARCH_URL,
                    params=params,
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()

                places = data.get("documents", [])
                meta = data.get("meta", {})

                return {
                    "success": True,
                    "total_count": meta.get("total_count", 0),
                    "is_end": meta.get("is_end", True),
                    "places": [self._parse_place(p) for p in places],
                }

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"HTTP 오류: {e.response.status_code}",
                "places": [],
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "error": f"요청 오류: {str(e)}",
                "places": [],
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"알 수 없는 오류: {str(e)}",
                "places": [],
            }

    async def search_category(
        self,
        category: str = "병원",
        x: Optional[str] = None,
        y: Optional[str] = None,
        radius: int = 5000,
        page: int = 1,
        size: int = 15,
        sort: str = "distance",
    ) -> dict:
        """
        카테고리로 장소 검색 (병원, 약국)

        Args:
            category: 카테고리 ("병원" 또는 "약국")
            x: 중심 좌표 경도 (longitude) - 필수
            y: 중심 좌표 위도 (latitude) - 필수
            radius: 검색 반경 (미터, 최대 20000)
            page: 페이지 번호 (1-45)
            size: 한 페이지 결과 수 (1-15)
            sort: 정렬 기준 (accuracy: 정확도순, distance: 거리순)

        Returns:
            검색 결과 딕셔너리
        """
        if not x or not y:
            return {
                "success": False,
                "error": "카테고리 검색은 좌표(x, y)가 필수입니다.",
                "places": [],
            }

        category_code = KAKAO_CATEGORY_CODES.get(category, "HP8")

        params = {
            "category_group_code": category_code,
            "x": x,
            "y": y,
            "radius": min(radius, 20000),
            "page": page,
            "size": size,
            "sort": sort,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    KAKAO_CATEGORY_SEARCH_URL,
                    params=params,
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()

                places = data.get("documents", [])
                meta = data.get("meta", {})

                return {
                    "success": True,
                    "total_count": meta.get("total_count", 0),
                    "is_end": meta.get("is_end", True),
                    "places": [self._parse_place(p) for p in places],
                }

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"HTTP 오류: {e.response.status_code}",
                "places": [],
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "error": f"요청 오류: {str(e)}",
                "places": [],
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"알 수 없는 오류: {str(e)}",
                "places": [],
            }

    async def search_hospitals_by_specialty(
        self,
        specialty: str,
        region: Optional[str] = None,
        x: Optional[str] = None,
        y: Optional[str] = None,
        radius: int = 10000,
    ) -> dict:
        """
        전문 분야로 병원 검색

        Args:
            specialty: 전문 분야/질환 (예: "아토피", "당뇨", "척추")
            region: 지역명 (예: "강남", "서울", "부산")
            x: 중심 좌표 경도
            y: 중심 좌표 위도
            radius: 검색 반경 (미터)

        Returns:
            전문 병원 검색 결과
        """
        # 검색 쿼리 구성
        query_parts = [specialty]
        if region:
            query_parts.append(region)
        query_parts.append("병원")

        query = " ".join(query_parts)

        result = await self.search_keyword(
            query=query,
            x=x,
            y=y,
            radius=radius,
            size=15,
            sort="accuracy",
        )

        if result["success"]:
            # 병원 카테고리만 필터링
            hospitals = [
                p for p in result["places"]
                if "병원" in p.get("category", "") or "의원" in p.get("category", "")
            ]

            return {
                "success": True,
                "specialty": specialty,
                "region": region,
                "total_count": len(hospitals),
                "hospitals": hospitals,
            }

        return result

    async def get_nearby_hospitals(
        self,
        x: str,
        y: str,
        radius: int = 3000,
        department: Optional[str] = None,
        size: int = 15,
    ) -> dict:
        """
        현재 위치 주변 병원 검색 (개인병원/의원 포함)

        Args:
            x: 현재 위치 경도
            y: 현재 위치 위도
            radius: 검색 반경 (미터)
            department: 진료과목 (선택)
            size: 결과 개수 (기본 15, 최대 15)

        Returns:
            주변 병원 목록 (거리순, 개인병원/의원 포함)
        """
        all_hospitals = []

        if department:
            # 진료과목이 있으면 다양한 검색어로 검색
            search_queries = [
                f"{department}",           # "피부과"
                f"{department} 의원",       # "피부과 의원"
                f"{department} 병원",       # "피부과 병원"
                f"{department} 클리닉",     # "피부과 클리닉"
            ]

            for query in search_queries:
                result = await self.search_keyword(
                    query=query,
                    x=x,
                    y=y,
                    radius=radius,
                    size=15,
                    sort="distance",
                )
                if result["success"]:
                    for place in result.get("places", []):
                        # 중복 제거 (ID 기준)
                        if not any(h.get("id") == place.get("id") for h in all_hospitals):
                            all_hospitals.append(place)

            # 거리순 정렬
            all_hospitals.sort(key=lambda h: float(h.get("distance") or "999999"))

        else:
            # 진료과목이 없으면 카테고리 검색 (모든 병원/의원)
            result = await self.search_category(
                category="병원",
                x=x,
                y=y,
                radius=radius,
                size=15,
                sort="distance",
            )
            if result["success"]:
                all_hospitals = result.get("places", [])

        # 결과 제한
        all_hospitals = all_hospitals[:size] if size else all_hospitals[:15]

        return {
            "success": True,
            "location": {"x": x, "y": y},
            "radius": radius,
            "department": department,
            "hospitals": all_hospitals,
        }

    async def get_nearby_pharmacies(
        self,
        x: str,
        y: str,
        radius: int = 2000,
    ) -> dict:
        """
        현재 위치 주변 약국 검색

        Args:
            x: 현재 위치 경도
            y: 현재 위치 위도
            radius: 검색 반경 (미터)

        Returns:
            주변 약국 목록
        """
        result = await self.search_category(
            category="약국",
            x=x,
            y=y,
            radius=radius,
            sort="distance",
        )

        if result["success"]:
            return {
                "success": True,
                "location": {"x": x, "y": y},
                "radius": radius,
                "pharmacies": result.get("places", []),
            }

        return result

    def _parse_place(self, raw_data: dict) -> dict:
        """카카오 API 응답 데이터를 정제된 형식으로 변환"""
        return {
            "id": raw_data.get("id", ""),
            "name": raw_data.get("place_name", ""),
            "category": raw_data.get("category_name", ""),
            "phone": raw_data.get("phone", ""),
            "address": raw_data.get("address_name", ""),
            "road_address": raw_data.get("road_address_name", ""),
            "coordinates": {
                "x": raw_data.get("x", ""),
                "y": raw_data.get("y", ""),
            },
            "distance": raw_data.get("distance", ""),
            "kakao_map_url": raw_data.get("place_url", ""),
        }

    def generate_map_url(self, place_name: str, x: str, y: str) -> str:
        """카카오맵 URL 생성"""
        encoded_name = quote(place_name)
        return f"https://map.kakao.com/link/map/{encoded_name},{y},{x}"

    def generate_directions_url(
        self,
        dest_name: str,
        dest_x: str,
        dest_y: str,
        origin_x: Optional[str] = None,
        origin_y: Optional[str] = None,
    ) -> str:
        """카카오맵 길찾기 URL 생성"""
        encoded_name = quote(dest_name)
        if origin_x and origin_y:
            return f"https://map.kakao.com/link/to/{encoded_name},{dest_y},{dest_x}/from/{origin_y},{origin_x}"
        return f"https://map.kakao.com/link/to/{encoded_name},{dest_y},{dest_x}"


# 싱글톤 인스턴스
kakao_client = KakaoLocalAPIClient()
