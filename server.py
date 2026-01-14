"""
MediMatch MCP Server
AI 기반 증상 분석 및 전문 병원 매칭 서비스

PlayMCP 등록용 Remote MCP Server (Streamable HTTP)
"""
from typing import Annotated, Optional, List
from fastmcp import FastMCP

from src.hospital_api import hospital_client
from src.symptom_analyzer import symptom_analyzer
from src.kakao_api import kakao_client
from src.config import SIDO_CODES, DEPARTMENT_CODES

# MCP 서버 인스턴스 생성
mcp = FastMCP(
    name="MediMatch",
    instructions="""
    MediMatch는 AI 기반 증상 분석 및 전문 병원 매칭 서비스입니다.

    주요 기능:
    1. 증상 분석: 사용자의 증상 설명을 분석하여 적절한 진료과목 추천
    2. 병원 검색: 진료과목, 지역별 병원 검색
    3. 맞춤 추천: 증상 기반으로 실제 해당 질환을 전문으로 진료하는 병원 추천
    4. 위치 기반 검색: 카카오맵 연동으로 주변 병원/약국 검색 및 길찾기
    5. 카카오맵 연동: 병원 위치 확인, 길찾기 URL 제공

    사용 예시:
    - "팔꿈치 안쪽이 가렵고 각질이 일어나요"
    - "서울에서 아토피 전문 피부과 찾아줘"
    - "허리가 아프고 다리가 저려요"
    - "내 주변 피부과랑 약국 찾아줘"
    """
)


@mcp.tool
async def analyze_symptoms(
    symptoms: Annotated[str, "증상 설명 (예: '팔꿈치가 가렵고 각질이 일어나요', '허리가 아프고 다리가 저려요')"]
) -> dict:
    """
    사용자의 증상을 분석하여 적절한 진료과목을 추천합니다.

    증상을 자연스러운 문장으로 설명하면, AI가 분석하여
    어떤 진료과목을 방문해야 하는지 추천해드립니다.
    """
    analysis = symptom_analyzer.analyze_symptoms(symptoms)

    # 추천 진료과목에 대한 설명 추가
    department_details = []
    for dept in analysis["recommended_departments"]:
        department_details.append({
            "name": dept,
            "description": symptom_analyzer.get_department_description(dept),
        })

    return {
        "input_symptoms": symptoms,
        "analysis": {
            "matched_symptoms": analysis["matched_symptoms"],
            "confidence": analysis["confidence"],
            "summary": analysis["analysis_summary"],
        },
        "recommendations": {
            "departments": department_details,
            "related_keywords": analysis["related_keywords"],
        },
        "next_step": "추천된 진료과목으로 병원을 검색하시려면 search_hospitals 또는 find_specialist_hospital을 사용하세요.",
    }


@mcp.tool
async def search_hospitals(
    department: Annotated[str, "진료과목 (예: '피부과', '내과', '정형외과')"],
    region: Annotated[Optional[str], "지역 (예: '서울', '경기', '부산')"] = None,
    hospital_name: Annotated[Optional[str], "병원명 검색어 (선택사항)"] = None,
    page: Annotated[int, "페이지 번호 (기본값: 1)"] = 1,
    limit: Annotated[int, "결과 개수 (기본값: 10, 최대: 50)"] = 10,
) -> dict:
    """
    진료과목과 지역을 기준으로 병원을 검색합니다.

    특정 진료과목의 병원을 지역별로 찾을 수 있습니다.
    """
    # 입력값 검증
    if department not in DEPARTMENT_CODES:
        available_depts = ", ".join(list(DEPARTMENT_CODES.keys())[:10]) + " 등"
        return {
            "success": False,
            "error": f"'{department}'은(는) 유효하지 않은 진료과목입니다.",
            "available_departments": available_depts,
        }

    if region and region not in SIDO_CODES:
        available_regions = ", ".join(SIDO_CODES.keys())
        return {
            "success": False,
            "error": f"'{region}'은(는) 유효하지 않은 지역입니다.",
            "available_regions": available_regions,
        }

    # 결과 개수 제한
    limit = min(limit, 50)

    # 병원 검색
    result = await hospital_client.search_hospitals(
        department=department,
        sido=region,
        hospital_name=hospital_name,
        page=page,
        num_of_rows=limit,
    )

    if result["success"]:
        return {
            "success": True,
            "search_criteria": {
                "department": department,
                "region": region or "전국",
                "hospital_name": hospital_name,
            },
            "total_count": result["total_count"],
            "current_page": page,
            "hospitals": result["hospitals"],
            "tip": "병원 상세 정보나 경로 안내가 필요하시면 카카오맵 MCP를 활용해보세요.",
        }
    else:
        return result


