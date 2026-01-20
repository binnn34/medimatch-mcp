"""증상 분석 및 진료과목 추천 모듈"""
import re
from typing import List, Dict, Tuple, Set, Optional
from .config import (
    SYMPTOM_TO_DEPARTMENT,
    DEPARTMENT_CODES,
    DISEASE_KEYWORDS,
    SYMPTOM_TO_DISEASE,
    SINGLE_SYMPTOM_TO_DISEASE,
    DISEASE_TO_SPECIALTY_KEYWORDS,
    SYMPTOM_TO_SPECIALTY,
)

# 응급 증상 키워드 (119 안내 필요)
EMERGENCY_SYMPTOMS = {
    # 뇌졸중 증상 (FAST)
    "뇌졸중": ["얼굴마비", "안면마비", "반신마비", "팔다리마비", "마비", "말어눌", "어눌", "발음이상", "언어장애", "갑자기쓰러", "의식잃"],
    # 심근경색/심장마비 증상
    "심근경색": ["가슴통증", "흉통", "가슴압박", "가슴아", "왼팔통증", "왼팔저", "턱통증", "식은땀", "호흡곤란", "숨못쉬"],
    # 중증 출혈
    "출혈": ["대량출혈", "피가멈추지않", "피가안멈", "피흘리"],
    # 호흡 응급
    "호흡곤란": ["숨못쉬", "호흡정지", "질식", "숨이안쉬", "기도막힘", "호흡곤란"],
    # 의식 이상
    "의식장애": ["의식없", "의식잃", "정신잃", "기절", "쓰러져서안일어", "혼수"],
    # 중독
    "중독": ["독극물", "약물과다", "가스중독", "일산화탄소"],
    # 심한 알레르기
    "아나필락시스": ["온몸부어", "목부어", "호흡곤란알러지", "아나필락시스"],
    # 경련
    "경련": ["경련", "발작", "전신경련", "간질발작"],
}

# 응급 상황 안내 메시지
EMERGENCY_GUIDANCE = {
    "immediate_action": "🚨 응급 상황으로 판단됩니다! 즉시 119에 전화하세요.",
    "call_119": "📞 119 (소방서/응급의료)",
    "while_waiting": "구급대 도착 전: 환자를 안정시키고, 의식과 호흡을 확인하세요.",
    "do_not_move": "무리하게 환자를 움직이지 마세요 (단, 위험한 장소에서는 안전한 곳으로 이동).",
}


