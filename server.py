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
    symptoms: Annotated[str, "증상 설명 (예: '머리가 어지럽고 귀에서 소리가 나', '허리가 아프고 다리가 저려요')"]
) -> dict:
    """
    사용자의 증상을 분석하여 의심되는 질병과 진료과목을 추천합니다.

    증상을 자연스러운 문장으로 설명하면:
    1. 먼저 의심되는 질병명을 알려드립니다
    2. 그 다음 어떤 진료과목을 방문해야 하는지 추천합니다

    예: "머리가 어지럽고 귀에서 소리가 나" → 메니에르병, 이석증 등 의심
    """
    # 1. 질병 진단 (우선 수행)
    diagnosis = symptom_analyzer.diagnose_disease(symptoms)

    # 2. 증상 분석 (진료과목 추천용)
    analysis = symptom_analyzer.analyze_symptoms(symptoms)

    # 추천 진료과목에 대한 설명 추가
    department_details = []
    # 질병 진단 결과의 진료과목을 우선 사용
    recommended_depts = diagnosis["recommended_departments"] if diagnosis["has_diagnosis"] else analysis["recommended_departments"]

    for dept in recommended_depts:
        department_details.append({
            "name": dept,
            "description": symptom_analyzer.get_department_description(dept),
        })

    # 응답 구성: 질병 진단 결과를 먼저 보여줌
    response = {
        "input_symptoms": symptoms,
    }

    # 질병 진단 결과가 있으면 먼저 표시
    if diagnosis["has_diagnosis"]:
        response["diagnosis"] = {
            "suspected_diseases": diagnosis["suspected_diseases"],
            "primary_disease": diagnosis["suspected_diseases"][0] if diagnosis["suspected_diseases"] else None,
            "severity": diagnosis["severity"],
            "description": diagnosis["diagnosis_description"],
            "message": f"입력하신 증상으로 보아 '{', '.join(diagnosis['suspected_diseases'][:3])}' 등이 의심됩니다.",
        }

    response["analysis"] = {
        "matched_symptoms": analysis["matched_symptoms"],
        "confidence": analysis["confidence"],
        "summary": analysis["analysis_summary"],
    }

    response["recommendations"] = {
        "departments": department_details,
        "related_keywords": analysis["related_keywords"],
    }

    response["next_step"] = "추천된 진료과목으로 병원을 검색하시려면 search_hospitals 또는 find_specialist_hospital을 사용하세요."

    return response


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
            "navigation_guide": {
                "message": "각 병원의 directions_url을 클릭하면 카카오맵에서 길찾기가 가능합니다.",
                "note": "directions_url 링크를 사용자에게 반드시 안내해주세요.",
            },
        }
    else:
        return result


@mcp.tool
async def find_specialist_hospital(
    symptoms: Annotated[str, "증상 또는 질환명 (예: '머리가 어지럽고 귀에서 소리가 나', '허리디스크', '아토피')"],
    region: Annotated[Optional[str], "지역 (예: '서울', '강남', '광주 봉선동', '부산 서면')"] = None,
    limit: Annotated[int, "결과 개수 (기본값: 10)"] = 10,
) -> dict:
    """
    증상이나 질환명을 입력하면:
    1. 먼저 의심되는 질병명(진단)을 알려드립니다
    2. 해당 질환을 진료하는 병원을 추천합니다

    카카오맵 API를 사용하여 대학병원뿐만 아니라 개인 병원/의원도 모두 검색됩니다.
    지역은 "서울", "강남", "광주 봉선동", "부산 서면" 등 다양한 형식으로 입력 가능합니다.

    예: "머리가 어지럽고 귀에서 소리가 나" → 메니에르병, 이석증 의심 → 이비인후과 추천
    """
    # 1. 질병 진단 (우선 수행)
    diagnosis = symptom_analyzer.diagnose_disease(symptoms)

    # 2. 증상 분석 (진료과목 추천용)
    analysis = symptom_analyzer.analyze_symptoms(symptoms)

    # 질병 진단 결과가 있으면 해당 진료과목 사용, 없으면 증상 분석 결과 사용
    if diagnosis["has_diagnosis"] and diagnosis["recommended_departments"]:
        recommended_departments = diagnosis["recommended_departments"]
    elif analysis["recommended_departments"]:
        recommended_departments = analysis["recommended_departments"]
    else:
        return {
            "success": False,
            "error": "입력하신 증상에 해당하는 진료과목을 찾을 수 없습니다.",
            "suggestion": "더 구체적인 증상을 설명해주시거나, 직접 진료과목을 지정하여 search_hospitals를 사용해주세요.",
        }

    # 주요 추천 진료과목
    primary_department = recommended_departments[0]

    # 카카오맵 API 우선 사용 (의원급 병원도 검색됨)
    hospitals = []

    if region:
        # 지역이 있으면 카카오맵으로 검색 (의원/병원/클리닉 모두 포함)
        location = await kakao_client.get_coordinates_from_place(region)

        if location["success"]:
            x, y = location["x"], location["y"]

            # 진료과목 + 지역으로 검색 (의원 포함)
            kakao_result = await kakao_client.get_nearby_hospitals(
                x=x,
                y=y,
                radius=10000,  # 10km 반경
                department=primary_department,
                size=limit,
            )

            if kakao_result["success"]:
                hospitals = kakao_result.get("hospitals", [])

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

            # 카카오맵에서 결과가 없으면 공공데이터 API도 시도
            if not hospitals:
                # 시도 이름 추출 (광주 봉선동 -> 광주)
                sido_name = region.split()[0] if " " in region else region
                if sido_name in SIDO_CODES:
                    public_result = await hospital_client.search_hospitals(
                        department=primary_department,
                        sido=sido_name,
                        page=1,
                        num_of_rows=limit,
                    )
                    if public_result["success"]:
                        hospitals = public_result.get("hospitals", [])
        else:
            # 지역 좌표 변환 실패 시 시도 코드로 검색
            sido_name = region.split()[0] if " " in region else region
            if sido_name in SIDO_CODES:
                public_result = await hospital_client.search_hospitals(
                    department=primary_department,
                    sido=sido_name,
                    page=1,
                    num_of_rows=limit,
                )
                if public_result["success"]:
                    hospitals = public_result.get("hospitals", [])
    else:
        # 지역이 없으면 공공데이터 API로 전국 검색
        public_result = await hospital_client.search_hospitals(
            department=primary_department,
            page=1,
            num_of_rows=limit,
        )
        if public_result["success"]:
            hospitals = public_result.get("hospitals", [])

    # 응답 구성: 질병 진단 결과를 먼저 보여줌
    response = {
        "success": True,
        "query": symptoms,
    }

    # 질병 진단 결과가 있으면 먼저 표시 (가장 중요!)
    if diagnosis["has_diagnosis"]:
        response["diagnosis"] = {
            "suspected_diseases": diagnosis["suspected_diseases"],
            "primary_disease": diagnosis["suspected_diseases"][0] if diagnosis["suspected_diseases"] else None,
            "severity": diagnosis["severity"],
            "description": diagnosis["diagnosis_description"],
            "message": f"입력하신 증상으로 보아 '{', '.join(diagnosis['suspected_diseases'][:3])}' 등이 의심됩니다.",
        }

    response["analysis"] = {
        "detected_symptoms": analysis["matched_symptoms"],
        "primary_department": primary_department,
        "all_recommended_departments": recommended_departments,
        "confidence": analysis["confidence"],
        "summary": analysis["analysis_summary"],
    }

    response["search_criteria"] = {
        "department": primary_department,
        "region": region or "전국",
    }

    response["hospitals"] = hospitals
    response["total_count"] = len(hospitals)

    response["recommendations"] = {
        "description": symptom_analyzer.get_department_description(primary_department),
        "keywords_to_look_for": analysis["related_keywords"],
        "tip": "병원 선택 시 '{}' 관련 키워드가 있는 병원을 추천드립니다. 카카오맵 URL에서 리뷰와 상세정보를 확인하세요.".format(
            "', '".join(analysis["related_keywords"][:3]) if analysis["related_keywords"] else symptoms
        ),
    }

    # 길찾기 안내 추가
    response["navigation_guide"] = {
        "message": "각 병원의 directions_url을 클릭하면 카카오맵에서 현재 위치부터 병원까지 길찾기가 가능합니다.",
        "note": "directions_url 링크를 사용자에게 반드시 안내해주세요.",
    }

    return response


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
            "navigation_guide": {
                "message": "각 병원의 directions_url을 클릭하면 카카오맵에서 길찾기가 가능합니다.",
                "note": "directions_url 링크를 사용자에게 반드시 안내해주세요.",
            },
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
            "navigation_guide": {
                "message": "각 병원의 directions_url을 클릭하면 카카오맵에서 길찾기가 가능합니다.",
                "note": "directions_url 링크를 사용자에게 반드시 안내해주세요.",
            },
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
            "navigation_guide": {
                "message": "각 병원/약국의 directions_url을 클릭하면 카카오맵에서 길찾기가 가능합니다.",
                "note": "directions_url 링크를 사용자에게 반드시 안내해주세요.",
            },
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
            "navigation_guide": {
                "message": "각 병원/약국의 directions_url을 클릭하면 카카오맵에서 길찾기가 가능합니다.",
                "note": "directions_url 링크를 사용자에게 반드시 안내해주세요.",
            },
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


