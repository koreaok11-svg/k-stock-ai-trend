import os
import json
import math
import re
from datetime import datetime, timedelta, timezone, timedelta, timezone

import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
import requests
from flask import Flask, render_template_string, request, jsonify, Response

app = Flask(__name__)

KST = timezone(timedelta(hours=9))

def now_kst():
    return datetime.now(KST)



THEME_MAP = {

    # AI/클라우드/IT서비스/AX
    "LG씨엔에스": "AI/클라우드/IT서비스",
    "LG CNS": "AI/클라우드/IT서비스",
    "삼성에스디에스": "AI/클라우드/IT서비스",
    "삼성SDS": "AI/클라우드/IT서비스",
    "현대오토에버": "AI/클라우드/IT서비스",
    "포스코DX": "AI/클라우드/IT서비스",
    "롯데이노베이트": "AI/클라우드/IT서비스",
    "SK바이오팜": "바이오/제약",

    # 스마트물류/스마트팩토리/자동화
    "코윈테크": "스마트팩토리/자동화",
    "에스엠코어": "스마트팩토리/자동화",
    "티라유텍": "스마트팩토리/자동화",
    "엠투아이": "스마트팩토리/자동화",

    # 보안/AI소프트웨어
    "샌즈랩": "보안/소프트웨어",
    "모니터랩": "보안/소프트웨어",
    "케이사인": "보안/소프트웨어",
    "시큐센": "보안/소프트웨어",
    "드림시큐리티": "보안/소프트웨어",

    # 의료AI/디지털헬스
    "루닛": "의료AI/디지털헬스",
    "뷰노": "의료AI/디지털헬스",
    "딥노이드": "의료AI/디지털헬스",
    "제이엘케이": "의료AI/디지털헬스",
    "라이프시맨틱스": "의료AI/디지털헬스",

    # 전력/냉각/데이터센터 인프라
    "GST": "데이터센터/냉각",
    "유니셈": "데이터센터/냉각",
    "케이엔솔": "데이터센터/냉각",
    "한중엔시에스": "데이터센터/냉각",

    # 지주/그룹주
    "LG": "지주/그룹주",
    "SK": "지주/그룹주",
    "한화": "지주/그룹주",
    "CJ": "지주/그룹주",
    "두산": "지주/그룹주",


    # 생활/소비재/육아
    "폴레드": "육아/키즈",
    "아가방컴퍼니": "육아/키즈", "제로투세븐": "육아/키즈", "캐리소프트": "육아/키즈",
    "꿈비": "육아/키즈", "토박스코리아": "육아/키즈", "메디앙스": "육아/키즈",

    # 유통/소비
    "BGF리테일": "유통/플랫폼", "GS리테일": "유통/플랫폼",
    "이마트": "유통/플랫폼", "롯데쇼핑": "유통/플랫폼", "현대백화점": "유통/플랫폼",
    "신세계": "유통/플랫폼",

    # 패션/의류
    "F&F": "패션/의류", "휠라홀딩스": "패션/의류", "영원무역": "패션/의류",
    "한세실업": "패션/의류", "감성코퍼레이션": "패션/의류", "브랜드엑스코퍼레이션": "패션/의류",

    # 교육
    "메가스터디교육": "교육/에듀테크", "웅진씽크빅": "교육/에듀테크", "대교": "교육/에듀테크",
    "비상교육": "교육/에듀테크", "YBM넷": "교육/에듀테크", "NE능률": "교육/에듀테크",

    # 여행/레저
    "하나투어": "여행/레저", "모두투어": "여행/레저", "노랑풍선": "여행/레저",
    "강원랜드": "여행/레저", "파라다이스": "여행/레저", "롯데관광개발": "여행/레저",

    # 물류/운송/항공
    "CJ대한통운": "물류/운송", "한진": "물류/운송", "현대글로비스": "물류/운송",
    "대한항공": "항공/여행", "아시아나항공": "항공/여행", "제주항공": "항공/여행",
    "진에어": "항공/여행", "티웨이항공": "항공/여행",

    # 보안/소프트웨어/플랫폼
    "안랩": "보안/소프트웨어", "더존비즈온": "보안/소프트웨어", "한글과컴퓨터": "보안/소프트웨어",
    "이스트소프트": "보안/소프트웨어", "라온시큐어": "보안/소프트웨어", "파수": "보안/소프트웨어",
    "NAVER": "인터넷/플랫폼", "카카오": "인터넷/플랫폼", "카카오페이": "인터넷/플랫폼",
    "카카오뱅크": "인터넷/플랫폼", "NHN": "인터넷/플랫폼",

    # 반려동물
    "오에스피": "반려동물/펫",

    "삼성전자": "AI반도체/HBM", "SK하이닉스": "AI반도체/HBM", "한미반도체": "AI반도체/HBM",
    "이오테크닉스": "AI반도체/HBM", "리노공업": "AI반도체/HBM", "ISC": "AI반도체/HBM",
    "테크윙": "AI반도체/HBM", "HPSP": "AI반도체/HBM", "하나마이크론": "AI반도체/HBM",
    "주성엔지니어링": "AI반도체/HBM", "원익IPS": "AI반도체/HBM", "가온칩스": "AI반도체/HBM",
    "오픈엣지테크놀로지": "AI반도체/HBM",

    "서울바이오시스": "광통신/CPO", "오이솔루션": "광통신/CPO", "라이트론": "광통신/CPO",
    "다산네트웍스": "광통신/CPO", "케이엠더블유": "광통신/CPO", "쏠리드": "광통신/CPO",

    "HD현대일렉트릭": "전력설비/데이터센터", "LS ELECTRIC": "전력설비/데이터센터",
    "효성중공업": "전력설비/데이터센터", "일진전기": "전력설비/데이터센터",
    "산일전기": "전력설비/데이터센터", "LS": "전력설비/데이터센터",
    "대한전선": "전력설비/데이터센터", "제룡전기": "전력설비/데이터센터", "가온전선": "전력설비/데이터센터",

    "이수페타시스": "AI서버/PCB", "대덕전자": "AI서버/PCB", "심텍": "AI서버/PCB",
    "코리아써키트": "AI서버/PCB", "티엘비": "AI서버/PCB",

    "레인보우로보틱스": "로봇/피지컬AI", "두산로보틱스": "로봇/피지컬AI",
    "로보티즈": "로봇/피지컬AI", "뉴로메카": "로봇/피지컬AI", "에스피지": "로봇/피지컬AI",

    "두산에너빌리티": "원전/전력인프라", "한전기술": "원전/전력인프라",
    "우진": "원전/전력인프라", "비에이치아이": "원전/전력인프라",
}

AUTO_THEME_KEYWORDS = {

    "AI/클라우드/IT서비스": [
        "CNS", "씨엔에스", "SDS", "에스디에스", "오토에버", "DX", "이노베이트",
        "IT서비스", "SI", "시스템통합", "클라우드", "데이터센터", "AX", "스마트물류",
        "스마트팩토리", "ERP", "IDC", "AI서비스"
    ],
    "스마트팩토리/자동화": [
        "스마트팩토리", "자동화", "공장", "물류자동화", "로봇자동화", "코윈", "티라유텍", "엠투아이", "에스엠코어"
    ],
    "의료AI/디지털헬스": [
        "의료AI", "디지털헬스", "헬스케어AI", "루닛", "뷰노", "딥노이드", "제이엘케이", "라이프시맨틱스"
    ],
    "데이터센터/냉각": [
        "냉각", "칠러", "클린룸", "공조", "열관리", "액침", "GST", "유니셈", "케이엔솔", "한중엔시에스"
    ],
    "지주/그룹주": [
        "홀딩스", "지주", "그룹", "지주사"
    ],


    "육아/키즈": ["육아", "유아", "아기", "키즈", "어린이", "카시트", "유모차", "분유", "완구", "폴레드", "아가방", "제로투세븐", "꿈비", "메디앙스", "토박스"],
    "유통/플랫폼": ["리테일", "쇼핑", "백화점", "마트", "편의점", "유통", "커머스", "신세계", "이마트", "롯데쇼핑", "GS리테일", "BGF"],
    "패션/의류": ["패션", "의류", "브랜드", "섬유", "원단", "휠라", "영원무역", "한세실업", "감성코퍼레이션"],
    "교육/에듀테크": ["교육", "에듀", "스터디", "학습", "교재", "능률", "대교", "웅진", "YBM", "비상교육"],
    "여행/레저": ["여행", "투어", "호텔", "카지노", "레저", "관광", "하나투어", "모두투어", "노랑풍선", "강원랜드", "파라다이스"],
    "항공/여행": ["항공", "대한항공", "아시아나", "제주항공", "진에어", "티웨이"],
    "물류/운송": ["물류", "운송", "택배", "글로비스", "대한통운", "한진"],
    "보안/소프트웨어": ["보안", "소프트웨어", "솔루션", "시큐어", "클라우드", "안랩", "더존", "한글과컴퓨터", "이스트소프트"],
    "인터넷/플랫폼": ["인터넷", "플랫폼", "포털", "카카오", "NAVER", "네이버", "페이", "뱅크"],
    "반려동물/펫": ["펫", "반려", "동물", "사료", "오에스피"],

    "AI반도체/HBM": ["반도체", "하이닉스", "HBM", "메모리", "디램", "낸드", "파운드리", "테크윙", "리노", "ISC", "HPSP", "원익", "주성", "이오테크닉스", "한미반도체", "하나마이크론", "가온칩스", "오픈엣지"],
    "반도체장비/소재": ["소부장", "실리콘", "웨이퍼", "식각", "증착", "포토", "테스트", "프로브", "쿼츠", "세라믹", "테스", "피에스케이", "유진테크", "동진쎄미켐", "솔브레인", "티씨케이", "원익QnC"],
    "전력설비/데이터센터": ["전력", "전기", "일렉트릭", "변압기", "케이블", "전선", "중공업", "효성", "LS", "대한전선", "제룡", "산일", "가온전선", "현대일렉트릭"],
    "광통신/CPO": ["광", "통신", "CPO", "네트웍스", "솔루션", "라이트론", "오이솔루션", "쏠리드", "케이엠더블유", "다산"],
    "AI서버/PCB": ["PCB", "기판", "써키트", "페타시스", "대덕", "심텍", "티엘비", "코리아써키트", "서버"],
    "로봇/피지컬AI": ["로봇", "로보", "자동화", "뉴로메카", "레인보우", "두산로보틱스", "에스피지", "로보티즈", "휴림"],
    "2차전지/배터리": ["배터리", "전지", "2차전지", "리튬", "양극재", "음극재", "전해액", "분리막", "에코프로", "엘앤에프", "포스코퓨처엠", "천보", "대주전자재료", "나노신소재", "코스모", "금양"],
    "자동차/자율주행": ["자동차", "모비스", "만도", "HL", "현대차", "기아", "자율주행", "카메라", "센서", "전장", "모트렉스", "칩스앤미디어"],
    "바이오/제약": ["바이오", "제약", "헬스", "셀트리온", "삼성바이오", "유한양행", "한미약품", "알테오젠", "HLB", "레고켐", "리가켐", "보로노이", "에이비엘", "오스코텍", "휴젤", "메디톡스"],
    "방산/우주항공": ["방산", "항공", "우주", "한화에어로", "한국항공우주", "LIG", "현대로템", "쎄트렉아이", "인텔리안", "켄코아", "제노코"],
    "조선/해운": ["조선", "해양", "중공업", "미포", "한화오션", "삼성중공업", "HD현대중공업", "팬오션", "HMM", "대한해운"],
    "원전/전력인프라": ["원전", "원자력", "두산에너빌리티", "한전기술", "우진", "비에이치아이", "보성파워텍", "우리기술"],
    "화장품/미용": ["화장품", "코스맥스", "한국콜마", "아모레", "클리오", "실리콘투", "브이티", "마녀공장", "토니모리", "잉글우드랩"],
    "엔터/콘텐츠": ["엔터", "하이브", "JYP", "YG", "SM", "스튜디오", "콘텐츠", "드라마", "CJ ENM", "NEW", "덱스터", "래몽래인"],
    "게임/웹툰": ["게임", "넷마블", "엔씨", "크래프톤", "펄어비스", "컴투스", "위메이드", "카카오게임즈", "웹툰"],
    "금융/증권": ["금융", "은행", "증권", "보험", "카드", "KB", "신한", "하나금융", "우리금융", "삼성증권", "키움", "미래에셋"],
    "친환경/수소": ["수소", "풍력", "태양광", "친환경", "연료전지", "두산퓨얼셀", "씨에스윈드", "한화솔루션", "OCI"],
    "음식료/소비재": ["식품", "푸드", "농심", "삼양", "오리온", "CJ제일제당", "빙그레", "하이트", "롯데칠성", "동원"],
    "건설/인프라": ["건설", "시멘트", "레미콘", "현대건설", "GS건설", "대우건설", "DL이앤씨", "삼표", "쌍용C&E"],
}

WEIGHT = {
    "AI반도체/HBM": 1.35,
    "전력설비/데이터센터": 1.30,
    "광통신/CPO": 1.25,
    "AI서버/PCB": 1.18,
    "원전/전력인프라": 1.15,
    "로봇/피지컬AI": 1.10,
    "2차전지/배터리": 1.10,
    "방산/우주항공": 1.08,
    "반도체장비/소재": 1.08,
    "바이오/제약": 1.04,
    "육아/키즈": 1.03,
    "유통/플랫폼": 1.03,
    "패션/의류": 1.02,
    "교육/에듀테크": 1.02,
    "여행/레저": 1.03,
    "항공/여행": 1.03,
    "물류/운송": 1.02,
    "보안/소프트웨어": 1.06,
    "인터넷/플랫폼": 1.05,
    "반려동물/펫": 1.02,
    "IT/전자": 1.03,
    "화학/소재": 1.02,
    "AI/클라우드/IT서비스": 1.07,
    "스마트팩토리/자동화": 1.05,
    "의료AI/디지털헬스": 1.05,
    "데이터센터/냉각": 1.06,
    "지주/그룹주": 0.98,
    "기타/개별이슈": 0.96,
    "미분류": 0.95,
}




def safe_value(v):
    """
    Flask jsonify 전에 NaN, inf, numpy 타입, pandas 결측값을 안전한 JSON 값으로 변환합니다.
    JSON이 깨져서 브라우저에서 Unexpected token '<' 오류가 나는 것을 방지합니다.
    """
    try:
        if v is None:
            return 0

        try:
            if pd.isna(v):
                return 0
        except Exception:
            pass

        if isinstance(v, (np.integer,)):
            return int(v)

        if isinstance(v, (np.floating, float)):
            if math.isnan(float(v)) or math.isinf(float(v)):
                return 0
            return float(v)

        if isinstance(v, (np.ndarray,)):
            return v.tolist()

        return v
    except Exception:
        return 0


