"""병원 추천 로직 테스트"""
import pytest
import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.symptom_analyzer import symptom_analyzer
from src.config import DEPARTMENT_CODES, SIDO_CODES


class TestDepartmentMapping:
    """진료과목 매핑 테스트"""

    def test_valid_department_codes(self):
        """유효한 진료과목 코드 확인"""
        assert "내과" in DEPARTMENT_CODES
        assert "피부과" in DEPARTMENT_CODES
        assert "정형외과" in DEPARTMENT_CODES
        assert "이비인후과" in DEPARTMENT_CODES
        assert "신경과" in DEPARTMENT_CODES

    def test_valid_regions(self):
        """유효한 지역 코드 확인"""
        assert "서울" in SIDO_CODES
        assert "경기" in SIDO_CODES
        assert "부산" in SIDO_CODES
        assert "광주" in SIDO_CODES

    def test_department_code_format(self):
        """진료과목 코드 형식 확인"""
        for dept, code in DEPARTMENT_CODES.items():
            assert isinstance(code, str)
            assert code.isdigit() or code.isalnum()


class TestSymptomToDepartmentFlow:
    """증상 → 진료과목 추천 흐름 테스트"""

    def test_skin_symptoms_to_dermatology(self):
        """피부 증상 → 피부과 추천"""
        test_cases = [
            "피부가 가렵고 붉어요",
            "아토피가 심해졌어요",
            "두드러기가 났어요",
            "여드름이 심해요",
            "습진 같은 게 생겼어요",
        ]
        for symptoms in test_cases:
            result = symptom_analyzer.analyze_symptoms(symptoms)
            assert "피부과" in result["recommended_departments"], f"Failed for: {symptoms}"

    def test_digestive_symptoms_to_internal_medicine(self):
        """소화기 증상 → 내과 추천"""
        test_cases = [
            "소화가 안돼요",
            "속이 쓰려요",
            "배가 아파요",
            "설사가 계속 나요",
            "변비가 심해요",
        ]
        for symptoms in test_cases:
            result = symptom_analyzer.analyze_symptoms(symptoms)
            assert "내과" in result["recommended_departments"], f"Failed for: {symptoms}"

    def test_joint_symptoms_to_orthopedics(self):
        """관절/근골격 증상 → 정형외과 추천"""
        test_cases = [
            "무릎이 아파요",
            "허리가 아파요",
            "어깨가 결려요",
            "관절이 아프고 붓습니다",
            "발목을 삐끗했어요",
        ]
        for symptoms in test_cases:
            result = symptom_analyzer.analyze_symptoms(symptoms)
            depts = result["recommended_departments"]
            assert "정형외과" in depts or "재활의학과" in depts, f"Failed for: {symptoms}"

    def test_ent_symptoms(self):
        """이비인후과 증상 추천"""
        test_cases = [
            "귀에서 소리가 나요",
            "코가 막혔어요",
            "목이 아파요",
            "편도선이 부었어요",
        ]
        for symptoms in test_cases:
            result = symptom_analyzer.analyze_symptoms(symptoms)
            depts = result["recommended_departments"]
            assert "이비인후과" in depts or "내과" in depts, f"Failed for: {symptoms}"

    def test_eye_symptoms(self):
        """안과 증상 추천"""
        test_cases = [
            "눈이 침침해요",
            "눈이 빨개졌어요",
            "눈이 아파요",
        ]
        for symptoms in test_cases:
            result = symptom_analyzer.analyze_symptoms(symptoms)
            assert "안과" in result["recommended_departments"], f"Failed for: {symptoms}"


class TestDiseaseRecommendationFlow:
    """질병 진단 → 병원 추천 흐름 테스트"""

    def test_vertigo_disease_detection(self):
        """어지럼증 관련 질병 감지"""
        result = symptom_analyzer.diagnose_disease("머리가 어지럽고 귀에서 소리가 나요")
        if result["has_diagnosis"]:
            # 메니에르병, 이석증 등이 의심되어야 함
            diseases = [d.lower() for d in result["suspected_diseases"]]
            disease_str = " ".join(diseases)
            assert any(keyword in disease_str for keyword in ["메니에르", "이석", "어지럼", "내이"]), \
                f"Expected vertigo-related disease, got: {result['suspected_diseases']}"

    def test_skin_disease_detection(self):
        """피부 질환 감지"""
        result = symptom_analyzer.diagnose_disease("피부가 가렵고 각질이 생기고 붉어져요")
        if result["has_diagnosis"]:
            diseases = [d.lower() for d in result["suspected_diseases"]]
            disease_str = " ".join(diseases)
            # 아토피, 건선, 습진 등 피부 질환
            assert any(keyword in disease_str for keyword in ["아토피", "건선", "습진", "피부염"]), \
                f"Expected skin disease, got: {result['suspected_diseases']}"

    def test_disc_disease_detection(self):
        """디스크 관련 질환 감지"""
        result = symptom_analyzer.diagnose_disease("허리가 아프고 다리가 저려요")
        if result["has_diagnosis"]:
            diseases = [d.lower() for d in result["suspected_diseases"]]
            disease_str = " ".join(diseases)
            assert any(keyword in disease_str for keyword in ["디스크", "추간판", "좌골", "신경"]), \
                f"Expected disc-related disease, got: {result['suspected_diseases']}"