# 헬스체크 엔드포인트 추가 (UptimeRobot 모니터링용)
from starlette.requests import Request
from starlette.responses import JSONResponse
import re


# ============================================
# 카카오 i 오픈빌더 스킬 서버 엔드포인트
# ============================================

# 세션별 검색 결과 캐시 (다른 병원 추천 기능용)
# key: user_id, value: {"region": str, "department": str, "shown_ids": set, "location": dict, "last_recommendation": dict}
from collections import defaultdict
import time

search_session_cache = defaultdict(lambda: {
    "region": None,
    "department": None,
    "shown_ids": set(),
    "location": None,
    "last_updated": 0,
    "last_recommendation": None,  # 마지막 추천 정보 (이유 설명용)
})

# 캐시 만료 시간 (30분)
CACHE_EXPIRY_SECONDS = 1800


# ============================================
# 진료과목별 추천 이유 데이터베이스
# ============================================
DEPARTMENT_REASONS = {
    # 배/복부 관련
    "배": {
        "내과": "소화기 문제 (위염, 장염, 소화불량, 변비 등)",
        "정형외과": "척추/근육 문제로 인한 연관통 (허리 디스크가 복부 통증으로 나타날 수 있음)",
        "외과": "충수염(맹장), 탈장 등 수술이 필요할 수 있는 질환",
        "산부인과": "여성의 경우 생리통, 자궁/난소 관련 질환",
        "비뇨의학과": "신장결석, 요로감염 등 비뇨기 문제",
    },
    "복통": {
        "내과": "위장관 질환 (위염, 장염, 과민성대장증후군 등)",
        "외과": "급성 복증 (충수염, 담낭염, 장폐색 등)",
        "산부인과": "여성 골반 질환, 자궁외임신 등",
    },
    # 머리 관련
    "머리": {
        "신경과": "편두통, 긴장성두통, 뇌혈관 질환",
        "이비인후과": "부비동염(축농증)으로 인한 두통",
        "안과": "눈 피로, 녹내장으로 인한 두통",
        "정형외과": "경추(목) 문제로 인한 두통",
        "정신건강의학과": "스트레스성 두통, 긴장성 두통",
    },
    # 허리 관련
    "허리": {
        "정형외과": "디스크, 척추관협착증, 근육/인대 손상",
        "신경외과": "심한 디스크 탈출, 수술이 필요한 척추 질환",
        "재활의학과": "만성 허리 통증, 물리치료 필요",
        "내과": "신장 질환(신우신염, 신장결석)으로 인한 허리 통증",
    },
    # 피부 관련
    "피부": {
        "피부과": "피부 질환 전문 진료 (습진, 아토피, 두드러기 등)",
        "알레르기내과": "알레르기 검사, 면역 관련 피부 질환",
        "내과": "내부 질환으로 인한 피부 증상 (간 질환, 갑상선 등)",
    },
    # 가슴 관련
    "가슴": {
        "내과": "심장 질환, 폐 질환, 역류성식도염",
        "흉부외과": "심각한 심장/폐 질환, 수술적 치료",
        "정형외과": "갈비뼈 손상, 흉추 문제",
        "정신건강의학과": "공황장애, 불안으로 인한 가슴 답답함",
    },
    # 목 관련
    "목": {
        "이비인후과": "인후염, 편도염, 성대 질환",
        "내과": "갑상선 질환, 림프절 부종",
        "정형외과": "경추 디스크, 목 근육 문제",
    },
    # 관절 관련
    "관절": {
        "정형외과": "관절염, 인대 손상, 골절",
        "류마티스내과": "류마티스 관절염, 자가면역 질환",
        "재활의학과": "만성 관절통, 재활 치료",
    },
    # 눈 관련
    "눈": {
        "안과": "시력 문제, 눈 질환 전문",
        "신경과": "시신경 문제, 복시",
        "내과": "당뇨망막병증 등 전신 질환 관련",
    },
    # 어지러움 관련
    "어지러움": {
        "이비인후과": "이석증, 메니에르병 등 전정기관 문제",
        "신경과": "뇌혈관 질환, 신경계 문제",
        "내과": "빈혈, 저혈압, 기립성 저혈압",
        "정신건강의학과": "불안장애로 인한 어지러움",
    },
}

