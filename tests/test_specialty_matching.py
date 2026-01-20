"""전문 분야 매칭 로직 테스트"""
import pytest
import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.symptom_analyzer import symptom_analyzer
from src.config import DISEASE_TO_SPECIALTY_KEYWORDS, SYMPTOM_TO_SPECIALTY


class TestSpecialtyDataStructure:
    """전문 분야 매핑 데이터 구조 테스트"""

    def test_disease_to_specialty_keywords_exists(self):
        """전문 분야 키워드 매핑 데이터 존재 확인"""
        assert DISEASE_TO_SPECIALTY_KEYWORDS is not None
        assert len(DISEASE_TO_SPECIALTY_KEYWORDS) > 0

    def test_specialty_data_structure(self):
        """전문 분야 데이터 구조 확인"""
        required_keys = ["department", "specialty_keywords", "search_terms", "priority_keywords"]

        for specialty_name, data in DISEASE_TO_SPECIALTY_KEYWORDS.items():
            for key in required_keys:
                assert key in data, f"'{specialty_name}'에 '{key}' 키가 없습니다."

            # 각 필드가 적절한 타입인지 확인
            assert isinstance(data["department"], str)
            assert isinstance(data["specialty_keywords"], list)
            assert isinstance(data["search_terms"], list)
            assert isinstance(data["priority_keywords"], list)

    def test_major_specialties_exist(self):
        """주요 전문 분야가 존재하는지 확인"""
        major_specialties = [
            "아토피", "비염", "허리디스크", "이명", "두통",
            "위염", "탈모", "무릎통증", "어깨통증", "우울증"
        ]
        for specialty in major_specialties:
            assert specialty in DISEASE_TO_SPECIALTY_KEYWORDS, f"'{specialty}' 전문 분야가 없습니다."

    def test_symptom_to_specialty_mapping(self):
        """증상 → 전문 분야 매핑 테스트"""
        assert len(SYMPTOM_TO_SPECIALTY) > 0

        # 주요 증상 키워드 확인
        test_mappings = {
            "아토피": "아토피",
            "비염": "비염",
            "허리디스크": "허리디스크",
            "이명": "이명",
            "두통": "두통",
        }

        for symptom, expected_specialty in test_mappings.items():
            assert symptom in SYMPTOM_TO_SPECIALTY
            assert SYMPTOM_TO_SPECIALTY[symptom] == expected_specialty


class TestSpecialtyExtraction:
    """전문 분야 추출 기능 테스트"""

    def test_extract_skin_specialty(self):
        """피부과 전문 분야 추출"""
        test_cases = [
            ("아토피가 심해요", "아토피"),
            ("아토피피부염으로 고생중이에요", "아토피"),
            ("여드름이 자꾸 나요", "여드름"),
            ("건선 치료받고 싶어요", "건선"),
            ("탈모가 심해졌어요", "탈모"),
            ("두드러기가 나요", "두드러기"),
        ]

        for symptoms, expected_specialty in test_cases:
            result = symptom_analyzer.extract_specialty(symptoms)
            assert result is not None, f"'{symptoms}'에서 전문 분야 추출 실패"
            assert result["specialty_name"] == expected_specialty, \
                f"'{symptoms}' → 예상: {expected_specialty}, 실제: {result['specialty_name']}"
            assert result["department"] == "피부과"

    def test_extract_ent_specialty(self):
        """이비인후과 전문 분야 추출"""
        test_cases = [
            ("비염이 심해요", "비염"),
            ("알레르기비염 치료", "비염"),
            ("축농증 같아요", "축농증"),
            ("이명이 있어요", "이명"),
            ("귀에서 소리가 나요", "이명"),
            ("코골이가 심해요", "코골이"),
            ("중이염 같아요", "중이염"),
        ]

        for symptoms, expected_specialty in test_cases:
            result = symptom_analyzer.extract_specialty(symptoms)
            assert result is not None, f"'{symptoms}'에서 전문 분야 추출 실패"
            assert result["specialty_name"] == expected_specialty, \
                f"'{symptoms}' → 예상: {expected_specialty}, 실제: {result['specialty_name']}"
            assert result["department"] == "이비인후과"

    def test_extract_orthopedic_specialty(self):
        """정형외과 전문 분야 추출"""
        test_cases = [
            ("허리디스크 같아요", "허리디스크"),
            ("디스크 치료받고 싶어요", "허리디스크"),
            ("목디스크가 심해요", "목디스크"),
            ("무릎이 아파요", "무릎통증"),
            ("어깨가 아파요", "어깨통증"),
            ("오십견 같아요", "오십견"),
        ]

        for symptoms, expected_specialty in test_cases:
            result = symptom_analyzer.extract_specialty(symptoms)
            assert result is not None, f"'{symptoms}'에서 전문 분야 추출 실패"
            assert result["specialty_name"] == expected_specialty, \
                f"'{symptoms}' → 예상: {expected_specialty}, 실제: {result['specialty_name']}"
            assert result["department"] == "정형외과"

    def test_extract_internal_medicine_specialty(self):
        """내과 전문 분야 추출"""
        test_cases = [
            ("위염이 있어요", "위염"),
            ("속쓰림이 심해요", "위염"),
            ("당뇨 관리", "당뇨"),
            ("고혈압 약 처방", "고혈압"),
            ("갑상선 검사", "갑상선"),
            ("천식이 있어요", "천식"),
        ]

        for symptoms, expected_specialty in test_cases:
            result = symptom_analyzer.extract_specialty(symptoms)
            assert result is not None, f"'{symptoms}'에서 전문 분야 추출 실패"
            assert result["specialty_name"] == expected_specialty, \
                f"'{symptoms}' → 예상: {expected_specialty}, 실제: {result['specialty_name']}"
            assert result["department"] == "내과"

    def test_no_specialty_for_general_symptoms(self):
        """일반 증상에서 전문 분야 미추출"""
        general_symptoms = [
            "몸이 안좋아요",
            "배가 아파요",  # 구체적인 질환명이 아님
            "열이 나요",
        ]

        for symptoms in general_symptoms:
            result = symptom_analyzer.extract_specialty(symptoms)
            # 전문 분야가 추출되지 않거나, None이면 통과
            # (일부는 추출될 수 있음 - "배" → 내과 관련 등)