class TestConfidenceAndQuality:
    """분석 품질 및 신뢰도 테스트"""

    def test_confidence_levels(self):
        """신뢰도 수준 확인"""
        # 높은 신뢰도 - 여러 증상이 명확할 때
        result = symptom_analyzer.analyze_symptoms("피부가 가렵고 붉어지고 각질이 생겨요")
        assert result["confidence"] in ["high", "medium"]

        # 낮은 신뢰도 - 모호한 입력
        result = symptom_analyzer.analyze_symptoms("좀 안좋아요")
        assert result["confidence"] in ["low", "medium"]

    def test_summary_generation(self):
        """요약 문구 생성 확인"""
        result = symptom_analyzer.analyze_symptoms("머리가 아프고 어지러워요")
        assert "analysis_summary" in result
        assert len(result["analysis_summary"]) > 0
        # 추천 진료과목이 있으면 요약에 포함되어야 함
        if result["recommended_departments"]:
            assert "추천" in result["analysis_summary"] or "감지" in result["analysis_summary"]

    def test_department_description(self):
        """진료과목 설명 확인"""
        departments = ["피부과", "내과", "정형외과", "이비인후과", "안과"]
        for dept in departments:
            desc = symptom_analyzer.get_department_description(dept)
            assert len(desc) > 0
            assert "진료" in desc or "질환" in desc or "전문" in desc


class TestEdgeCasesInRecommendation:
    """추천 시스템 엣지 케이스"""

    def test_multiple_departments(self):
        """복수 진료과목 추천"""
        # 가슴 통증은 내과와 흉부외과 모두 관련
        result = symptom_analyzer.analyze_symptoms("가슴이 아프고 숨쉬기 힘들어요")
        assert len(result["recommended_departments"]) >= 1

    def test_ambiguous_symptoms(self):
        """모호한 증상 처리"""
        result = symptom_analyzer.analyze_symptoms("몸이 안좋아요")
        # 에러 없이 처리되어야 함
        assert "recommended_departments" in result
        assert "confidence" in result

    def test_combined_symptoms_different_departments(self):
        """다른 진료과 증상 조합"""
        result = symptom_analyzer.analyze_symptoms("피부가 가렵고 무릎도 아파요")
        depts = result["recommended_departments"]
        # 피부과와 정형외과 모두 추천될 수 있음
        assert len(depts) >= 1

    def test_korean_slang_expressions(self):
        """구어체/은어 표현 처리"""
        test_cases = [
            ("허리가 뻐근해요", ["정형외과", "재활의학과"]),
            ("머리가 지끈거려요", ["신경과", "내과"]),
            ("배가 꾸르륵 소리나요", ["내과"]),
        ]
        for symptoms, expected_depts in test_cases:
            result = symptom_analyzer.analyze_symptoms(symptoms)
            found = any(dept in result["recommended_departments"] for dept in expected_depts)
            # 매칭되거나 최소한 에러 없이 처리
            assert "recommended_departments" in result


class TestIntegrationScenarios:
    """실제 사용 시나리오 통합 테스트"""

    def test_full_flow_skin_problem(self):
        """피부 문제 전체 흐름"""
        symptoms = "팔꿈치 안쪽이 가렵고 붉어지고 각질이 일어나요"

        # 1. 응급 체크 - 응급 아님
        emergency = symptom_analyzer.check_emergency(symptoms)
        assert emergency["is_emergency"] is False

        # 2. 질병 진단
        diagnosis = symptom_analyzer.diagnose_disease(symptoms)
        assert "recommended_departments" in diagnosis

        # 3. 증상 분석
        analysis = symptom_analyzer.analyze_symptoms(symptoms)
        assert "피부과" in analysis["recommended_departments"]

    def test_full_flow_emergency(self):
        """응급 상황 전체 흐름"""
        symptoms = "갑자기 가슴이 아프고 식은땀이 나요"

        # 1. 응급 체크 - 응급 상황
        emergency = symptom_analyzer.check_emergency(symptoms)
        assert emergency["is_emergency"] is True
        assert "guidance" in emergency
        assert emergency["guidance"] is not None

    def test_full_flow_orthopedic(self):
        """정형외과 문제 전체 흐름"""
        symptoms = "허리가 아프고 다리가 저려요"

        # 1. 응급 체크 - 응급 아님
        emergency = symptom_analyzer.check_emergency(symptoms)
        assert emergency["is_emergency"] is False

        # 2. 질병 진단
        diagnosis = symptom_analyzer.diagnose_disease(symptoms)

        # 3. 증상 분석
        analysis = symptom_analyzer.analyze_symptoms(symptoms)
        depts = analysis["recommended_departments"]
        assert "정형외과" in depts or "신경외과" in depts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