# 증상-진료과목 연결 설명
SYMPTOM_DEPARTMENT_EXPLANATIONS = {
    ("배", "정형외과"): "배 통증이 항상 소화기 문제만은 아니에요. 허리 디스크나 척추 문제가 있으면 신경이 눌려서 복부로 통증이 전달될 수 있어요. 특히 자세를 바꿀 때 통증이 변하면 척추 문제일 가능성이 있어요.",
    ("배", "내과"): "배 통증의 가장 흔한 원인은 소화기 질환이에요. 위염, 장염, 소화불량, 과민성대장증후군 등이 대표적이에요.",
    ("머리", "정형외과"): "두통이 목에서 시작되거나, 목을 움직일 때 더 아프다면 경추(목뼈) 문제일 수 있어요. 목 디스크나 근육 긴장이 두통을 유발할 수 있어요.",
    ("허리", "내과"): "허리 통증이 옆구리까지 퍼지거나, 소변 볼 때 문제가 있다면 신장 질환일 수 있어요. 신장결석이나 신우신염은 허리 통증을 유발해요.",
    ("가슴", "정형외과"): "가슴 통증이 숨 쉴 때나 움직일 때 더 아프다면 갈비뼈나 흉추 문제일 수 있어요. 근육통이나 늑연골염도 가슴 통증의 원인이에요.",
    ("가슴", "정신건강의학과"): "가슴이 답답하고 두근거리는데 검사상 이상이 없다면 공황장애나 불안장애일 수 있어요. 심리적 요인도 신체 증상으로 나타날 수 있어요.",
}


def get_department_reason(symptom_area: str, department: str) -> str:
    """특정 증상에 대해 해당 진료과목을 추천하는 이유 반환"""
    # 정확한 매칭 시도
    if symptom_area in DEPARTMENT_REASONS:
        reasons = DEPARTMENT_REASONS[symptom_area]
        if department in reasons:
            return reasons[department]

    # 부분 매칭 시도
    for area, reasons in DEPARTMENT_REASONS.items():
        if area in symptom_area or symptom_area in area:
            if department in reasons:
                return reasons[department]

    # 기본 설명
    default_reasons = {
        "내과": "내장 기관 관련 질환 진료",
        "외과": "수술적 치료가 필요한 질환",
        "정형외과": "뼈, 관절, 근육, 인대 질환",
        "신경과": "신경계 질환 진료",
        "피부과": "피부 질환 전문 진료",
        "이비인후과": "귀, 코, 목 질환 진료",
        "안과": "눈 관련 질환 진료",
        "산부인과": "여성 질환 및 임신 관련",
        "비뇨의학과": "비뇨기 및 남성 질환",
        "정신건강의학과": "정신건강 및 심리 질환",
        "재활의학과": "재활 치료 및 만성 통증",
    }
    return default_reasons.get(department, f"{department} 전문 진료")


def get_why_explanation(symptom_area: str, department: str) -> str:
    """'왜 OO과?' 질문에 대한 상세 설명 반환"""
    key = (symptom_area, department)
    if key in SYMPTOM_DEPARTMENT_EXPLANATIONS:
        return SYMPTOM_DEPARTMENT_EXPLANATIONS[key]

    reason = get_department_reason(symptom_area, department)
    return f"{department}를 추천드린 이유는 {reason} 때문이에요."


def get_user_id_from_request(body: dict) -> str:
    """카카오 요청에서 사용자 ID 추출"""
    user_request = body.get("userRequest", {})
    user = user_request.get("user", {})
    return user.get("id", "anonymous")


def create_kakao_response(text: str, buttons: list = None, quick_replies: list = None) -> dict:
    """카카오 오픈빌더 응답 형식 생성"""
    outputs = []

    # 텍스트 응답 (최대 1000자)
    if len(text) > 1000:
        text = text[:997] + "..."

    simple_text = {"simpleText": {"text": text}}
    outputs.append(simple_text)

    # 버튼이 있으면 추가
    if buttons:
        button_list = []
        for btn in buttons[:3]:  # 최대 3개
            button_list.append({
                "label": btn.get("label", ""),
                "action": btn.get("action", "message"),
                "messageText": btn.get("message", btn.get("label", "")),
            })
        if button_list:
            outputs.append({
                "basicCard": {
                    "description": "추가 기능",
                    "buttons": button_list
                }
            })

    response = {
        "version": "2.0",
        "template": {
            "outputs": outputs
        }
    }

    # 빠른 응답 추가
    if quick_replies:
        response["template"]["quickReplies"] = [
            {
                "label": qr.get("label", ""),
                "action": "message",
                "messageText": qr.get("message", qr.get("label", ""))
            }
            for qr in quick_replies[:10]  # 최대 10개
        ]

    return response


def create_kakao_cards_response(cards: list, quick_replies: list = None) -> dict:
    """카카오 오픈빌더 카드 캐러셀 응답 형식 생성 (최대 10개)"""
    # carousel을 사용하면 최대 10개 카드 가능
    carousel = {
        "carousel": {
            "type": "basicCard",
            "items": cards[:10]  # 최대 10개
        }
    }

    response = {
        "version": "2.0",
        "template": {
            "outputs": [carousel]
        }
    }

    if quick_replies:
        response["template"]["quickReplies"] = [
            {
                "label": qr.get("label", ""),
                "action": "message",
                "messageText": qr.get("message", qr.get("label", ""))
            }
            for qr in quick_replies[:10]
        ]

    return response


def create_symptom_analysis_with_cards_response(
    text: str, cards: list, quick_replies: list = None
) -> dict:
    """증상 분석 텍스트 + 병원 카드 캐러셀 응답 형식 생성"""
    outputs = []

    # 1. 증상 분석 텍스트
    if len(text) > 1000:
        text = text[:997] + "..."
    outputs.append({"simpleText": {"text": text}})

    # 2. 병원 카드 캐러셀
    if cards:
        carousel = {
            "carousel": {
                "type": "basicCard",
                "items": cards[:10]
            }
        }
        outputs.append(carousel)

    response = {
        "version": "2.0",
        "template": {
            "outputs": outputs
        }
    }

    if quick_replies:
        response["template"]["quickReplies"] = [
            {
                "label": qr.get("label", ""),
                "action": "message",
                "messageText": qr.get("message", qr.get("label", ""))
            }
            for qr in quick_replies[:10]
        ]

    return response


