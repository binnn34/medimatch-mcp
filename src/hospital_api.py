"""공공데이터포털 병원 정보 API 클라이언트"""
import httpx
from typing import Optional, List
from urllib.parse import quote
from .config import (
    DATA_GO_KR_API_KEY,
    HIRA_HOSPITAL_API_URL,
    DEPARTMENT_CODES,
    SIDO_CODES,
)
from .kakao_api import kakao_client


class HospitalAPIClient:
    """건강보험심사평가원 병원정보서비스 API 클라이언트"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or DATA_GO_KR_API_KEY
        self.base_url = HIRA_HOSPITAL_API_URL

    async def search_hospitals(
        self,
        department: Optional[str] = None,
        sido: Optional[str] = None,
        sigungu: Optional[str] = None,
        hospital_name: Optional[str] = None,
        page: int = 1,
        num_of_rows: int = 10,
    ) -> dict:
        """
        병원 정보 검색

        Args:
            department: 진료과목명 (예: "피부과", "내과")
            sido: 시도명 (예: "서울", "경기")
            sigungu: 시군구명
            hospital_name: 병원명 검색어
            page: 페이지 번호
            num_of_rows: 페이지당 결과 수

        Returns:
            검색 결과 딕셔너리
        """
        params = {
            "serviceKey": self.api_key,
            "pageNo": page,
            "numOfRows": num_of_rows,
            "_type": "json",
        }

        # 진료과목 코드 변환
        if department and department in DEPARTMENT_CODES:
            params["dgsbjtCd"] = DEPARTMENT_CODES[department]

        # 시도 코드 변환
        if sido and sido in SIDO_CODES:
            params["sidoCd"] = SIDO_CODES[sido]

        # 병원명 검색
        if hospital_name:
            params["yadmNm"] = hospital_name

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()

                # API 응답 구조 파싱
                if "response" in data:
                    body = data["response"].get("body", {})
                    items = body.get("items", {})

                    # items가 빈 문자열이거나 None인 경우 처리
                    if not items or items == "":
                        return {
                            "success": True,
                            "total_count": 0,
                            "hospitals": [],
                            "message": "검색 결과가 없습니다.",
                        }

                    hospital_list = items.get("item", [])

                    # 단일 결과인 경우 리스트로 변환
                    if isinstance(hospital_list, dict):
                        hospital_list = [hospital_list]

                    return {
                        "success": True,
                        "total_count": body.get("totalCount", 0),
                        "hospitals": [
                            self._parse_hospital(h) for h in hospital_list
                        ],
                    }
                else:
                    return {
                        "success": False,
                        "error": "API 응답 형식 오류",
                        "hospitals": [],
                    }

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"HTTP 오류: {e.response.status_code}",
                "hospitals": [],
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "error": f"요청 오류: {str(e)}",
                "hospitals": [],
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"알 수 없는 오류: {str(e)}",
                "hospitals": [],
            }

    def _parse_hospital(self, raw_data: dict) -> dict:
        """API 응답 데이터를 정제된 형식으로 변환"""
        name = raw_data.get("yadmNm", "")
        x_pos = raw_data.get("XPos", "")
        y_pos = raw_data.get("YPos", "")

        result = {
            "name": name,
            "address": raw_data.get("addr", ""),
            "phone": raw_data.get("telno", ""),
            "hospital_type": raw_data.get("clCdNm", ""),
            "department": raw_data.get("dgsbjtCdNm", ""),
            "doctors_count": raw_data.get("drTotCnt", 0),
            "specialists_count": raw_data.get("sdrCnt", 0),
            "coordinates": {
                "lat": y_pos,
                "lng": x_pos,
            },
            "sido": raw_data.get("sidoCdNm", ""),
            "sigungu": raw_data.get("sgguCdNm", ""),
            "medical_institution_code": raw_data.get("ykiho", ""),
        }

        # 카카오맵 URL 추가
        if name and x_pos and y_pos:
            result["kakao_map_url"] = kakao_client.generate_map_url(name, x_pos, y_pos)

        return result

    async def search_with_kakao(
        self,
        keyword: str,
        region: Optional[str] = None,
        x: Optional[str] = None,
        y: Optional[str] = None,
        radius: int = 5000,
    ) -> dict:
        """
        카카오 로컬 API를 활용한 병원 검색

        공공데이터와 카카오 데이터를 결합하여 더 풍부한 정보 제공

        Args:
            keyword: 검색 키워드 (질환명, 병원명 등)
            region: 지역명
            x: 중심 좌표 경도
            y: 중심 좌표 위도
            radius: 검색 반경 (미터)

        Returns:
            병원 검색 결과 (카카오맵 URL 포함)
        """
        result = await kakao_client.search_hospitals_by_specialty(
            specialty=keyword,
            region=region,
            x=x,
            y=y,
            radius=radius,
        )

        if result["success"]:
            # 길찾기 URL 추가
            hospitals = result.get("hospitals", [])
            for hospital in hospitals:
                coords = hospital.get("coordinates", {})
                if coords.get("x") and coords.get("y"):
                    hospital["directions_url"] = kakao_client.generate_directions_url(
                        dest_name=hospital.get("name", ""),
                        dest_x=coords["x"],
                        dest_y=coords["y"],
                        origin_x=x,
                        origin_y=y,
                    )

            return {
                "success": True,
                "source": "kakao",
                "keyword": keyword,
                "region": region,
                "total_count": result.get("total_count", 0),
                "hospitals": hospitals,
            }

        return result

    async def search_nearby_with_pharmacy(
        self,
        x: str,
        y: str,
        radius: int = 3000,
        department: Optional[str] = None,
    ) -> dict:
        """
        주변 병원과 약국을 함께 검색

        Args:
            x: 현재 위치 경도
            y: 현재 위치 위도
            radius: 검색 반경 (미터)
            department: 진료과목 (선택)

        Returns:
            주변 병원 및 약국 목록
        """
        # 병원과 약국을 병렬로 검색
        hospital_result = await kakao_client.get_nearby_hospitals(
            x=x,
            y=y,
            radius=radius,
            department=department,
        )

        pharmacy_result = await kakao_client.get_nearby_pharmacies(
            x=x,
            y=y,
            radius=min(radius, 2000),  # 약국은 더 가까운 반경
        )

        return {
            "success": True,
            "location": {"x": x, "y": y},
            "radius": radius,
            "hospitals": hospital_result.get("hospitals", []) if hospital_result["success"] else [],
            "pharmacies": pharmacy_result.get("pharmacies", []) if pharmacy_result["success"] else [],
        }


# 싱글톤 인스턴스
hospital_client = HospitalAPIClient()