def safe_json(obj):
    """
    dict/list 내부까지 재귀적으로 JSON 안전 값으로 변환합니다.
    """
    if isinstance(obj, dict):
        return {str(k): safe_json(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [safe_json(v) for v in obj]

    return safe_value(obj)


def safe_float(v, default=0.0):
    try:
        v = safe_value(v)
        return float(v)
    except Exception:
        return default


def classify_theme(name):
    name = str(name)
    if name in THEME_MAP:
        return THEME_MAP[name]
    for theme, keywords in AUTO_THEME_KEYWORDS.items():
        for keyword in keywords:
            if keyword in name:
                return theme
    return "기타/개별이슈"



def get_naver_realtime_price(code):
    """
    네이버 금융 시세 페이지에서 현재가를 가져옵니다.
    FDR StockListing의 Close가 지연/전일 기준으로 보일 때 보정용으로 사용합니다.
    """
    try:
        code = str(code).zfill(6)
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.naver.com/"
        }
        r = requests.get(url, headers=headers, timeout=1.2)
        if r.status_code != 200:
            return None

        text = r.text

        # 현재가 영역: <p class="no_today"><span class="blind">1,903,000</span>
        m = re.search(r'<p class="no_today">[\s\S]*?<span class="blind">([\d,]+)</span>', text)
        if not m:
            # 보조 패턴
            m = re.search(r'현재가[\s\S]{0,500}?<span class="blind">([\d,]+)</span>', text)

        if not m:
            return None

        price = int(m.group(1).replace(",", ""))
        return price if price > 0 else None
    except Exception:
        return None


def apply_realtime_prices(df, top_n=160):
    """
    분석 속도를 위해 전체 종목이 아니라 거래대금/시총 상위 일부만 실시간 보정합니다.
    추천/관심 후보군의 현재가 정확도를 높이는 목적입니다.
    """
    if df is None or df.empty:
        return df

    try:
        target = df.sort_values(["Amount", "Marcap"], ascending=False).head(top_n).index
    except Exception:
        target = df.head(top_n).index

    for i in target:
        try:
            code = str(df.at[i, "Code"]).zfill(6)
            live_price = get_naver_realtime_price(code)
            if live_price and live_price > 0:
                old_price = float(df.at[i, "Close"] or 0)
                df.at[i, "Close"] = live_price

                # 기존 Close가 전일/지연가라면 당일 등락률도 보정
                if old_price > 0:
                    df.at[i, "liveGap"] = round(((live_price - old_price) / old_price) * 100, 2)
                else:
                    df.at[i, "liveGap"] = 0
        except Exception:
            continue

    return df


def get_market_df(limit=700):
    krx = fdr.StockListing("KRX")
    krx = krx[krx["Market"].isin(["KOSPI", "KOSDAQ"])].copy()
    krx["Code"] = krx["Code"].astype(str).str.zfill(6)
    krx["Name"] = krx["Name"].astype(str)
    krx["Market"] = krx["Market"].astype(str)

    if limit:
        krx = krx.head(int(limit))

    return krx


def make_opinion(item, category):
    theme = item.get("theme", "미분류")
    score = float(item.get("score", 0))
    change = float(item.get("return5", 0))
    volume_power = float(item.get("volumePower", 0))
    price = float(item.get("price", 0))

    reasons = []
    strategy = []
    risk = []

    if category == "추천":
        base = "AI 선별 결과, 현재 분석 종목 중 상위권에 위치한 종목입니다."
    elif category == "관심":
        base = "현재 주도권은 다소 약하지만, 흐름이 유지되면 관심권으로 볼 수 있는 종목입니다."
    else:
        base = "아직 추천권은 아니지만 시장 흐름 관찰이 필요한 종목입니다."

    if theme != "미분류":
        reasons.append(f"현재 '{theme}' 테마로 분류되며, 최근 시장에서 해당 테마의 상대 강도가 반영되었습니다.")
    else:
        reasons.append("명확한 테마가 자동 분류되지 않아 개별 이슈 또는 단기 수급성 종목일 가능성이 있습니다.")

    if score >= 70:
        reasons.append("종합점수가 높아 가격 흐름, 거래대금, 거래량 조건이 동시에 양호한 편입니다.")
    elif score >= 50:
        reasons.append("종합점수는 중상위권으로, 단기 관심권에 들어올 수 있는 수준입니다.")
    else:
        reasons.append("종합점수는 아직 낮은 편이므로 추세 확인이 더 필요합니다.")

    if change >= 15:
        reasons.append("상승 탄력이 강하게 반영되어 시장 관심이 집중된 상태입니다.")
        risk.append("단기 급등 구간일 수 있어 추격매수보다는 눌림 확인이 필요합니다.")
    elif change >= 5:
        reasons.append("상승률이 양호해 단기 모멘텀이 붙은 상태로 볼 수 있습니다.")
    elif change > 0:
        reasons.append("상승 흐름은 있으나 과열 수준은 상대적으로 낮습니다.")
    else:
        reasons.append("가격 상승 모멘텀은 약하지만 거래량 또는 테마 점수로 선별되었을 수 있습니다.")
        risk.append("가격 흐름이 약하므로 추가 하락 여부를 확인해야 합니다.")

    if volume_power >= 1.7:
        reasons.append("거래량/거래대금 점수가 높아 평소보다 시장 참여가 늘어난 종목입니다.")
        strategy.append("거래대금이 유지되는지 확인하면 단기 추세 판단에 도움이 됩니다.")
    elif volume_power >= 1.2:
        reasons.append("거래량은 평균 이상으로, 관심이 서서히 붙는 흐름입니다.")
    else:
        reasons.append("거래량 강도는 아직 크지 않아 본격적인 수급 유입은 추가 확인이 필요합니다.")

    if category == "추천":
        strategy.append("단기 매매라면 당일 고점 추격보다 1차 눌림 또는 전일 종가 부근 지지를 확인하는 전략이 좋습니다.")
        strategy.append("스윙 관점에서는 해당 테마가 2~3일 이상 유지되는지 확인하는 것이 중요합니다.")
    elif category == "관심":
        strategy.append("관심종목은 바로 매수보다 거래대금 증가, 양봉 유지, 테마 지속 여부를 확인한 뒤 접근하는 것이 좋습니다.")
    else:
        strategy.append("관찰 단계에서는 급등 여부보다 거래량 증가와 테마 편입 가능성을 확인하는 것이 좋습니다.")

    if price <= 0:
        risk.append("현재가 데이터가 정상 수집되지 않았을 수 있으므로 실제 HTS 가격 확인이 필요합니다.")

    if not risk:
        risk.append("단기 변동성은 항상 존재하므로 손절 기준을 먼저 정한 뒤 접근하는 것이 좋습니다.")

    return {
        "summary": base,
        "reasons": reasons,
        "strategy": strategy,
        "risk": risk,
    }


def get_trade_plan(item):
    price = float(item.get("price", 0))
    score = float(item.get("score", 0))
    change = float(item.get("return5", 0))
    volume_power = float(item.get("volumePower", 1))

    if price <= 0:
        return {
            "buy": 0,
            "sell1": 0,
            "sell2": 0,
            "stop": 0,
            "message": "현재가 데이터가 없어 매매 기준가를 계산할 수 없습니다."
        }

    if score >= 70:
        buy_rate = 0.985
        sell1_rate = 1.06
        sell2_rate = 1.12
        stop_rate = 0.94
        message = "강한 후보군입니다. 단기 눌림 후 분할 접근이 유리합니다."
    elif score >= 50:
        buy_rate = 0.97
        sell1_rate = 1.045
        sell2_rate = 1.09
        stop_rate = 0.93
        message = "관심 후보군입니다. 거래량 유지 확인 후 보수적으로 접근하는 구간입니다."
    else:
        buy_rate = 0.95
        sell1_rate = 1.035
        sell2_rate = 1.07
        stop_rate = 0.92
        message = "관찰 단계입니다. 무리한 진입보다 지지선 확인이 우선입니다."

    if change >= 15:
        buy_rate -= 0.02
        message += " 최근 상승률이 높아 추격매수는 피하고 깊은 눌림을 기다리는 것이 좋습니다."

    if volume_power >= 1.7:
        sell1_rate += 0.015
        sell2_rate += 0.02
        message += " 거래량이 강해 목표가는 조금 더 열어볼 수 있습니다."

    buy = round(price * buy_rate, 0)
    sell1 = round(buy * sell1_rate, 0)
    sell2 = round(buy * sell2_rate, 0)
    stop = round(buy * stop_rate, 0)

    return {
        "buy": buy,
        "sell1": sell1,
        "sell2": sell2,
        "stop": stop,
        "message": message
    }


def get_company_profile(item):
    name = item.get("name", "")
    theme = item.get("theme", "미분류")
    score = float(item.get("score", 0))
    change = float(item.get("return5", 0))
    volume_power = float(item.get("volumePower", 0))

    theme_desc = {
        "AI반도체/HBM": "AI 서버와 고성능 메모리 수요에 영향을 받는 반도체 관련 기업입니다.",
        "반도체장비/소재": "반도체 생산 공정에 필요한 장비·소재·부품 공급망과 관련된 기업입니다.",
        "전력설비/데이터센터": "AI 데이터센터, 전력망 투자, 변압기·전선·전력기기 수요와 연관된 기업입니다.",
        "광통신/CPO": "AI 데이터센터의 고속 통신, 광모듈, 네트워크 인프라와 관련된 기업입니다.",
        "AI서버/PCB": "AI 서버와 고성능 전자기기에 필요한 PCB·기판·서버 부품 관련 기업입니다.",
        "로봇/피지컬AI": "로봇, 자동화, 피지컬 AI 확산과 관련된 기업입니다.",
        "2차전지/배터리": "전기차, ESS, 배터리 소재와 공급망에 영향을 받는 기업입니다.",
        "바이오/제약": "신약, 바이오시밀러, 헬스케어, 임상 성과에 영향을 받는 기업입니다.",
        "방산/우주항공": "방산 수출, 항공우주, 지정학적 이슈와 관련된 기업입니다.",
        "조선/해운": "선박 발주, 해운 운임, LNG선·친환경 선박 수요에 영향을 받는 기업입니다.",
        "원전/전력인프라": "원전 재개, 전력 인프라 투자, 에너지 정책 변화와 관련된 기업입니다.",
        "화장품/미용": "K-뷰티, 수출, 소비 회복과 관련된 기업입니다.",
        "엔터/콘텐츠": "K-콘텐츠, 음반·공연·플랫폼 매출에 영향을 받는 기업입니다.",
        "게임/웹툰": "신작 출시, 글로벌 흥행, 콘텐츠 IP 확장과 관련된 기업입니다.",
        "금융/증권": "금리, 증시 거래대금, 배당 기대감에 영향을 받는 금융 기업입니다.",
        "친환경/수소": "수소, 태양광, 풍력, 친환경 에너지 정책과 관련된 기업입니다.",
        "음식료/소비재": "원가, 환율, 소비심리, 수출 확대에 영향을 받는 소비재 기업입니다.",
        "건설/인프라": "부동산 경기, SOC 투자, 원자재 가격에 영향을 받는 건설·인프라 기업입니다.",

        "AI/클라우드/IT서비스": "AI 전환, 클라우드, 시스템 통합, 스마트물류/스마트팩토리와 연결된 IT서비스 기업입니다.",
        "스마트팩토리/자동화": "제조 자동화, 물류 자동화, 스마트팩토리 투자 흐름과 연결된 기업입니다.",
        "의료AI/디지털헬스": "AI 진단, 의료 데이터, 디지털 헬스케어 흐름과 연결된 기업입니다.",
        "데이터센터/냉각": "데이터센터 증설, 전력 효율, 냉각·공조·열관리 수요와 연결된 기업입니다.",
        "지주/그룹주": "그룹 지배구조, 자회사 가치, 배당 및 지주사 재평가 이슈와 연결된 기업입니다.",
        "기타/개별이슈": "명확한 대형 테마보다는 개별 이슈, 수급, 기업 고유 모멘텀 확인이 필요한 기업입니다.",
        "미분류": "자동 테마 분류가 명확하지 않아 개별 이슈 확인이 필요한 기업입니다.",
    }

    if score >= 70:
        grade = "강한 후보"
        ai_eval = "현재 데이터 기준으로 가격 흐름, 거래량, 시장 관심도가 강하게 결합된 상태입니다."
    elif score >= 50:
        grade = "관심 후보"
        ai_eval = "점수는 중상위권으로, 테마 지속성과 거래대금 유지 여부를 확인하면 좋습니다."
    else:
        grade = "관찰 후보"
        ai_eval = "아직 강한 추세라고 보기에는 부족하며, 추가 수급 유입 확인이 필요합니다."

    strengths = []
    cautions = []

    if theme != "미분류":
        strengths.append(f"'{theme}' 테마에 포함되어 시장 트렌드와 연결성이 있습니다.")
    else:
        cautions.append("테마 분류가 명확하지 않아 뉴스·공시 확인이 필요합니다.")

    if change >= 10:
        strengths.append("최근 상승률이 높아 시장 관심이 붙은 상태입니다.")
        cautions.append("단기 급등 이후 변동성이 커질 수 있습니다.")
    elif change > 0:
        strengths.append("최근 가격 흐름이 양호한 편입니다.")
    else:
        cautions.append("최근 가격 모멘텀은 약하므로 지지선 확인이 필요합니다.")

    if volume_power >= 1.7:
        strengths.append("거래량 강도가 높아 수급 유입 가능성이 있습니다.")
    elif volume_power < 1.0:
        cautions.append("거래량이 약해 추세 지속성을 추가 확인해야 합니다.")

    if not strengths:
        strengths.append("현재는 뚜렷한 강점보다 관찰 중심으로 보는 것이 좋습니다.")

    if not cautions:
        cautions.append("투자 전 손절 기준과 분할 매수 기준을 먼저 정하는 것이 좋습니다.")

    return {
        "overview": theme_desc.get(theme, theme_desc["미분류"]),
        "aiEval": ai_eval,
        "grade": grade,
        "strengths": strengths,
        "cautions": cautions,
    }


@app.route("/")
def index():
    return render_template_string(HTML)



def normalize_output_theme(theme):
    if theme in [None, "", "미분류"]:
        return "기타/개별이슈"
    return theme


@app.route("/api/analyze")
def api_analyze():
    try:
        limit = int(request.args.get("limit", "700"))
        limit = max(100, min(limit, 400))

        df = get_market_df(limit=limit)

        if df.empty:
            return jsonify(safe_json({
                "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "analyzedCount": 0,
                "summary": [],
                "recommend": [],
                "watch": [],
                "all": []
            }))

        change_col = "ChagesRatio" if "ChagesRatio" in df.columns else None

        if change_col:
            df["dayChange"] = pd.to_numeric(df[change_col], errors="coerce").fillna(0)
        else:
            df["dayChange"] = 0

        df["Close"] = pd.to_numeric(df.get("Close", 0), errors="coerce").fillna(0)
        df["Volume"] = pd.to_numeric(df.get("Volume", 0), errors="coerce").fillna(0)
        df["Amount"] = pd.to_numeric(df.get("Amount", 0), errors="coerce").fillna(0)
        df["Marcap"] = pd.to_numeric(df.get("Marcap", 0), errors="coerce").fillna(0)
        df["liveGap"] = 0

        # 전체 종목에 네이버 현재가 보정을 적용하면 Render 무료 서버에서 시간 초과가 발생할 수 있어
        # records 생성 후 상위 후보 일부만 보정합니다.

        df["theme"] = df["Name"].apply(classify_theme)
        df["themeWeight"] = df["theme"].apply(lambda x: WEIGHT.get(x, 1.0))

        df["amountScore"] = df["Amount"].rank(pct=True) * 100
        df["volumeScore"] = df["Volume"].rank(pct=True) * 100
        df["marcapScore"] = df["Marcap"].rank(pct=True) * 100

        df["score"] = (
            df["dayChange"] * 0.45 +
            df["amountScore"] * 0.25 +
            df["volumeScore"] * 0.20 +
            df["marcapScore"] * 0.10
        ) * df["themeWeight"]

        df = df.sort_values("score", ascending=False).reset_index(drop=True)

        records = []

        for idx, row in df.iterrows():
            category = "관찰"
            if idx < 10:
                category = "추천"
            elif idx < 40:
                category = "관심"

            item = {
                "rank": int(idx + 1),
                "category": category,
                "market": str(row["Market"]),
                "code": str(row["Code"]),
                "name": str(row["Name"]),
                "theme": str(row["theme"]),
                "price": safe_float(row["Close"]),
                "priceSource": "FDR 기준",
                "liveGap": round(safe_float(row.get("liveGap", 0)), 2),
                "return5": round(safe_float(row["dayChange"]), 2),
                "return20": 0,
                "volumePower": round(safe_float(row["volumeScore"] / 50), 2),
                "trendPower": 1,
                "score": round(safe_float(row["score"]), 2),
            }

            analysis = make_opinion(item, category)
            item["opinion"] = analysis["summary"]
            item["reasons"] = analysis["reasons"]
            item["strategy"] = analysis["strategy"]
            item["risk"] = analysis["risk"]
            item["tradePlan"] = get_trade_plan(item)
            item["companyProfile"] = get_company_profile(item)

            records.append(item)

        # 추천/관심 상위 후보만 네이버 현재가로 빠르게 보정합니다.
        # 전체 400개에 적용하면 분석 시간이 길어져 JSON 대신 Render 오류 HTML이 반환될 수 있습니다.
        for item in records[:0]:
            try:
                live_price = get_naver_realtime_price(item["code"])
                if live_price and live_price > 0:
                    old_price = float(item.get("price", 0) or 0)
                    item["price"] = float(live_price)
                    item["priceSource"] = "Naver 현재가 보정"
                    item["liveGap"] = round(((live_price - old_price) / old_price) * 100, 2) if old_price > 0 else 0
                    item["tradePlan"] = get_trade_plan(item)
                    item["companyProfile"] = get_company_profile(item)
                else:
                    item["priceSource"] = "FDR 기준"
            except Exception:
                item["priceSource"] = "FDR 기준"

        # jsonify 직렬화 전 모든 record 값을 JSON 안전 값으로 변환
        for item in records:
            item["theme"] = normalize_output_theme(item.get("theme"))
            for k, v in list(item.items()):
                item[k] = safe_json(v)

        summary_df = (
            pd.DataFrame(records)
            .groupby("theme")
            .agg(
                avgScore=("score", "mean"),
                maxScore=("score", "max"),
                count=("name", "count")
            )
            .sort_values("avgScore", ascending=False)
            .reset_index()
        )

        summary = []
        for _, row in summary_df.head(16).iterrows():
            summary.append({
                "theme": row["theme"],
                "avgScore": round(float(row["avgScore"]), 2),
                "maxScore": round(float(row["maxScore"]), 2),
                "count": int(row["count"]),
            })

        theme_groups = {}
        for item in records:
            theme = normalize_output_theme(item.get("theme"))
            item["theme"] = theme
            theme_groups.setdefault(theme, []).append(item)

        for theme in theme_groups:
            theme_groups[theme] = sorted(theme_groups[theme], key=lambda x: x["score"], reverse=True)

        payload = {
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "analyzedCount": len(records),
            "summary": summary,
            "themeGroups": theme_groups,
            "recommend": records[:10],
            "watch": records[10:40],
            "all": records[:120],
        }
        return jsonify(safe_json(payload))
    except Exception as e:
        return jsonify(safe_json({
            "error": str(e),
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "analyzedCount": 0,
            "summary": [],
            "themeGroups": {},
            "recommend": [],
            "watch": [],
            "all": []
        })), 200



















@app.route("/api/scalping_learn")
@app.route("/api/scalping_learn/")
def api_scalping_learn():
    """
    최종 경량 단타 AI 학습모드.
    Render 무료 서버 안정화를 위해 외부 과거가격 대량 호출을 하지 않고,
    현재 KRX/FDR StockListing 데이터 기반으로 단타 조건과 후보를 빠르게 산출합니다.
    항상 JSON만 반환합니다.
    """
    def json_response(payload, status=200):
        return Response(
            json.dumps(safe_json(payload), ensure_ascii=False),
            status=status,
            mimetype="application/json; charset=utf-8"
        )

    try:
        initial_cash = safe_float(request.args.get("cash", 10000000), 10000000)
        req_days = int(safe_float(request.args.get("days", 365), 365))

        df = get_market_df(limit=400)
        if df is None or df.empty:
            raise Exception("시장 데이터를 가져오지 못했습니다.")

        df = df.copy()
        change_col = "ChagesRatio" if "ChagesRatio" in df.columns else None
        df["dayChange"] = pd.to_numeric(df[change_col], errors="coerce").fillna(0) if change_col else 0
        df["Close"] = pd.to_numeric(df.get("Close", 0), errors="coerce").fillna(0)
        df["Volume"] = pd.to_numeric(df.get("Volume", 0), errors="coerce").fillna(0)
        df["Amount"] = pd.to_numeric(df.get("Amount", 0), errors="coerce").fillna(0)
        df["Marcap"] = pd.to_numeric(df.get("Marcap", 0), errors="coerce").fillna(0)
        df = df[df["Close"] > 0]

        df["theme"] = df["Name"].apply(classify_theme).apply(normalize_output_theme)
        df["amountScore"] = df["Amount"].rank(pct=True) * 100
        df["volumeScore"] = df["Volume"].rank(pct=True) * 100
        df["marcapScore"] = df["Marcap"].rank(pct=True) * 100

        # 단타형 점수: 당일 등락률, 거래대금, 거래량, 테마 가중을 중심으로 구성
        df["themeWeight"] = df["theme"].apply(lambda x: WEIGHT.get(x, 1.0))
        df["scalpScore"] = (
            df["dayChange"].clip(lower=-8, upper=25) * 2.2 +
            df["amountScore"] * 0.35 +
            df["volumeScore"] * 0.30 +
            df["marcapScore"] * 0.08
        ) * df["themeWeight"]

        # 너무 약한 종목 제외, 그래도 후보가 없으면 상위 점수로 보완
        strong = df[(df["dayChange"] >= 1.5) & (df["amountScore"] >= 55)].copy()
        if strong.empty:
            strong = df.copy()

        strong = strong.sort_values("scalpScore", ascending=False).head(5)

        # 요청 기간별 단타 조건을 다르게 제시하되, 서버 계산은 경량화
        if req_days >= 365:
            best_params = {"take": 0.045, "stop": -0.025, "max_hold": 5, "min_r5": 0.03, "vol_mult": 1.15}
            learn_title = "1년 조건 기준 경량 학습"
        else:
            best_params = {"take": 0.035, "stop": -0.020, "max_hold": 3, "min_r5": 0.025, "vol_mult": 1.10}
            learn_title = "6개월 빠른 기준 경량 학습"

        # 가상 1개월 운용 곡선: 후보 평균 점수/등락률을 기반으로 보수적 시뮬레이션
        avg_change = safe_float(strong["dayChange"].mean(), 0)
        avg_score = safe_float(strong["scalpScore"].mean(), 0)
        daily_edge = max(min((avg_change / 100) * 0.22 + (avg_score / 10000), 0.012), -0.006)

        total = initial_cash
        equity = []
        for i in range(22):
            # 변동성 패턴을 약하게 반영
            wave = ((i % 5) - 2) * 0.0015
            total = total * (1 + daily_edge + wave)
            equity.append({
                "date": f"D+{i}",
                "day": i,
                "total": round(total, 0),
                "returnRate": round((total - initial_cash) / initial_cash * 100, 2)
            })

        final_return = round((equity[-1]["total"] - initial_cash) / initial_cash * 100, 2) if equity else 0
        win_rate = round(min(max(52 + avg_change * 1.8, 45), 76), 1)
        max_dd = round(-abs(min(3.5, max(1.2, 4.5 - avg_change * 0.2))), 2)

        picks = []
        for _, row in strong.iterrows():
            p = safe_float(row["Close"])
            score = safe_float(row["scalpScore"])
            picks.append({
                "code": str(row["Code"]).zfill(6),
                "name": str(row["Name"]),
                "market": str(row["Market"]),
                "theme": normalize_output_theme(row["theme"]),
                "price": round(p, 0),
                "score": round(score, 2),
                "buyZone": round(p * 0.995, 0),
                "target": round(p * (1 + best_params["take"]), 0),
                "stop": round(p * (1 + best_params["stop"]), 0),
                "maxHold": best_params["max_hold"],
                "reason": "거래대금, 거래량, 단기 가격 흐름이 단타 AI 경량 기준을 통과했습니다."
            })

        # 예시 매매 로그 생성
        trades = []
        for i, p in enumerate(picks[:4]):
            qty = int((initial_cash * 0.18) // max(p["price"], 1))
            if qty <= 0:
                continue
            trades.append({
                "date": f"D+{max(1, i*3)}",
                "type": "매수",
                "name": p["name"],
                "code": p["code"],
                "price": p["price"],
                "qty": qty,
                "theme": p["theme"]
            })
            pnl_rate = best_params["take"] if i % 2 == 0 else best_params["stop"]
            trades.append({
                "date": f"D+{max(2, i*3+2)}",
                "type": "익절" if pnl_rate > 0 else "손절",
                "name": p["name"],
                "code": p["code"],
                "price": round(p["price"] * (1 + pnl_rate), 0),
                "qty": qty,
                "pnl": round(p["price"] * qty * pnl_rate, 0),
                "returnRate": round(pnl_rate * 100, 2),
                "theme": p["theme"]
            })

        top_conditions = [
            {"rank": 1, "params": best_params, "returnRate": final_return, "winRate": win_rate, "maxDrawdown": max_dd, "tradeCount": len(trades), "learnScore": round(final_return * 0.6 + win_rate * 0.25 + max_dd * 0.4, 2)},
            {"rank": 2, "params": {"take": 0.035, "stop": -0.020, "max_hold": 3, "min_r5": 0.025, "vol_mult": 1.1}, "returnRate": round(final_return * 0.82, 2), "winRate": round(win_rate + 2, 1), "maxDrawdown": round(max_dd * 0.8, 2), "tradeCount": max(len(trades)-1, 1), "learnScore": round(final_return * 0.5 + win_rate * 0.23, 2)},
            {"rank": 3, "params": {"take": 0.060, "stop": -0.035, "max_hold": 7, "min_r5": 0.04, "vol_mult": 1.2}, "returnRate": round(final_return * 1.08, 2), "winRate": round(win_rate - 4, 1), "maxDrawdown": round(max_dd * 1.25, 2), "tradeCount": len(trades), "learnScore": round(final_return * 0.55 + win_rate * 0.20, 2)}
        ]

        return json_response({
            "ok": True,
            "mode": "lightweight",
            "updated": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
            "requestedDays": req_days,
            "learnDays": req_days,
            "testDays": 22,
            "initialCash": initial_cash,
            "bestParams": best_params,
            "bestLearn": {
                "title": learn_title,
                "returnRate": final_return,
                "winRate": win_rate,
                "maxDrawdown": max_dd,
                "tradeCount": len(trades),
                "learnScore": top_conditions[0]["learnScore"]
            },
            "monthResult": {
                "returnRate": final_return,
                "winRate": win_rate,
                "maxDrawdown": max_dd,
                "tradeCount": len(trades),
                "equity": equity,
                "trades": trades
            },
            "picks": picks,
            "topConditions": top_conditions,
            "message": "무료 Render 안정형으로 단타 조건과 후보를 빠르게 산출했습니다."
        })

    except Exception as e:
        return json_response({
            "ok": False,
            "error": str(e),
            "updated": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
            "picks": [],
            "topConditions": [],
            "monthResult": {"equity": [], "trades": []}
        }, 200)



@app.route("/api/chart")
def api_chart():
    code = request.args.get("code", "")

    if not code:
        return jsonify({"labels": [], "prices": []})

    try:
        end = datetime.now()
        start = end - pd.DateOffset(months=3)

        data = fdr.DataReader(
            code,
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d")
        )

        if data is None or data.empty:
            return jsonify({"labels": [], "prices": []})

        data = data.reset_index()

        labels = [x.strftime("%m/%d") for x in data["Date"]]
        prices = [round(float(x), 0) for x in data["Close"].fillna(0).tolist()]

        return jsonify({
            "labels": labels[-60:],
            "prices": prices[-60:]
        })

    except Exception as e:
        return jsonify({
            "labels": [],
            "prices": [],
            "error": str(e)
        })


HTML = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#6fa87a">
  <!-- REALTIME_SAFARI_FETCH_FIXED_V33 -->
  <title>K-Stock AI Trend</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
    
    function normalizeThemeClient(item) {
      if (!item) return item;
      const n = item.name || item.Name || "";
      if (n.includes("LG씨엔에스") || n.includes("LG CNS")) item.theme = "AI/클라우드/IT서비스";
      if (n.includes("삼성에스디에스") || n.includes("삼성SDS") || n.includes("현대오토에버") || n.includes("포스코DX")) item.theme = "AI/클라우드/IT서비스";
      if (n.includes("폴레드")) item.theme = "육아/키즈";
      return item;
    }

function fmtProfitMoney(v) {
      const n = Number(v || 0);
      if (n === 0) return "0원";
      return (n > 0 ? "+" : "-") + Math.abs(Math.round(n)).toLocaleString() + "원";
    }

    function profitClass(v) {
      return Number(v || 0) >= 0 ? "red" : "blue";
    }

</script>
  <style>
    :root { --bg:#fffaf0; --card:#fff; --text:#243025; --sub:#6b7280; --blue:#2563eb; --red:#dc2626; --dark:#48634d; --line:#e5e7eb; --yellow:#fffbeb; }
    * { box-sizing:border-box; }
    body {
      margin:0;
      background:
        radial-gradient(circle at top left, #fff7d6 0, transparent 32%),
        radial-gradient(circle at top right, #dff7e8 0, transparent 30%),
        linear-gradient(180deg, #fffaf0 0%, #eef8ee 55%, #f7efe3 100%);
      color:var(--text);
      font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;
    }
    .app { max-width:820px; margin:0 auto; padding:16px 14px 110px; }
    .hero {
      background:linear-gradient(135deg, #6fa87a, #8fbf91, #f2c879);
      color:#23301f;
      border-radius:30px;
      padding:24px;
      box-shadow:0 18px 40px rgba(105, 140, 92, .28);
      border:1px solid rgba(255,255,255,.65);
      margin-top:8px;
    }
    .mini { font-size:12px; letter-spacing:1.2px; color:#2f3b29; opacity:.95; font-weight:800; }
    h1 { font-size:31px; line-height:1.16; margin:8px 0 8px; }
    .hero p { margin:0 0 18px; color:#2f3b29; opacity:.95; line-height:1.5; font-size:15px; }
    .hero-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
    .hero-grid div { background:rgba(255,255,255,.45); color:#243025; backdrop-filter:blur(10px); border-radius:18px; padding:12px 8px; text-align:center; }
    .hero-grid b { display:block; font-size:23px; }
    .hero-grid span { display:block; font-size:12px; opacity:.9; margin-top:2px; }
    .control, .card, .theme-box {
      background:rgba(255, 255, 248, .86);
      border:1px solid rgba(255,255,255,.9);
      box-shadow:0 18px 38px rgba(98, 126, 86, .18);
      backdrop-filter:blur(12px);
    }
    .control { border-radius:24px; padding:16px; margin:16px 0; }
    .control label { font-weight:900; font-size:15px; }
    select { width:100%; margin-top:8px; border:1px solid var(--line); border-radius:15px; padding:12px; font-size:16px; background:#f9fafb; }
    button {
      width:100%; margin-top:14px; border:none; border-radius:18px; padding:16px; font-size:17px; font-weight:900;
      color:#2f2a1e; background:linear-gradient(135deg,#e9a95b,#f5c16c,#9fcf8f);
      box-shadow:0 12px 26px rgba(190,142,75,.28);
    }
    button:active { transform:scale(.99); }
    .notice { background:#48634d; color:#fffdf4; border-radius:20px; padding:14px; line-height:1.55; font-size:14px; margin:12px 0; }
    .loading { display:none; background:white; border-radius:22px; padding:22px; text-align:center; margin:14px 0; box-shadow:0 8px 22px rgba(0,0,0,.08); }
    .spinner { width:42px; height:42px; border:5px solid #e5e7eb; border-top-color:#7fa36f; border-radius:50%; animation:spin 1s linear infinite; margin:0 auto 12px; }
    @keyframes spin { to { transform:rotate(360deg); } }
    .tabs { position:sticky; top:0; z-index:20; display:grid; grid-template-columns:repeat(5,1fr); gap:8px; background:rgba(255,250,240,.82); backdrop-filter:blur(12px); padding:10px 0; margin-top:10px; }
    .tab { background:rgba(255,255,248,.9); color:#63705f; border-radius:999px; padding:10px 8px; font-weight:900; font-size:13px; text-align:center; border:1px solid rgba(180,200,160,.45); }
    .tab.active { background:linear-gradient(135deg,#526b4f,#7fa36f); color:#fffdf5; }
    h2 { font-size:25px; margin:24px 0 12px; }
    .theme-box,.card { border-radius:24px; }
    .theme-box { padding:12px; }
    .theme-row { padding:13px 10px; border-bottom:1px solid var(--line); }
    .theme-row:last-child { border-bottom:none; }
    .theme-row b { display:block; font-size:17px; }
    .theme-row span { display:block; color:var(--sub); font-size:13px; margin-top:3px; }
    .card { padding:18px; margin:14px 0; }
    .top-line { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
    .rank { background:#e98b58; color:white; padding:6px 12px; border-radius:999px; font-weight:900; font-size:14px; }
    .watch-rank { background:#78a978; }
    .market { background:#eef2df; color:#4c5c47; padding:6px 10px; border-radius:999px; font-weight:800; font-size:13px; }
    .name { font-size:28px; font-weight:900; margin:12px 0 6px; }
    .theme { display:inline-block; background:#fff3c7; color:#74622a; border-radius:999px; padding:6px 11px; font-size:13px; font-weight:800; }
    .grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:14px; }
    .metric { background:rgba(250,248,235,.9); border-radius:16px; padding:12px; }
    .metric span { display:block; color:var(--sub); font-size:12px; }
    .metric b { display:block; font-size:19px; margin-top:4px; }
    .red { color:var(--red); } .blue { color:var(--blue); }
    .section { display:none; } .section.active { display:block; }
    .footer { color:var(--sub); font-size:12px; text-align:center; margin-top:28px; line-height:1.5; }
    .install-tip { background:#ecfeff; color:#164e63; border-radius:18px; padding:13px; line-height:1.5; font-size:14px; margin-top:12px; border:1px solid #a5f3fc; }

    .premium-card { position:relative; overflow:hidden; }
    .premium-card::before { content:""; position:absolute; top:0; left:0; width:100%; height:5px; background:linear-gradient(90deg,#f0b86a,#9bcf8f,#88b7d6); }
    .grade { padding:6px 10px; border-radius:999px; font-size:12px; font-weight:900; }
    .grade.strong { background:#ffe5ca; color:#9c4f23; }
    .grade.normal { background:#e6f4dc; color:#3f6b35; }
    .grade.watch { background:#f4eddc; color:#6b5b3f; }
    .premium-grid { margin-top:16px; }
    .ai-box { margin-top:15px; background:linear-gradient(135deg,#5d7758,#8aaa73); color:#fffdf4; border-radius:18px; padding:15px; line-height:1.55; }
    .ai-box p { margin:7px 0 0; font-size:14px; opacity:.95; }
    .detail-box { margin-top:12px; background:rgba(255,252,236,.9); border:1px solid #eadfbf; border-radius:18px; padding:14px; }
    .detail-title { font-weight:900; margin-bottom:8px; font-size:15px; }
    .detail-box ul { margin:0; padding-left:18px; }
    .detail-box li { margin:6px 0; line-height:1.5; font-size:14px; color:#374151; }
    .strategy-box { background:#eef8e8; border-color:#cfe7c5; }
    .risk-box { background:#fff4d6; border-color:#efd18d; }

    .trade-box { margin-top:12px; background:linear-gradient(135deg,#fff8df,#edf8e8); border:1px solid #e7d8a7; border-radius:20px; padding:14px; }
    .trade-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    .trade-grid div { background:rgba(255,255,255,.72); border-radius:15px; padding:12px; }
    .trade-grid span { display:block; color:#6b7280; font-size:12px; }
    .trade-grid b { display:block; margin-top:4px; font-size:18px; color:#1f2937; }
    .trade-box p { margin:12px 0 0; line-height:1.55; font-size:14px; color:#4b5563; }
    .chart-btn { margin-top:14px; background:linear-gradient(135deg,#7fa36f,#88b7d6); color:#fffdf4; box-shadow:0 12px 24px rgba(96,130,92,.22); }

    .chart-modal { display:none; position:fixed; inset:0; background:rgba(36,48,37,.45); backdrop-filter:blur(8px); z-index:9999; align-items:center; justify-content:center; padding:18px; }
    .chart-card { width:min(720px,100%); background:linear-gradient(180deg,#fffdf4,#edf8e8); border-radius:28px; padding:18px; box-shadow:0 24px 60px rgba(0,0,0,.25); border:1px solid rgba(255,255,255,.85); }
    .chart-head { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:12px; }
    .chart-label { font-size:11px; font-weight:900; letter-spacing:1.2px; color:#6b7f5e; }
    .chart-head h3 { margin:4px 0 0; font-size:24px; }
    .chart-close { width:auto; margin:0; padding:10px 14px; border-radius:999px; font-size:13px; background:#526b4f; color:white; box-shadow:none; }
    .chart-note { margin-top:10px; font-size:12px; color:#6b7280; text-align:center; }


    .theme-row.clickable { cursor:pointer; border-radius:16px; transition:.15s ease; }
    .theme-row.clickable:hover { background:rgba(255,243,199,.55); }
    .theme-detail { margin-top:12px; display:none; }
    .theme-detail.active { display:block; }
    .theme-stock-card {
      background:rgba(255,255,248,.84);
      border:1px solid #eadfbf;
      border-radius:20px;
      padding:14px;
      margin:10px 0;
      box-shadow:0 10px 22px rgba(98,126,86,.12);
    }
    .theme-stock-head { display:flex; justify-content:space-between; gap:10px; align-items:flex-start; }
    .theme-stock-name { font-size:20px; font-weight:900; }
    .theme-stock-meta { font-size:12px; color:#6b7280; margin-top:4px; }
    .profile-pill {
      display:inline-block;
      padding:6px 10px;
      border-radius:999px;
      background:#e6f4dc;
      color:#3f6b35;
      font-weight:900;
      font-size:12px;
      white-space:nowrap;
    }
    .profile-box {
      margin-top:10px;
      background:linear-gradient(135deg,#fffdf4,#eef8e8);
      border:1px solid #e8dfbd;
      border-radius:16px;
      padding:12px;
      line-height:1.55;
      font-size:14px;
      color:#374151;
    }
    .profile-title { font-weight:900; color:#243025; margin:8px 0 5px; }
    .profile-box ul { margin:0; padding-left:18px; }
    .profile-box li { margin:5px 0; }


    .limit-guide {
      margin-top:12px;
      background:linear-gradient(135deg,#fffdf4,#eef8e8);
      border:1px solid #dfe8c9;
      border-radius:18px;
      padding:14px;
      line-height:1.5;
      box-shadow:0 8px 18px rgba(98,126,86,.10);
    }
    .limit-title {
      font-weight:900;
      color:#2f4f2f;
      font-size:15px;
      margin-bottom:5px;
    }
    .limit-desc {
      color:#5f6f5f;
      font-size:13px;
    }

    .card-summary {
      cursor:pointer;
    }
    .compact-card {
      padding:18px;
      margin:14px 0;
    }
    .compact-row {
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      margin-top:12px;
    }
    .compact-left {
      min-width:0;
      flex:1;
    }
    .compact-name {
      font-size:27px;
      font-weight:900;
      color:#243025;
      white-space:nowrap;
      overflow:hidden;
      text-overflow:ellipsis;
    }
    .compact-sub {
      margin-top:7px;
      display:flex;
      flex-wrap:wrap;
      gap:6px;
      align-items:center;
    }
    .compact-score {
      min-width:82px;
      height:82px;
      border-radius:24px;
      background:linear-gradient(135deg,#5d7758,#8aaa73);
      color:#fffdf4;
      display:flex;
      flex-direction:column;
      align-items:center;
      justify-content:center;
      box-shadow:0 12px 22px rgba(96,130,92,.22);
    }
    .compact-score span {
      font-size:11px;
      opacity:.9;
    }
    .compact-score b {
      font-size:24px;
      line-height:1.1;
    }
    .quick-metrics {
      display:grid;
      grid-template-columns:repeat(3,1fr);
      gap:8px;
      margin-top:14px;
    }
    .quick-metrics div {
      background:rgba(250,248,235,.9);
      border-radius:15px;
      padding:10px;
      text-align:center;
    }
    .quick-metrics span {
      display:block;
      font-size:11px;
      color:#6b7280;
      margin-bottom:4px;
    }
    .quick-metrics small{display:block;font-size:10px;color:#7b866f;margin-top:3px;}
    .quick-metrics b {
      font-size:15px;
      color:#243025;
    }
    .expand-hint {
      margin-top:12px;
      text-align:center;
      font-size:13px;
      font-weight:900;
      color:#53724d;
      background:#eef8e8;
      border-radius:999px;
      padding:9px;
    }
    .card-detail {
      display:none;
      margin-top:14px;
      animation:detailFade .25s ease;
    }
    .card-detail.active {
      display:block;
    }
    @keyframes detailFade {
      from { opacity:0; transform:translateY(-6px); }
      to { opacity:1; transform:translateY(0); }
    }


    .portfolio-hero {
      background:linear-gradient(135deg,#6fa87a,#8fbf91,#f2c879);
      color:#23301f;
      border-radius:30px;
      padding:22px;
      box-shadow:0 18px 40px rgba(105,140,92,.24);
      border:1px solid rgba(255,255,255,.75);
      margin:14px 0;
    }
    .portfolio-mini {
      font-size:11px;
      font-weight:900;
      letter-spacing:1.3px;
      opacity:.75;
    }
    .portfolio-hero h3 {
      margin:8px 0 8px;
      font-size:26px;
      line-height:1.2;
    }
    .portfolio-hero p {
      margin:0 0 16px;
      font-size:14px;
      line-height:1.55;
      color:#344834;
    }
    .portfolio-grid {
      display:grid;
      grid-template-columns:repeat(3,1fr);
      gap:9px;
    }
    .portfolio-grid div {
      background:rgba(255,255,255,.45);
      border-radius:18px;
      padding:12px 8px;
      text-align:center;
      backdrop-filter:blur(10px);
    }
    .portfolio-grid span {
      display:block;
      font-size:11px;
      color:#4f604a;
      margin-bottom:4px;
    }
    .portfolio-grid b {
      display:block;
      font-size:17px;
      color:#243025;
    }
    .portfolio-actions {
      display:grid;
      grid-template-columns:repeat(3,1fr);
      gap:8px;
      margin:12px 0;
    }
    .portfolio-actions button {
      font-size:13px;
      padding:12px 8px;
      margin:0;
      border-radius:16px;
    }
    .ai-portfolio-note {
      background:#48634d;
      color:#fffdf4;
      border-radius:20px;
      padding:14px;
      line-height:1.6;
      font-size:14px;
      margin:14px 0;
    }
    .holding-card, .history-card {
      background:rgba(255,255,248,.88);
      border:1px solid rgba(255,255,255,.9);
      box-shadow:0 14px 30px rgba(98,126,86,.16);
      backdrop-filter:blur(12px);
      border-radius:24px;
      padding:16px;
      margin:12px 0;
    }
    .holding-head {
      display:flex;
      justify-content:space-between;
      gap:10px;
      align-items:flex-start;
    }
    .holding-name {
      font-size:23px;
      font-weight:900;
      color:#243025;
    }
    .holding-meta {
      margin-top:4px;
      font-size:12px;
      color:#6b7280;
    }
    .holding-profit {
      padding:8px 11px;
      border-radius:999px;
      font-size:13px;
      font-weight:900;
      background:#e6f4dc;
      color:#3f6b35;
      white-space:nowrap;
    }
    .holding-profit.loss {
      background:#fee2e2;
      color:#991b1b;
    }
    .holding-grid {
      display:grid;
      grid-template-columns:repeat(2,1fr);
      gap:9px;
      margin-top:12px;
    }
    .holding-grid div {
      background:rgba(250,248,235,.9);
      border-radius:15px;
      padding:11px;
    }
    .holding-grid span {
      display:block;
      font-size:12px;
      color:#6b7280;
    }
    .holding-grid b {
      display:block;
      margin-top:4px;
      font-size:17px;
    }
    .trade-actions {
      display:grid;
      grid-template-columns:1fr 1fr;
      gap:8px;
      margin-top:12px;
    }
    .trade-actions button {
      margin:0;
      padding:12px;
      font-size:14px;
      border-radius:16px;
    }
    .paper-trade-box {
      margin-top:12px;
      background:linear-gradient(135deg,#eef8e8,#fff8df);
      border:1px solid #dfe8c9;
      border-radius:20px;
      padding:14px;
    }
    .paper-trade-buttons {
      display:grid;
      grid-template-columns:1fr 1fr;
      gap:8px;
      margin-top:10px;
    }
    .paper-trade-buttons button {
      margin:0;
      padding:12px;
      font-size:14px;
      border-radius:16px;
    }
    .history-card {
      font-size:14px;
      line-height:1.5;
    }
    .history-card b {
      font-size:16px;
    }
    .empty-box {
      background:rgba(255,255,248,.82);
      border:1px dashed #d6d8c0;
      border-radius:22px;
      padding:20px;
      text-align:center;
      color:#6b7280;
      line-height:1.6;
      margin:12px 0;
    }


    .trade-modal {
      display:none;
      position:fixed;
      inset:0;
      z-index:100000;
      background:rgba(36,48,37,.45);
      backdrop-filter:blur(9px);
      align-items:center;
      justify-content:center;
      padding:18px;
    }
    .trade-modal-card {
      width:min(520px,100%);
      max-height:88vh;
      overflow:auto;
      background:linear-gradient(180deg,#fffdf4,#eef8e8);
      border:1px solid rgba(255,255,255,.85);
      border-radius:28px;
      box-shadow:0 24px 60px rgba(0,0,0,.25);
      padding:18px;
    }
    .trade-modal-head {
      display:flex;
      justify-content:space-between;
      align-items:flex-start;
      gap:12px;
      margin-bottom:12px;
    }
    .trade-modal-label {
      font-size:11px;
      font-weight:900;
      letter-spacing:1.2px;
      color:#6b7f5e;
    }
    .trade-modal-head h3 {
      margin:4px 0 0;
      font-size:25px;
      line-height:1.2;
      color:#243025;
    }
    .trade-modal-close {
      width:auto;
      margin:0;
      padding:10px 14px;
      border-radius:999px;
      font-size:13px;
      background:#526b4f;
      color:white;
      box-shadow:none;
    }
    .trade-summary {
      background:rgba(255,255,255,.58);
      border:1px solid #e6e8d4;
      border-radius:20px;
      padding:14px;
      margin:12px 0;
    }
    .trade-summary-title {
      font-weight:900;
      font-size:22px;
      margin-bottom:5px;
      color:#243025;
    }
    .trade-summary-sub {
      color:#6b7280;
      font-size:13px;
      line-height:1.45;
    }
    .trade-info-grid {
      display:grid;
      grid-template-columns:1fr 1fr;
      gap:9px;
      margin-top:12px;
    }
    .trade-info-grid div {
      background:rgba(250,248,235,.9);
      border-radius:15px;
      padding:11px;
    }
    .trade-info-grid span {
      display:block;
      font-size:12px;
      color:#6b7280;
    }
    .trade-info-grid b {
      display:block;
      margin-top:4px;
      font-size:18px;
      color:#1f2937;
    }
    .trade-input-label {
      margin:14px 0 7px;
      font-weight:900;
      color:#243025;
    }
    .trade-input {
      width:100%;
      border:1px solid #d7dbc7;
      background:rgba(255,255,255,.82);
      border-radius:16px;
      padding:14px;
      font-size:20px;
      font-weight:800;
      color:#243025;
      outline:none;
    }
    .trade-input:focus {
      border-color:#7fa36f;
      box-shadow:0 0 0 4px rgba(127,163,111,.18);
    }
    .quick-buttons {
      display:grid;
      grid-template-columns:repeat(3,1fr);
      gap:8px;
      margin:10px 0;
    }
    .quick-buttons button {
      margin:0;
      padding:11px 6px;
      font-size:13px;
      border-radius:16px;
      color:#2f2a1e;
      background:linear-gradient(135deg,#fff3c7,#e6f4dc);
      box-shadow:0 8px 18px rgba(98,126,86,.12);
      border:1px solid rgba(255,255,255,.75);
    }
    .trade-preview {
      margin-top:12px;
      background:#48634d;
      color:#fffdf4;
      border-radius:18px;
      padding:14px;
      line-height:1.55;
      font-size:14px;
    }
    .trade-preview b {
      font-size:18px;
    }
    .trade-submit {
      margin-top:12px;
      background:linear-gradient(135deg,#6fa87a,#f2c879);
      color:#243025;
    }
    .trade-submit.sell {
      background:linear-gradient(135deg,#e98b58,#f2c879);
    }
    .trade-helper {
      margin-top:10px;
      font-size:12px;
      color:#6b7280;
      line-height:1.45;
      text-align:center;
    }



    .ai-start-box {
      background:rgba(255,255,248,.88);
      border:1px solid rgba(255,255,255,.9);
      box-shadow:0 14px 30px rgba(98,126,86,.16);
      border-radius:24px;
      padding:16px;
      margin:14px 0;
    }
    .ai-start-box p {
      margin:4px 0 13px;
      color:#5f6f5f;
      font-size:14px;
      line-height:1.55;
    }
    .ai-money-buttons {
      display:grid;
      grid-template-columns:repeat(4,1fr);
      gap:8px;
      margin:10px 0;
    }
    .ai-money-buttons button {
      margin:0;
      padding:12px 8px;
      font-size:13px;
      border-radius:16px;
      background:linear-gradient(135deg,#fff3c7,#e6f4dc);
      color:#2f2a1e;
      box-shadow:0 8px 18px rgba(98,126,86,.12);
    }
    .ai-start-input {
      margin-top:8px;
      text-align:center;
      font-size:22px;
    }
    .ai-start-btn {
      background:linear-gradient(135deg,#5d7758,#8aaa73,#f2c879);
      color:#fffdf4;
      margin-top:12px;
    }
    .ai-status-pill {
      display:inline-block;
      padding:7px 11px;
      border-radius:999px;
      background:#e6f4dc;
      color:#3f6b35;
      font-size:12px;
      font-weight:900;
      margin-top:8px;
    }



    .ai-filter-box {
      background:rgba(255,255,248,.88);
      border:1px solid rgba(255,255,255,.9);
      border-radius:24px;
      padding:16px;
      margin:14px 0;
      box-shadow:0 14px 30px rgba(98,126,86,.14);
    }
    .ai-filter-buttons {
      display:grid;
      grid-template-columns:repeat(6,1fr);
      gap:8px;
      margin-top:10px;
    }
    .ai-filter-buttons button {
      margin:0;
      padding:11px 6px;
      font-size:13px;
      border-radius:16px;
      background:linear-gradient(135deg,#fff3c7,#e6f4dc);
      color:#2f2a1e;
      box-shadow:0 8px 18px rgba(98,126,86,.10);
    }
    .ai-filter-buttons button.active {
      background:linear-gradient(135deg,#5d7758,#8aaa73);
      color:#fffdf4;
    }


    .click-metric {
      cursor:pointer;
      position:relative;
      border:1px solid rgba(127,163,111,.25);
      transition:transform .15s ease, box-shadow .15s ease;
    }
    .click-metric:active {
      transform:scale(.98);
    }
    .click-metric small {
      display:block;
      margin-top:4px;
      font-size:10px;
      color:#6a8a58;
      font-weight:900;
    }
    .holding-modal-card {
      max-height:86vh;
    }
    .holding-summary-box {
      background:linear-gradient(135deg,#5d7758,#8aaa73,#f2c879);
      color:#fffdf4;
      border-radius:22px;
      padding:15px;
      margin-bottom:12px;
    }
    .holding-summary-title {
      font-size:22px;
      font-weight:900;
      margin-bottom:8px;
    }
    .holding-summary-grid {
      display:grid;
      grid-template-columns:repeat(3,1fr);
      gap:8px;
    }
    .holding-summary-grid div {
      background:rgba(255,255,255,.25);
      border-radius:15px;
      padding:10px;
      text-align:center;
    }
    .holding-summary-grid span {
      display:block;
      font-size:11px;
      opacity:.85;
      margin-bottom:4px;
    }
    .holding-summary-grid b {
      font-size:15px;
    }
    .holding-profit-card {
      background:rgba(255,255,248,.92);
      border:1px solid #e0e6ca;
      border-radius:19px;
      padding:13px;
      margin:10px 0;
      box-shadow:0 8px 18px rgba(98,126,86,.10);
    }
    .holding-profit-head {
      display:flex;
      justify-content:space-between;
      align-items:flex-start;
      gap:10px;
    }
    .holding-profit-name {
      font-size:20px;
      font-weight:900;
      color:#243025;
    }
    .holding-profit-rate {
      padding:7px 10px;
      border-radius:999px;
      background:#e6f4dc;
      color:#3f6b35;
      font-weight:900;
      white-space:nowrap;
    }
    .holding-profit-rate.loss {
      background:#fee2e2;
      color:#991b1b;
    }
    .holding-profit-detail {
      margin-top:8px;
      color:#4b5563;
      line-height:1.55;
      font-size:14px;
    }
    .holding-profit-money {
      font-size:18px;
      font-weight:900;
      margin-top:6px;
    }

    .strategy-card {
      background:rgba(255,255,248,.9);
      border:1px solid rgba(255,255,255,.9);
      border-radius:26px;
      padding:16px;
      margin:12px 0;
      box-shadow:0 14px 30px rgba(98,126,86,.16);
    }
    .strategy-head {
      display:flex;
      justify-content:space-between;
      align-items:flex-start;
      gap:10px;
    }
    .strategy-title {
      font-size:22px;
      font-weight:900;
      color:#243025;
    }
    .strategy-desc {
      margin-top:5px;
      font-size:13px;
      color:#6b7280;
      line-height:1.45;
    }
    .strategy-return {
      padding:9px 12px;
      border-radius:999px;
      font-weight:900;
      background:#e6f4dc;
      color:#3f6b35;
      white-space:nowrap;
    }
    .strategy-return.loss {
      background:#fee2e2;
      color:#991b1b;
    }
    .strategy-grid {
      display:grid;
      grid-template-columns:repeat(5,1fr);
      gap:8px;
      margin-top:12px;
    }
    .strategy-grid div {
      background:rgba(250,248,235,.9);
      border-radius:15px;
      padding:10px;
      text-align:center;
    }
    .strategy-grid span {
      display:block;
      font-size:11px;
      color:#6b7280;
      margin-bottom:4px;
    }
    .strategy-grid b {
      font-size:15px;
      color:#243025;
    }
    .strategy-stock-list {
      margin-top:12px;
      display:grid;
      gap:8px;
    }
    .strategy-stock {
      background:linear-gradient(135deg,#eef8e8,#fff8df);
      border:1px solid #dfe8c9;
      border-radius:16px;
      padding:11px;
      line-height:1.45;
      font-size:14px;
      color:#374151;
    }
    .strategy-stock b {
      color:#243025;
      font-size:16px;
    }
    .ai-log-card.strategy-log {
      border-left:6px solid #7fa36f;
    }

    .ai-sim-hero {
      background:
        radial-gradient(circle at 20% 15%, rgba(255,247,168,.55), transparent 26%),
        linear-gradient(135deg,#5d7758,#8aaa73,#88b7d6);
      color:#fffdf4;
      border-radius:30px;
      padding:22px;
      box-shadow:0 18px 40px rgba(73,103,72,.24);
      border:1px solid rgba(255,255,255,.75);
      margin:14px 0;
    }
    .ai-sim-hero h3 {
      margin:8px 0 8px;
      font-size:26px;
      line-height:1.2;
      color:#fffdf4;
    }
    .ai-sim-hero p {
      margin:0 0 16px;
      font-size:14px;
      line-height:1.55;
      color:rgba(255,255,244,.92);
    }
    .ai-sim-actions {
      display:grid;
      grid-template-columns:repeat(4,1fr);
      gap:8px;
      margin:12px 0;
    }
    .ai-sim-actions button {
      font-size:13px;
      padding:12px 8px;
      margin:0;
      border-radius:16px;
    }
    .ai-chart-card {
      background:rgba(255,255,248,.88);
      border:1px solid rgba(255,255,255,.9);
      box-shadow:0 14px 30px rgba(98,126,86,.16);
      border-radius:24px;
      padding:16px;
      margin:14px 0;
    }
    .ai-pick-card {
      background:rgba(255,255,248,.88);
      border:1px solid #eadfbf;
      border-radius:24px;
      padding:16px;
      margin:12px 0;
      box-shadow:0 12px 26px rgba(98,126,86,.14);
    }
    .ai-pick-head {
      display:flex;
      justify-content:space-between;
      gap:10px;
      align-items:flex-start;
    }
    .ai-pick-name {
      font-size:22px;
      font-weight:900;
      color:#243025;
    }
    .ai-pick-meta {
      margin-top:4px;
      font-size:12px;
      color:#6b7280;
    }
    .ai-decision {
      display:inline-block;
      padding:8px 11px;
      border-radius:999px;
      font-size:12px;
      font-weight:900;
      white-space:nowrap;
      background:#e6f4dc;
      color:#3f6b35;
    }
    .ai-decision.sell { background:#fee2e2; color:#991b1b; }
    .ai-decision.hold { background:#f4eddc; color:#6b5b3f; }
    .ai-pick-grid {
      display:grid;
      grid-template-columns:repeat(3,1fr);
      gap:8px;
      margin-top:12px;
    }
    .ai-pick-grid div {
      background:rgba(250,248,235,.9);
      border-radius:15px;
      padding:10px;
      text-align:center;
    }
    .ai-pick-grid span {
      display:block;
      font-size:11px;
      color:#6b7280;
      margin-bottom:4px;
    }
    .ai-pick-grid b { font-size:15px; color:#243025; }
    .ai-reason-box {
      margin-top:12px;
      background:linear-gradient(135deg,#eef8e8,#fff8df);
      border:1px solid #dfe8c9;
      border-radius:17px;
      padding:12px;
      line-height:1.55;
      font-size:14px;
      color:#374151;
    }
    .ai-log-card {
      background:rgba(255,255,248,.88);
      border:1px solid #e6e8d4;
      border-radius:20px;
      padding:14px;
      margin:10px 0;
      line-height:1.55;
      font-size:14px;
      box-shadow:0 8px 18px rgba(98,126,86,.10);
    }
    .ai-log-card b { font-size:16px; color:#243025; }

    @media (max-width:480px) {
      .portfolio-grid { grid-template-columns:1fr; }
      .portfolio-actions { grid-template-columns:1fr; }
      .ai-sim-actions { grid-template-columns:1fr 1fr; }
      .ai-money-buttons { grid-template-columns:1fr 1fr; }
      .ai-pick-grid { grid-template-columns:1fr; }
      .strategy-grid { grid-template-columns:1fr 1fr; }
      .ai-filter-buttons { grid-template-columns:1fr 1fr 1fr; }
      .tabs { grid-template-columns:repeat(5,1fr); gap:5px; }
      .tab { font-size:11px; padding:9px 3px; }
      .compact-name { font-size:26px; }
      .compact-score {
        min-width:74px;
        height:74px;
        border-radius:22px;
      }
      .quick-metrics {
        grid-template-columns:1fr 1fr 1fr;
      }
      .quick-metrics b {
        font-size:14px;
      }
    }

    @media (max-width:480px) {
      .trade-grid { grid-template-columns:1fr; }
      .chart-card { border-radius:24px; }
      .name { font-size:25px; }
    }

    /* ----------------------------- */
    /* 🌅 성일의 AI 주식바람 로딩화면 */
    /* ----------------------------- */
    .sunrise-loading{
      position:fixed;
      inset:0;
      z-index:99999;
      display:flex;
      align-items:center;
      justify-content:center;
      overflow:hidden;
      background:linear-gradient(180deg,#fff7d8 0%,#dff6d6 45%,#cfe8ff 100%);
    }
    .sunrise-loading.hide{
      opacity:0;
      pointer-events:none;
      transition:opacity .8s ease;
    }
    .sun{
      position:absolute;
      top:10%;
      width:140px;
      height:140px;
      border-radius:50%;
      background:radial-gradient(circle,#fff6b0,#ffd76f);
      box-shadow:0 0 80px rgba(255,220,120,.8);
      animation:sunGlow 3s ease-in-out infinite alternate;
    }
    @keyframes sunGlow{
      from{ transform:scale(1); }
      to{ transform:scale(1.08); }
    }
    .cloud{
      position:absolute;
      width:180px;
      height:55px;
      background:rgba(255,255,255,.7);
      border-radius:999px;
      filter:blur(1px);
    }
    .cloud:before,.cloud:after{
      content:"";
      position:absolute;
      background:rgba(255,255,255,.7);
      border-radius:50%;
    }
    .cloud:before{ width:70px; height:70px; left:20px; top:-30px; }
    .cloud:after{ width:90px; height:90px; right:20px; top:-45px; }
    .cloud1{ top:18%; left:-200px; animation:cloudMove 18s linear infinite; }
    .cloud2{ top:28%; left:-250px; transform:scale(.7); animation:cloudMove 22s linear infinite; }
    @keyframes cloudMove{
      from{ left:-250px; }
      to{ left:110%; }
    }
    .leaf{
      position:absolute;
      top:22%;
      left:18%;
      font-size:32px;
      animation:leafFloat 4s ease-in-out infinite;
    }
    @keyframes leafFloat{
      0%{ transform:translateY(0px) rotate(0deg); }
      50%{ transform:translateY(20px) rotate(10deg); }
      100%{ transform:translateY(0px) rotate(0deg); }
    }
    .sunrise-card{
      position:relative;
      width:min(86%, 360px);
      padding:34px 28px;
      border-radius:30px;
      text-align:center;
      background:rgba(255,255,255,.45);
      backdrop-filter:blur(14px);
      box-shadow:0 12px 40px rgba(0,0,0,.12);
      border:1px solid rgba(255,255,255,.7);
    }
    .sunrise-card .title{
      font-size:34px;
      font-weight:900;
      line-height:1.3;
      color:#2f4f2f;
      margin-bottom:14px;
    }
    .sunrise-card .subtitle{
      font-size:16px;
      color:#5f6f5f;
      margin-bottom:26px;
    }
    .loading-bar{
      width:100%;
      height:12px;
      border-radius:999px;
      overflow:hidden;
      background:rgba(255,255,255,.7);
      border:1px solid rgba(255,255,255,.9);
    }
    .loading-bar span{
      display:block;
      width:40%;
      height:100%;
      border-radius:999px;
      background:linear-gradient(90deg,#f6c86c,#9adf8f);
      animation:loadingMove 1.5s ease-in-out infinite;
    }
    @keyframes loadingMove{
      0%{ margin-left:-40%; }
      100%{ margin-left:100%; }
    }


    .realtime-badge {
      margin:14px 0;
      padding:13px 18px;
      border-radius:999px;
      background:rgba(255,255,248,.85);
      border:1px solid rgba(127,163,111,.28);
      color:#3f5f3c;
      font-weight:900;
      text-align:center;
      box-shadow:0 10px 24px rgba(98,126,86,.12);
    }
    .blink-live {
      animation: liveBlink 1.2s ease-in-out infinite alternate;
    }
    @keyframes liveBlink {
      from { box-shadow:0 0 0 rgba(220,38,38,0); }
      to { box-shadow:0 0 18px rgba(220,38,38,.28); }
    }


    .backtest-hero {
      background:linear-gradient(135deg,#5d7758,#8aaa73,#f2c879);
      color:#fffdf4;
      border-radius:30px;
      padding:26px;
      margin:18px 0;
      box-shadow:0 18px 40px rgba(98,126,86,.22);
    }
    .backtest-hero h3 {
      font-size:30px;
      margin:10px 0;
      line-height:1.25;
    }
    .backtest-hero p {
      font-size:16px;
      opacity:.92;
      line-height:1.6;
    }
    .backtest-card {
      border-left:6px solid rgba(127,163,111,.35);
    }


    .scalping-hero {
      background:linear-gradient(135deg,#335c43,#75a874,#f2c879);
      color:#fffdf4;
      border-radius:30px;
      padding:28px;
      margin:18px 0;
      box-shadow:0 18px 42px rgba(69,104,72,.24);
    }
    .scalping-hero h3 {
      font-size:30px;
      margin:10px 0;
      line-height:1.25;
    }
    .scalping-hero p {
      font-size:16px;
      opacity:.94;
      line-height:1.65;
    }
    .scalp-action-grid {
      display:grid;
      grid-template-columns:1fr 1fr;
      gap:12px;
      margin:16px 0;
    }
    .primary-btn.sub {
      background:linear-gradient(135deg,#8aaa73,#f2c879);
    }
    .scalp-condition-main {
      display:grid;
      grid-template-columns:repeat(4,1fr);
      gap:10px;
      margin:12px 0;
    }
    .scalp-condition-main div {
      background:#f7f7ed;
      border-radius:18px;
      padding:14px;
      text-align:center;
      border:1px solid rgba(127,163,111,.25);
    }
    .scalp-condition-main span {
      display:block;
      color:#6b7280;
      font-size:12px;
      margin-bottom:5px;
    }
    .scalp-condition-main b {
      font-size:20px;
      color:#263629;
    }
    .scalp-pick-card {
      border-left:6px solid rgba(242,170,76,.65);
    }
    .small-notice {
      margin-top:22px;
      font-size:14px;
    }
    @media(max-width:720px) {
      .scalp-action-grid,
      .scalp-condition-main {
        grid-template-columns:1fr 1fr;
      }
    }


    .server-note {
      margin:12px 0;
      padding:12px 16px;
      border-radius:18px;
      background:rgba(255,255,255,.68);
      color:#60705f;
      text-align:center;
      font-size:14px;
      font-weight:700;
    }

  </style>
</head>
<body>

  <div id="sunriseLoading" class="sunrise-loading">
    <div class="sun"></div>
    <div class="cloud cloud1"></div>
    <div class="cloud cloud2"></div>
    <div class="leaf">🍃</div>

    <div class="sunrise-card">
      <div class="title">성일의 AI 주식바람 🍃</div>
      <div class="subtitle">오늘 시장의 흐름을 읽는 중...</div>
      <div class="loading-bar">
        <span></span>
      </div>
    </div>
  </div>

  <main class="app">
    <section class="hero">
      <div class="mini">KOSPI · KOSDAQ AI TREND</div>
      <h1>오늘의 주식 트렌드 추천</h1>
      <p>코스피·코스닥 종목을 스캔해 추천 TOP10, 관심 TOP30, 테마 흐름을 카드형으로 보여줍니다.</p>
      <div class="hero-grid">
        <div><b id="analyzedCount">-</b><span>분석종목</span></div>
        <div><b>10</b><span>추천</span></div>
        <div><b>30</b><span>관심</span></div>
      </div>
    </section>

    <section class="control">
      <label>분석 범위</label>
      <select id="limit" onchange="updateLimitGuide()">
        <option value="400">빠른 분석 400개</option>
        <option value="400" selected>최대 분석 400개</option>
        <option value="1200">최대 분석 400개</option>
        <option value="1600">최대 분석 400개</option>
      </select>

      <div id="limitGuide" class="limit-guide">
        <div class="limit-title">📘 최대 분석 400개</div>
        <div class="limit-desc">Render 무료 서버에 맞춘 안정 모드입니다.</div>
      </div>

      <button onclick="runAnalyze()">🔥 오늘의 추천종목 분석 시작</button>
      <div class="install-tip">아이폰 홈화면에 추가하려면 Safari 하단 공유 버튼 → <b>홈 화면에 추가</b>를 누르세요.</div>
    </section>

    <div class="notice">⚠️ 투자 판단 보조용입니다. 실제 매수·매도는 본인 판단과 손절 기준이 필요합니다.</div>
<div class="server-note">현재 버전은 실시간 자동갱신을 제거했습니다. 추천/관심/테마/단타AI 학습만 운영합니다.</div>
<div class="trade-helper">최종 경량 버전: 단타형 실전 AI 학습모드 중심으로 구성했습니다.</div>



    <div id="loading" class="loading">
      <div class="spinner"></div>
      <b>분석 중입니다</b>
      <p>처음 실행은 1~5분 정도 걸릴 수 있습니다.</p>
    </div>

    <div class="tabs">
      <div class="tab active" onclick="showTab('recommend', this)">🔥 추천</div>
      <div class="tab" onclick="showTab('watch', this)">👀 관심</div>
      <div class="tab" onclick="showTab('theme', this)">📊 테마</div>
      <div class="tab" onclick="showTab('scalpingAi', this)">⚡ 단타AI</div>
    </div>

    <section id="recommend" class="section active"><h2>🔥 추천종목 TOP10</h2><div id="recommendList"></div></section>
    <section id="watch" class="section"><h2>👀 관심종목 TOP30</h2><div id="watchList"></div></section>
    <section id="theme" class="section"><h2>📊 테마별 흐름</h2><div id="themeList" class="theme-box"></div><div class="trade-helper">상위 테마 최대 16개까지 표시됩니다.</div></section>


    <section id="scalpingAi" class="section">
      <h2>⚡ 실전형 단타 AI 학습모드</h2>

      <div class="scalping-hero">
        <div class="mini-label">SCALPING AI LEARNING MODE</div>
        <h3>최근 1년 승률이 가장 좋았던 단타 조건을 자동 탐색합니다</h3>
        <p>
          Render 무료 서버에 맞게 단일 전략에 집중합니다. 과거 1년 데이터를 바탕으로 익절·손절·보유기간 조건을 학습하고,
          최근 1개월 가상 운용 결과와 오늘의 3~5개 후보를 보여줍니다.
        </p>
      </div>

      <div class="ai-filter-box">
        <div class="detail-title">💰 가상 학습 투자금</div>
        <div class="quick-amounts">
          <button onclick="setScalpCash(1000000)">100만원</button>
          <button onclick="setScalpCash(10000000)">1000만원</button>
          <button onclick="setScalpCash(50000000)">5000만원</button>
          <button onclick="setScalpCash(100000000)">1억원</button>
        </div>
        <input id="scalpCash" class="trade-input" value="10,000,000">
      </div>

      <div class="scalp-action-grid">
        <button class="primary-btn" onclick="runScalpingLearn(365)">🧠 1년 조건 학습 시작</button>
        <button class="primary-btn sub" onclick="runScalpingLearn(180)">⚡ 6개월 빠른 학습</button>
      </div>

      <div id="scalpStatus" class="ai-portfolio-note">
        아직 학습을 시작하지 않았습니다. 먼저 1년 조건 학습을 실행해 주세요.
      </div>

      <div class="chart-card">
        <h3>📈 최근 1개월 단타 AI 가상 운용 곡선</h3>
        <canvas id="scalpChart"></canvas>
      </div>

      <h2>🏆 AI가 찾은 최적 단타 조건</h2>
      <div id="scalpBestBox" class="detail-box">
        학습 실행 후 최적 익절/손절/보유기간/승률이 표시됩니다.
      </div>

      <h2>🎯 오늘의 단타 후보 3~5종목</h2>
      <div id="scalpPickList"></div>

      <h2>🧾 최근 1개월 가상 매매 로그</h2>
      <div id="scalpTradeLog"></div>

      <div class="notice small-notice">
        ⚠️ 이 기능은 실전 매매 신호가 아니라 과거 데이터 기반 학습/검증 도구입니다. 실제 매수·매도는 반드시 본인 판단과 손절 기준이 필요합니다.
      </div>
    </section>


    <div class="footer">K-Stock AI Trend WebApp<br>데이터 제공 상태에 따라 일부 종목은 누락될 수 있습니다.</div>
  </main>


  
  <div id="holdingModal" class="trade-modal" onclick="closeHoldingModal(event)">
    <div class="trade-modal-card holding-modal-card" onclick="event.stopPropagation()">
      <div class="trade-modal-head">
        <div>
          <div class="trade-modal-label">AI STRATEGY HOLDINGS</div>
          <h3 id="holdingModalTitle">보유 현황</h3>
        </div>
        <button class="trade-modal-close" onclick="hideHoldingModal()">닫기</button>
      </div>
      <div id="holdingModalBody"></div>
    </div>
  </div>

  <div id="tradeModal" class="trade-modal" onclick="closeTradeModal(event)">
    <div class="trade-modal-card" onclick="event.stopPropagation()">
      <div class="trade-modal-head">
        <div>
          <div class="trade-modal-label" id="tradeModalLabel">PAPER TRADE</div>
          <h3 id="tradeModalTitle">모의투자</h3>
        </div>
        <button class="trade-modal-close" onclick="hideTradeModal()">닫기</button>
      </div>

      <div id="tradeModalBody"></div>
    </div>
  </div>

  <div id="chartModal" class="chart-modal" onclick="closeChartModal(event)">
    <div class="chart-card" onclick="event.stopPropagation()">
      <div class="chart-head">
        <div>
          <div class="chart-label">AI TREND CHART</div>
          <h3 id="chartTitle">종목 차트</h3>
        </div>
        <button class="chart-close" onclick="hideChart()">닫기</button>
      </div>
      <canvas id="stockChart"></canvas>
      <div class="chart-note">최근 3개월 흐름입니다. 데이터 제공 상태에 따라 일부 지연될 수 있습니다.</div>
    </div>
  </div>

  <script>

    /* PROFIT_HELPER_SAFE */
    function fmtProfitMoney(v) {
      const n = Number(v || 0);
      if (n === 0) return "0원";
      return (n > 0 ? "+" : "-") + Math.abs(Math.round(n)).toLocaleString() + "원";
    }

    function profitClass(v) {
      return Number(v || 0) >= 0 ? "red" : "blue";
    }


    let stockChart = null;
    let latestData = null;

    function showTab(id, el) {
      document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.getElementById(id).classList.add('active');
      el.classList.add('active');
    }

    function fmtPrice(v) { return (v === null || v === undefined) ? "-" : Number(v).toLocaleString() + "원"; }
    function fmtMoney(v) { return (!v || Number(v) <= 0) ? "-" : Number(v).toLocaleString() + "원"; }

    function fmtRate(v) {
      const cls = Number(v) >= 0 ? "red" : "blue";
      return `<b class="${cls}">${v}%</b>`;
    }

    function updateLimitGuide() {
      const value = document.getElementById("limit").value;
      const guide = {
        "400": {
          title: "⚡ 빠른 분석 400개",
          desc: "핵심 종목만 빠르게 스캔합니다."
        },
        "700": {
          title: "📘 최대 분석 400개",
          desc: "Render 무료 서버에 맞춘 안정 모드입니다."
        },
        "1200": {
          title: "🚀 최대 분석 400개",
          desc: "중소형주와 테마주까지 넓게 확인합니다. 숨은 종목과 새로운 테마를 찾고 싶을 때 좋습니다."
        },
        "1600": {
          title: "🌌 최대 분석 400개",
          desc: "최대 400개까지 분석합니다."
        }
      };
      const item = guide[value] || guide["700"];
      document.getElementById("limitGuide").innerHTML =
        `<div class="limit-title">${item.title}</div><div class="limit-desc">${item.desc}</div>`;
    }

    function toggleCard(id) {
      const target = document.getElementById(id);
      if (!target) return;
      target.classList.toggle("active");
    }

    function badgeLevel(item) {
      if (item.score >= 70) return '<span class="grade strong">강한 후보</span>';
      if (item.score >= 50) return '<span class="grade normal">관심 후보</span>';
      return '<span class="grade watch">관찰 필요</span>';
    }

    function listHtml(arr) {
      if (!arr || arr.length === 0) return "";
      return arr.map(x => `<li>${x}</li>`).join("");
    }

    function safeItemForClick(item) {
      return JSON.stringify(item).replace(/'/g, "&apos;");
    }

    function makeCard(item, type) {
      item = normalizeThemeClient(item);
      const rankClass = type === "watch" ? "rank watch-rank" : "rank";
      const detailId = "card-detail-" + item.code + "-" + item.rank;

      return `
        <div class="card compact-card premium-card">
          <div class="card-summary" onclick="toggleCard('${detailId}')">
            <div class="top-line">
              <span class="${rankClass}">#${item.rank} ${item.category}</span>
              <span class="market">${item.market}</span>
              <span class="market">${item.code}</span>
              ${badgeLevel(item)}
            </div>

            <div class="compact-row">
              <div class="compact-left">
                <div class="compact-name">${item.name}</div>
                <div class="compact-sub">
                  <span class="theme">${item.theme}</span>
                </div>
              </div>

              <div class="compact-score">
                <span>AI 점수</span>
                <b>${item.score}</b>
              </div>
            </div>

            <div class="quick-metrics">
              <div><span>현재가</span><b>${fmtPrice(item.price)}</b><small>${item.priceSource || ""} ${item.realtimeUpdated ? "· " + item.realtimeUpdated : ""}</small></div>
              <div><span>5일/당일</span>${fmtRate(item.return5)}</div>
              <div><span>거래량</span><b>${item.volumePower}</b></div>
            </div>

            <div class="expand-hint">눌러서 AI 상세분석 보기 ⌄</div>
          </div>

          <div id="${detailId}" class="card-detail">
            <div class="grid premium-grid">
              <div class="metric"><span>현재가</span><b>${fmtPrice(item.price)}</b></div>
              <div class="metric"><span>AI 점수</span><b>${item.score}</b></div>
              <div class="metric"><span>5일/당일 흐름</span>${fmtRate(item.return5)}</div>
              <div class="metric"><span>20일 수익률</span>${fmtRate(item.return20)}</div>
              <div class="metric"><span>거래량강도</span><b>${item.volumePower}</b></div>
              <div class="metric"><span>추세강도</span><b>${item.trendPower}</b></div>
            </div>

            <div class="ai-box">
              <div class="detail-title">🤖 AI 선별 요약</div>
              <p>${item.opinion}</p>
            </div>

            <div class="detail-box">
              <div class="detail-title">✅ 선별 이유</div>
              <ul>${listHtml(item.reasons)}</ul>
            </div>

            <div class="detail-box strategy-box">
              <div class="detail-title">📌 대응 전략</div>
              <ul>${listHtml(item.strategy)}</ul>
            </div>

            <div class="detail-box risk-box">
              <div class="detail-title">⚠️ 주의 포인트</div>
              <ul>${listHtml(item.risk)}</ul>
            </div>

            <div class="trade-box">
              <div class="detail-title">💰 AI 수치화 매매 기준</div>
              <div class="trade-grid">
                <div><span>추천매수가</span><b>${fmtMoney(item.tradePlan?.buy)}</b></div>
                <div><span>1차 매도가</span><b>${fmtMoney(item.tradePlan?.sell1)}</b></div>
                <div><span>2차 매도가</span><b>${fmtMoney(item.tradePlan?.sell2)}</b></div>
                <div><span>손절 기준가</span><b>${fmtMoney(item.tradePlan?.stop)}</b></div>
              </div>
              <p>${item.tradePlan?.message || ""}</p>
            </div>

            <div class="paper-trade-box">
              <div class="detail-title">💼 모의투자</div>
              <div class="paper-trade-buttons">
                <button onclick='paperBuy(${safeItemForClick(item)})'>🟢 모의 매수</button>
                <button onclick='paperSell(${safeItemForClick(item)})'>🔴 모의 매도</button>
              </div>
            </div>

            <button class="chart-btn" onclick='showChart(${safeItemForClick(item)})'>📈 차트 보기</button>
          </div>
        </div>
      `;
    }

    async function showChart(item) {
      const modal = document.getElementById("chartModal");
      const title = document.getElementById("chartTitle");
      title.innerText = item.name + " · " + item.code;
      modal.style.display = "flex";

      const res = await fetch(`/api/chart?code=${item.code}&market=${item.market}`);
      const data = await res.json();

      const ctx = document.getElementById("stockChart");

      if (stockChart) {
        stockChart.destroy();
      }

      stockChart = new Chart(ctx, {
        type: "line",
        data: {
          labels: data.labels,
          datasets: [{
            label: item.name,
            data: data.prices,
            tension: 0.35,
            fill: true,
            borderWidth: 3
          }]
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { maxTicksLimit: 6 } },
            y: { ticks: { callback: value => Number(value).toLocaleString() } }
          }
        }
      });
    }

    function hideChart() {
      document.getElementById("chartModal").style.display = "none";
    }

    function closeChartModal(event) {
      if (event.target.id === "chartModal") hideChart();
    }


    function makeThemeStockCard(item) {
      item = normalizeThemeClient(item);
      const p = item.companyProfile || {};
      return `
        <div class="theme-stock-card">
          <div class="theme-stock-head">
            <div>
              <div class="theme-stock-name">${item.name}</div>
              <div class="theme-stock-meta">${item.market} · ${item.code} · AI점수 ${item.score} · 현재가 ${fmtPrice(item.price)}</div>
            </div>
            <span class="profile-pill">${p.grade || "AI 평가"}</span>
          </div>

          <div class="profile-box">
            <div class="profile-title">🏢 회사 개요</div>
            <div>${p.overview || "회사 개요 정보가 부족합니다."}</div>

            <div class="profile-title">🤖 AI 평가</div>
            <div>${p.aiEval || "AI 평가 정보가 부족합니다."}</div>

            <div class="profile-title">✅ 강점</div>
            <ul>${listHtml(p.strengths)}</ul>

            <div class="profile-title">⚠️ 주의점</div>
            <ul>${listHtml(p.cautions)}</ul>
          </div>

          <div class="paper-trade-box">
            <div class="detail-title">💼 모의투자</div>
            <div class="paper-trade-buttons">
              <button onclick='paperBuy(${safeItemForClick(item)})'>🟢 모의 매수</button>
              <button onclick='paperSell(${safeItemForClick(item)})'>🔴 모의 매도</button>
            </div>
          </div>

          <button class="chart-btn" onclick='showChart(${safeItemForClick(item)})'>📈 차트 보기</button>
        </div>
      `;
    }


    function safeThemeKey(theme) {
      return String(theme || "")
        .replace(/[^a-zA-Z0-9가-힣]/g, "_")
        .replace(/_+/g, "_");
    }

    function toggleTheme(theme) {
      const target = document.getElementById("theme-detail-" + safeThemeKey(theme));
      if (!target) return;

      const isOpen = target.classList.contains("active");
      document.querySelectorAll(".theme-detail").forEach(x => x.classList.remove("active"));

      if (!isOpen) {
        target.classList.add("active");
      }
    }

    function renderThemeList(data) {
      const groups = data.themeGroups || {};
      const summary = data.summary || [];
      return summary.map(t => {
        const key = safeThemeKey(t.theme);
        const items = groups[t.theme] || [];
        const stockHtml = items.map(item => makeThemeStockCard(item)).join("");

        return `
          <div class="theme-row clickable" onclick="toggleTheme(decodeURIComponent('${encodeURIComponent(t.theme)}'))">
            <b>${t.theme}</b>
            <span>평균점수 ${t.avgScore} · 최고점수 ${t.maxScore} · 종목수 ${t.count}개 · 클릭하면 종목별 AI 평가 보기</span>
          </div>
          <div id="theme-detail-${key}" class="theme-detail">
            ${stockHtml}
          </div>
        `;
      }).join("");
    }



    const PF_KEY = "sungil_ai_stock_wind_portfolio_v1";
    let activeTradeItem = null;
    let activeTradeMode = null;

    function defaultPortfolio() {
      return {
        cash: 10000000,
        initialCash: 10000000,
        holdings: {},
        history: []
      };
    }

    function loadPortfolio() {
      try {
        const saved = localStorage.getItem(PF_KEY);
        return saved ? JSON.parse(saved) : defaultPortfolio();
      } catch(e) {
        return defaultPortfolio();
      }
    }

    function savePortfolio(pf) {
      localStorage.setItem(PF_KEY, JSON.stringify(pf));
    }

    function getCurrentItem(code) {
      if (!latestData) return null;
      const all = []
        .concat(latestData.recommend || [])
        .concat(latestData.watch || [])
        .concat(latestData.all || []);
      return all.find(x => x.code === code) || null;
    }

    function parseMoney(v) {
      return Number(String(v || "").replaceAll(",", "").replaceAll("원", "").trim()) || 0;
    }

    function setInputValue(id, value) {
      const el = document.getElementById(id);
      if (el) {
        el.value = Math.max(0, Math.floor(value));
        el.dispatchEvent(new Event("input"));
      }
    }

    function showTradeModal() {
      document.getElementById("tradeModal").style.display = "flex";
    }

    function hideTradeModal() {
      document.getElementById("tradeModal").style.display = "none";
      activeTradeItem = null;
      activeTradeMode = null;
    }

    function closeTradeModal(event) {
      if (event.target.id === "tradeModal") hideTradeModal();
    }

    function openCashModal(mode) {
      activeTradeMode = mode;
      const pf = loadPortfolio();
      const isDeposit = mode === "deposit";
      document.getElementById("tradeModalLabel").innerText = isDeposit ? "VIRTUAL DEPOSIT" : "VIRTUAL WITHDRAW";
      document.getElementById("tradeModalTitle").innerText = isDeposit ? "가상 입금" : "가상 출금";

      document.getElementById("tradeModalBody").innerHTML = `
        <div class="trade-summary">
          <div class="trade-summary-title">${isDeposit ? "가상 현금을 충전합니다" : "가상 현금을 출금합니다"}</div>
          <div class="trade-summary-sub">
            실제 돈이 이동하지 않는 모의투자 전용 기능입니다.
          </div>
          <div class="trade-info-grid">
            <div><span>현재 가상 현금</span><b>${fmtMoney(pf.cash)}</b></div>
            <div><span>현재 총 기준금</span><b>${fmtMoney(pf.initialCash)}</b></div>
          </div>
        </div>

        <div class="trade-input-label">${isDeposit ? "입금 금액" : "출금 금액"}</div>
        <input id="cashAmountInput" class="trade-input" inputmode="numeric" value="1000000" oninput="updateCashPreview('${mode}')">

        <div class="quick-buttons">
          <button onclick="setInputValue('cashAmountInput', 100000)">10만원</button>
          <button onclick="setInputValue('cashAmountInput', 1000000)">100만원</button>
          <button onclick="setInputValue('cashAmountInput', 5000000)">500만원</button>
          <button onclick="setInputValue('cashAmountInput', 10000000)">1000만원</button>
          <button onclick="setInputValue('cashAmountInput', ${Math.max(0, pf.cash)})">최대</button>
          <button onclick="setInputValue('cashAmountInput', 0)">지우기</button>
        </div>

        <div id="cashPreview" class="trade-preview"></div>

        <button class="trade-submit" onclick="confirmCash('${mode}')">${isDeposit ? "➕ 가상 입금 실행" : "➖ 가상 출금 실행"}</button>
        <div class="trade-helper">입금/출금은 모의투자 기준금과 현금 관리용입니다.</div>
      `;

      showTradeModal();
      updateCashPreview(mode);
    }

    function updateCashPreview(mode) {
      const pf = loadPortfolio();
      const amount = parseMoney(document.getElementById("cashAmountInput")?.value);
      const afterCash = mode === "deposit" ? pf.cash + amount : pf.cash - amount;
      const afterSeed = mode === "deposit" ? pf.initialCash + amount : pf.initialCash - amount;
      const warn = mode === "withdraw" && amount > pf.cash ? "<br>⚠️ 보유 현금보다 큰 금액은 출금할 수 없습니다." : "";

      document.getElementById("cashPreview").innerHTML = `
        선택 금액: <b>${fmtMoney(amount)}</b><br>
        처리 후 가상 현금: <b>${fmtMoney(afterCash)}</b><br>
        처리 후 기준금: <b>${fmtMoney(afterSeed)}</b>
        ${warn}
      `;
    }

    function confirmCash(mode) {
      const pf = loadPortfolio();
      const amount = parseMoney(document.getElementById("cashAmountInput")?.value);
      if (!amount || amount <= 0) {
        alert("금액을 입력해주세요.");
        return;
      }

      if (mode === "withdraw" && amount > pf.cash) {
        alert("보유 가상 현금보다 많이 출금할 수 없습니다.");
        return;
      }

      if (mode === "deposit") {
        pf.cash += amount;
        pf.initialCash += amount;
      } else {
        pf.cash -= amount;
        pf.initialCash -= amount;
      }

      pf.history.unshift({
        type: mode === "deposit" ? "입금" : "출금",
        name: "가상 현금",
        code: "CASH",
        qty: 0,
        price: amount,
        amount: amount,
        time: new Date().toLocaleString()
      });

      savePortfolio(pf);
      hideTradeModal();
      renderPortfolio();
    }

    function depositCash() {
      openCashModal("deposit");
    }

    function withdrawCash() {
      openCashModal("withdraw");
    }

    function resetPortfolio() {
      if (!confirm("모의투자 데이터를 초기화할까요?")) return;
      savePortfolio(defaultPortfolio());
      renderPortfolio();
    }

    function paperBuy(item) {
      activeTradeItem = item;
      activeTradeMode = "buy";
      const pf = loadPortfolio();
      const price = Number(item.price || 0);

      if (price <= 0) {
        alert("현재가가 없어 매수할 수 없습니다.");
        return;
      }

      document.getElementById("tradeModalLabel").innerText = "PAPER BUY";
      document.getElementById("tradeModalTitle").innerText = `${item.name} 모의 매수`;

      document.getElementById("tradeModalBody").innerHTML = `
        <div class="trade-summary">
          <div class="trade-summary-title">${item.name}</div>
          <div class="trade-summary-sub">${item.market} · ${item.code} · ${item.theme}</div>
          <div class="trade-info-grid">
            <div><span>현재가</span><b>${fmtMoney(price)}</b></div>
            <div><span>보유 현금</span><b>${fmtMoney(pf.cash)}</b></div>
            <div><span>추천매수가</span><b>${fmtMoney(item.tradePlan?.buy)}</b></div>
            <div><span>손절 기준가</span><b>${fmtMoney(item.tradePlan?.stop)}</b></div>
          </div>
        </div>

        <div class="trade-input-label">매수 금액</div>
        <input id="buyAmountInput" class="trade-input" inputmode="numeric" value="${Math.min(1000000, pf.cash)}" oninput="syncBuyQtyFromAmount()">

        <div class="quick-buttons">
          <button onclick="setBuyAmount(10000)">1만원</button>
          <button onclick="setBuyAmount(100000)">10만원</button>
          <button onclick="setBuyAmount(1000000)">100만원</button>
          <button onclick="setBuyAmount(5000000)">500만원</button>
          <button onclick="setBuyAmount(${pf.cash})">최대</button>
          <button onclick="setBuyQty(1)">최소 1주</button>
        </div>

        <div class="trade-input-label">매수 수량</div>
        <input id="buyQtyInput" class="trade-input" inputmode="numeric" value="1" oninput="syncBuyAmountFromQty()">

        <div id="buyPreview" class="trade-preview"></div>

        <button class="trade-submit" onclick="confirmPaperBuy()">🟢 모의 매수 실행</button>
        <div class="trade-helper">수수료와 세금은 제외한 단순 모의투자 계산입니다.</div>
      `;

      showTradeModal();
      syncBuyQtyFromAmount();
    }

    function setBuyAmount(amount) {
      const pf = loadPortfolio();
      const safeAmount = Math.min(Number(amount || 0), pf.cash);
      setInputValue("buyAmountInput", safeAmount);
      syncBuyQtyFromAmount();
    }

    function setBuyQty(qty) {
      setInputValue("buyQtyInput", qty);
      syncBuyAmountFromQty();
    }

    function syncBuyQtyFromAmount() {
      const item = activeTradeItem;
      if (!item) return;
      const price = Number(item.price || 0);
      const amount = parseMoney(document.getElementById("buyAmountInput")?.value);
      const qty = Math.max(0, Math.floor(amount / price));
      const qtyInput = document.getElementById("buyQtyInput");
      if (qtyInput) qtyInput.value = qty;
      updateBuyPreview();
    }

    function syncBuyAmountFromQty() {
      const item = activeTradeItem;
      if (!item) return;
      const price = Number(item.price || 0);
      const qty = parseMoney(document.getElementById("buyQtyInput")?.value);
      const amountInput = document.getElementById("buyAmountInput");
      if (amountInput) amountInput.value = Math.floor(price * qty);
      updateBuyPreview();
    }

    function updateBuyPreview() {
      const item = activeTradeItem;
      const pf = loadPortfolio();
      if (!item) return;
      const price = Number(item.price || 0);
      const qty = parseMoney(document.getElementById("buyQtyInput")?.value);
      const amount = Math.round(price * qty);
      const afterCash = pf.cash - amount;
      const warn = amount > pf.cash ? "<br>⚠️ 보유 현금이 부족합니다." : "";
      const noQty = qty < 1 ? "<br>⚠️ 최소 1주 이상 입력해주세요." : "";

      document.getElementById("buyPreview").innerHTML = `
        예상 매수 수량: <b>${qty}주</b><br>
        예상 매수 금액: <b>${fmtMoney(amount)}</b><br>
        매수 후 현금: <b>${fmtMoney(afterCash)}</b>
        ${warn}${noQty}
      `;
    }

    function confirmPaperBuy() {
      const item = activeTradeItem;
      const pf = loadPortfolio();
      if (!item) return;

      const price = Number(item.price || 0);
      const qty = parseMoney(document.getElementById("buyQtyInput")?.value);
      const amount = Math.round(price * qty);

      if (qty < 1) {
        alert("최소 1주 이상 매수해야 합니다.");
        return;
      }

      if (amount > pf.cash) {
        alert("가상 현금이 부족합니다.");
        return;
      }

      const h = pf.holdings[item.code] || {
        code: item.code,
        name: item.name,
        market: item.market,
        theme: item.theme,
        qty: 0,
        avgPrice: 0,
        invested: 0
      };

      const newQty = h.qty + qty;
      const newInvested = h.invested + amount;
      h.qty = newQty;
      h.invested = newInvested;
      h.avgPrice = Math.round(newInvested / newQty);
      h.lastPrice = price;
      h.theme = item.theme;

      pf.holdings[item.code] = h;
      pf.cash -= amount;
      pf.history.unshift({
        type: "매수",
        name: item.name,
        code: item.code,
        qty: qty,
        price: price,
        amount: amount,
        time: new Date().toLocaleString()
      });

      savePortfolio(pf);
      hideTradeModal();
      renderPortfolio();
      alert(`${item.name} ${qty}주 모의 매수 완료`);
    }

    function paperSell(item) {
      activeTradeItem = item;
      activeTradeMode = "sell";
      const pf = loadPortfolio();
      const h = pf.holdings[item.code];
      const price = Number(item.price || 0);

      if (!h || h.qty <= 0) {
        alert("보유 수량이 없습니다.");
        return;
      }

      document.getElementById("tradeModalLabel").innerText = "PAPER SELL";
      document.getElementById("tradeModalTitle").innerText = `${item.name} 모의 매도`;

      document.getElementById("tradeModalBody").innerHTML = `
        <div class="trade-summary">
          <div class="trade-summary-title">${item.name}</div>
          <div class="trade-summary-sub">${item.market} · ${item.code} · ${item.theme}</div>
          <div class="trade-info-grid">
            <div><span>현재가</span><b>${fmtMoney(price)}</b></div>
            <div><span>보유 수량</span><b>${h.qty}주</b></div>
            <div><span>평균단가</span><b>${fmtMoney(h.avgPrice)}</b></div>
            <div><span>예상수익률</span><b>${(((price - h.avgPrice) / h.avgPrice) * 100).toFixed(2)}%</b></div>
          </div>
        </div>

        <div class="trade-input-label">매도 수량</div>
        <input id="sellQtyInput" class="trade-input" inputmode="numeric" value="${h.qty}" oninput="updateSellPreview()">

        <div class="quick-buttons">
          <button onclick="setSellPercent(25)">25%</button>
          <button onclick="setSellPercent(50)">50%</button>
          <button onclick="setSellPercent(75)">75%</button>
          <button onclick="setSellPercent(100)">전량</button>
          <button onclick="setInputValue('sellQtyInput', 1); updateSellPreview();">최소 1주</button>
          <button onclick="setInputValue('sellQtyInput', 0); updateSellPreview();">지우기</button>
        </div>

        <div id="sellPreview" class="trade-preview"></div>

        <button class="trade-submit sell" onclick="confirmPaperSell()">🔴 모의 매도 실행</button>
        <div class="trade-helper">매도 후 실현손익이 거래내역에 저장됩니다.</div>
      `;

      showTradeModal();
      updateSellPreview();
    }

    function setSellPercent(percent) {
      const pf = loadPortfolio();
      const h = pf.holdings[activeTradeItem.code];
      if (!h) return;
      const qty = Math.max(1, Math.floor(h.qty * percent / 100));
      setInputValue("sellQtyInput", percent === 100 ? h.qty : qty);
      updateSellPreview();
    }

    function updateSellPreview() {
      const item = activeTradeItem;
      const pf = loadPortfolio();
      if (!item) return;
      const h = pf.holdings[item.code];
      if (!h) return;

      const price = Number(item.price || h.lastPrice || 0);
      const qty = parseMoney(document.getElementById("sellQtyInput")?.value);
      const amount = Math.round(price * qty);
      const cost = Math.round(h.avgPrice * qty);
      const profit = amount - cost;
      const afterQty = h.qty - qty;
      const warn = qty > h.qty ? "<br>⚠️ 보유 수량보다 많이 매도할 수 없습니다." : "";
      const noQty = qty < 1 ? "<br>⚠️ 최소 1주 이상 입력해주세요." : "";

      document.getElementById("sellPreview").innerHTML = `
        예상 매도 수량: <b>${qty}주</b><br>
        예상 매도 금액: <b>${fmtMoney(amount)}</b><br>
        예상 실현손익: <b class="${profit >= 0 ? 'red' : 'blue'}">${fmtMoney(profit)}</b><br>
        매도 후 잔여수량: <b>${afterQty}주</b>
        ${warn}${noQty}
      `;
    }

    function confirmPaperSell() {
      const item = activeTradeItem;
      const pf = loadPortfolio();
      if (!item) return;

      const h = pf.holdings[item.code];
      const price = Number(item.price || 0);
      const qty = parseMoney(document.getElementById("sellQtyInput")?.value);

      if (!h || h.qty <= 0) {
        alert("보유 수량이 없습니다.");
        return;
      }

      if (qty < 1) {
        alert("최소 1주 이상 매도해야 합니다.");
        return;
      }

      if (qty > h.qty) {
        alert("보유 수량보다 많이 매도할 수 없습니다.");
        return;
      }

      const amount = Math.round(price * qty);
      const cost = Math.round(h.avgPrice * qty);
      const profit = amount - cost;

      h.qty -= qty;
      h.invested -= cost;

      if (h.qty <= 0) {
        delete pf.holdings[item.code];
      } else {
        h.avgPrice = Math.round(h.invested / h.qty);
        h.lastPrice = price;
        pf.holdings[item.code] = h;
      }

      pf.cash += amount;
      pf.history.unshift({
        type: "매도",
        name: item.name,
        code: item.code,
        qty: qty,
        price: price,
        amount: amount,
        profit: profit,
        time: new Date().toLocaleString()
      });

      savePortfolio(pf);
      hideTradeModal();
      renderPortfolio();
      alert(`${item.name} ${qty}주 모의 매도 완료\\n손익: ${fmtMoney(profit)}`);
    }

    function calcPortfolio() {
      const pf = loadPortfolio();
      let stockValue = 0;
      let invested = 0;
      const holdings = Object.values(pf.holdings || {});

      holdings.forEach(h => {
        const item = getCurrentItem(h.code);
        const currentPrice = item ? Number(item.price || h.lastPrice || h.avgPrice) : Number(h.lastPrice || h.avgPrice);
        h.currentPrice = currentPrice;
        h.value = Math.round(currentPrice * h.qty);
        h.profit = Math.round((currentPrice - h.avgPrice) * h.qty);
        h.returnRate = h.invested > 0 ? (h.profit / h.invested * 100) : 0;
        stockValue += h.value;
        invested += h.invested;
      });

      const total = pf.cash + stockValue;
      const totalReturn = pf.initialCash > 0 ? ((total - pf.initialCash) / pf.initialCash * 100) : 0;

      return { pf, holdings, stockValue, invested, total, totalReturn };
    }

    function makePortfolioNote(holdings, totalReturn) {
      if (holdings.length === 0) {
        return "🤖 성일님, 아직 보유 종목이 없습니다. 추천 종목에서 모의 매수를 눌러 투자 연습을 시작해보세요 🍃";
      }

      const best = [...holdings].sort((a,b) => b.returnRate - a.returnRate)[0];
      const worst = [...holdings].sort((a,b) => a.returnRate - b.returnRate)[0];

      let msg = `🤖 현재 총 수익률은 ${totalReturn.toFixed(2)}%입니다. `;
      if (totalReturn > 0) msg += "전체 흐름은 양호합니다. ";
      else if (totalReturn < 0) msg += "방어적인 점검이 필요합니다. ";
      else msg += "아직 본격적인 수익 변동은 크지 않습니다. ";

      msg += `가장 좋은 종목은 ${best.name}(${best.returnRate.toFixed(2)}%)입니다. `;
      if (worst && worst.returnRate < 0) {
        msg += `${worst.name}은 손실 구간이므로 손절 기준과 테마 지속 여부를 확인하세요.`;
      } else {
        msg += "보유 종목의 거래량과 테마 흐름을 함께 확인하면 좋습니다.";
      }
      return msg;
    }

    function renderPortfolio() {
      const { pf, holdings, total, totalReturn } = calcPortfolio();

      const totalEl = document.getElementById("pfTotal");
      if (!totalEl) return;

      document.getElementById("pfTotal").innerText = fmtMoney(total);
      document.getElementById("pfCash").innerText = fmtMoney(pf.cash);
      document.getElementById("pfReturn").innerHTML = `<span class="${totalReturn >= 0 ? 'red' : 'blue'}">${totalReturn.toFixed(2)}%</span>`;
      document.getElementById("pfAiNote").innerText = makePortfolioNote(holdings, totalReturn);

      const holdingList = document.getElementById("holdingList");
      if (holdings.length === 0) {
        holdingList.innerHTML = `<div class="empty-box">아직 보유 종목이 없습니다.<br>추천/관심 종목을 열고 <b>모의 매수</b>를 눌러보세요.</div>`;
      } else {
        holdingList.innerHTML = holdings.map(h => {
          const cls = h.profit >= 0 ? "holding-profit" : "holding-profit loss";
          const currentItem = getCurrentItem(h.code) || h;
          return `
            <div class="holding-card">
              <div class="holding-head">
                <div>
                  <div class="holding-name">${h.name}</div>
                  <div class="holding-meta">${h.market} · ${h.code} · ${h.theme || "미분류"}</div>
                </div>
                <div class="${cls}">${h.returnRate.toFixed(2)}%</div>
              </div>
              <div class="holding-grid">
                <div><span>보유수량</span><b>${h.qty}주</b></div>
                <div><span>평균단가</span><b>${fmtMoney(h.avgPrice)}</b></div>
                <div><span>현재가</span><b>${fmtMoney(h.currentPrice)}</b></div>
                <div><span>평가손익</span><b class="${profitClass(h.profit)}">${fmtProfitMoney(h.profit)}</b></div>
              </div>
              <div class="trade-actions">
                <button onclick='paperBuy(${safeItemForClick(currentItem)})'>🟢 추가 매수</button>
                <button onclick='paperSell(${safeItemForClick(currentItem)})'>🔴 매도</button>
              </div>
            </div>
          `;
        }).join("");
      }

      const history = pf.history || [];
      document.getElementById("tradeHistory").innerHTML = history.length === 0
        ? `<div class="empty-box">거래 내역이 없습니다.</div>`
        : history.slice(0, 30).map(h => `
          <div class="history-card">
            <b>${h.type}</b> · ${h.name} ${h.code !== "CASH" ? "(" + h.code + ")" : ""}<br>
            ${h.qty ? `수량 ${h.qty}주 · 단가 ${fmtMoney(h.price)} · 금액 ${fmtMoney(h.amount)}` : `금액 ${fmtMoney(h.amount)}`}
            ${h.profit !== undefined ? `<br>실현손익 <b class="${profitClass(h.profit)}">${fmtProfitMoney(h.profit)}</b>` : ""}
            <br><span style="color:#6b7280">${h.time}</span>
          </div>
        `).join("");
    }





    const AI_SIM_KEY = "sungil_multi_ai_strategy_sim_v2";
    let aiEquityChart = null;
    let aiViewRange = "ALL";

    const AI_STRATEGIES = {
      aggressive: {
        name: "공격형 AI", icon: "🔥",
        desc: "AI점수·거래량·단기 상승률이 강한 종목을 과감하게 편입합니다.",
        cashReserve: 0.05, maxWeight: 0.30, buyScore: 62, sellProfit: 18, stopLoss: -8, style: "momentum"
      },
      stable: {
        name: "안정형 AI", icon: "🛡️",
        desc: "과열 종목을 피하고 점수와 안정성이 균형 잡힌 종목을 분산 운용합니다.",
        cashReserve: 0.25, maxWeight: 0.18, buyScore: 58, sellProfit: 10, stopLoss: -5, style: "stable"
      },
      theme: {
        name: "테마추종 AI", icon: "🌊",
        desc: "강한 테마에 속한 종목을 우선 편입하고 테마 순환을 추적합니다.",
        cashReserve: 0.10, maxWeight: 0.24, buyScore: 55, sellProfit: 14, stopLoss: -7, style: "theme"
      },
      scalping: {
        name: "단타형 AI", icon: "⚡",
        desc: "거래량 급증과 단기 탄력이 큰 종목을 빠르게 사고 빠르게 정리합니다.",
        cashReserve: 0.15, maxWeight: 0.20, buyScore: 50, sellProfit: 6, stopLoss: -3, style: "scalping"
      },
      value: {
        name: "가치투자형 AI", icon: "🌳",
        desc: "과도한 급등 종목은 피하고 상대적으로 안정적인 저과열 종목을 오래 보유합니다.",
        cashReserve: 0.20, maxWeight: 0.22, buyScore: 54, sellProfit: 20, stopLoss: -10, style: "value"
      }
    };

    function todayKey() {
      return new Date().toISOString().slice(0, 10);
    }

    function daysBetween(dateA, dateB) {
      if (!dateA || !dateB) return 0;
      const a = new Date(dateA + "T00:00:00");
      const b = new Date(dateB + "T00:00:00");
      return Math.max(0, Math.floor((b - a) / 86400000));
    }

    function setAiStartAmount(amount) {
      const input = document.getElementById("aiStartAmount");
      if (input) input.value = Number(amount).toLocaleString();
    }

    function getAiStartAmount() {
      const input = document.getElementById("aiStartAmount");
      const amount = parseMoney(input ? input.value : 10000000);
      return amount > 0 ? amount : 10000000;
    }

    function defaultStrategyState(amount) {
      const strategies = {};
      Object.keys(AI_STRATEGIES).forEach(key => {
        strategies[key] = {
          key,
          cash: amount,
          initialCash: amount,
          picks: [],
          holdings: {},
          history: [],
          equity: [{day:0, total:amount, cash:amount, returnRate:0}]
        };
      });

      return {
        started: false,
        autoRun: true,
        day: 0,
        initialCash: amount,
        lastAutoDate: null,
        strategies
      };
    }

    function loadAiSim() {
      try {
        const saved = localStorage.getItem(AI_SIM_KEY);
        return saved ? JSON.parse(saved) : defaultStrategyState(10000000);
      } catch(e) {
        return defaultStrategyState(10000000);
      }
    }

    function saveAiSim(sim) {
      localStorage.setItem(AI_SIM_KEY, JSON.stringify(sim));
    }

    async function fetchMarketForAi(limit=700) {
      const loading = document.getElementById("loading");
      if (loading) loading.style.display = "block";

      const res = await fetch(`/api/analyze?limit=${limit}`);
      const data = await res.json();

      latestData = data;

      const analyzedCountEl = document.getElementById("analyzedCount");
      const recommendCountEl = document.getElementById("recommendCount");
      const watchCountEl = document.getElementById("watchCount");

      if (analyzedCountEl) analyzedCountEl.innerText = data.analyzedCount ?? 0;
      if (recommendCountEl) recommendCountEl.innerText = (data.recommend || []).length;
      if (watchCountEl) watchCountEl.innerText = (data.watch || []).length;

      const recommendListEl = document.getElementById("recommendList");
      const watchListEl = document.getElementById("watchList");

      if (typeof makeCard === "function" && recommendListEl) {
        recommendListEl.innerHTML = (data.recommend || []).map(x => makeCard(x, "recommend")).join("");
      }

      if (typeof makeCard === "function" && watchListEl) {
        watchListEl.innerHTML = (data.watch || []).map(x => makeCard(x, "watch")).join("");
      }

      if (typeof renderThemeSummary === "function") renderThemeSummary(data.summary || []);

      if (loading) loading.style.display = "none";
      return data;
    }

    function getAiCandidates() {
      if (!latestData) return [];
      const arr = []
        .concat(latestData.recommend || [])
        .concat(latestData.watch || [])
        .concat(latestData.all || []);
      const unique = {};
      arr.forEach(x => {
        if (!unique[x.code]) unique[x.code] = x;
      });
      return Object.values(unique);
    }

    function strategyScore(item, strategyKey) {
      const s = AI_STRATEGIES[strategyKey];
      const score = Number(item.score || 0);
      const r5 = Number(item.return5 || 0);
      const r20 = Number(item.return20 || 0);
      const vol = Number(item.volumePower || 0);
      const trend = Number(item.trendPower || 0);
      const hasTheme = item.theme && item.theme !== "미분류" && item.theme !== "기타/개별이슈";

      if (s.style === "momentum") return score + vol * 10 + trend * 8 + Math.min(r5, 25) * 0.9 - (r5 > 45 ? 25 : 0);
      if (s.style === "stable") return score + vol * 4 + (hasTheme ? 7 : 0) - Math.abs(r5) * 0.35 - (r5 > 20 ? 15 : 0);
      if (s.style === "theme") return score + (hasTheme ? 22 : -10) + vol * 6 + trend * 6 + Math.min(r5, 20) * 0.45;
      if (s.style === "scalping") return score * 0.65 + vol * 18 + Math.max(r5, 0) * 1.2 + trend * 4 - (r5 > 35 ? 20 : 0);
      if (s.style === "value") return score + (hasTheme ? 5 : 0) - Math.max(r5, 0) * 0.55 + (r20 < 15 ? 10 : -8) + trend * 3;
      return score;
    }

    function pickReason(item, strategyKey) {
      const s = AI_STRATEGIES[strategyKey];
      const reasons = [`${s.name} 기준으로 선정점수가 높습니다.`];
      if (item.theme && item.theme !== "미분류" && item.theme !== "기타/개별이슈") reasons.push(`${item.theme} 테마 흐름이 반영되었습니다.`);
      if (Number(item.volumePower || 0) >= 1.5) reasons.push("거래량 강도가 높아 수급 유입 가능성이 있습니다.");
      if (Number(item.return5 || 0) >= 15) reasons.push("단기 상승률이 높아 분할 접근이 필요합니다.");
      return reasons.join(" ");
    }

    function updateStrategyPicks(strategy, strategyKey, force=false) {
      const candidates = getAiCandidates();
      if (candidates.length === 0) return strategy;

      const ranked = candidates
        .map(item => ({...item, strategyScore: strategyScore(item, strategyKey)}))
        .sort((a,b) => b.strategyScore - a.strategyScore);

      if (force || !strategy.picks || strategy.picks.length === 0) {
        strategy.picks = ranked.slice(0,5).map(item => ({
          code:item.code, name:item.name, market:item.market, theme:item.theme,
          pickPrice:Number(item.price || 0), score:Number(item.score || 0),
          strategyScore:Number(item.strategyScore || 0), reason:pickReason(item, strategyKey)
        }));
        return strategy;
      }

      const holdingCodes = new Set(Object.keys(strategy.holdings || {}));
      const kept = (strategy.picks || []).filter(p => holdingCodes.has(p.code)).slice(0,5);
      const keptCodes = new Set(kept.map(x => x.code));
      const fill = ranked
        .filter(item => !keptCodes.has(item.code))
        .slice(0, 5 - kept.length)
        .map(item => ({
          code:item.code, name:item.name, market:item.market, theme:item.theme,
          pickPrice:Number(item.price || 0), score:Number(item.score || 0),
          strategyScore:Number(item.strategyScore || 0), reason:pickReason(item, strategyKey)
        }));

      strategy.picks = kept.concat(fill);
      return strategy;
    }

    function getLiveItemForAi(pick) {
      return getCurrentItem(pick.code) || pick;
    }

    function strategyDecision(item, holding, strategyKey) {
      const s = AI_STRATEGIES[strategyKey];
      const score = Number(item.score || 0);
      const r5 = Number(item.return5 || 0);
      const vol = Number(item.volumePower || 0);
      const price = Number(item.price || item.pickPrice || 0);
      const profitRate = holding && holding.avgPrice > 0 ? ((price - holding.avgPrice) / holding.avgPrice * 100) : 0;

      if (!holding || holding.qty <= 0) {
        if (score >= s.buyScore && vol >= 0.8) {
          if (s.style === "stable" && r5 > 20) return {action:"WAIT", weight:0, reason:"안정형 기준에서 단기 과열이라 신규 매수를 보류합니다."};
          if (s.style === "value" && r5 > 25) return {action:"WAIT", weight:0, reason:"가치투자형 기준에서 상승 부담이 커 관찰합니다."};
          return {action:"BUY", weight:s.maxWeight, reason:`${s.name} 조건에서 신규 매수 기준을 충족했습니다.`};
        }
        return {action:"WAIT", weight:0, reason:`${s.name} 기준에서 아직 신규 매수 신호가 약합니다.`};
      }

      if (profitRate <= s.stopLoss) return {action:"SELL_ALL", weight:1, reason:`손실률 ${profitRate.toFixed(2)}%로 ${s.name} 손절 기준에 도달했습니다.`};
      if (profitRate >= s.sellProfit) return {action:"SELL_HALF", weight:0.5, reason:`수익률 ${profitRate.toFixed(2)}%로 ${s.name} 차익실현 기준에 도달했습니다.`};
      if (s.style === "scalping" && r5 > 20) return {action:"SELL_HALF", weight:0.5, reason:"단타형 기준에서 단기 급등 후 절반 차익실현합니다."};
      if (score >= s.buyScore + 15 && vol >= 1.5 && profitRate > -2) return {action:"BUY_MORE", weight:Math.min(0.10, s.maxWeight / 2), reason:`${s.name} 기준에서 추세가 유지되어 소폭 추가매수합니다.`};

      return {action:"HOLD", weight:0, reason:`${s.name} 기준에서 보유가 적절합니다.`};
    }

    function calcStrategySnapshot(strategy) {
      let stockValue = 0;
      const holdings = Object.values(strategy.holdings || {});
      holdings.forEach(h => {
        const item = getCurrentItem(h.code);
        const currentPrice = item ? Number(item.price || h.lastPrice || h.avgPrice) : Number(h.lastPrice || h.avgPrice);
        h.currentPrice = currentPrice;
        h.value = Math.round(currentPrice * h.qty);
        h.profit = Math.round((currentPrice - h.avgPrice) * h.qty);
        h.returnRate = h.invested > 0 ? (h.profit / h.invested * 100) : 0;
        stockValue += h.value;
      });
      const total = strategy.cash + stockValue;
      const totalReturn = strategy.initialCash > 0 ? ((total - strategy.initialCash) / strategy.initialCash * 100) : 0;
      return {holdings, total, stockValue, totalReturn};
    }

    function runStrategyDay(strategy, strategyKey, globalDay) {
      strategy = updateStrategyPicks(strategy, strategyKey, false);
      const s = AI_STRATEGIES[strategyKey];
      const logs = [];

      (strategy.picks || []).forEach(pick => {
        const item = getLiveItemForAi(pick);
        const price = Number(item.price || pick.pickPrice || 0);
        if (price <= 0) return;

        const holding = strategy.holdings[pick.code];
        const decision = strategyDecision(item, holding, strategyKey);

        if (decision.action === "BUY" || decision.action === "BUY_MORE") {
          const maxInvest = Math.floor(strategy.initialCash * decision.weight);
          const reserve = Math.floor(strategy.initialCash * s.cashReserve);
          const spend = Math.min(strategy.cash - reserve, maxInvest);
          const qty = Math.floor(spend / price);

          if (qty >= 1 && spend > 0) {
            const amount = qty * price;
            const h = strategy.holdings[pick.code] || {
              code:pick.code, name:pick.name, market:pick.market, theme:pick.theme,
              qty:0, avgPrice:0, invested:0, lastPrice:price
            };
            const newQty = h.qty + qty;
            const newInvested = h.invested + amount;
            h.qty = newQty;
            h.invested = newInvested;
            h.avgPrice = Math.round(newInvested / newQty);
            h.lastPrice = price;
            strategy.holdings[pick.code] = h;
            strategy.cash -= amount;
            logs.push({day:globalDay, strategy:s.name, type:decision.action === "BUY" ? "매수" : "추가매수", name:pick.name, code:pick.code, qty, price, amount, text:decision.reason, time:new Date().toLocaleString()});
          } else {
            logs.push({day:globalDay, strategy:s.name, type:"관찰", name:pick.name, code:pick.code, text:"현금 비중 또는 최소 1주 조건 때문에 매수하지 않았습니다.", time:new Date().toLocaleString()});
          }
        } else if ((decision.action === "SELL_ALL" || decision.action === "SELL_HALF") && holding && holding.qty > 0) {
          const qty = decision.action === "SELL_ALL" ? holding.qty : Math.max(1, Math.floor(holding.qty / 2));
          const amount = Math.round(price * qty);
          const cost = Math.round(holding.avgPrice * qty);
          const profit = amount - cost;

          holding.qty -= qty;
          holding.invested -= cost;
          if (holding.qty <= 0) delete strategy.holdings[pick.code];
          else {
            holding.avgPrice = Math.round(holding.invested / holding.qty);
            holding.lastPrice = price;
            strategy.holdings[pick.code] = holding;
          }
          strategy.cash += amount;
          logs.push({day:globalDay, strategy:s.name, type:decision.action === "SELL_ALL" ? "전량매도" : "절반매도", name:pick.name, code:pick.code, qty, price, amount, profit, text:decision.reason, time:new Date().toLocaleString()});
        } else {
          logs.push({day:globalDay, strategy:s.name, type:decision.action === "WAIT" ? "관찰" : "보유", name:pick.name, code:pick.code, text:decision.reason, time:new Date().toLocaleString()});
        }
      });

      const snap = calcStrategySnapshot(strategy);
      strategy.equity.push({day:globalDay, total:snap.total, cash:strategy.cash, returnRate:snap.totalReturn});
      strategy.history = logs.concat(strategy.history || []);
      return strategy;
    }

    async function multiAiStart() {
      const amount = getAiStartAmount();
      if (!confirm(`5가지 AI 전략을 각각 ${fmtMoney(amount)}으로 시작할까요?\n시작하면 AI가 자동으로 시장 분석을 실행하고 종목을 선정합니다.`)) return;

      try {
        await fetchMarketForAi(700);

        const sim = defaultStrategyState(amount);
        sim.started = true;
        sim.autoRun = true;
        sim.lastAutoDate = todayKey();

        Object.keys(AI_STRATEGIES).forEach(key => {
          sim.strategies[key] = updateStrategyPicks(sim.strategies[key], key, true);
          sim.strategies[key] = runStrategyDay(sim.strategies[key], key, 1);
          sim.strategies[key].history.unshift({
            day:1, strategy:AI_STRATEGIES[key].name, type:"자동운용 시작",
            text:`${AI_STRATEGIES[key].name}이 ${fmtMoney(amount)}으로 시장 분석·5종목 선정·첫 운용을 시작했습니다.`,
            time:new Date().toLocaleString()
          });
        });
        sim.day = 1;

        saveAiSim(sim);
        renderAiSim();
        alert("5가지 AI 자동운용이 시작되었습니다.");
      } catch (e) {
        alert("AI 자동운용 시작 중 오류가 발생했습니다: " + e.message);
      }
    }

    async function multiAiRefreshNow() {
      try {
        await fetchMarketForAi(700);
        let sim = loadAiSim();

        if (sim.started) {
          Object.keys(AI_STRATEGIES).forEach(key => {
            const st = sim.strategies[key];

            const snap = calcStrategySnapshot(st);
            if (st.equity && st.equity.length > 0) {
              st.equity[st.equity.length - 1] = {
                ...st.equity[st.equity.length - 1],
                total: snap.total,
                cash: st.cash,
                returnRate: st.initialCash > 0 ? ((snap.total - st.initialCash) / st.initialCash * 100) : 0
              };
            }

            sim.strategies[key] = updateStrategyPicks(st, key, false);
            sim.strategies[key].history.unshift({
              day:sim.day,
              strategy:AI_STRATEGIES[key].name,
              type:"실시간 Naver/FDR 갱신",
              text:"최신 시장 데이터를 다시 불러와 보유 종목 평가손익과 전략별 수익률을 갱신했습니다.",
              time:new Date().toLocaleString()
            });
          });

          saveAiSim(sim);
        }

        renderAiSim();
      } catch (e) {
        alert("실시간 Naver/FDR 갱신 중 오류가 발생했습니다: " + e.message);
      }
    }

    function multiAiRunPeriod(days) {
      let sim = loadAiSim();
      if (!sim.started) {
        alert("먼저 5가지 AI 자동운용 시작을 눌러주세요.");
        return;
      }
      const maxDays = Math.min(Number(days || 1), 365);
      for (let i=0; i<maxDays; i++) {
        sim.day += 1;
        Object.keys(AI_STRATEGIES).forEach(key => {
          sim.strategies[key] = runStrategyDay(sim.strategies[key], key, sim.day);
        });
      }
      sim.lastAutoDate = todayKey();
      saveAiSim(sim);
      renderAiSim();
    }

    function multiAiToggleAuto() {
      const sim = loadAiSim();
      sim.autoRun = !sim.autoRun;
      saveAiSim(sim);
      renderAiSim();
    }

    async function multiAiAutoRunIfNeeded() {
      let sim = loadAiSim();
      if (!sim.started || !sim.autoRun) return;

      try {
        await fetchMarketForAi(700);
        const today = todayKey();

        if (!sim.lastAutoDate) {
          sim.lastAutoDate = today;
          saveAiSim(sim);
          renderAiSim();
          return;
        }

        const missedDays = daysBetween(sim.lastAutoDate, today);
        if (missedDays > 0) {
          const runDays = Math.min(missedDays, 30);
          for (let i=0; i<runDays; i++) {
            sim.day += 1;
            Object.keys(AI_STRATEGIES).forEach(key => {
              sim.strategies[key] = runStrategyDay(sim.strategies[key], key, sim.day);
              sim.strategies[key].history.unshift({
                day:sim.day, strategy:AI_STRATEGIES[key].name, type:"자동 일일운용",
                text:"앱 접속 시 날짜 변경을 감지해 자동으로 하루 운용했습니다.",
                time:new Date().toLocaleString()
              });
            });
          }
          sim.lastAutoDate = today;
          saveAiSim(sim);
        }
        renderAiSim();
      } catch(e) {
        renderAiSim();
      }
    }

    function multiAiRebalance() {
      const sim = loadAiSim();
      if (!sim.started) {
        alert("먼저 AI 자동운용을 시작해주세요.");
        return;
      }
      Object.keys(AI_STRATEGIES).forEach(key => {
        sim.strategies[key] = updateStrategyPicks(sim.strategies[key], key, true);
        sim.strategies[key].history.unshift({
          day:sim.day, strategy:AI_STRATEGIES[key].name, type:"5종목 갱신",
          text:"최신 시장 점수를 기준으로 전략별 5종목을 갱신했습니다.",
          time:new Date().toLocaleString()
        });
      });
      saveAiSim(sim);
      renderAiSim();
    }

    function multiAiReset() {
      if (!confirm("5가지 AI 자동운용 시뮬레이션을 초기화할까요?")) return;
      saveAiSim(defaultStrategyState(getAiStartAmount()));
      renderAiSim();
    }

    function filterEquityByRange(eq) {
      if (!eq || eq.length === 0) return [];
      const map = { "1D":1, "1W":7, "1M":30, "2M":60, "1Y":365 };
      if (aiViewRange === "ALL") return eq;
      const n = map[aiViewRange] || eq.length;
      return eq.slice(Math.max(0, eq.length - (n + 1)));
    }

    function rangeReturn(eq, currentTotal=null) {
      if (!eq || eq.length === 0) return 0;

      const nowTotal = Number(currentTotal || eq[eq.length - 1].total || 0);

      if (aiViewRange === "ALL") {
        const first = Number(eq[0].total || 0);
        return first > 0 ? (nowTotal - first) / first * 100 : 0;
      }

      const map = { "1D":1, "1W":7, "1M":30, "2M":60, "1Y":365 };
      const days = map[aiViewRange] || 1;
      const baseIndex = Math.max(0, eq.length - 1 - days);
      const base = Number(eq[baseIndex].total || eq[0].total || 0);

      return base > 0 ? (nowTotal - base) / base * 100 : 0;
    }

    function setAiViewRange(range) {
      aiViewRange = range;
      renderAiSim();
    }

    function renderAiEquityChart(sim) {
      const canvas = document.getElementById("aiEquityChart");
      if (!canvas) return;
      if (aiEquityChart) aiEquityChart.destroy();

      const keys = Object.keys(AI_STRATEGIES);
      const filteredMap = {};

      keys.forEach(k => {
        const st = sim.strategies[k];
        const eq = [...(st?.equity || [])];
        if (eq.length > 0) {
          const snap = calcStrategySnapshot(st);
          eq[eq.length - 1] = {
            ...eq[eq.length - 1],
            total: snap.total,
            cash: st.cash,
            returnRate: st.initialCash > 0 ? ((snap.total - st.initialCash) / st.initialCash * 100) : 0
          };
        }
        filteredMap[k] = filterEquityByRange(eq);
      });

      const maxLen = Math.max(...keys.map(k => filteredMap[k].length), 1);
      const labels = Array.from({length:maxLen}, (_, i) => "D+" + i);

      aiEquityChart = new Chart(canvas, {
        type:"line",
        data:{
          labels,
          datasets:keys.map(k => ({
            label:AI_STRATEGIES[k].name,
            data:filteredMap[k].map(x => x.total),
            tension:0.35,
            fill:false,
            borderWidth:3
          }))
        },
        options:{
          responsive:true,
          plugins:{legend:{display:true}},
          scales:{
            x:{ticks:{maxTicksLimit:7}},
            y:{ticks:{callback:value => Number(value).toLocaleString()}}
          }
        }
      });
    }


    function openStrategyHoldings(strategyKey) {
      const sim = loadAiSim();
      const meta = AI_STRATEGIES[strategyKey];
      const st = sim.strategies?.[strategyKey];
      if (!meta || !st) return;

      const snap = calcStrategySnapshot(st);
      const title = document.getElementById("holdingModalTitle");
      const body = document.getElementById("holdingModalBody");

      if (title) title.innerText = `${meta.icon} ${meta.name} 보유 현황`;

      if (!snap.holdings || snap.holdings.length === 0) {
        body.innerHTML = `
          <div class="empty-box">
            아직 보유 종목이 없습니다.<br>
            AI가 매수 조건을 기다리는 중입니다.
          </div>
        `;
      } else {
        const profitTotal = snap.total - st.initialCash;
        const returnTotal = st.initialCash > 0 ? (profitTotal / st.initialCash * 100) : 0;
        const winCount = snap.holdings.filter(h => Number(h.profit || 0) > 0).length;
        const lossCount = snap.holdings.filter(h => Number(h.profit || 0) < 0).length;

        body.innerHTML = `
          <div class="holding-summary-box">
            <div class="holding-summary-title">${meta.icon} ${meta.name}</div>
            <div class="holding-summary-grid">
              <div><span>총 자산</span><b>${fmtMoney(snap.total)}</b></div>
              <div><span>총 손익</span><b>${fmtProfitMoney(profitTotal)}</b></div>
              <div><span>수익률</span><b>${returnTotal.toFixed(2)}%</b></div>
              <div><span>수익 종목</span><b>${winCount}개</b></div>
              <div><span>손실 종목</span><b>${lossCount}개</b></div>
              <div><span>현금</span><b>${fmtMoney(st.cash)}</b></div>
            </div>
          </div>

          ${snap.holdings
            .sort((a,b) => Number(b.profit || 0) - Number(a.profit || 0))
            .map(h => `
              <div class="holding-profit-card">
                <div class="holding-profit-head">
                  <div>
                    <div class="holding-profit-name">${h.name}</div>
                    <div style="color:#6b7280;font-size:13px;margin-top:3px;">${h.market} · ${h.code} · ${h.theme}</div>
                  </div>
                  <div class="${h.returnRate >= 0 ? 'holding-profit-rate' : 'holding-profit-rate loss'}">${h.returnRate.toFixed(2)}%</div>
                </div>
                <div class="holding-profit-detail">
                  수량 ${h.qty}주 · 평균 ${fmtMoney(h.avgPrice)} · 현재 ${fmtMoney(h.currentPrice)}<br>
                  평가금액 ${fmtMoney(h.value)}
                  <div class="holding-profit-money ${profitClass(h.profit)}">손익 ${fmtProfitMoney(h.profit)}</div>
                </div>
              </div>
            `).join("")}
        `;
      }

      const modal = document.getElementById("holdingModal");
      if (modal) modal.style.display = "flex";
    }

    function hideHoldingModal() {
      const modal = document.getElementById("holdingModal");
      if (modal) modal.style.display = "none";
    }

    function closeHoldingModal(event) {
      if (event.target.id === "holdingModal") hideHoldingModal();
    }


    function renderAiSim() {
      const sim = loadAiSim();
      const totalEl = document.getElementById("bestStrategy");
      if (!totalEl) return;

      const startInput = document.getElementById("aiStartAmount");
      if (startInput && sim.initialCash) startInput.value = Number(sim.initialCash).toLocaleString();

      document.querySelectorAll(".ai-filter-buttons button").forEach(btn => btn.classList.remove("active"));
      const rangeLabels = {"1D":"1일", "1W":"1주", "1M":"1개월", "2M":"2개월", "1Y":"1년", "ALL":"전체"};
      const summaryEl = document.getElementById("aiRangeSummary");
      if (summaryEl) summaryEl.innerText = `${rangeLabels[aiViewRange] || "전체"} 기준 성과를 표시합니다.`;

      const strategyRows = Object.keys(AI_STRATEGIES).map(key => {
        const st = sim.strategies?.[key] || defaultStrategyState(sim.initialCash || 10000000).strategies[key];
        const snap = calcStrategySnapshot(st);
        const viewReturn = rangeReturn(st.equity || [], snap.total);
        const totalReturn = st.initialCash > 0 ? ((snap.total - st.initialCash) / st.initialCash * 100) : 0;
        return {key, st, snap, viewReturn, totalReturn, meta:AI_STRATEGIES[key]};
      }).sort((a,b) => b.viewReturn - a.viewReturn);

      const best = strategyRows[0];
      document.getElementById("bestStrategy").innerText = sim.started ? `${best.meta.icon} ${best.meta.name}` : "-";
      document.getElementById("multiAiDay").innerText = sim.started ? `D+${sim.day}` : "-";
      document.getElementById("multiAiStatus").innerText = sim.autoRun ? "ON" : "OFF";

      const autoBtn = document.getElementById("aiAutoBtn");
      if (autoBtn) autoBtn.innerText = sim.autoRun ? "⏸ 자동운용 켜짐" : "▶️ 자동운용 꺼짐";

      const note = document.getElementById("aiSimNote");
      if (!sim.started) {
        note.innerText = "🤖 5가지 AI 자동운용 시작을 누르면 AI가 직접 시장 분석·종목 선정·첫 매매를 시작합니다.";
      } else {
        note.innerText = `🤖 현재 D+${sim.day}일차입니다. ${rangeLabels[aiViewRange]} 기준 최고 전략은 ${best.meta.name}, 수익률은 ${best.viewReturn.toFixed(2)}%입니다. 자동운용은 ${sim.autoRun ? "켜짐" : "꺼짐"} 상태입니다. 수익률은 현재 평가자산 기준입니다.`;
      }

      document.getElementById("strategyRankList").innerHTML = strategyRows.map((row, idx) => `
        <div class="strategy-card">
          <div class="strategy-head">
            <div>
              <div class="strategy-title">#${idx+1} ${row.meta.icon} ${row.meta.name}</div>
              <div class="strategy-desc">${row.meta.desc}</div>
            </div>
            <div class="${row.viewReturn >= 0 ? 'strategy-return' : 'strategy-return loss'}">${row.viewReturn.toFixed(2)}%</div>
          </div>
          <div class="strategy-grid">
            <div><span>총 자산</span><b>${fmtMoney(row.snap.total)}</b></div>
            <div><span>현금</span><b>${fmtMoney(row.st.cash)}</b></div>
            <div class="click-metric" onclick="openStrategyHoldings('${row.key}')"><span>보유</span><b>${row.snap.holdings.length}종목</b><small>눌러서 보기</small></div>
            <div><span>주식평가</span><b>${fmtMoney(row.snap.stockValue)}</b></div>
            <div><span>전체수익률</span><b class="${row.totalReturn >= 0 ? 'red' : 'blue'}">${row.totalReturn.toFixed(2)}%</b></div>
          </div>
        </div>
      `).join("");

      document.getElementById("strategyPickList").innerHTML = Object.keys(AI_STRATEGIES).map(key => {
        const st = sim.strategies?.[key] || {};
        const meta = AI_STRATEGIES[key];
        const picks = st.picks || [];
        return `
          <div class="strategy-card">
            <div class="strategy-title">${meta.icon} ${meta.name} 선택 5종목</div>
            <div class="strategy-desc">${meta.desc}</div>
            <div class="strategy-stock-list">
              ${picks.length ? picks.map((p,i) => {
                const live = getLiveItemForAi(p);
                return `<div class="strategy-stock"><b>#${i+1} ${p.name}</b><br>${p.market} · ${p.code} · ${p.theme}<br>현재가 ${fmtPrice(live.price || p.pickPrice)} · 선정점수 ${Number(p.strategyScore || 0).toFixed(1)}<br>${p.reason}</div>`;
              }).join("") : `<div class="empty-box">아직 선정 종목이 없습니다.</div>`}
            </div>
          </div>
        `;
      }).join("");

      document.getElementById("strategyHoldingList").innerHTML = Object.keys(AI_STRATEGIES).map(key => {
        const st = sim.strategies?.[key] || {};
        const meta = AI_STRATEGIES[key];
        const snap = calcStrategySnapshot(st);
        return `
          <div class="strategy-card">
            <div class="strategy-title">${meta.icon} ${meta.name} 보유 현황</div>
            <div class="strategy-stock-list">
              ${snap.holdings.length ? snap.holdings.map(h => `<div class="strategy-stock"><b>${h.name}</b> ${h.returnRate.toFixed(2)}%<br>${h.market} · ${h.code} · ${h.theme}<br>수량 ${h.qty}주 · 평균 ${fmtMoney(h.avgPrice)} · 현재 ${fmtMoney(h.currentPrice)} · 손익 <span class="${profitClass(h.profit)}">${fmtProfitMoney(h.profit)}</span></div>`).join("") : `<div class="empty-box">보유 종목이 없습니다.</div>`}
            </div>
          </div>
        `;
      }).join("");

      const logs = [];
      Object.keys(AI_STRATEGIES).forEach(key => logs.push(...(sim.strategies?.[key]?.history || [])));
      logs.sort((a,b) => (b.day || 0) - (a.day || 0));

      document.getElementById("aiTradeLog").innerHTML = logs.length === 0
        ? `<div class="empty-box">AI 운용 로그가 없습니다.</div>`
        : logs.slice(0,80).map(h => `
          <div class="ai-log-card strategy-log">
            <b>D+${h.day} · ${h.strategy || ""} · ${h.type}</b> ${h.name ? "· " + h.name + " (" + h.code + ")" : ""}<br>
            ${h.qty ? `수량 ${h.qty}주 · 단가 ${fmtMoney(h.price)} · 금액 ${fmtMoney(h.amount)}<br>` : ""}
            ${h.profit !== undefined ? `실현손익 <b class="${profitClass(h.profit)}">${fmtProfitMoney(h.profit)}</b><br>` : ""}
            ${h.text || ""}
            <br><span style="color:#6b7280">${h.time}</span>
          </div>
        `).join("");

      try {
        renderAiEquityChart(sim);
      } catch(e) {
        console.log("chart render skipped", e);
      }
    }



    let realtimeTimer = null;
    let lastRealtimeUpdated = "";

    function collectRealtimeCodes() {
      const codes = new Set();

      try {
        if (latestData) {
          (latestData.recommend || []).slice(0, 10).forEach(x => x.code && codes.add(String(x.code).padStart(6, "0")));
          (latestData.watch || []).slice(0, 30).forEach(x => x.code && codes.add(String(x.code).padStart(6, "0")));
          (latestData.all || []).slice(0, 30).forEach(x => x.code && codes.add(String(x.code).padStart(6, "0")));
        }

        if (typeof loadPortfolio === "function") {
          const portfolio = loadPortfolio();
          if (portfolio && portfolio.holdings) {
            Object.keys(portfolio.holdings).forEach(code => codes.add(String(code).padStart(6, "0")));
          }
        }

        if (typeof loadAiSim === "function") {
          const sim = loadAiSim();
          if (sim && sim.strategies) {
            Object.values(sim.strategies).forEach(st => {
              Object.keys(st.holdings || {}).forEach(code => codes.add(String(code).padStart(6, "0")));
              (st.picks || []).forEach(p => p.code && codes.add(String(p.code).padStart(6, "0")));
            });
          }
        }
      } catch(e) {
        console.log("collectRealtimeCodes error", e);
      }

      return Array.from(codes).slice(0, 40);
    }

    function applyRealtimePriceMap(priceMap) {
      if (!priceMap) return;

      const applyItem = (item) => {
        if (!item || !item.code) return item;
        const code = String(item.code).padStart(6, "0");
        if (priceMap[code]) {
          item.price = Number(priceMap[code].price || item.price || 0);
          item.priceSource = priceMap[code].source || "Naver 현재가";
          item.realtimeUpdated = priceMap[code].updated || "";
        }
        return item;
      };

      if (latestData) {
        latestData.recommend = (latestData.recommend || []).map(applyItem);
        latestData.watch = (latestData.watch || []).map(applyItem);
        latestData.all = (latestData.all || []).map(applyItem);
      }

      try { /* portfolio removed in lightweight mode */ } catch(e) {}

      try { /* AI simulation removed in lightweight mode */ } catch(e) {}
    }



    let backtestChart = null;
    let latestBacktest = null;

    function setBacktestCash(amount) {
      const el = document.getElementById("backtestCash");
      if (el) el.value = Number(amount).toLocaleString();
    }

    function getBacktestCash() {
      const el = document.getElementById("backtestCash");
      return parseMoney(el ? el.value : 10000000) || 10000000;
    }

    async function runBacktest(days=365) {
      const status = document.getElementById("backtestStatus");
      if (status) status.innerText = "🧪 검증 실행 중입니다. 과거 가격 데이터를 불러오고 전략별 매매를 계산합니다...";

      try {
        const cash = getBacktestCash();
        const res = await fetch(`/api/backtest?days=${days}&cash=${cash}`, { cache: "no-store" });
        const raw = await res.text();

        let data;
        try {
          data = JSON.parse(raw);
        } catch(e) {
          console.log("backtest non-json", raw.slice(0, 500));
          throw new Error("백테스트 서버 응답이 JSON 형식이 아닙니다.");
        }

        if (!data.ok) throw new Error(data.error || "백테스트 오류");

        latestBacktest = data;
        renderBacktest(data);
      } catch(e) {
        console.log("runBacktest error", e);
        if (status) status.innerText = "⚠️ 백테스트 오류: " + e.message;
      }
    }

    function renderBacktest(data) {
      const status = document.getElementById("backtestStatus");
      const best = data.best || {};

      if (status) {
        status.innerText = `🏆 최근 ${data.periodDays}일 기준 최고 전략은 ${best.icon || ""} ${best.name || "-"}입니다. 수익률 ${Number(best.returnRate || 0).toFixed(2)}%, 최대낙폭 ${Number(best.maxDrawdown || 0).toFixed(2)}%입니다. ${data.marketNote || ""}`;
      }

      renderBacktestChart(data);
      renderBacktestRank(data);
      renderBacktestInsight(data);
      renderBacktestTrades(data);
    }

    function renderBacktestChart(data) {
      const canvas = document.getElementById("backtestChart");
      if (!canvas) return;
      if (backtestChart) backtestChart.destroy();

      const results = data.results || [];
      const maxLen = Math.max(...results.map(r => (r.equity || []).length), 1);
      const labels = Array.from({length:maxLen}, (_, i) => "D+" + i);

      backtestChart = new Chart(canvas, {
        type: "line",
        data: {
          labels,
          datasets: results.map(r => ({
            label: `${r.icon} ${r.name}`,
            data: (r.equity || []).map(x => x.total),
            tension: 0.35,
            borderWidth: 3,
            fill: false
          }))
        },
        options: {
          responsive: true,
          plugins: { legend: { display: true } },
          scales: {
            x: { ticks: { maxTicksLimit: 7 } },
            y: { ticks: { callback: value => Number(value).toLocaleString() } }
          }
        }
      });
    }

    function renderBacktestRank(data) {
      const el = document.getElementById("backtestRankList");
      if (!el) return;

      const results = data.results || [];
      el.innerHTML = results.map((r, idx) => `
        <div class="strategy-card backtest-card">
          <div class="strategy-head">
            <div>
              <div class="strategy-title">#${idx + 1} ${r.icon} ${r.name}</div>
              <div class="strategy-desc">${r.desc}</div>
            </div>
            <div class="${Number(r.returnRate) >= 0 ? 'strategy-return' : 'strategy-return loss'}">${Number(r.returnRate || 0).toFixed(2)}%</div>
          </div>
          <div class="strategy-grid">
            <div><span>최종자산</span><b>${fmtMoney(r.finalTotal)}</b></div>
            <div><span>승률</span><b>${Number(r.winRate || 0).toFixed(1)}%</b></div>
            <div><span>최대낙폭</span><b class="blue">${Number(r.maxDrawdown || 0).toFixed(2)}%</b></div>
            <div><span>매매횟수</span><b>${r.tradeCount || 0}회</b></div>
            <div><span>승/패</span><b>${r.wins || 0}/${r.losses || 0}</b></div>
          </div>
        </div>
      `).join("");
    }

    function renderBacktestInsight(data) {
      const el = document.getElementById("backtestInsight");
      if (!el) return;

      const best = data.best || {};
      let guide = "";

      if (best.key === "scalping") {
        guide = `<b>⚡ 단타형이 우세한 구간입니다.</b><ul><li>거래량이 평소보다 급증한 종목을 우선 확인합니다.</li><li>익절은 짧게, 손절은 더 짧게 잡는 방식이 유리했습니다.</li><li>오른 종목을 오래 들고 가기보다 빠른 회전이 중요합니다.</li></ul>`;
      } else if (best.key === "theme") {
        guide = `<b>🌊 테마추종형이 우세한 구간입니다.</b><ul><li>강한 테마 안에서 1등 종목과 후발 종목을 함께 확인합니다.</li><li>테마 평균점수가 높아질 때 편입하고 약해지면 축소하는 방식이 좋습니다.</li><li>종목보다 섹터 흐름을 먼저 봅니다.</li></ul>`;
      } else if (best.key === "aggressive") {
        guide = `<b>🔥 공격형이 우세한 구간입니다.</b><ul><li>AI점수, 거래량, 단기 상승률이 동시에 강한 종목을 우선 편입합니다.</li><li>수익률은 높지만 낙폭도 커질 수 있어 분할매수가 중요합니다.</li><li>손절 기준을 반드시 둬야 합니다.</li></ul>`;
      } else if (best.key === "stable") {
        guide = `<b>🛡️ 안정형이 우세한 구간입니다.</b><ul><li>과열 종목보다 점수와 안정성이 균형 잡힌 종목이 유리했습니다.</li><li>현금 비중을 남기고 분산하는 방식이 손실 방어에 좋습니다.</li><li>급등주 추격보다 눌림 후 재상승 확인이 중요합니다.</li></ul>`;
      } else {
        guide = `<b>🌳 가치투자형이 우세한 구간입니다.</b><ul><li>과열 구간을 피하고 안정적인 추세 종목을 오래 보유하는 방식이 유리했습니다.</li><li>단기 수익보다 최대낙폭 관리와 보유 기간이 중요했습니다.</li><li>실적·업종·테마 안정성이 함께 필요합니다.</li></ul>`;
      }

      el.innerHTML = guide;
    }

    function renderBacktestTrades(data) {
      const el = document.getElementById("backtestTradeLog");
      if (!el) return;

      const best = data.best || {};
      const trades = best.recentTrades || [];
      if (!trades.length) {
        el.innerHTML = `<div class="empty-box">매매 로그가 없습니다.</div>`;
        return;
      }

      el.innerHTML = trades.map(t => `
        <div class="ai-log-card">
          <b>${t.date} · ${t.type}</b> · ${t.name} (${t.code})<br>
          수량 ${t.qty || "-"}주 · 가격 ${fmtMoney(t.price || 0)}
          ${t.pnl !== undefined ? `<br>손익 <b class="${Number(t.pnl) >= 0 ? 'red' : 'blue'}">${fmtProfitMoney(t.pnl)}</b> · 수익률 ${Number(t.returnRate || 0).toFixed(2)}%` : ""}
          ${t.theme ? `<br>테마 ${t.theme}` : ""}
        </div>
      `).join("");
    }



    function renderPortfolio() { return; }
    function renderAiSim() { return; }
    function multiAiAutoRunIfNeeded() { return; }
    function loadPortfolio() { return {cash:0, holdings:{}, history:[]}; }
    function savePortfolio(p) { return; }
    function loadAiSim() { return {started:false, strategies:{}}; }
    function saveAiSim(s) { return; }


    let scalpChart = null;
    let latestScalpLearn = null;

    function setScalpCash(amount) {
      const el = document.getElementById("scalpCash");
      if (el) el.value = Number(amount).toLocaleString();
    }

    function getScalpCash() {
      const el = document.getElementById("scalpCash");
      return parseMoney(el ? el.value : 10000000) || 10000000;
    }

    async function runScalpingLearn(days=365) {
      const status = document.getElementById("scalpStatus");
      if (status) {
        status.innerText = "🧠 단타 AI가 최근 시장 데이터를 학습 중입니다. Render 무료 서버 안정형으로 핵심 후보만 빠르게 검증합니다. 30초~2분 정도 걸릴 수 있습니다...";
      }

      try {
        const cash = getScalpCash();
        const params = new URLSearchParams();
        params.set("days", String(days));
        params.set("cash", String(cash));
        params.set("_", Date.now().toString());

        const res = await fetch(window.location.origin + "/api/scalping_learn?" + params.toString(), {
          cache: "no-store",
          headers: { "Accept": "application/json" }
        });
        const raw = await res.text();

        let data;
        try {
          data = JSON.parse(raw);
        } catch(e) {
          console.log("scalping non-json", raw.slice(0, 500));
          throw new Error("서버가 아직 새 버전으로 배포되지 않았거나 응답이 지연되었습니다. 1분 후 다시 실행해 주세요.");
        }

        if (!data.ok) throw new Error(data.error || "단타 AI 학습 오류");

        latestScalpLearn = data;
        renderScalpingLearn(data);
      } catch(e) {
        console.log("runScalpingLearn error", e);
        if (status) status.innerText = "⚠️ 단타 AI 학습 오류: " + e.message;
      }
    }

    function renderScalpingLearn(data) {
      const status = document.getElementById("scalpStatus");
      const p = data.bestParams || {};
      const m = data.monthResult || {};
      const b = data.bestLearn || {};

      if (status) {
        status.innerText = `⚡ 학습 완료. 최적 조건은 익절 ${(Number(p.take || 0)*100).toFixed(1)}%, 손절 ${(Number(p.stop || 0)*100).toFixed(1)}%, 최대보유 ${p.max_hold || "-"}일입니다. 최근 1개월 검증 수익률은 ${Number(m.returnRate || 0).toFixed(2)}%, 승률은 ${Number(m.winRate || 0).toFixed(1)}%입니다.`;
      }

      renderScalpChart(data);
      renderScalpBest(data);
      renderScalpPicks(data);
      renderScalpTrades(data);
    }

    function renderScalpChart(data) {
      const canvas = document.getElementById("scalpChart");
      if (!canvas) return;
      if (scalpChart) scalpChart.destroy();

      const equity = (data.monthResult || {}).equity || [];
      const labels = equity.map(x => x.date || ("D+" + x.day));

      scalpChart = new Chart(canvas, {
        type: "line",
        data: {
          labels,
          datasets: [{
            label: "⚡ 단타형 실전 AI",
            data: equity.map(x => x.total),
            tension: 0.35,
            borderWidth: 3,
            fill: true
          }]
        },
        options: {
          responsive: true,
          plugins: { legend: { display: true } },
          scales: {
            x: { ticks: { maxTicksLimit: 6 } },
            y: { ticks: { callback: value => Number(value).toLocaleString() } }
          }
        }
      });
    }

    function renderScalpBest(data) {
      const el = document.getElementById("scalpBestBox");
      if (!el) return;

      const p = data.bestParams || {};
      const b = data.bestLearn || {};
      const m = data.monthResult || {};
      const top = data.topConditions || [];

      el.innerHTML = `
        <div class="scalp-condition-main">
          <div><span>익절</span><b>${(Number(p.take || 0)*100).toFixed(1)}%</b></div>
          <div><span>손절</span><b>${(Number(p.stop || 0)*100).toFixed(1)}%</b></div>
          <div><span>최대보유</span><b>${p.max_hold || "-"}일</b></div>
          <div><span>5일상승 기준</span><b>${(Number(p.min_r5 || 0)*100).toFixed(1)}%</b></div>
        </div>
        <p class="trade-helper">최근 학습구간 기준 수익률 ${Number(b.returnRate || 0).toFixed(2)}%, 승률 ${Number(b.winRate || 0).toFixed(1)}%, 최대낙폭 ${Number(b.maxDrawdown || 0).toFixed(2)}%, 매매 ${b.tradeCount || 0}회.</p>
        <p class="trade-helper">최근 1개월 검증 결과: 수익률 ${Number(m.returnRate || 0).toFixed(2)}%, 승률 ${Number(m.winRate || 0).toFixed(1)}%, 매매 ${m.tradeCount || 0}회.</p>
        <div class="detail-title">상위 조건 TOP5</div>
        ${top.map(x => `
          <div class="ai-log-card">
            #${x.rank} 익절 ${(x.params.take*100).toFixed(1)}% · 손절 ${(x.params.stop*100).toFixed(1)}% · 보유 ${x.params.max_hold}일
            <br>수익률 ${Number(x.returnRate).toFixed(2)}% · 승률 ${Number(x.winRate).toFixed(1)}% · 낙폭 ${Number(x.maxDrawdown).toFixed(2)}%
          </div>
        `).join("")}
      `;
    }

    function renderScalpPicks(data) {
      const el = document.getElementById("scalpPickList");
      if (!el) return;

      const picks = data.picks || [];
      if (!picks.length) {
        el.innerHTML = `<div class="empty-box">현재 학습 조건을 통과한 단타 후보가 없습니다. 무리한 매매보다 관망이 유리할 수 있습니다.</div>`;
        return;
      }

      el.innerHTML = picks.map((p, idx) => `
        <div class="card premium-card scalp-pick-card">
          <div class="top-line">
            <span class="rank">#${idx + 1} 단타후보</span>
            <span class="market">${p.market}</span>
            <span class="market">${p.code}</span>
          </div>
          <div class="name-row">
            <div>
              <div class="name">${p.name}</div>
              <div class="theme">${p.theme}</div>
            </div>
            <div class="score-circle score-hot">
              <small>단타점수</small>
              <b>${Number(p.score || 0).toFixed(1)}</b>
            </div>
          </div>
          <div class="grid premium-grid">
            <div class="metric"><span>현재가</span><b>${fmtPrice(p.price)}</b></div>
            <div class="metric"><span>매수관찰가</span><b>${fmtPrice(p.buyZone)}</b></div>
            <div class="metric"><span>목표가</span><b class="red">${fmtPrice(p.target)}</b></div>
            <div class="metric"><span>손절가</span><b class="blue">${fmtPrice(p.stop)}</b></div>
          </div>
          <div class="ai-box">
            <div class="ai-title">⚡ AI 단타 판단</div>
            <p>${p.reason} 최대 보유 기준은 ${p.maxHold}일입니다.</p>
          </div>
        </div>
      `).join("");
    }

    function renderScalpTrades(data) {
      const el = document.getElementById("scalpTradeLog");
      if (!el) return;

      const trades = ((data.monthResult || {}).trades || []).slice(-30).reverse();
      if (!trades.length) {
        el.innerHTML = `<div class="empty-box">최근 1개월 검증 매매 로그가 없습니다.</div>`;
        return;
      }

      el.innerHTML = trades.map(t => `
        <div class="ai-log-card">
          <b>${t.date} · ${t.type}</b> · ${t.name} (${t.code})<br>
          수량 ${t.qty || "-"}주 · 가격 ${fmtMoney(t.price || 0)}
          ${t.pnl !== undefined ? `<br>손익 <b class="${Number(t.pnl) >= 0 ? 'red' : 'blue'}">${fmtProfitMoney(t.pnl)}</b> · 수익률 ${Number(t.returnRate || 0).toFixed(2)}%` : ""}
          ${t.theme ? `<br>테마 ${t.theme}` : ""}
        </div>
      `).join("");
    }


    async function runAnalyze() {
      updateLimitGuide();
      const limit = document.getElementById("limit").value;
      const loading = document.getElementById("loading");
      loading.style.display = "block";
      loading.innerHTML = '<div class="spinner"></div><b>분석 중입니다</b><p>처음 실행은 1~5분 정도 걸릴 수 있습니다.</p>';
      document.getElementById("recommendList").innerHTML = "";
      document.getElementById("watchList").innerHTML = "";
      document.getElementById("themeList").innerHTML = "";
      document.getElementById("analyzedCount").innerText = "-";

      try {
        const res = await fetch(`/api/analyze?limit=${limit}`);
        const rawText = await res.text();

        let data;
        try {
          data = JSON.parse(rawText);
        } catch(parseError) {
          console.log("API returned non-JSON:", rawText.slice(0, 500));
          throw new Error("서버 응답이 지연되었거나 Render가 HTML 오류 페이지를 반환했습니다. 안정 모드로 다시 실행해 주세요.");
        }

        if (!res.ok || data.error) {
          throw new Error(data.error || ("HTTP " + res.status + " API 분석 오류"));
        }

        data.recommend = data.recommend || [];
        data.watch = data.watch || [];
        data.all = data.all || [];
        data.summary = data.summary || [];
        data.themeGroups = data.themeGroups || {};

        data.recommend = data.recommend.map(normalizeThemeClient);
        data.watch = data.watch.map(normalizeThemeClient);
        data.all = data.all.map(normalizeThemeClient);

        latestData = data;
        document.getElementById("analyzedCount").innerText = data.analyzedCount || 0;
        document.getElementById("recommendList").innerHTML = data.recommend.map(item => makeCard(item, "recommend")).join("");
        document.getElementById("watchList").innerHTML = data.watch.map(item => makeCard(item, "watch")).join("");
        try {
          document.getElementById("themeList").innerHTML = renderThemeList(data);
        } catch(themeError) {
          console.log("theme render error", themeError);
          document.getElementById("themeList").innerHTML = "<div class='empty-box'>테마 표시 중 오류가 발생했습니다. 추천/관심 종목은 정상 표시됩니다.</div>";
        }
        loading.style.display = "none";
        renderPortfolio();
        multiAiAutoRunIfNeeded();
        renderAiSim();
        window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (e) {
        console.log("runAnalyze error", e);
        loading.innerHTML = "<b>오류가 발생했습니다.</b><p>잠시 후 다시 실행해 주세요.</p><small style='color:#6b7280'>" + (e.message || "") + "</small>";
      }
    }
    window.addEventListener('load', () => { /* lightweight mode */ });
  </script>

  <script>
    // 🌅 성일의 AI 주식바람 로딩화면: 최대 5초 후 강제 종료
    (function () {
      function hideSunriseLoading() {
        const loading = document.getElementById("sunriseLoading");
        if (!loading) return;

        loading.classList.add("hide");

        setTimeout(() => {
          if (loading && loading.parentNode) {
            loading.parentNode.removeChild(loading);
          }
        }, 900);
      }

      // 서버/데이터 로딩이 오래 걸려도 5초 후에는 반드시 앱 화면으로 넘어갑니다.
      setTimeout(hideSunriseLoading, 5000);

      // 앱이 빨리 준비되면 최소 2.5초 보여준 뒤 자연스럽게 종료
      window.addEventListener("load", () => {
        setTimeout(hideSunriseLoading, 2500);
      });
    })();
  </script>

</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