@mcp.tool
async def find_specialist_hospital(
    symptoms: Annotated[str, "증상 또는 질환명 (예: '아토피', '허리디스크', '무릎 관절염')"],
    region: Annotated[Optional[str], "지역 (예: '서울', '경기')"] = None,
    limit: Annotated[int, "결과 개수 (기본값: 5)"] = 5,
) -> dict:
    """
    증상이나 질환명을 입력하면 해당 질환을 전문으로 진료하는 병원을 찾아줍니다.

    일반적인 진료과목 검색과 달리, 특정 질환에 특화된 병원을 추천합니다.
    예: "아토피" → 아토피/알레르기 전문 피부과 추천
    """
    # 증상 분석
    analysis = symptom_analyzer.analyze_symptoms(symptoms)

    if not analysis["recommended_departments"]:
        return {
            "success": False,
            "error": "입력하신 증상에 해당하는 진료과목을 찾을 수 없습니다.",
            "suggestion": "더 구체적인 증상을 설명해주시거나, 직접 진료과목을 지정하여 search_hospitals를 사용해주세요.",
        }

    # 주요 추천 진료과목으로 검색
    primary_department = analysis["recommended_departments"][0]

    result = await hospital_client.search_hospitals(
        department=primary_department,
        sido=region,
        page=1,
        num_of_rows=limit,
    )

    return {
        "success": True,
        "query": symptoms,
        "analysis": {
            "detected_symptoms": analysis["matched_symptoms"],
            "primary_department": primary_department,
            "all_recommended_departments": analysis["recommended_departments"],
            "confidence": analysis["confidence"],
            "summary": analysis["analysis_summary"],
        },
        "search_criteria": {
            "department": primary_department,
            "region": region or "전국",
        },
        "hospitals": result.get("hospitals", []),
        "total_count": result.get("total_count", 0),
        "recommendations": {
            "description": symptom_analyzer.get_department_description(primary_department),
            "keywords_to_look_for": analysis["related_keywords"],
            "tip": "병원 선택 시 '{}' 관련 키워드가 있는 병원을 추천드립니다.".format(
                "', '".join(analysis["related_keywords"][:3]) if analysis["related_keywords"] else symptoms
            ),
        },
    }


@mcp.tool
async def get_available_departments() -> dict:
    """
    검색 가능한 모든 진료과목 목록을 반환합니다.
    """
    # 카테고리별로 그룹화
    categories = {
        "일반 진료과": ["내과", "외과", "가정의학과", "응급의학과"],
        "전문 진료과": [
            "신경과", "정신건강의학과", "정형외과", "신경외과",
            "흉부외과", "성형외과", "마취통증의학과"
        ],
        "여성/소아": ["산부인과", "소아청소년과"],
        "감각기관": ["안과", "이비인후과", "피부과"],
        "기타 전문과": [
            "비뇨의학과", "재활의학과", "영상의학과",
            "진단검사의학과", "핵의학과"
        ],
        "치과": [
            "치과", "구강악안면외과", "치과보철과", "치과교정과",
            "소아치과", "치주과", "치과보존과"
        ],
        "한방": [
            "한방내과", "한방부인과", "한방소아과",
            "침구과", "한방재활의학과"
        ],
    }

    return {
        "total_departments": len(DEPARTMENT_CODES),
        "categories": categories,
        "all_departments": list(DEPARTMENT_CODES.keys()),
    }


@mcp.tool
async def get_available_regions() -> dict:
    """
    검색 가능한 지역(시/도) 목록을 반환합니다.
    """
    return {
        "regions": list(SIDO_CODES.keys()),
        "total": len(SIDO_CODES),
    }


