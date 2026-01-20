"""증상 분석기 테스트"""
import pytest
import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.symptom_analyzer import symptom_analyzer


class TestSymptomMatching:
    """증상 매칭 테스트"""

    def test_basic_symptom_matching(self):
        """기본 증상 매칭"""
        result = symptom_analyzer.analyze_symptoms("머리가 아파요")
        assert "matched_symptoms" in result
        assert len(result["recommended_departments"]) > 0

    def test_multiple_symptoms(self):
        """복합 증상 매칭"""
        result = symptom_analyzer.analyze_symptoms("두통이 있고 어지러워요")
        assert len(result["matched_symptoms"]) >= 1

    def test_korean_colloquial(self):
        """구어체 표현 매칭"""
        result = symptom_analyzer.analyze_symptoms("배가 꾸르륵 소리나고 아파")
        assert "matched_symptoms" in result

    def test_fuzzy_matching(self):
        """퍼지 매칭 테스트"""
        # 정확하지 않은 표현도 매칭되어야 함
        result = symptom_analyzer.analyze_symptoms("허리뻐근해요")
        assert "matched_symptoms" in result


class TestDiseasesDiagnosis:
    """질병 진단 테스트"""

    def test_disease_diagnosis(self):
        """질병 진단 기능"""
        result = symptom_analyzer.diagnose_disease("머리가 어지럽고 귀에서 소리가 나요")
        assert "has_diagnosis" in result
        assert "suspected_diseases" in result
        assert "recommended_departments" in result

    def test_combination_symptoms(self):
        """복합 증상 조합 진단"""
        result = symptom_analyzer.diagnose_disease("피부가 가렵고 붉어지고 각질이 있어요")
        assert result["has_diagnosis"] is True
        assert len(result["suspected_diseases"]) > 0


class TestEmergencyDetection:
    """응급 증상 감지 테스트"""

    def test_stroke_detection(self):
        """뇌졸중 증상 감지"""
        result = symptom_analyzer.check_emergency("갑자기 팔다리가 마비되고 말이 어눌해요")
        assert result["is_emergency"] is True
        assert any(e["type"] == "뇌졸중" for e in result["detected_emergencies"])

    def test_heart_attack_detection(self):
        """심근경색 증상 감지"""
        result = symptom_analyzer.check_emergency("가슴통증이 있고 식은땀이 나요")
        assert result["is_emergency"] is True
        assert any(e["type"] == "심근경색" for e in result["detected_emergencies"])

    def test_breathing_emergency(self):
        """호흡 응급 감지"""
        result = symptom_analyzer.check_emergency("숨을 못 쉬겠어요 호흡곤란")
        assert result["is_emergency"] is True

    def test_normal_symptom_not_emergency(self):
        """일반 증상은 응급이 아님"""
        result = symptom_analyzer.check_emergency("콧물이 나고 기침이 나요")
        assert result["is_emergency"] is False

    def test_emergency_guidance_included(self):
        """응급 상황 안내 포함 확인"""
        result = symptom_analyzer.check_emergency("의식을 잃었어요")
        if result["is_emergency"]:
            assert "guidance" in result
            assert result["guidance"] is not None


class TestDepartmentRecommendation:
    """진료과 추천 테스트"""

    def test_skin_department(self):
        """피부과 추천"""
        result = symptom_analyzer.analyze_symptoms("피부가 가렵고 붉어요")
        assert "피부과" in result["recommended_departments"]

    def test_orthopedic_department(self):
        """정형외과 추천"""
        result = symptom_analyzer.analyze_symptoms("무릎이 아파요")
        assert "정형외과" in result["recommended_departments"]

    def test_internal_medicine(self):
        """내과 추천"""
        result = symptom_analyzer.analyze_symptoms("소화가 안되고 속이 더부룩해요")
        assert "내과" in result["recommended_departments"]


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_input(self):
        """빈 입력"""
        result = symptom_analyzer.analyze_symptoms("")
        assert result["confidence"] == "low"

    def test_unrecognized_symptoms(self):
        """인식 불가 증상"""
        result = symptom_analyzer.analyze_symptoms("asdfasdf")
        assert result["matched_symptoms"] == []

    def test_special_characters(self):
        """특수문자 처리"""
        result = symptom_analyzer.analyze_symptoms("머리가 아파요!!???")
        assert "matched_symptoms" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
