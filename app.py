from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

import streamlit as st


# -----------------------------
# 공통 유틸리티
# -----------------------------

def normalize(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[\s\n\t]+", " ", text)
    text = re.sub(r"[‘’“”\"'.,!?·:;()\[\]{}]", "", text)
    return text


def contains_any(text: str, terms: List[str]) -> bool:
    n = normalize(text)
    return any(normalize(t) in n for t in terms)


def contains_group(text: str, groups: List[List[str]]) -> bool:
    """각 그룹에서 하나 이상씩 포함해야 True."""
    return all(contains_any(text, group) for group in groups)


def matched_terms(text: str, terms: List[str]) -> List[str]:
    return [t for t in terms if contains_any(text, [t])]


def split_declared_method(text: str) -> Tuple[str, str]:
    """문장 끝 괄호 속 설명 방법을 추출. 예: '... (인과)'"""
    m = re.search(r"\(([^()]*)\)\s*$", text.strip())
    if not m:
        return text.strip(), ""
    method = m.group(1).strip()
    sentence = text[: m.start()].strip()
    return sentence, method


METHOD_ALIASES = {
    "정의": ["정의"],
    "예시": ["예시", "예"],
    "인과": ["인과", "원인과 결과", "원인 결과"],
    "분석": ["분석"],
    "비교와 대조": ["비교와 대조", "비교대조", "비교", "대조"],
    "분류와 구분": ["분류와 구분", "분류구분", "분류", "구분"],
}


def canonical_method(label: str) -> str:
    n = normalize(label)
    for canonical, aliases in METHOD_ALIASES.items():
        if any(normalize(a) == n for a in aliases):
            return canonical
    return ""


def detect_methods(sentence: str) -> List[str]:
    """키워드와 문장 구조를 이용한 설명 방법 탐지."""
    n = normalize(sentence)
    found: List[str] = []

    # 정의: 대상의 뜻/개념을 밝히는 구조
    if re.search(r"(이란|란 |뜻은|의미는|개념은|말한다|이다$|현상이다|작품이다)", n):
        found.append("정의")

    # 예시: 구체적 사례 표지
    if re.search(r"(예를 들어|예를 들면|예로|대표적으로|으로는|의 예)", n):
        found.append("예시")

    # 인과: 원인과 결과가 모두 드러나는 연결어
    if re.search(r"(때문에|므로|으므로|해서|하여|따라서|그래서|그 결과|결과적으로)", n):
        found.append("인과")

    # 분석: 요소·부분·구성 분해
    if re.search(r"(요소|부분|구성|이루어져|이루어진|각각|측면)", n):
        found.append("분석")

    # 비교·대조: 둘 이상의 대상과 공통점/차이/반대 관계
    comparison_marker = re.search(r"(반면|하지만|그러나|둘 다|공통점|차이점|보다|와 달리|인 데 비해|같지만)", n)
    if comparison_marker:
        found.append("비교와 대조")

    # 분류·구분: 기준에 따라 나누거나 묶음
    if re.search(r"(나눌 수|나뉜다|나누면|분류|구분|종류|묶을 수|묶인다)", n):
        found.append("분류와 구분")

    return sorted(set(found))


@dataclass
class GradeResult:
    score: float
    max_score: float
    passed: bool
    checks: List[Tuple[str, bool, str]] = field(default_factory=list)
    feedback: List[str] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((name, ok, detail))


# -----------------------------
# 세트별 지식 베이스
# -----------------------------

SETS: Dict[int, Dict] = {
    1: {
        "title": "사회적 촉진·사회적 억제",
        "q1": {
            "answers": {
                "㉠": {
                    "groups": [["쉬운", "비교적 쉬운", "익숙한", "친숙한", "큰 노력이 들지 않는", "노력을 많이 들이지 않는"], ["과제", "취미", "공부", "과목"]],
                    "forbidden": ["지나치게 어렵", "도전이 필요한"],
                    "model": "비교적 쉬운 취미 생활이나 큰 노력을 들일 필요가 없는 과제",
                },
                "㉡": {
                    "groups": [["혼자", "홀로"], ["집중", "차분", "조용"], ["연습", "익숙"]],
                    "forbidden": ["함께", "모임", "커피숍", "도서관"],
                    "model": "충분히 연습하며 익숙해질 때까지 차분하게 혼자 집중하는 시간을 가짐",
                },
                "㉢": {
                    "groups": [["사회적 억제", "억제 현상"]],
                    "forbidden": ["사회적 촉진"],
                    "model": "사회적 억제",
                },
            }
        },
        "q2": {
            "required_conclusions": [
                ["쉬운", "익숙", "친숙"],
                ["함께", "다른 사람", "모임", "도서관", "커피숍"],
                ["어려운", "도전"],
                ["혼자", "차분", "집중", "연습", "익숙해질 때까지"],
            ],
            "forbidden_pairs": [
                (["쉬운", "익숙"], ["혼자 해야", "혼자 공부해야"]),
                (["어려운", "도전"], ["함께 해야", "모임에서", "사람들과 함께"]),
            ],
            "models": {
                "예시": "예를 들어 비교적 쉬운 과제는 커피숍이나 도서관에서 다른 사람들과 함께 하는 것이 효율적이다. (예시)",
                "인과": "어려운 과제는 충분히 연습하며 익숙해질 때까지 혼자 집중해야 하므로 학습 효율을 높일 수 있다. (인과)",
                "비교와 대조": "쉬운 과제는 다른 사람들과 함께 하는 것이 좋지만, 어려운 과제는 차분하게 혼자 집중하는 것이 좋다. (비교와 대조)",
                "분류와 구분": "과제는 난이도에 따라 비교적 쉬운 과제와 지나치게 어렵거나 도전이 필요한 과제로 나눌 수 있다. (분류와 구분)",
                "분석": "효율적인 학습 전략은 과제의 난이도, 학습 공간, 다른 사람과의 공동 학습 여부로 이루어진다. (분석)",
            },
        },
        "q3": {
            "visual_groups": [["혼자", "한 명", "홀로"], ["집중", "차분", "조용", "연습"], ["방", "독서실", "빈 교실", "책상", "공간"]],
            "audio_groups": [["조용", "무음", "정적", "잔잔", "작은"], ["연필", "종이", "책장", "시계", "소리 없음", "배경음악 없음"]],
            "forbidden_visual": ["친구들과", "여럿이", "모임", "시끌벅적"],
            "forbidden_audio": ["경쾌", "신나는", "박수", "웃음", "응원", "큰 소리"],
            "evidence": ["어려운 과제", "도전", "혼자", "차분", "집중", "연습", "익숙"],
            "models": {
                "visual": "조용한 방에서 학생이 혼자 책상에 앉아 어려운 문제에 집중하는 모습을 가까운 화면으로 보여 준다.",
                "visual_effect": "혼자 차분하게 집중하는 환경을 보여 주어 어려운 과제는 충분히 연습하며 혼자 집중하는 것이 좋다는 점을 전달한다.",
                "audio": "주변 소음을 없애고 연필 쓰는 소리와 책장 넘기는 소리만 작게 들려준다.",
                "audio_effect": "방해 요소가 적은 분위기를 만들어 어려운 과제를 할 때 차분하게 혼자 집중해야 한다는 점을 청각적으로 전달한다.",
            },
        },
    },
    2: {
        "title": "정전기",
        "q1": {
            "answers": {
                "㉠": {"groups": [["고여", "머물러", "정지된", "흐르지 않는"], ["물"]], "forbidden": ["흐르는 물", "폭포", "급류"], "model": "높은 곳에 고여 있는 물"},
                "㉡": {"groups": [["전하"], ["이동하지", "움직이지", "머물러", "정지"]], "forbidden": ["전하가 이동함", "흐른다"], "model": "전하가 이동하지 않고 머물러 있음"},
                "㉢": {"groups": [["위험하지", "위험이 없", "감전 위험이 없", "안전"]], "forbidden": ["위험하다", "감전된다"], "model": "위험하지 않음"},
            }
        },
        "q2": {
            "required_conclusions": [["정전기"], ["전하"], ["이동하지", "머물러", "정지"], ["위험하지", "위험이 없", "안전"]],
            "forbidden_pairs": [
                (["정전기"], ["전하가 이동한다", "흐르는 물이다", "감전 위험이 있다"]),
                (["실생활 전기"], ["고여 있는 물", "전하가 머물러"]),
            ],
            "models": {
                "정의": "정전기란 전하가 이동하지 않고 머물러 있는 전기와 그로 인한 전기 현상을 말한다. (정의)",
                "예시": "예를 들어 정전기는 높은 곳에 고여 있는 물과 같은 상태이다. (예시)",
                "인과": "정전기는 전하가 이동하지 않고 머물러 있기 때문에 전압이 높아도 위험하지 않다. (인과)",
                "비교와 대조": "실생활 전기는 흐르는 물과 같지만 정전기는 높은 곳에 고여 있는 물과 같다. (비교와 대조)",
                "분류와 구분": "전기는 전하가 이동하는 실생활 전기와 전하가 머물러 있는 정전기로 나눌 수 있다. (분류와 구분)",
                "분석": "정전기의 특징은 높은 전압, 이동하지 않는 전하, 낮은 위험성의 세 요소로 나누어 살펴볼 수 있다. (분석)",
            },
        },
        "q3": {
            "visual_groups": [["고여", "머물러", "정지", "흐르지"], ["물", "호수", "저수지", "댐", "물웅덩이"]],
            "audio_groups": [["조용", "무음", "정적", "잔잔", "거의 들리지"], ["물", "소리", "침묵"]],
            "forbidden_visual": ["폭포", "급류", "흐르는 강", "쏟아져"],
            "forbidden_audio": ["거센 물소리", "큰 물소리", "웅장", "콸콸", "폭포 소리"],
            "evidence": ["정전기", "전하", "이동하지", "머물러", "고여", "위험하지", "전압"],
            "models": {
                "visual": "높은 곳의 저수지에 물이 가득 고여 있지만 아래로 흐르지 않는 모습을 보여 준다.",
                "visual_effect": "고여 있는 물을 통해 정전기의 전하가 이동하지 않고 머물러 있는 상태를 시각적으로 전달한다.",
                "audio": "물이 거의 흐르지 않는 고요한 분위기와 아주 잔잔한 물결 소리만 들려준다.",
                "audio_effect": "거센 흐름이 없는 소리를 사용해 전하가 이동하지 않으므로 정전기가 위험하지 않다는 점을 전달한다.",
            },
        },
    },
    3: {
        "title": "인공 지능 그림과 예술",
        "q1": {
            "answers": {
                "㉠": {"groups": [["로봇"], ["피겨", "스케이팅"], ["완벽", "실수 없이"]], "forbidden": ["인간 선수"], "model": "로봇이 한 번의 실수 없이 완벽하게 피겨 스케이팅을 하는 경기"},
                "㉡": {"groups": [["감정", "철학", "이야기", "경험", "관점", "환경"], ["없", "느끼지 못"], ["예술로 보기 어렵", "예술이 아니"]], "forbidden": ["예술이다", "감정이 있다"], "model": "감정이나 독자적인 철학·이야기가 없으므로 예술로 보기 어렵다"},
                "㉢": {"groups": [["미술계 변화", "변화를 가져", "예술의 범주", "범주를 확장", "상징적 가치", "의미"]], "forbidden": ["가치가 없다", "아무 의미 없다"], "model": "미술계에 변화를 가져오고 예술의 범주를 확장할 수 있다는 상징적 가치"},
            }
        },
        "q2": {
            "required_conclusions": [["인공 지능", "ai"], ["예술로 보기 어렵", "예술이 아니"], ["가치", "의미", "변화", "범주를 확장"]],
            "forbidden_pairs": [
                (["인공 지능", "ai"], ["감정이 있다", "독자적인 철학이 있다", "삶의 경험이 담겼다"]),
                (["예술로 보기 어렵", "예술이 아니"], ["가치가 없다", "의미가 없다"]),
                (["인간의 예술", "인간 작품"], ["감정이 없다", "철학이 없다", "경험이 없다"]),
            ],
            "models": {
                "정의": "인간의 예술은 작가의 감정과 철학, 삶의 경험과 관점이 담긴 작품이다. (정의)",
                "예시": "예를 들어 「에드몽 드 벨라미」는 알고리즘과 데이터를 사용해 제작된 인공 지능 그림이다. (예시)",
                "인과": "인공 지능은 감정과 독자적인 철학이나 이야기가 없기 때문에 그 그림을 예술로 보기는 어렵다. (인과)",
                "비교와 대조": "인간의 작품에는 감정과 삶의 경험이 담기지만 인공 지능 그림에는 그것이 없어 예술로 보기 어렵다. (비교와 대조)",
                "분류와 구분": "그림은 제작 주체에 따라 인간이 만든 작품과 인공 지능이 만든 그림으로 나눌 수 있다. (분류와 구분)",
                "분석": "인간 예술에는 작가의 감정, 철학, 삶의 경험, 관점, 환경 등의 요소가 담겨 있다. (분석)",
            },
        },
        "q3": {
            "visual_groups": [["작가", "화가", "인간"], ["감정", "철학", "경험", "관점", "삶"], ["그림", "작품", "그리"]],
            "audio_groups": [["따뜻", "잔잔", "감성", "부드럽", "서정"], ["음악", "피아노", "현악", "목소리"]],
            "forbidden_visual": ["로봇만", "기계만", "감정 없는", "완벽한 로봇"],
            "forbidden_audio": ["기계음", "메트로놈", "차갑", "일정한 박자"],
            "evidence": ["감정", "철학", "삶의 경험", "관점", "환경", "감동", "마음을 울리", "인간 예술"],
            "models": {
                "visual": "한 작가가 자신의 삶의 경험과 감정을 떠올리며 그림을 그리고, 관람객이 완성된 작품에 감동하는 모습을 보여 준다.",
                "visual_effect": "작가의 감정과 철학, 삶의 경험이 작품에 담겨 인간의 예술이 감상자의 마음을 울린다는 점을 전달한다.",
                "audio": "잔잔하고 따뜻한 피아노와 현악기 음악을 배경으로 사용한다.",
                "audio_effect": "따뜻한 음악이 인간의 감정이 담긴 분위기를 강화하여 작품이 감상자에게 감동을 준다는 점을 느끼게 한다.",
            },
        },
    },
}


# -----------------------------
# 채점 함수
# -----------------------------

def grade_q1(set_no: int, answers: Dict[str, str]) -> GradeResult:
    specs = SETS[set_no]["q1"]["answers"]
    result = GradeResult(score=0, max_score=3, passed=False)

    for label, spec in specs.items():
        text = answers.get(label, "")
        has_meaning = contains_group(text, spec["groups"])
        has_misconception = contains_any(text, spec.get("forbidden", []))
        ok = bool(text.strip()) and has_meaning and not has_misconception
        result.score += 1 if ok else 0
        result.add(label, ok, f"모범 답안: {spec['model']}")
        if not text.strip():
            result.feedback.append(f"{label}: 답안이 비어 있습니다.")
        elif has_misconception:
            result.feedback.append(f"{label}: 다른 개념의 특성 또는 반대 방향의 설명이 포함되어 있습니다.")
        elif not has_meaning:
            result.feedback.append(f"{label}: 필수 의미 요소가 모두 드러나지 않습니다.")

    result.passed = result.score == result.max_score
    return result


def check_forbidden_pairs(text: str, pairs: List[Tuple[List[str], List[str]]]) -> List[str]:
    problems = []
    for concept_terms, wrong_terms in pairs:
        if contains_any(text, concept_terms) and contains_any(text, wrong_terms):
            problems.append(f"{concept_terms[0]}의 특성에 {wrong_terms[0]} 방향을 연결함")
    return problems


def grade_q2(set_no: int, ans1: str, ans2: str) -> GradeResult:
    spec = SETS[set_no]["q2"]
    result = GradeResult(score=0, max_score=6, passed=False)

    sentences = [ans1, ans2]
    declared_methods: List[str] = []

    for idx, raw in enumerate(sentences, start=1):
        sentence, declared = split_declared_method(raw)
        declared_canonical = canonical_method(declared)
        detected = detect_methods(sentence)
        declared_methods.append(declared_canonical)

        # 1점: 문장 작성
        written = bool(sentence.strip())
        result.score += 1 if written else 0
        result.add(f"({idx}) 문장 작성", written, sentence)

        # 1점: 선택한 방법과 실제 특성 일치
        method_ok = bool(declared_canonical) and declared_canonical in detected
        result.score += 1 if method_ok else 0
        detail = f"표기: {declared or '없음'} / 감지: {', '.join(detected) if detected else '없음'}"
        result.add(f"({idx}) 설명 방법 일치", method_ok, detail)
        if not declared_canonical:
            result.feedback.append(f"({idx}): 문장 끝에 허용된 설명 방법 명칭을 표기해야 합니다.")
        elif not method_ok:
            result.feedback.append(f"({idx}): 선택한 '{declared_canonical}'의 특성이 실제 문장에 드러나지 않습니다.")

        # 오개념 검사: 한 개념의 특성을 다른 개념에 연결하면 해당 문장 내용점수 불인정
        misconceptions = check_forbidden_pairs(sentence, spec["forbidden_pairs"])
        if misconceptions:
            result.feedback.append(f"({idx}): 오개념 — " + "; ".join(misconceptions))

    # 1점: 서로 다른 방법
    methods_distinct = bool(declared_methods[0] and declared_methods[1]) and declared_methods[0] != declared_methods[1]
    result.score += 1 if methods_distinct else 0
    result.add("서로 다른 설명 방법", methods_distinct, f"{declared_methods[0] or '미표기'} / {declared_methods[1] or '미표기'}")
    if not methods_distinct:
        result.feedback.append("(1)과 (2)에 서로 다른 설명 방법을 사용해야 합니다.")

    # 1점: 두 문장을 합쳐 결론 방향과 본문 핵심 의미 충족
    combined = " ".join(split_declared_method(x)[0] for x in sentences)
    conclusion_ok = contains_group(combined, spec["required_conclusions"])
    misconception_all = bool(check_forbidden_pairs(combined, spec["forbidden_pairs"]))
    content_ok = conclusion_ok and not misconception_all
    result.score += 1 if content_ok else 0
    result.add("본문 근거·결론 방향", content_ok, "필수 의미군 모두 충족 + 오개념 없음")
    if not conclusion_ok:
        result.feedback.append("두 문장을 합쳤을 때 문항이 요구한 핵심 결론이 모두 드러나지 않습니다.")
    if misconception_all:
        result.feedback.append("핵심 개념의 특성을 다른 개념에 잘못 연결했습니다.")

    result.passed = result.score == result.max_score
    return result


def grade_q3(set_no: int, visual: str, visual_effect: str, audio: str, audio_effect: str) -> GradeResult:
    spec = SETS[set_no]["q3"]
    result = GradeResult(score=0, max_score=6, passed=False)

    # 시각 요소 2점
    visual_meaning = contains_group(visual, spec["visual_groups"])
    visual_wrong = contains_any(visual, spec["forbidden_visual"])
    if visual_meaning and not visual_wrong:
        v_score = 2
    elif visual.strip() and not visual_wrong and any(contains_any(visual, g) for g in spec["visual_groups"]):
        v_score = 1
    else:
        v_score = 0
    result.score += v_score
    result.add("시각 요소", v_score == 2, f"{v_score}/2점")

    # 시각 효과 1점: 앞 요소 연결 + 본문 근거
    visual_link = any(term in normalize(visual_effect) for term in [normalize(t) for t in matched_terms(visual, sum(spec["visual_groups"], []))])
    visual_evidence = contains_any(visual_effect, spec["evidence"])
    visual_effect_ok = bool(visual_effect.strip()) and visual_evidence and (visual_link or contains_any(visual_effect, sum(spec["visual_groups"], [])))
    result.score += 1 if visual_effect_ok else 0
    result.add("시각 요소의 효과", visual_effect_ok, "시각 요소와 연결 + 본문 근거")

    # 청각 요소 2점
    audio_meaning = contains_group(audio, spec["audio_groups"])
    audio_wrong = contains_any(audio, spec["forbidden_audio"])
    if audio_meaning and not audio_wrong:
        a_score = 2
    elif audio.strip() and not audio_wrong and any(contains_any(audio, g) for g in spec["audio_groups"]):
        a_score = 1
    else:
        a_score = 0
    result.score += a_score
    result.add("청각 요소", a_score == 2, f"{a_score}/2점")

    # 청각 효과 1점
    audio_link = any(term in normalize(audio_effect) for term in [normalize(t) for t in matched_terms(audio, sum(spec["audio_groups"], []))])
    audio_evidence = contains_any(audio_effect, spec["evidence"])
    audio_effect_ok = bool(audio_effect.strip()) and audio_evidence and (audio_link or contains_any(audio_effect, sum(spec["audio_groups"], [])))
    result.score += 1 if audio_effect_ok else 0
    result.add("청각 요소의 효과", audio_effect_ok, "청각 요소와 연결 + 본문 근거")

    if visual_wrong:
        result.feedback.append("시각 요소에 본문과 반대되는 장면이 포함되어 있습니다.")
    elif v_score < 2:
        result.feedback.append("시각 요소에 본문 핵심 특성이 모두 드러나지 않습니다.")
    if not visual_effect_ok:
        result.feedback.append("시각 효과가 앞서 쓴 시각 요소와 연결되며 본문 근거를 포함해야 합니다.")
    if audio_wrong:
        result.feedback.append("청각 요소에 본문과 반대되는 소리가 포함되어 있습니다.")
    elif a_score < 2:
        result.feedback.append("청각 요소에 본문 핵심 특성이 모두 드러나지 않습니다.")
    if not audio_effect_ok:
        result.feedback.append("청각 효과가 앞서 쓴 청각 요소와 연결되며 본문 근거를 포함해야 합니다.")

    result.passed = result.score == result.max_score
    return result


# -----------------------------
# Streamlit UI
# -----------------------------

# -----------------------------
# Streamlit UI
# -----------------------------

PASSAGES = {
    1: {
        "heading": "💡 [실전 적용 1] 과제 난이도와 사회적 촉진/억제",
        "question": "[기자] 사회적 촉진과 억제를 일상생활에 어떻게 적용할 수 있을까요?",
        "answer": "[전문가] 비교적 쉬운 취미 생활이나 큰 노력을 들일 필요가 없는 과제를 할 때는 커피숍이나 도서관에서 하거나 공부 모임을 만드는 것이 효율적일 수 있습니다. 반대로 지나치게 어렵거나 도전이 필요한 과제는 차분하게 혼자 집중하는 시간을 가지는 것이 좋습니다.",
        "q1_intro": "윗글을 요약하여 표로 정리하였다. 빈칸 ㉠~㉢에 들어갈 내용을 찾아 쓰시오.",
    },
    2: {
        "heading": "⚡ [실전 적용 2] 정전기의 원리",
        "question": "[기자] 정전기는 왜 전압이 높아도 위험하지 않은가요?",
        "answer": "[전문가] 정전기는 높은 곳에 고여 있는 물과 비슷합니다. 물이 높은 곳에 있어도 흐르지 않으면 큰 힘을 전달하지 못하듯, 정전기도 전하가 이동하지 않고 머물러 있기 때문에 전압이 높아도 위험하지 않습니다.",
        "q1_intro": "윗글을 요약하여 표로 정리하였다. 빈칸 ㉠~㉢에 들어갈 내용을 찾아 쓰시오.",
    },
    3: {
        "heading": "🎨 [실전 적용 3] 인공 지능 그림과 예술",
        "question": "[기자] 인공 지능이 만든 그림도 예술이라고 할 수 있을까요?",
        "answer": "[전문가] 인간의 예술에는 작가의 감정과 철학, 삶의 경험과 관점이 담깁니다. 인공 지능 그림에는 이러한 요소가 없어 예술로 보기 어렵지만, 기존 미술계에 변화를 가져오고 예술의 범주를 확장할 수 있다는 상징적 가치는 있습니다.",
        "q1_intro": "윗글을 요약하여 표로 정리하였다. 빈칸 ㉠~㉢에 들어갈 내용을 찾아 쓰시오.",
    },
}

st.set_page_config(page_title="서·논술형 자동 채점기", page_icon="💡", layout="wide")

st.markdown(
    """
    <style>
    .block-container {max-width: 1080px; padding-top: 2.2rem; padding-bottom: 3rem;}
    h1, h2, h3 {color:#1f2f46;}
    .hero-title {font-size:2.05rem; font-weight:800; color:#1f2f46; margin:0 0 1.2rem 0;}
    .passage-card {background:#eaf2ff; border-radius:14px; padding:24px 28px; line-height:1.95; font-size:1.12rem; color:#17243a; margin-bottom:1.35rem;}
    .section-line {border-top:1px solid #d7dee8; margin:2.1rem 0 1.6rem 0;}
    .question-title {font-size:1.18rem; line-height:1.7; margin-bottom:1rem;}
    .score-card {background:#f5f8fc; border:1px solid #d8e0ec; border-radius:12px; padding:18px 20px; margin-top:1rem;}
    .stTabs [data-baseweb="tab-list"] {gap:18px;}
    .stTabs [data-baseweb="tab"] {height:54px; border:1px solid #d5dbe5; border-radius:10px 10px 0 0; padding:0 28px; background:white;}
    .stTabs [aria-selected="true"] {background:#2878c8 !important; color:white !important; font-weight:700;}
    div[data-testid="stTextArea"] textarea {font-size:1rem;}
    div[data-testid="stTextInput"] input {font-size:1rem; text-align:center;}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    set_no = st.selectbox("세트 선택", [1, 2, 3], format_func=lambda x: f"{x}세트 — {SETS[x]['title']}")
    show_models = st.toggle("채점 후 모범 답안 표시", value=True)
    st.caption("답안을 입력한 뒤 각 문항의 채점 버튼을 누르세요.")

p = PASSAGES[set_no]
st.markdown(f'<div class="hero-title">{p["heading"]}</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="passage-card"><div>{p["question"]}</div><br><div>{p["answer"]}</div></div>',
    unsafe_allow_html=True,
)

tab1, tab2, tab3 = st.tabs(["🖍️ 1번 빈칸 채우기", "🟪 2번 설명문 쓰기", "🟪 3번 영상 기획"])

with tab1:
    st.markdown('<div class="section-line"></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="question-title"><b>[서·논술형 1]</b> {p["q1_intro"]}</div>', unsafe_allow_html=True)

    if set_no == 1:
        h = st.columns([1.1, 2.1, 1.1])
        for col, txt in zip(h, ["과제의 특성", "환경", "현상"]):
            col.markdown(f"<div style='background:#dfe8f4;border:1px solid #cbd5e1;padding:18px;text-align:center;font-weight:700'>{txt}</div>", unsafe_allow_html=True)
        r1 = st.columns([1.1, 2.1, 1.1])
        a1 = r1[0].text_input("㉠", key="q1_1_a", label_visibility="collapsed", placeholder="㉠ 입력")
        r1[1].markdown("<div style='border:1px solid #cbd5e1;padding:20px;text-align:center'>공부 모임 등 여러 명이 함께함</div>", unsafe_allow_html=True)
        r1[2].markdown("<div style='border:1px solid #cbd5e1;padding:20px;text-align:center'>사회적 촉진</div>", unsafe_allow_html=True)
        r2 = st.columns([1.1, 2.1, 1.1])
        r2[0].markdown("<div style='border:1px solid #cbd5e1;padding:20px;text-align:center'>어려운 과제</div>", unsafe_allow_html=True)
        a2 = r2[1].text_input("㉡", key="q1_1_b", label_visibility="collapsed", placeholder="㉡ 입력")
        a3 = r2[2].text_input("㉢", key="q1_1_c", label_visibility="collapsed", placeholder="㉢ 입력")
    else:
        specs = SETS[set_no]["q1"]["answers"]
        cols = st.columns(3)
        vals = []
        for col, label in zip(cols, ["㉠", "㉡", "㉢"]):
            vals.append(col.text_area(label, key=f"q1_{set_no}_{label}", height=110, placeholder=f"{label}에 들어갈 내용을 쓰세요."))
        a1, a2, a3 = vals

    if st.button("1번 채점하기", type="primary", use_container_width=True, key=f"grade_q1_{set_no}"):
        result = grade_q1(set_no, {"㉠": a1, "㉡": a2, "㉢": a3})
        st.markdown(f"<div class='score-card'><b>점수: {result.score:.0f} / {result.max_score:.0f}</b></div>", unsafe_allow_html=True)
        for name, ok, detail in result.checks:
            (st.success if ok else st.error)(f"{name}: {'통과' if ok else '미통과'} — {detail}")
        if result.feedback:
            st.warning("\n".join(f"- {x}" for x in result.feedback))
        if show_models:
            with st.expander("모범 답안 보기"):
                for label, spec in SETS[set_no]["q1"]["answers"].items():
                    st.write(f"**{label}** {spec['model']}")

with tab2:
    st.markdown('<div class="section-line"></div>', unsafe_allow_html=True)
    st.markdown('<div class="question-title"><b>[서·논술형 2]</b> 윗글의 내용을 서로 다른 두 가지 설명 방법으로 설명하시오. 각 문장 끝에 사용한 설명 방법을 괄호 안에 쓰시오.</div>', unsafe_allow_html=True)
    allowed = list(SETS[set_no]["q2"]["models"].keys())
    c1, c2 = st.columns(2)
    with c1:
        m1 = st.selectbox("(1) 설명 방법", allowed, key=f"m1_{set_no}")
        s1 = st.text_area("(1) 설명문", key=f"s1_{set_no}", height=150)
    with c2:
        m2 = st.selectbox("(2) 설명 방법", allowed, index=1 if len(allowed) > 1 else 0, key=f"m2_{set_no}")
        s2 = st.text_area("(2) 설명문", key=f"s2_{set_no}", height=150)
    ans1 = f"{s1} ({m1})" if s1.strip() else ""
    ans2 = f"{s2} ({m2})" if s2.strip() else ""

    if st.button("2번 채점하기", type="primary", use_container_width=True, key=f"grade_q2_{set_no}"):
        result = grade_q2(set_no, ans1, ans2)
        st.markdown(f"<div class='score-card'><b>점수: {result.score:.0f} / {result.max_score:.0f}</b></div>", unsafe_allow_html=True)
        for name, ok, detail in result.checks:
            (st.success if ok else st.error)(f"{name}: {'통과' if ok else '미통과'} — {detail}")
        if result.feedback:
            st.warning("\n".join(f"- {x}" for x in result.feedback))
        if show_models:
            with st.expander("선택지별 모범 답안 보기"):
                for method, model in SETS[set_no]["q2"]["models"].items():
                    st.write(f"**{method}**: {model}")

with tab3:
    st.markdown('<div class="section-line"></div>', unsafe_allow_html=True)
    st.markdown('<div class="question-title"><b>[서·논술형 3, 총 6점]</b> 윗글의 핵심 내용을 영상으로 표현하려고 한다. 시각 요소와 청각 요소, 그리고 각각의 효과를 구체적으로 쓰시오.</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        visual = st.text_area("시각 요소 Ⓐ (2점)", key=f"v_{set_no}", height=130)
        visual_effect = st.text_area("시각 요소의 효과 (1점)", key=f"ve_{set_no}", height=130)
    with c2:
        audio = st.text_area("청각 요소 Ⓑ (2점)", key=f"a_{set_no}", height=130)
        audio_effect = st.text_area("청각 요소의 효과 (1점)", key=f"ae_{set_no}", height=130)

    if st.button("3번 채점하기", type="primary", use_container_width=True, key=f"grade_q3_{set_no}"):
        result = grade_q3(set_no, visual, visual_effect, audio, audio_effect)
        st.markdown(f"<div class='score-card'><b>점수: {result.score:.0f} / {result.max_score:.0f}</b></div>", unsafe_allow_html=True)
        for name, ok, detail in result.checks:
            (st.success if ok else st.error)(f"{name}: {'통과' if ok else '미통과'} — {detail}")
        if result.feedback:
            st.warning("\n".join(f"- {x}" for x in result.feedback))
        if show_models:
            models = SETS[set_no]["q3"]["models"]
            with st.expander("모범 답안 보기"):
                st.write(f"**시각 요소:** {models['visual']}")
                st.write(f"**시각 요소의 효과:** {models['visual_effect']}")
                st.write(f"**청각 요소:** {models['audio']}")
                st.write(f"**청각 요소의 효과:** {models['audio_effect']}")

st.divider()
st.caption("규칙 기반 자동 채점 초안입니다. 실제 평가 전에 학생 답안 표본을 활용해 동의어·오개념 규칙을 보정하세요.")