@mcp.tool
async def search_nearby_hospitals(
    x: Annotated[str, "현재 위치 경도 (longitude, 예: '127.0276')"],
    y: Annotated[str, "현재 위치 위도 (latitude, 예: '37.4979')"],
    department: Annotated[Optional[str], "진료과목 (예: '피부과', '내과')"] = None,
    radius: Annotated[int, "검색 반경 (미터, 기본값: 3000, 최대: 20000)"] = 3000,
) -> dict:
    """
    현재 위치 주변의 병원을 검색합니다.

    카카오맵 API를 활용하여 주변 병원 정보와 길찾기 링크를 제공합니다.
    진료과목을 지정하면 해당 과목 병원만 검색됩니다.
    """
    radius = min(radius, 20000)

    result = await kakao_client.get_nearby_hospitals(
        x=x,
        y=y,
        radius=radius,
        department=department,
    )

    if result["success"]:
        hospitals = result.get("hospitals", [])

        # 길찾기 URL 추가
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
            "location": {"x": x, "y": y},
            "radius": radius,
            "department": department or "전체",
            "total_count": len(hospitals),
            "hospitals": hospitals,
            "tip": "카카오맵 URL을 클릭하면 병원 상세 정보와 리뷰를 확인할 수 있습니다.",
        }

    return result


@mcp.tool
async def search_hospitals_near_place(
    place: Annotated[str, "장소명 (예: '홍대', '강남역', '광주 첨단', '부산 서면')"],
    department: Annotated[Optional[str], "진료과목 (예: '피부과', '정형외과')"] = None,
    radius: Annotated[int, "검색 반경 (미터, 기본값: 5000)"] = 5000,
) -> dict:
    """
    특정 장소 주변의 병원을 검색합니다.

    전국 어디든 장소명을 입력하면 주변 병원을 찾아드립니다.
    예시:
    - 서울: "홍대", "강남역", "신촌", "잠실"
    - 광주: "광주 첨단", "상무지구", "충장로"
    - 부산: "서면", "해운대", "센텀시티"
    - 대구: "동성로", "수성구"
    - 기타: "판교", "수원역", "제주시"
    """
    # 장소명 → 좌표 변환
    location = await kakao_client.get_coordinates_from_place(place)

    if not location["success"]:
        return {
            "success": False,
            "error": location.get("error", f"'{place}'의 위치를 찾을 수 없습니다."),
            "tried_queries": location.get("tried_queries", []),
            "suggestion": location.get("suggestion", "더 구체적인 장소명을 입력해주세요."),
            "examples": ["홍대입구역", "강남역", "광주 첨단", "부산 서면", "대구 동성로"],
        }

    x, y = location["x"], location["y"]
    radius = min(radius, 20000)

    result = await kakao_client.get_nearby_hospitals(
        x=x,
        y=y,
        radius=radius,
        department=department,
    )

    if result["success"]:
        hospitals = result.get("hospitals", [])

        # 결과가 없으면 반경 확대 시도
        if not hospitals and radius < 10000:
            result = await kakao_client.get_nearby_hospitals(
                x=x, y=y, radius=10000, department=department
            )
            hospitals = result.get("hospitals", [])
            if hospitals:
                radius = 10000

        # 길찾기 URL 추가
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
            "search_location": {
                "query": place,
                "resolved_name": location.get("place_name", place),
                "address": location.get("address", ""),
                "coordinates": {"x": x, "y": y},
            },
            "radius": radius,
            "department": department or "전체",
            "total_count": len(hospitals),
            "hospitals": hospitals,
            "tip": "카카오맵 URL을 클릭하면 병원 상세 정보와 리뷰를 확인할 수 있습니다.",
        }

    return result


@mcp.tool
async def search_nearby_with_pharmacy_by_place(
    place: Annotated[str, "장소명 (예: '홍대', '강남역', '광주 첨단', '부산 서면')"],
    department: Annotated[Optional[str], "진료과목 (예: '피부과', '내과')"] = None,
    radius: Annotated[int, "검색 반경 (미터, 기본값: 5000)"] = 5000,
) -> dict:
    """
    특정 장소 주변의 병원과 약국을 함께 검색합니다.

    전국 어디든 장소명을 입력하면 주변 병원과 약국을 함께 찾아드립니다.
    예시: "홍대 근처 병원이랑 약국", "광주 첨단 피부과랑 약국"
    """
    # 장소명 → 좌표 변환
    location = await kakao_client.get_coordinates_from_place(place)

    if not location["success"]:
        return {
            "success": False,
            "error": location.get("error", f"'{place}'의 위치를 찾을 수 없습니다."),
            "tried_queries": location.get("tried_queries", []),
            "suggestion": location.get("suggestion", "더 구체적인 장소명을 입력해주세요."),
            "examples": ["홍대입구역", "강남역", "광주 첨단", "부산 서면"],
        }

    x, y = location["x"], location["y"]
    radius = min(radius, 20000)

    result = await hospital_client.search_nearby_with_pharmacy(
        x=x,
        y=y,
        radius=radius,
        department=department,
    )

    if result["success"]:
        hospitals = result.get("hospitals", [])
        pharmacies = result.get("pharmacies", [])

        # 길찾기 URL 추가
        for item in hospitals + pharmacies:
            coords = item.get("coordinates", {})
            if coords.get("x") and coords.get("y"):
                item["directions_url"] = kakao_client.generate_directions_url(
                    dest_name=item.get("name", ""),
                    dest_x=coords["x"],
                    dest_y=coords["y"],
                    origin_x=x,
                    origin_y=y,
                )

        return {
            "success": True,
            "search_location": {
                "query": place,
                "resolved_name": location.get("place_name", place),
                "address": location.get("address", ""),
                "coordinates": {"x": x, "y": y},
            },
            "radius": radius,
            "department": department,
            "hospitals": {
                "count": len(hospitals),
                "list": hospitals,
            },
            "pharmacies": {
                "count": len(pharmacies),
                "list": pharmacies,
            },
            "tip": "진료 후 가까운 약국에서 처방전을 받으세요.",
        }

    return result


