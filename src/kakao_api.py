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
        장소명/주소를 좌표로 변환

        Args:
            place_name: 장소명 또는 주소 (예: "홍대", "강남역", "서울시 강남구")

        Returns:
            좌표 정보 딕셔너리
        """
        # 먼저 키워드 검색으로 장소 찾기
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    KAKAO_KEYWORD_SEARCH_URL,
                    params={"query": place_name, "size": 1},
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()

                documents = data.get("documents", [])
                if documents:
                    place = documents[0]
                    return {
                        "success": True,
                        "x": place.get("x"),
                        "y": place.get("y"),
                        "place_name": place.get("place_name", place_name),
                        "address": place.get("address_name", ""),
                    }

                # 키워드 검색 실패 시 주소 검색 시도
                response = await client.get(
                    KAKAO_ADDRESS_SEARCH_URL,
                    params={"query": place_name},
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()

                documents = data.get("documents", [])
                if documents:
                    addr = documents[0]
                    return {
                        "success": True,
                        "x": addr.get("x"),
                        "y": addr.get("y"),
                        "place_name": place_name,
                        "address": addr.get("address_name", ""),
                    }

                return {
                    "success": False,
                    "error": f"'{place_name}'의 위치를 찾을 수 없습니다.",
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"좌표 변환 오류: {str(e)}",
            }

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
    ) -> dict:
        """
        현재 위치 주변 병원 검색

        Args:
            x: 현재 위치 경도
            y: 현재 위치 위도
            radius: 검색 반경 (미터)
            department: 진료과목 (선택)

        Returns:
            주변 병원 목록
        """
        if department:
            # 진료과목이 있으면 키워드 검색
            result = await self.search_keyword(
                query=f"{department} 병원",
                x=x,
                y=y,
                radius=radius,
                sort="distance",
            )
        else:
            # 진료과목이 없으면 카테고리 검색
            result = await self.search_category(
                category="병원",
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
                "department": department,
                "hospitals": result.get("places", []),
            }

        return result

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