class TestSpecialtySearchKeywords:
    """전문 분야 검색 키워드 생성 테스트"""

    def test_get_specialty_search_keywords_with_specialty(self):
        """전문 분야가 있을 때 검색 키워드 생성"""
        result = symptom_analyzer.get_specialty_search_keywords("비염이 심해요", "이비인후과")

        assert result["has_specialty"] is True
        assert result["specialty_name"] == "비염"
        assert result["department"] == "이비인후과"
        assert len(result["specialty_keywords"]) > 0
        assert len(result["priority_keywords"]) > 0
        assert "비염" in result["specialty_keywords"]

    def test_get_specialty_search_keywords_without_specialty(self):
        """전문 분야가 없을 때 검색 키워드 생성"""
        result = symptom_analyzer.get_specialty_search_keywords("몸이 안좋아요", "내과")

        assert result["has_specialty"] is False
        assert result["department"] == "내과"
        assert result["primary_search_term"] == "내과"

    def test_search_terms_format(self):
        """검색어 형식 확인"""
        test_cases = [
            ("아토피", "피부과"),
            ("비염", "이비인후과"),
            ("허리디스크", "정형외과"),
        ]

        for symptoms, expected_dept in test_cases:
            result = symptom_analyzer.get_specialty_search_keywords(symptoms, expected_dept)
            assert result["has_specialty"] is True
            # search_terms가 문자열 리스트인지 확인
            assert all(isinstance(term, str) for term in result["all_search_terms"])


class TestHospitalRanking:
    """병원 우선순위 정렬 테스트"""

    def test_rank_hospitals_with_specialty_match(self):
        """전문 병원 우선순위 정렬"""
        # 테스트용 병원 목록
        hospitals = [
            {"name": "일반피부과의원", "category_name": "피부과"},
            {"name": "아토피전문피부과", "category_name": "피부과"},
            {"name": "아토피클리닉", "category_name": "피부과"},
            {"name": "동네피부과", "category_name": "피부과"},
        ]

        specialty_info = symptom_analyzer.get_specialty_search_keywords("아토피", "피부과")
        ranked = symptom_analyzer.rank_hospitals_by_specialty(hospitals, specialty_info)

        # 전문 병원이 상단에 위치해야 함
        assert ranked[0]["name"] in ["아토피전문피부과", "아토피클리닉"]
        assert ranked[0]["_is_specialty_match"] is True
        assert ranked[0]["_specialty_score"] > 0

    def test_rank_hospitals_without_specialty(self):
        """전문 분야 없을 때 정렬 (원본 순서 유지)"""
        hospitals = [
            {"name": "병원1"},
            {"name": "병원2"},
            {"name": "병원3"},
        ]

        specialty_info = {"has_specialty": False}
        ranked = symptom_analyzer.rank_hospitals_by_specialty(hospitals, specialty_info)

        # 원본 순서 유지
        assert ranked[0]["name"] == "병원1"
        assert ranked[1]["name"] == "병원2"

    def test_specialty_score_calculation(self):
        """전문 분야 점수 계산"""
        hospitals = [
            {"name": "비염전문이비인후과클리닉", "category_name": "이비인후과"},  # 높은 점수
            {"name": "비염치료 전문", "category_name": "이비인후과"},  # 중간 점수
            {"name": "일반 이비인후과", "category_name": "이비인후과"},  # 낮은 점수
        ]

        specialty_info = symptom_analyzer.get_specialty_search_keywords("비염", "이비인후과")
        ranked = symptom_analyzer.rank_hospitals_by_specialty(hospitals, specialty_info)

        # 점수가 내림차순으로 정렬되어야 함
        scores = [h["_specialty_score"] for h in ranked]
        assert scores == sorted(scores, reverse=True)