@mcp.tool
async def search_nearby_with_pharmacy(
    x: Annotated[str, "현재 위치 경도 (longitude)"],
    y: Annotated[str, "현재 위치 위도 (latitude)"],
    department: Annotated[Optional[str], "진료과목 (예: '피부과', '내과')"] = None,
    radius: Annotated[int, "검색 반경 (미터, 기본값: 3000)"] = 3000,
) -> dict:
    """
    현재 위치 주변의 병원과 약국을 함께 검색합니다.

    병원 방문 후 약국도 찾아야 할 때 유용합니다.
    """
    result = await hospital_client.search_nearby_with_pharmacy(
        x=x,
        y=y,
        radius=radius,
        department=department,
    )

    if result["success"]:
        hospitals = result.get("hospitals", [])
        pharmacies = result.get("pharmacies", [])

        # 길찾기 URL 추가
        for place in hospitals + pharmacies:
            coords = place.get("coordinates", {})
            if coords.get("x") and coords.get("y"):
                place["directions_url"] = kakao_client.generate_directions_url(
                    dest_name=place.get("name", ""),
                    dest_x=coords["x"],
                    dest_y=coords["y"],
                    origin_x=x,
                    origin_y=y,
                )

        return {
            "success": True,
            "location": {"x": x, "y": y},
            "radius": radius,
            "department": department,
            "hospitals": {
                "count": len(hospitals),
                "list": hospitals,
            },
            "pharmacies": {
                "count": len(pharmacies),
                "list": pharmacies,
            },
            "tip": "진료 후 가까운 약국에서 처방전을 받으세요.",
        }

    return result


@mcp.tool
async def search_specialist_with_kakao(
    keyword: Annotated[str, "질환명 또는 전문 분야 (예: '아토피', '디스크', '당뇨')"],
    region: Annotated[Optional[str], "지역명 (예: '강남', '서울', '부산')"] = None,
    x: Annotated[Optional[str], "현재 위치 경도 (선택)"] = None,
    y: Annotated[Optional[str], "현재 위치 위도 (선택)"] = None,
    radius: Annotated[int, "검색 반경 (미터, 기본값: 10000)"] = 10000,
) -> dict:
    """
    카카오맵에서 특정 질환 전문 병원을 검색합니다.

    공공데이터보다 더 풍부한 카카오맵 정보를 활용하여
    병원명, 리뷰, 위치 정보를 함께 제공합니다.
    """
    result = await hospital_client.search_with_kakao(
        keyword=keyword,
        region=region,
        x=x,
        y=y,
        radius=radius,
    )

    if result["success"]:
        return {
            "success": True,
            "search_info": {
                "keyword": keyword,
                "region": region,
                "source": "kakao",
            },
            "total_count": result.get("total_count", 0),
            "hospitals": result.get("hospitals", []),
            "tip": "카카오맵 URL에서 실제 방문자 리뷰와 상세 정보를 확인하세요.",
        }

    return result


# 서버 실행
if __name__ == "__main__":
    import os
    from src.config import HOST, PORT

    print(f"🏥 MediMatch MCP Server 시작")
    print(f"📍 Endpoint: http://{HOST}:{PORT}/mcp")
    print(f"🔧 Transport: Streamable HTTP")

    # Streamable HTTP로 실행 (PlayMCP 호환)
    mcp.run(
        transport="streamable-http",
        host=HOST,
        port=PORT,
        path="/mcp",
    )