def extract_intent(user_message: str) -> dict:
    """사용자 메시지에서 의도 추출 (확장된 자연어 인식)"""
    message = user_message.lower()
    original_message = user_message  # 원본 보존

    # 지역 패턴 (먼저 추출)
    region_pattern = r'(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주|강남|홍대|신촌|서면|해운대|동성로|판교|분당|첨단|잠실|여의도|명동|종로|신림|사당|왕십리|건대|혜화|이태원|영등포|동대문|용산|수원|일산|부천|안양|의정부|평택|송도|부평|둔산|유성|수성구|남포동|센텀시티|광안리|상무|충장로|금남로)'
    region_match = re.search(region_pattern, message)

    # 진료과목 패턴 (확장)
    dept_pattern = r'(내과|외과|피부과|정형외과|이비인후과|안과|치과|산부인과|소아과|소아청소년과|신경과|신경외과|정신과|정신건강의학과|비뇨기과|비뇨의학과|재활의학과|가정의학과|흉부외과|성형외과|마취통증의학과|영상의학과|진단검사의학과|병리과|응급의학과|핵의학과|직업환경의학과|예방의학과|결핵과|한의원|한방|통증의학과)'
    dept_match = re.search(dept_pattern, message)

    # ============================================
    # 1. 인사 (우선순위 높음)
    # ============================================
    greeting_keywords = [
        "안녕", "하이", "반가", "시작", "헬로", "hello", "hi",
        "처음", "왔어", "뭐야", "뭐해", "누구"
    ]
    if any(word in message for word in greeting_keywords) and len(message) < 15:
        return {"intent": "greeting"}

    # ============================================
    # 2. 추천 이유 질문 (왜 OO과? 등) - 우선순위 높음
    # ============================================
    why_question_patterns = [
        # "왜 정형외과?" 패턴
        r'왜\s*(내과|외과|피부과|정형외과|이비인후과|안과|치과|산부인과|소아과|신경과|신경외과|정신과|비뇨기과|재활의학과|가정의학과|흉부외과)',
        # "정형외과는 왜?" 패턴
        r'(내과|외과|피부과|정형외과|이비인후과|안과|치과|산부인과|소아과|신경과|신경외과|정신과|비뇨기과|재활의학과|가정의학과|흉부외과).{0,5}(왜|이유|뭐)',
        # "정형외과 왜 가?" 패턴
        r'(내과|외과|피부과|정형외과|이비인후과|안과|치과|산부인과|소아과|신경과|신경외과|정신과|비뇨기과|재활의학과|가정의학과|흉부외과).{0,10}(왜|이유)',
    ]

    # "왜?" 질문 키워드
    why_keywords = [
        "왜 ", "이유가", "이유는", "이유 ", "무슨 상관", "상관이", "관련이",
        "이해가 안", "이해안", "왜요", "왜죠", "왜지", "왜야", "웬", "의아",
        "뭔 상관", "무슨상관", "어떤 관계", "무슨 관계",
    ]

    # 진료과목이 메시지에 있고 + 왜? 질문 패턴이 있는 경우
    if dept_match:
        has_why_pattern = any(re.search(pattern, message) for pattern in why_question_patterns)
        has_why_keyword = any(word in message for word in why_keywords)

        if has_why_pattern or has_why_keyword:
            return {
                "intent": "explain_recommendation",
                "department": dept_match.group(1),
            }

    # "왜" 키워드만 있는 경우 (진료과목 없이) - 이전 추천에 대한 질문일 수 있음
    simple_why_patterns = ["왜요", "왜죠", "왜지", "왜야", "이유가 뭐", "왜 그래", "이해가 안 돼", "이해안돼"]
    if any(word in message for word in simple_why_patterns) and len(message) < 20:
        return {"intent": "explain_recommendation", "department": None}

    # ============================================
    # 3. 도움말
    # ============================================
    help_keywords = [
        "도움", "사용법", "뭐 할 수", "기능", "어떻게 써", "사용 방법",
        "뭘 할 수 있", "알려줘 기능", "메뉴", "명령어"
    ]
    if any(word in message for word in help_keywords):
        return {"intent": "help"}

    # ============================================
    # 3. 다른 병원 추천 요청
    # ============================================
    more_hospital_keywords = [
        # 다른 병원 요청
        "다른 병원", "다른곳", "다른 곳", "다른 데", "다른데",
        "또 다른", "또다른", "다른거", "다른 거",
        # 더 보기/찾기 요청
        "더 보여", "더 찾아", "더 알려", "더 검색", "더 추천",
        "더 없어", "더 있어", "더 없나", "더 있나",
        # 새로운 추천 요청
        "새로운", "다른 추천", "다시 찾아", "다시 검색", "다시 추천",
        # 질문형
        "없어?", "없나요", "없어요", "없을까", "또 없어", "또 있어",
        # 추가 요청
        "말고", "외에", "빼고",
    ]
    # "다른" 단독은 "다른 병원", "다른 곳" 등과 함께 쓰일 때만 인식
    more_hospital_patterns = ["다른", "또", "더"]
    has_more_keyword = any(word in message for word in more_hospital_keywords)
    has_pattern_with_hospital = any(
        pattern in message and ("병원" in message or "추천" in message or "찾아" in message or "검색" in message or "알려" in message)
        for pattern in more_hospital_patterns
    )
    if has_more_keyword or has_pattern_with_hospital:
        return {"intent": "more_hospitals"}

    # ============================================
    # 4. 약국 검색
    # ============================================
    if "약국" in message:
        return {
            "intent": "search_pharmacy",
            "region": region_match.group(1) if region_match else None,
        }

    # ============================================
    # 5. 병원 검색 (지역 + 과목이 명확한 경우)
    # ============================================
    hospital_keywords = [
        "병원", "의원", "클리닉", "찾아", "검색", "추천", "알려",
        "어디", "어딜", "가까운", "근처", "주변"
    ]

    if dept_match and (region_match or any(word in message for word in hospital_keywords)):
        return {
            "intent": "search_hospital",
            "region": region_match.group(1) if region_match else None,
            "department": dept_match.group(1) if dept_match else None,
        }

    # ============================================
    # 6. 증상 분석 (대폭 확장된 키워드)
    # ============================================

    # 6-1. 통증/불편감 표현 (구어체 포함)
    pain_keywords = [
        # 기본 통증
        "아파", "아프", "아픔", "아팠", "아플", "아픈", "통증", "쑤시", "쑤셔", "쑤심",
        # 찌르는/날카로운 통증
        "찌릿", "찌르", "콕콕", "쿡쿡", "뻐근", "뻣뻣", "뻑뻑",
        # 저림/무감각
        "저리", "저림", "저려", "마비", "감각이 없", "먹먹",
        # 당김/뻗침
        "당기", "당김", "뻗치", "뻗어", "땡기", "땡김",
        # 욱신/울림
        "욱신", "지끈", "지근", "울리", "울림",
        # 화끈/열감
        "화끈", "뜨거", "뜨겁", "열감", "후끈", "달아올",
        # 시림/차가움
        "시리", "시림", "시려", "차가", "차갑", "썰렁",
        # 묵직/무거움
        "묵직", "무거", "무겁", "눌리", "짓눌",
        # 결림
        "결리", "결림", "담", "뭉치", "뭉침", "뭉쳐",
    ]

    # 6-2. 신체 부위별 표현
    body_part_keywords = [
        # 머리
        "머리", "두통", "관자놀이", "뒷통수", "이마", "정수리", "편두통",
        # 눈
        "눈", "눈알", "안구", "시력", "눈물", "충혈", "눈꺼풀",
        # 코
        "코", "콧물", "코막힘", "재채기", "비염", "축농증",
        # 귀
        "귀", "이명", "귀울림", "청력", "중이염",
        # 입/목
        "입", "혀", "입술", "목", "목구멍", "인후", "편도", "성대", "기도",
        # 치아
        "이", "이빨", "치아", "잇몸", "사랑니", "충치",
        # 목/어깨
        "목덜미", "어깨", "승모근", "견갑골",
        # 가슴/흉부
        "가슴", "흉부", "심장", "폐", "갈비뼈", "명치",
        # 배/복부
        "배", "복부", "위", "장", "소장", "대장", "맹장", "간", "췌장", "신장", "콩팥",
        # 등/허리
        "등", "허리", "척추", "요추", "디스크", "꼬리뼈",
        # 팔/손
        "팔", "팔꿈치", "손목", "손", "손가락", "손바닥", "손등",
        # 다리/발
        "다리", "허벅지", "종아리", "무릎", "발목", "발", "발가락", "발바닥", "발등", "아킬레스",
        # 피부
        "피부", "살", "살갗",
        # 기타
        "관절", "뼈", "근육", "힘줄", "인대",
    ]

    # 6-3. 증상/상태 표현 (구어체 대폭 확장)
    symptom_keywords = [
        # 열/감기 관련
        "열", "열나", "열이", "발열", "고열", "미열", "오한", "춥", "으슬으슬",
        "기침", "마른기침", "가래", "기침이", "콜록", "캑캑",
        "콧물", "코막힘", "코가", "재채기", "훌쩍",
        "감기", "독감", "몸살", "오들오들",

        # 소화기 관련
        "속", "속이", "속쓰림", "더부룩", "소화", "체", "체했", "체한", "소화불량",
        "구토", "토", "울렁", "메스꺼", "메슥", "욕지기", "헛구역",
        "설사", "묽은변", "변비", "배변", "대변", "변", "똥",
        "복통", "배탈", "배아파", "배가", "뱃속",
        "가스", "방귀", "트림", "장",
        "식욕", "입맛", "못먹", "안먹",

        # 피부 관련
        "가려", "가렵", "간지러", "간지", "긁", "두드러기",
        "발진", "뾰루지", "여드름", "트러블", "피부트러블",
        "붓", "부었", "부어", "붓기", "부종", "퉁퉁",
        "빨개", "빨갛", "붉", "충혈", "발적",
        "건조", "각질", "갈라", "터져", "트",
        "멍", "멍이", "피멍", "타박",
        "물집", "수포",
        "탈모", "머리카락", "빠져",

        # 호흡기 관련
        "숨", "호흡", "숨쉬기", "답답", "가쁘", "헐떡", "천식",

        # 순환기 관련
        "심장", "두근", "두근거리", "빈맥", "맥박", "혈압", "어지러", "어지럼", "현기증", "빙글빙글",

        # 신경/정신 관련
        "두통", "머리아파", "머리가", "편두통",
        "불면", "잠", "못자", "안자", "잠이안와", "수면",
        "피곤", "피로", "지치", "기운", "힘이없", "무기력", "나른",
        "스트레스", "우울", "불안", "초조", "예민", "짜증",
        "집중", "건망증", "깜빡", "기억",

        # 근골격계 관련
        "삐끗", "삐었", "접질", "염좌", "골절", "부러",
        "관절", "뻣뻣", "굳", "뻑뻑",

        # 비뇨기/생식기 관련
        "소변", "오줌", "소변볼때", "자주", "화장실",
        "생리", "월경", "생리통", "생리불순",

        # 눈 관련
        "침침", "흐릿", "안보여", "눈아파", "눈이", "눈물",

        # 귀 관련
        "안들려", "이명", "귀울림", "귀에서",

        # 기타 일반 증상
        "증상", "이상", "불편", "안좋", "좀이상", "뭔가이상",
        "아무래도", "걱정", "신경쓰", "찜찜",
    ]

    # 6-4. 질병명 직접 인식
    disease_keywords = [
        # 감염성 질환
        "감기", "독감", "코로나", "코비드", "장염", "식중독", "위염", "위궤양",
        "방광염", "요로감염", "결막염", "중이염", "편도염", "폐렴", "기관지염",
        "축농증", "비염", "부비동염",

        # 피부 질환
        "아토피", "습진", "건선", "두드러기", "대상포진", "헤르페스",
        "무좀", "백선", "사마귀", "티눈",

        # 근골격계 질환
        "디스크", "허리디스크", "목디스크", "관절염", "류마티스", "통풍",
        "오십견", "회전근개", "테니스엘보", "골다공증",

        # 소화기 질환
        "역류성", "역류성식도염", "과민성대장", "변비", "치질", "치핵",
        "담석", "담낭염", "췌장염", "간염",

        # 순환기/심장 질환
        "고혈압", "저혈압", "부정맥", "협심증", "심근경색",

        # 대사 질환
        "당뇨", "당뇨병", "고지혈증", "갑상선", "갑상선기능",

        # 신경계 질환
        "편두통", "긴장성두통", "어지럼증", "메니에르", "이석증",
        "수근관증후군", "손목터널",

        # 정신건강
        "우울증", "불안장애", "공황장애", "공황", "불면증", "수면장애",

        # 알레르기
        "알레르기", "알러지", "꽃가루", "비염",

        # 여성 질환
        "생리통", "생리불순", "다낭성", "자궁근종", "자궁내막",

        # 기타
        "탈장", "치질", "대장용종",
    ]

    # 6-5. 질문 패턴 인식
    question_patterns = [
        "어디로 가", "어디 가", "뭘 먹", "어떻게 해", "어떡해", "어쩌지", "어쩔",
        "왜 이러", "왜이러", "왜 그러", "왜그러", "무슨 일", "무슨일",
        "괜찮", "심각", "위험", "병원 가야", "응급", "급해",
        "치료", "낫", "좋아지", "언제", "얼마나",
        "~인가요", "~일까요", "~한가요", "~할까요",
        "인 것 같", "인것같", "인거같", "인가", "일까",
        "같아요", "같은데", "것 같은데",
    ]

    # 6-6. 상태 확인
    has_symptom = any(word in message for word in pain_keywords + symptom_keywords)
    has_body_part = any(word in message for word in body_part_keywords)
    has_disease = any(word in message for word in disease_keywords)
    has_question = any(word in message for word in question_patterns)

    # 증상 분석으로 처리할지 결정
    should_analyze = (
        has_symptom or
        has_disease or
        (has_body_part and has_question) or  # "머리 왜이러지" 같은 패턴
        (has_body_part and len(message) > 5)  # "허리가요" 같은 짧은 표현도 처리
    )

    if should_analyze:
        return {
            "intent": "analyze_symptoms",
            "symptoms": original_message,
            "region": region_match.group(1) if region_match else None,
            "has_disease_mention": has_disease,
        }

    # ============================================
    # 7. 병원 검색 키워드만 있는 경우
    # ============================================
    if any(word in message for word in hospital_keywords):
        return {
            "intent": "search_hospital",
            "region": region_match.group(1) if region_match else None,
            "department": None,
        }

    # ============================================
    # 8. 기본값: 증상 분석으로 처리 (폴백)
    # ============================================
    # 메시지가 너무 짧거나 의미없으면 도움말로
    if len(message.strip()) < 3:
        return {"intent": "help"}

    # 그 외 모든 경우 증상 분석 시도
    return {
        "intent": "analyze_symptoms",
        "symptoms": original_message,
        "region": region_match.group(1) if region_match else None,
    }