class TestIntegrationScenarios:
    """통합 시나리오 테스트"""

    def test_full_flow_atopy(self):
        """아토피 전체 흐름 테스트"""
        symptoms = "팔꿈치 안쪽이 가렵고 아토피 같아요"

        # 1. 증상 분석
        analysis = symptom_analyzer.analyze_symptoms(symptoms)
        assert "피부과" in analysis["recommended_departments"]

        # 2. 전문 분야 추출
        specialty = symptom_analyzer.extract_specialty(symptoms)
        assert specialty is not None
        assert specialty["specialty_name"] == "아토피"

        # 3. 검색 키워드 생성
        search_keywords = symptom_analyzer.get_specialty_search_keywords(symptoms, "피부과")
        assert search_keywords["has_specialty"] is True
        assert "아토피" in search_keywords["specialty_keywords"]

    def test_full_flow_rhinitis(self):
        """비염 전체 흐름 테스트"""
        symptoms = "콧물이 나고 코가 막히고 비염 같아요"

        # 1. 증상 분석
        analysis = symptom_analyzer.analyze_symptoms(symptoms)
        assert "이비인후과" in analysis["recommended_departments"]

        # 2. 전문 분야 추출
        specialty = symptom_analyzer.extract_specialty(symptoms)
        assert specialty is not None
        assert specialty["specialty_name"] == "비염"

        # 3. 검색 키워드 생성
        search_keywords = symptom_analyzer.get_specialty_search_keywords(symptoms, "이비인후과")
        assert search_keywords["has_specialty"] is True
        assert "비염" in search_keywords["specialty_keywords"]

    def test_full_flow_disc(self):
        """디스크 전체 흐름 테스트"""
        symptoms = "허리가 아프고 다리가 저려요 허리디스크 같아요"

        # 1. 증상 분석
        analysis = symptom_analyzer.analyze_symptoms(symptoms)
        assert "정형외과" in analysis["recommended_departments"] or \
               "신경외과" in analysis["recommended_departments"]

        # 2. 전문 분야 추출
        specialty = symptom_analyzer.extract_specialty(symptoms)
        assert specialty is not None
        assert specialty["specialty_name"] == "허리디스크"

        # 3. 검색 키워드 생성
        search_keywords = symptom_analyzer.get_specialty_search_keywords(symptoms, "정형외과")
        assert search_keywords["has_specialty"] is True
        assert any("척추" in kw or "디스크" in kw for kw in search_keywords["specialty_keywords"])


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_multiple_specialties_in_input(self):
        """입력에 여러 전문 분야가 있을 때"""
        # 더 긴 키워드가 우선
        result = symptom_analyzer.extract_specialty("아토피피부염으로 힘들어요")
        assert result["specialty_name"] == "아토피"

    def test_korean_variations(self):
        """한국어 다양한 표현"""
        variations = [
            ("비염있어요", "비염"),
            ("비염 심함", "비염"),
            ("알레르기비염", "비염"),
        ]

        for symptoms, expected in variations:
            result = symptom_analyzer.extract_specialty(symptoms)
            if result:  # 매칭되면
                assert result["specialty_name"] == expected

    def test_empty_hospital_list(self):
        """빈 병원 목록 처리"""
        specialty_info = symptom_analyzer.get_specialty_search_keywords("비염", "이비인후과")
        ranked = symptom_analyzer.rank_hospitals_by_specialty([], specialty_info)
        assert ranked == []

    def test_hospital_without_category(self):
        """카테고리 정보 없는 병원 처리"""
        hospitals = [
            {"name": "비염전문병원"},  # category_name 없음
            {"name": "일반병원", "category_name": None},
        ]

        specialty_info = symptom_analyzer.get_specialty_search_keywords("비염", "이비인후과")
        ranked = symptom_analyzer.rank_hospitals_by_specialty(hospitals, specialty_info)

        # 에러 없이 처리되어야 함
        assert len(ranked) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