class SymptomAnalyzer:
    """증상을 분석하여 의심 질병과 진료과목을 추천하는 클래스"""

    def __init__(self):
        self.symptom_mapping = SYMPTOM_TO_DEPARTMENT
        self.disease_keywords = DISEASE_KEYWORDS
        self.symptom_to_disease = SYMPTOM_TO_DISEASE
        self.single_symptom_to_disease = SINGLE_SYMPTOM_TO_DISEASE
        self.emergency_symptoms = EMERGENCY_SYMPTOMS
        # 불용어 (매칭에서 제외할 단어들)
        self.stopwords = {'이', '가', '을', '를', '은', '는', '에', '의', '로', '으로', '와', '과', '도', '만', '좀', '너무', '많이', '조금', '약간', '계속', '자꾸', '요즘', '오늘', '어제', '최근'}

    def check_emergency(self, user_input: str) -> Dict:
        """
        응급 증상 여부를 확인합니다.

        Args:
            user_input: 사용자가 입력한 증상 설명

        Returns:
            응급 상황 정보 딕셔너리
        """
        normalized_input = self._normalize_text(user_input)
        detected_emergencies = []

        for emergency_type, keywords in self.emergency_symptoms.items():
            for keyword in keywords:
                keyword_normalized = self._normalize_text(keyword)
                if keyword_normalized in normalized_input:
                    detected_emergencies.append({
                        "type": emergency_type,
                        "matched_keyword": keyword,
                    })
                    break  # 같은 카테고리 중복 방지

        if detected_emergencies:
            return {
                "is_emergency": True,
                "detected_emergencies": detected_emergencies,
                "guidance": EMERGENCY_GUIDANCE,
                "message": f"⚠️ '{', '.join([e['type'] for e in detected_emergencies])}' 관련 응급 증상이 감지되었습니다!",
            }

        return {
            "is_emergency": False,
            "detected_emergencies": [],
            "guidance": None,
            "message": None,
        }

    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화: 공백 제거, 소문자화, 특수문자 제거"""
        # 공백 제거
        text = text.replace(" ", "")
        # 소문자화
        text = text.lower()
        # 물음표, 마침표 등 제거
        text = re.sub(r'[?.!,~\-]', '', text)
        return text

    def _extract_symptom_keywords(self, text: str) -> Set[str]:
        """텍스트에서 의미있는 증상 키워드 추출"""
        # 정규화
        normalized = self._normalize_text(text)

        # 다양한 길이의 부분 문자열 생성 (2~10자)
        substrings = set()
        for length in range(2, min(len(normalized) + 1, 11)):
            for i in range(len(normalized) - length + 1):
                substrings.add(normalized[i:i+length])

        return substrings

    def _fuzzy_match(self, symptom_key: str, normalized_input: str, input_substrings: Set[str]) -> bool:
        """
        증상 키워드와 사용자 입력 간의 퍼지 매칭

        매칭 전략:
        1. 정확한 포함 매칭 (symptom in input) - 2글자 이상
        2. 역방향 매칭 (input의 일부가 symptom에 포함) - 3글자 이상 (오매칭 방지)
        3. 부분 문자열 매칭 (3글자 이상 공통 부분)
        """
        symptom_normalized = self._normalize_text(symptom_key)

        # 1. 정확한 포함 매칭 (증상 키워드가 입력에 포함)
        # 2글자 이상 키워드도 정확히 포함되면 매칭 (뻐근, 지끈, 침침 등)
        if len(symptom_normalized) >= 2 and symptom_normalized in normalized_input:
            return True

        # 2. 역방향 매칭: 입력의 부분 문자열이 증상 키워드에 포함
        # 최소 3글자 이상만 매칭 (너무 짧으면 오매칭 발생)
        min_match_length = 3
        for sub in input_substrings:
            if len(sub) >= min_match_length:
                # 입력의 일부가 증상 키워드를 포함
                if sub in symptom_normalized and len(symptom_normalized) <= len(sub) + 2:
                    return True
                # 증상 키워드의 일부가 입력에 포함
                if symptom_normalized in sub:
                    return True

        # 3. 핵심 키워드 추출 매칭 (꾸르륵, 뻐근, 삐끗 등)
        # 증상 키워드에서 핵심 부분 추출 (3~6글자)
        # 단, 증상 키워드 자체가 3글자 이상이어야 함
        if len(symptom_normalized) >= 3:
            for length in range(3, min(len(symptom_normalized) + 1, 7)):
                for i in range(len(symptom_normalized) - length + 1):
                    keyword_part = symptom_normalized[i:i+length]
                    if keyword_part in normalized_input:
                        return True

        return False

    def diagnose_disease(self, user_input: str) -> Dict:
        """
        증상을 분석하여 의심되는 질병(진단)을 반환

        Args:
            user_input: 사용자가 입력한 증상 설명

        Returns:
            의심 질병 정보 딕셔너리
        """
        normalized_input = self._normalize_text(user_input)
        input_substrings = self._extract_symptom_keywords(user_input)

        # 1. 복합 증상 매칭 (여러 증상이 함께 나타날 때)
        matched_combo_diseases = []
        for symptom_combo, disease_info in self.symptom_to_disease.items():
            # 증상 조합의 모든 증상이 입력에 포함되는지 확인
            all_matched = True
            for symptom in symptom_combo:
                if not self._fuzzy_match(symptom, normalized_input, input_substrings):
                    all_matched = False
                    break

            if all_matched:
                matched_combo_diseases.append({
                    "symptom_combo": symptom_combo,
                    "diseases": disease_info["diseases"],
                    "description": disease_info["description"],
                    "severity": disease_info["severity"],
                    "departments": disease_info["departments"],
                    "match_type": "combination",
                })

        # 2. 단일 증상 매칭 (더 유연한 매칭)
        matched_single_diseases = []
        matched_symptom_keys = set()  # 중복 방지

        for symptom_key, disease_info in self.single_symptom_to_disease.items():
            if self._fuzzy_match(symptom_key, normalized_input, input_substrings):
                # 같은 질병 목록을 가진 증상은 중복 제거
                disease_tuple = tuple(disease_info["diseases"])
                if disease_tuple not in matched_symptom_keys:
                    matched_symptom_keys.add(disease_tuple)
                    matched_single_diseases.append({
                        "symptom": symptom_key,
                        "diseases": disease_info["diseases"],
                        "description": disease_info["description"],
                        "severity": disease_info["severity"],
                        "departments": disease_info["departments"],
                        "match_type": "single",
                    })

        # 결과 조합 (복합 + 단일 모두 포함하여 더 많은 의심 질환 제공)
        all_diseases = []
        all_departments = []

        # 복합 증상 매칭 결과 추가
        for match in matched_combo_diseases:
            all_diseases.extend(match["diseases"])
            all_departments.extend(match["departments"])

        # 단일 증상 매칭 결과도 추가 (복합 매칭과 함께 표시)
        for match in matched_single_diseases:
            all_diseases.extend(match["diseases"])
            all_departments.extend(match["departments"])

        # 중복 제거 (순서 유지)
        unique_diseases = list(dict.fromkeys(all_diseases))
        unique_departments = list(dict.fromkeys(all_departments))

        # 가장 관련성 높은 질병 정보 (복합 매칭 우선)
        primary_diagnosis = None
        if matched_combo_diseases:
            primary_diagnosis = matched_combo_diseases[0]
        elif matched_single_diseases:
            primary_diagnosis = matched_single_diseases[0]

        return {
            "has_diagnosis": bool(unique_diseases),
            "suspected_diseases": unique_diseases[:5],  # 상위 5개
            "primary_diagnosis": primary_diagnosis,
            "combo_matches": matched_combo_diseases,
            "single_matches": matched_single_diseases,
            "recommended_departments": unique_departments[:3],
            "severity": primary_diagnosis["severity"] if primary_diagnosis else None,
            "diagnosis_description": primary_diagnosis["description"] if primary_diagnosis else None,
        }

    def analyze_symptoms(self, user_input: str) -> Dict:
        """
        사용자 입력을 분석하여 증상과 추천 진료과목을 반환

        Args:
            user_input: 사용자가 입력한 증상 설명

        Returns:
            분석 결과 딕셔너리
        """
        # 입력 정규화
        normalized_input = self._normalize_text(user_input)

        # 부분 문자열 추출 (퍼지 매칭용)
        input_substrings = self._extract_symptom_keywords(user_input)

        # 매칭된 증상들
        matched_symptoms = []
        matched_symptom_keys = set()  # 중복 방지용
        # 추천 진료과목 (점수 기반)
        department_scores: Dict[str, float] = {}

        # 증상 매칭 - 3가지 방식 시도
        for symptom, departments in self.symptom_mapping.items():
            symptom_normalized = self._normalize_text(symptom)

            # 1. 정확한 포함 매칭 (기존 방식)
            exact_match = symptom_normalized in normalized_input

            # 2. 역방향 매칭 (사용자 입력의 일부가 증상 키워드에 포함)
            reverse_match = any(
                sub in symptom_normalized
                for sub in input_substrings
                if len(sub) >= 3  # 최소 3글자 이상
            )

            # 3. 증상 키워드가 입력에 포함 (정규화된 상태)
            keyword_match = symptom_normalized in input_substrings

            if exact_match or reverse_match or keyword_match:
                # 중복 방지: 같은 진료과를 가리키는 유사 증상은 하나만
                symptom_key = tuple(sorted(departments))
                if symptom_key not in matched_symptom_keys or exact_match:
                    if exact_match:  # 정확한 매칭이면 기존 것 대체
                        matched_symptom_keys.add(symptom_key)

                    # 매칭 점수 계산 (정확도에 따라)
                    if exact_match:
                        match_score = 1.0
                    elif keyword_match:
                        match_score = 0.9
                    else:
                        match_score = 0.7

                    matched_symptoms.append(symptom)
                    for i, dept in enumerate(departments):
                        # 첫 번째 진료과목에 더 높은 점수 부여
                        base_score = 1.0 / (i + 1)
                        score = base_score * match_score
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

    def extract_specialty(self, user_input: str) -> Optional[Dict]:
        """
        사용자 입력에서 전문 분야를 추출합니다.

        Args:
            user_input: 사용자가 입력한 증상/질환 설명

        Returns:
            전문 분야 정보 딕셔너리 또는 None
        """
        normalized_input = self._normalize_text(user_input)

        # 전문 분야 키워드 매칭 - 정확한 포함 매칭만 사용
        matched_specialty = None
        match_score = 0

        for keyword, specialty_name in SYMPTOM_TO_SPECIALTY.items():
            keyword_normalized = self._normalize_text(keyword)

            # 정확한 포함 매칭만 사용 (부분 매칭 제거하여 오매칭 방지)
            # 예: "아래" → "어깨" 오매칭 방지
            if keyword_normalized in normalized_input:
                # 더 긴 키워드에 높은 우선순위 부여
                if len(keyword_normalized) > match_score:
                    match_score = len(keyword_normalized)
                    matched_specialty = specialty_name

        if matched_specialty and matched_specialty in DISEASE_TO_SPECIALTY_KEYWORDS:
            specialty_info = DISEASE_TO_SPECIALTY_KEYWORDS[matched_specialty]
            return {
                "specialty_name": matched_specialty,
                "department": specialty_info["department"],
                "specialty_keywords": specialty_info["specialty_keywords"],
                "search_terms": specialty_info["search_terms"],
                "priority_keywords": specialty_info["priority_keywords"],
            }

        return None

    def get_specialty_search_keywords(self, user_input: str, department: str) -> Dict:
        """
        병원 검색을 위한 전문 분야 키워드를 반환합니다.

        Args:
            user_input: 사용자 입력
            department: 추천된 진료과목

        Returns:
            검색 키워드 정보
        """
        # 전문 분야 추출
        specialty_info = self.extract_specialty(user_input)

        if specialty_info:
            # 전문 분야가 매칭된 경우
            return {
                "has_specialty": True,
                "specialty_name": specialty_info["specialty_name"],
                "department": specialty_info["department"],
                "primary_search_term": specialty_info["search_terms"][0] if specialty_info["search_terms"] else f"{department}",
                "specialty_keywords": specialty_info["specialty_keywords"],
                "priority_keywords": specialty_info["priority_keywords"],
                "all_search_terms": specialty_info["search_terms"],
            }
        else:
            # 전문 분야 매칭 없음 - 일반 진료과목으로 검색
            return {
                "has_specialty": False,
                "specialty_name": None,
                "department": department,
                "primary_search_term": department,
                "specialty_keywords": [],
                "priority_keywords": [],
                "all_search_terms": [department],
            }

    def rank_hospitals_by_specialty(
        self,
        hospitals: List[Dict],
        specialty_info: Dict
    ) -> List[Dict]:
        """
        전문 분야 키워드를 기반으로 병원을 우선순위로 정렬합니다.

        Args:
            hospitals: 병원 목록
            specialty_info: get_specialty_search_keywords의 반환값

        Returns:
            우선순위로 정렬된 병원 목록
        """
        if not specialty_info.get("has_specialty") or not hospitals:
            return hospitals

        priority_keywords = specialty_info.get("priority_keywords", [])
        specialty_keywords = specialty_info.get("specialty_keywords", [])

        def calculate_score(hospital: Dict) -> int:
            """병원의 전문 분야 매칭 점수 계산"""
            score = 0
            hospital_name = hospital.get("name", "").lower()
            hospital_category = hospital.get("category_name", "").lower() if hospital.get("category_name") else ""

            combined_text = f"{hospital_name} {hospital_category}"

            # priority_keywords 매칭 (높은 점수)
            for keyword in priority_keywords:
                if keyword.lower() in combined_text:
                    score += 100

            # specialty_keywords 매칭 (중간 점수)
            for keyword in specialty_keywords:
                if keyword.lower() in combined_text:
                    score += 50

            # 전문/클리닉 키워드가 있으면 추가 점수
            if "전문" in combined_text:
                score += 30
            if "클리닉" in combined_text:
                score += 20
            if "센터" in combined_text:
                score += 20

            return score

        # 점수 계산 및 정렬
        scored_hospitals = []
        for hospital in hospitals:
            score = calculate_score(hospital)
            hospital_copy = hospital.copy()
            hospital_copy["_specialty_score"] = score
            hospital_copy["_is_specialty_match"] = score > 0
            scored_hospitals.append(hospital_copy)

        # 점수 기준 내림차순 정렬
        scored_hospitals.sort(key=lambda h: h["_specialty_score"], reverse=True)

        return scored_hospitals


# 싱글톤 인스턴스
symptom_analyzer = SymptomAnalyzer()