async def process_kakao_skill(user_message: str, user_id: str = "anonymous") -> dict:
    """카카오 스킬 요청 처리"""
    intent_data = extract_intent(user_message)
    intent = intent_data.get("intent")

    # 캐시 만료 체크
    current_time = time.time()
    if current_time - search_session_cache[user_id]["last_updated"] > CACHE_EXPIRY_SECONDS:
        search_session_cache[user_id] = {
            "region": None,
            "department": None,
            "shown_ids": set(),
            "location": None,
            "last_updated": 0,
            "last_recommendation": None,
        }

    # ============================================
    # 추천 이유 설명 처리 (왜 OO과?)
    # ============================================
    if intent == "explain_recommendation":
        asked_department = intent_data.get("department")
        cache = search_session_cache[user_id]
        last_rec = cache.get("last_recommendation")

        # 1. 특정 진료과목에 대해 물어본 경우
        if asked_department:
            if last_rec and last_rec.get("symptom_area"):
                symptom_area = last_rec["symptom_area"]
                explanation = get_why_explanation(symptom_area, asked_department)

                response_text = f"❓ 왜 {asked_department}를 추천했나요?\n\n"
                response_text += explanation + "\n\n"

                # 다른 진료과목 옵션도 설명
                if symptom_area in DEPARTMENT_REASONS:
                    other_depts = [d for d in DEPARTMENT_REASONS[symptom_area].keys() if d != asked_department]
                    if other_depts:
                        response_text += "📋 다른 가능성:\n"
                        for dept in other_depts[:2]:
                            reason = get_department_reason(symptom_area, dept)
                            response_text += f"• {dept}: {reason}\n"

                response_text += "\n💡 증상에 따라 적합한 진료과가 달라요. 추가 증상이 있으시면 알려주세요!"

                quick_replies = []
                if last_rec.get("departments"):
                    for dept in last_rec["departments"][:2]:
                        if dept != asked_department:
                            quick_replies.append({
                                "label": f"왜 {dept}?",
                                "message": f"왜 {dept}를 추천했어?"
                            })
                quick_replies.append({"label": "증상 다시 말하기", "message": "증상 분석해줘"})

                return create_kakao_response(response_text, quick_replies=quick_replies)
            else:
                # 이전 추천 정보가 없는 경우
                reason = get_department_reason("", asked_department)
                return create_kakao_response(
                    f"❓ {asked_department}는요...\n\n"
                    f"{reason}\n\n"
                    "💡 증상을 말씀해주시면 왜 해당 진료과를 추천했는지 더 자세히 설명드릴 수 있어요!",
                    quick_replies=[
                        {"label": "증상 말하기", "message": "배가 아파요"},
                        {"label": "도움말", "message": "도움말"},
                    ]
                )

        # 2. "왜요?" 같은 단순 질문 (진료과목 없음)
        else:
            if last_rec and last_rec.get("departments") and last_rec.get("symptom_area"):
                symptom_area = last_rec["symptom_area"]
                departments = last_rec["departments"]

                response_text = f"❓ 추천 이유 설명\n\n"
                response_text += f"'{symptom_area}' 증상으로 다음 진료과를 추천드렸어요:\n\n"

                for dept in departments[:3]:
                    reason = get_department_reason(symptom_area, dept)
                    response_text += f"• {dept}: {reason}\n"

                response_text += "\n💡 특정 진료과에 대해 더 궁금하시면 물어봐주세요!"

                quick_replies = [
                    {"label": f"왜 {dept}?", "message": f"왜 {dept}?"}
                    for dept in departments[:2]
                ]
                quick_replies.append({"label": "병원 찾기", "message": f"서울 {departments[0]} 찾아줘"})

                return create_kakao_response(response_text, quick_replies=quick_replies)
            else:
                return create_kakao_response(
                    "이전에 추천드린 진료과가 없어요.\n\n"
                    "증상을 말씀해주시면 적합한 진료과와 이유를 알려드릴게요!",
                    quick_replies=[
                        {"label": "증상 말하기", "message": "배가 아파요"},
                        {"label": "도움말", "message": "도움말"},
                    ]
                )

    # 다른 병원 추천 요청 처리
    if intent == "more_hospitals":
        cache = search_session_cache[user_id]

        if not cache["region"] or not cache["department"] or not cache["location"]:
            return create_kakao_response(
                "이전에 검색하신 병원 정보가 없어요.\n\n"
                "먼저 병원을 검색해주세요!\n"
                "예: \"홍대 이비인후과 찾아줘\"",
                quick_replies=[
                    {"label": "홍대 이비인후과", "message": "홍대 이비인후과 찾아줘"},
                    {"label": "강남 피부과", "message": "강남 피부과 찾아줘"},
                ]
            )

        # 더 많은 병원 검색 (size를 늘려서 검색)
        result = await kakao_client.get_nearby_hospitals(
            x=cache["location"]["x"],
            y=cache["location"]["y"],
            radius=7000,  # 검색 반경 확대
            department=cache["department"],
            size=15,  # 더 많이 검색
        )

        if result["success"] and result.get("hospitals"):
            hospitals = result["hospitals"]

            # 이미 보여준 병원 제외
            new_hospitals = [
                h for h in hospitals
                if h.get("id") not in cache["shown_ids"]
            ]

            if not new_hospitals:
                return create_kakao_response(
                    f"{cache['region']} 주변에서 더 이상 찾을 수 있는 {cache['department']}이 없어요.\n\n"
                    "다른 지역이나 진료과를 검색해보세요!",
                    quick_replies=[
                        {"label": "서울 전체 검색", "message": f"서울 {cache['department']} 찾아줘"},
                        {"label": "다른 진료과", "message": "도움말"},
                    ]
                )

            # 새로운 병원 카드 생성
            cards = []
            for h in new_hospitals[:5]:
                hospital_id = h.get("id")
                if hospital_id:
                    cache["shown_ids"].add(hospital_id)

                name = h.get("name", "")
                title = name if name else "병원 정보"

                address = h.get("road_address") or h.get("address") or ""
                phone = h.get("phone") or ""
                description_parts = []
                if address:
                    description_parts.append(f"주소: {address}")
                if phone:
                    description_parts.append(f"전화: {phone}")
                description = "\n".join(description_parts) if description_parts else "상세정보 없음"

                coords = h.get("coordinates") or {}
                x = coords.get("x")
                y = coords.get("y")

                map_url = h.get("kakao_map_url")
                if not map_url and name and x and y:
                    map_url = kakao_client.generate_map_url(name, x, y)

                directions_url = None
                if name and x and y:
                    directions_url = kakao_client.generate_directions_url(
                        dest_name=name,
                        dest_x=x,
                        dest_y=y,
                        origin_x=cache["location"]["x"],
                        origin_y=cache["location"]["y"],
                    )

                card = {
                    "title": title,
                    "description": description,
                    "thumbnail": {
                        "imageUrl": "https://t1.kakaocdn.net/openbuilder/sample/img_005.jpg"
                    },
                }

                buttons = []
                if map_url:
                    buttons.append({
                        "label": "카카오맵 보기",
                        "action": "webLink",
                        "webLinkUrl": map_url,
                    })
                if directions_url:
                    buttons.append({
                        "label": "길찾기",
                        "action": "webLink",
                        "webLinkUrl": directions_url,
                    })
                if buttons:
                    card["buttons"] = buttons

                cards.append(card)

            cache["last_updated"] = current_time

            return create_kakao_cards_response(
                cards,
                quick_replies=[
                    {"label": "다른 병원 더 보기", "message": "다른 병원 추천해줘"},
                ]
            )

        return create_kakao_response(
            f"{cache['region']} 주변에서 더 찾을 수 있는 {cache['department']}이 없어요.",
            quick_replies=[
                {"label": "범위 넓혀 검색", "message": f"서울 {cache['department']} 찾아줘"},
            ]
        )

    # 인사
    if intent == "greeting":
        return create_kakao_response(
            "안녕하세요! 🏥 MediMatch입니다.\n\n"
            "증상을 말씀해주시면 의심 질병과 추천 진료과를 알려드리고, "
            "주변 병원도 찾아드려요.\n\n"
            "예시:\n"
            "• \"머리가 아프고 어지러워요\"\n"
            "• \"강남 피부과 찾아줘\"\n"
            "• \"배가 아프고 설사해요\"",
            quick_replies=[
                {"label": "증상 분석하기", "message": "증상 분석해줘"},
                {"label": "사용법 보기", "message": "도움말"},
            ]
        )

    # 도움말
    if intent == "help":
        return create_kakao_response(
            "📋 MediMatch 사용법\n\n"
            "1️⃣ 증상 말하기\n"
            "\"머리가 아파요\", \"피부가 가려워요\"\n\n"
            "2️⃣ 병원 찾기\n"
            "\"강남 피부과\", \"홍대 근처 정형외과\"\n\n"
            "3️⃣ 병원+약국 찾기\n"
            "\"서면 내과랑 약국\"\n\n"
            "증상을 자세히 설명할수록 더 정확한 분석이 가능해요!",
            quick_replies=[
                {"label": "증상 말하기", "message": "배가 아파요"},
                {"label": "병원 찾기", "message": "강남 피부과 찾아줘"},
            ]
        )

    # 증상 분석 + 병원 추천
    if intent == "analyze_symptoms":
        symptoms = intent_data.get("symptoms", user_message)
        region = intent_data.get("region")

        # 증상 분석
        diagnosis = symptom_analyzer.diagnose_disease(symptoms)
        analysis = symptom_analyzer.analyze_symptoms(symptoms)

        # 증상 부위 추출 (이유 설명용)
        symptom_area = ""
        body_parts = ["배", "머리", "허리", "가슴", "목", "피부", "눈", "귀", "관절", "어지러"]
        for part in body_parts:
            if part in symptoms:
                symptom_area = part
                break

        # 응답 텍스트 구성
        response_text = ""

        # 질병 진단 결과
        if diagnosis["has_diagnosis"]:
            diseases = diagnosis["suspected_diseases"][:3]
            response_text += f"🔍 증상 분석 결과\n\n"
            response_text += f"의심 질병: {', '.join(diseases)}\n"
            response_text += f"심각도: {diagnosis['severity']}\n\n"

        # 추천 진료과
        departments = diagnosis["recommended_departments"] if diagnosis["has_diagnosis"] else analysis["recommended_departments"]
        if departments:
            # 진료과목과 함께 간단한 이유 표시
            response_text += f"🏥 추천 진료과:\n"
            for dept in departments[:2]:
                reason = get_department_reason(symptom_area, dept)
                response_text += f"• {dept} - {reason}\n"
            response_text += "\n"

        # 세션 캐시에 마지막 추천 정보 저장 (이유 질문 대비)
        cache = search_session_cache[user_id]
        cache["last_recommendation"] = {
            "symptom_area": symptom_area,
            "symptoms": symptoms,
            "departments": departments,
            "diseases": diagnosis.get("suspected_diseases", []),
        }
        cache["last_updated"] = current_time

        # 지역이 있으면 병원 검색
        hospitals = []
        if region and departments:
            primary_dept = departments[0]
            location = await kakao_client.get_coordinates_from_place(region)

            if location["success"]:
                result = await kakao_client.get_nearby_hospitals(
                    x=location["x"],
                    y=location["y"],
                    radius=5000,
                    department=primary_dept,
                    size=10,  # 더 많이 검색해서 "다른 병원" 요청에 대비
                )
                if result["success"]:
                    hospitals = result.get("hospitals", [])

                # 세션 캐시 저장 (다른 병원 추천 기능용)
                cache["region"] = region
                cache["department"] = primary_dept
                cache["location"] = {"x": location["x"], "y": location["y"]}
                cache["shown_ids"] = set()
                cache["last_updated"] = current_time

        if hospitals:
            response_text += f"📍 {region} 주변 {departments[0]}"

            # 병원 카드 생성 (카카오맵, 길찾기 링크 포함)
            cards = []
            for h in hospitals[:3]:
                # 세션 캐시에 보여준 병원 ID 저장
                hospital_id = h.get("id")
                if hospital_id:
                    cache["shown_ids"].add(hospital_id)
                name = h.get("name", "")
                if not name:
                    continue

                address = h.get("road_address") or h.get("address") or ""
                phone = h.get("phone") or ""

                description_parts = []
                if address:
                    description_parts.append(f"📍 {address}")
                if phone:
                    description_parts.append(f"📞 {phone}")
                description = "\n".join(description_parts) if description_parts else "상세정보 없음"

                coords = h.get("coordinates") or {}
                x = coords.get("x")
                y = coords.get("y")

                map_url = h.get("kakao_map_url")
                if not map_url and name and x and y:
                    map_url = kakao_client.generate_map_url(name, x, y)

                directions_url = None
                if name and x and y:
                    directions_url = kakao_client.generate_directions_url(
                        dest_name=name,
                        dest_x=x,
                        dest_y=y,
                        origin_x=location["x"],
                        origin_y=location["y"],
                    )

                card = {
                    "title": name,
                    "description": description,
                }

                buttons = []
                if map_url:
                    buttons.append({
                        "label": "카카오맵 보기",
                        "action": "webLink",
                        "webLinkUrl": map_url,
                    })
                if directions_url:
                    buttons.append({
                        "label": "길찾기",
                        "action": "webLink",
                        "webLinkUrl": directions_url,
                    })
                if buttons:
                    card["buttons"] = buttons

                cards.append(card)

            # 빠른 응답
            quick_replies = [
                {"label": "다른 병원 더 보기", "message": "다른 병원 추천해줘"}
            ]
            if departments:
                quick_replies.append({
                    "label": f"서울 {departments[0]} 찾기",
                    "message": f"서울 {departments[0]} 찾아줘"
                })

            if cards:
                # 텍스트 + 카드 캐러셀 응답
                return create_symptom_analysis_with_cards_response(
                    response_text, cards, quick_replies
                )
            else:
                return create_kakao_response(response_text, quick_replies=quick_replies)
        else:
            response_text += "\n\n💡 지역을 알려주시면 주변 병원을 찾아드릴게요.\n"
            response_text += "예: \"강남 피부과\", \"홍대 근처 정형외과\""

            # 빠른 응답
            quick_replies = []
            if departments:
                quick_replies.append({
                    "label": f"서울 {departments[0]} 찾기",
                    "message": f"서울 {departments[0]} 찾아줘"
                })

            return create_kakao_response(response_text, quick_replies=quick_replies)

    # 병원 검색
    if intent == "search_hospital":
        region = intent_data.get("region", "서울")
        department = intent_data.get("department")

        if not department:
            return create_kakao_response(
                f"어떤 진료과를 찾으시나요?\n\n"
                f"예: \"{region} 피부과\", \"{region} 정형외과\"",
                quick_replies=[
                    {"label": "내과", "message": f"{region} 내과 찾아줘"},
                    {"label": "피부과", "message": f"{region} 피부과 찾아줘"},
                    {"label": "정형외과", "message": f"{region} 정형외과 찾아줘"},
                ]
            )

        # 병원 검색
        location = await kakao_client.get_coordinates_from_place(region)

        if not location["success"]:
            return create_kakao_response(
                f"'{region}'의 위치를 찾을 수 없어요.\n"
                "더 구체적인 지역명을 입력해주세요.\n\n"
                "예: 강남역, 홍대입구, 부산 서면"
            )

        result = await kakao_client.get_nearby_hospitals(
            x=location["x"],
            y=location["y"],
            radius=5000,
            department=department,
            size=5,
        )

        if result["success"] and result.get("hospitals"):
            hospitals = result["hospitals"]
            cards = []

            # 세션 캐시 저장 (다른 병원 추천 기능용)
            cache = search_session_cache[user_id]
            cache["region"] = region
            cache["department"] = department
            cache["location"] = {"x": location["x"], "y": location["y"]}
            cache["shown_ids"] = set()
            cache["last_updated"] = current_time

            for h in hospitals[:5]:
                hospital_id = h.get("id")
                if hospital_id:
                    cache["shown_ids"].add(hospital_id)

                name = h.get("name", "")
                title = name if name else "병원 정보"

                address = h.get("road_address") or h.get("address") or ""
                phone = h.get("phone") or ""
                description_parts = []
                if address:
                    description_parts.append(f"주소: {address}")
                if phone:
                    description_parts.append(f"전화: {phone}")
                description = "\n".join(description_parts) if description_parts else "상세정보 없음"

                coords = h.get("coordinates") or {}
                x = coords.get("x")
                y = coords.get("y")

                map_url = h.get("kakao_map_url")
                if not map_url and name and x and y:
                    map_url = kakao_client.generate_map_url(name, x, y)

                directions_url = None
                if name and x and y:
                    directions_url = kakao_client.generate_directions_url(
                        dest_name=name,
                        dest_x=x,
                        dest_y=y,
                        origin_x=location["x"],
                        origin_y=location["y"],
                    )

                card = {
                    "title": title,
                    "description": description,
                    "thumbnail": {
                        "imageUrl": "https://t1.kakaocdn.net/openbuilder/sample/img_005.jpg"
                    },
                }

                buttons = []
                if map_url:
                    buttons.append({
                        "label": "카카오맵 보기",
                        "action": "webLink",
                        "webLinkUrl": map_url,
                    })
                if directions_url:
                    buttons.append({
                        "label": "길찾기",
                        "action": "webLink",
                        "webLinkUrl": directions_url,
                    })
                if buttons:
                    card["buttons"] = buttons

                cards.append(card)

            return create_kakao_cards_response(
                cards,
                quick_replies=[
                    {"label": "다른 병원 더 보기", "message": "다른 병원 추천해줘"},
                ]
            )

        else:
            return create_kakao_response(
                f"{region} 주변에서 {department}를 찾지 못했어요.\n"
                "검색 범위를 넓혀서 다시 찾아볼까요?",
                quick_replies=[
                    {"label": "범위 넓혀 검색", "message": f"서울 {department} 찾아줘"},
                ]
            )

    # 약국 검색
    if intent == "search_pharmacy":
        region = intent_data.get("region", "서울")

        location = await kakao_client.get_coordinates_from_place(region)

        if location["success"]:
            result = await kakao_client.get_nearby_pharmacies(
                x=location["x"],
                y=location["y"],
                radius=3000,
            )

            if result["success"] and result.get("pharmacies"):
                pharmacies = result["pharmacies"]
                response_text = f"💊 {region} 주변 약국\n\n"

                for i, p in enumerate(pharmacies[:5], 1):
                    name = p.get("name", "")
                    distance = p.get("distance", "")
                    dist_text = f" ({distance}m)" if distance else ""
                    response_text += f"{i}. {name}{dist_text}\n"

                return create_kakao_response(response_text)

        return create_kakao_response(f"{region} 주변에서 약국을 찾지 못했어요.")

    # 기본 응답
    return create_kakao_response(
        "죄송해요, 잘 이해하지 못했어요.\n\n"
        "증상을 말씀해주시거나, 찾으시는 병원 종류를 알려주세요.\n\n"
        "예시:\n"
        "• \"머리가 아프고 어지러워요\"\n"
        "• \"강남 피부과 찾아줘\"",
        quick_replies=[
            {"label": "사용법 보기", "message": "도움말"},
        ]
    )


