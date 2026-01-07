"""증상 분석 및 진료과목 추천 모듈"""
from typing import List, Dict, Tuple
from .config import SYMPTOM_TO_DEPARTMENT, DEPARTMENT_CODES, DISEASE_KEYWORDS


class SymptomAnalyzer:
    """증상을 분석하여 적절한 진료과목을 추천하는 클래스"""

    def __init__(self):
        self.symptom_mapping = SYMPTOM_TO_DEPARTMENT
        self.disease_keywords = DISEASE_KEYWORDS

    def analyze_symptoms(self, user_input: str) -> Dict:
        """
        사용자 입력을 분석하여 증상과 추천 진료과목을 반환

        Args:
            user_input: 사용자가 입력한 증상 설명

        Returns:
            분석 결과 딕셔너리
        """
        # 입력 정규화
        normalized_input = user_input.lower().replace(" ", "")

        # 매칭된 증상들
        matched_symptoms = []
        # 추천 진료과목 (점수 기반)
        department_scores: Dict[str, float] = {}

        # 증상 매칭
        for symptom, departments in self.symptom_mapping.items():
            symptom_normalized = symptom.lower().replace(" ", "")
            if symptom_normalized in normalized_input:
                matched_symptoms.append(symptom)
                for i, dept in enumerate(departments):
                    # 첫 번째 진료과목에 더 높은 점수 부여
                    score = 1.0 / (i + 1)
                    department_scores[dept] = department_scores.get(dept, 0) + score

        # 점수 기준 정렬
        sorted_departments = sorted(
            department_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # 상위 3개 진료과목 추출
        recommended_departments = [dept for dept, _ in sorted_departments[:3]]

        # 관련 질환 키워드 추출
        related_keywords = set()
        for symptom in matched_symptoms:
            for disease, keywords in self.disease_keywords.items():
                if symptom in disease or disease in symptom:
                    related_keywords.update(keywords)

        return {
            "matched_symptoms": matched_symptoms,
            "recommended_departments": recommended_departments,
            "department_scores": dict(sorted_departments),
            "related_keywords": list(related_keywords),
            "confidence": self._calculate_confidence(matched_symptoms, sorted_departments),
            "analysis_summary": self._generate_summary(matched_symptoms, recommended_departments),
        }

    def _calculate_confidence(
        self,
        matched_symptoms: List[str],
        sorted_departments: List[Tuple[str, float]]
    ) -> str:
        """분석 신뢰도 계산"""
        if not matched_symptoms:
            return "low"
        if len(matched_symptoms) >= 3 and sorted_departments and sorted_departments[0][1] >= 2.0:
            return "high"
        if len(matched_symptoms) >= 1:
            return "medium"
        return "low"

    def _generate_summary(
        self,
        matched_symptoms: List[str],
        recommended_departments: List[str]
    ) -> str:
        """분석 요약 문구 생성"""
        if not matched_symptoms:
            return "입력하신 내용에서 특정 증상을 파악하기 어렵습니다. 더 구체적인 증상을 설명해주세요."

        symptoms_str = ", ".join(matched_symptoms[:3])
        if len(matched_symptoms) > 3:
            symptoms_str += f" 외 {len(matched_symptoms) - 3}개"

        if recommended_departments:
            dept_str = ", ".join(recommended_departments[:2])
            return f"'{symptoms_str}' 증상이 감지되었습니다. {dept_str} 진료를 추천드립니다."
        else:
            return f"'{symptoms_str}' 증상이 감지되었습니다."

    def get_department_description(self, department: str) -> str:
        """진료과목 설명 반환"""
        descriptions = {
            "피부과": "피부 질환(아토피, 건선, 여드름, 습진 등)을 전문으로 진료합니다.",
            "내과": "감기, 소화기 질환, 만성질환(당뇨, 고혈압) 등 내장 기관 질환을 진료합니다.",
            "정형외과": "뼈, 관절, 근육, 인대 등 근골격계 질환을 진료합니다.",
            "신경외과": "디스크, 척추 질환, 뇌 질환 등을 수술적으로 치료합니다.",
            "이비인후과": "귀, 코, 목 관련 질환을 전문으로 진료합니다.",
            "안과": "눈과 시력 관련 질환을 진료합니다.",
            "신경과": "두통, 어지럼증, 뇌졸중 등 신경계 질환을 진료합니다.",
            "정신건강의학과": "우울증, 불안, 불면증 등 정신건강 관련 질환을 진료합니다.",
            "비뇨의학과": "방광, 신장, 전립선 등 비뇨기계 질환을 진료합니다.",
            "산부인과": "여성 생식기 질환 및 임신 관련 진료를 합니다.",
            "소아청소년과": "영유아 및 청소년의 질환을 전문으로 진료합니다.",
            "외과": "수술이 필요한 다양한 질환을 치료합니다.",
            "재활의학과": "손상 후 재활치료 및 만성 통증 관리를 합니다.",
        }
        return descriptions.get(department, f"{department} 관련 질환을 진료합니다.")

    def is_valid_department(self, department: str) -> bool:
        """유효한 진료과목인지 확인"""
        return department in DEPARTMENT_CODES


# 싱글톤 인스턴스
symptom_analyzer = SymptomAnalyzer()