@mcp.custom_route("/kakao/skill", methods=["POST"])
async def kakao_skill_endpoint(request: Request) -> JSONResponse:
    """
    카카오 i 오픈빌더 스킬 서버 엔드포인트

    오픈빌더에서 스킬 서버로 등록하여 사용합니다.
    URL: https://medimatch-mcp.onrender.com/kakao/skill
    """
    try:
        body = await request.json()

        # 사용자 발화 및 ID 추출
        user_request = body.get("userRequest", {})
        utterance = user_request.get("utterance", "")
        user_id = get_user_id_from_request(body)

        if not utterance:
            return JSONResponse(create_kakao_response("메시지를 입력해주세요."))

        # 스킬 처리
        response = await process_kakao_skill(utterance, user_id)
        return JSONResponse(response)

    except Exception as e:
        error_response = create_kakao_response(
            "죄송해요, 오류가 발생했어요.\n잠시 후 다시 시도해주세요."
        )
        return JSONResponse(error_response)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """서버 상태 확인용 헬스체크 엔드포인트"""
    return JSONResponse({"status": "ok", "service": "MediMatch MCP Server"})


@mcp.custom_route("/", methods=["GET"])
async def root(request: Request) -> JSONResponse:
    """루트 경로 - 서비스 정보 제공"""
    return JSONResponse({
        "service": "MediMatch",
        "description": "AI 기반 증상 분석 및 전문 병원 매칭 MCP 서버",
        "mcp_endpoint": "/mcp",
        "health_check": "/health",
        "status": "running"
    })


# 서버 실행
if __name__ == "__main__":
    import os
    from src.config import HOST, PORT

    print(f"🏥 MediMatch MCP Server 시작")
    print(f"📍 MCP Endpoint: http://{HOST}:{PORT}/mcp")
    print(f"💚 Health Check: http://{HOST}:{PORT}/health")
    print(f"🔧 Transport: Streamable HTTP")

    # Streamable HTTP로 실행 (PlayMCP 호환)
    mcp.run(
        transport="streamable-http",
        host=HOST,
        port=PORT,
        path="/mcp",
    )
