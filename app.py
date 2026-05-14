import os
from datetime import datetime

import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

THEME_MAP = {
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
    "미분류": 1.00,
}


def classify_theme(name):
    name = str(name)
    if name in THEME_MAP:
        return THEME_MAP[name]
    for theme, keywords in AUTO_THEME_KEYWORDS.items():
        for keyword in keywords:
            if keyword in name:
                return theme
    return "미분류"


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


@app.route("/api/analyze")
def api_analyze():
    limit = int(request.args.get("limit", "700"))
    limit = max(100, min(limit, 1600))

    df = get_market_df(limit=limit)

    if df.empty:
        return jsonify({
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "analyzedCount": 0,
            "summary": [],
            "recommend": [],
            "watch": [],
            "all": []
        })

    change_col = "ChagesRatio" if "ChagesRatio" in df.columns else None

    if change_col:
        df["dayChange"] = pd.to_numeric(df[change_col], errors="coerce").fillna(0)
    else:
        df["dayChange"] = 0

    df["Close"] = pd.to_numeric(df.get("Close", 0), errors="coerce").fillna(0)
    df["Volume"] = pd.to_numeric(df.get("Volume", 0), errors="coerce").fillna(0)
    df["Amount"] = pd.to_numeric(df.get("Amount", 0), errors="coerce").fillna(0)
    df["Marcap"] = pd.to_numeric(df.get("Marcap", 0), errors="coerce").fillna(0)

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
            "price": float(row["Close"]),
            "return5": round(float(row["dayChange"]), 2),
            "return20": 0,
            "volumePower": round(float(row["volumeScore"] / 50), 2),
            "trendPower": 1,
            "score": round(float(row["score"]), 2),
        }

        analysis = make_opinion(item, category)
        item["opinion"] = analysis["summary"]
        item["reasons"] = analysis["reasons"]
        item["strategy"] = analysis["strategy"]
        item["risk"] = analysis["risk"]
        item["tradePlan"] = get_trade_plan(item)
        item["companyProfile"] = get_company_profile(item)

        records.append(item)

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
    for _, row in summary_df.head(8).iterrows():
        summary.append({
            "theme": row["theme"],
            "avgScore": round(float(row["avgScore"]), 2),
            "maxScore": round(float(row["maxScore"]), 2),
            "count": int(row["count"]),
        })

    theme_groups = {}
    for item in records:
        theme_groups.setdefault(item["theme"], []).append(item)

    for theme in theme_groups:
        theme_groups[theme] = sorted(theme_groups[theme], key=lambda x: x["score"], reverse=True)

    return jsonify({
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "analyzedCount": len(records),
        "summary": summary,
        "themeGroups": theme_groups,
        "recommend": records[:10],
        "watch": records[10:40],
        "all": records[:120],
    })


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
  <title>K-Stock AI Trend</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
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
  </style>
</head>
<body>
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
        <option value="700" selected>기본 분석 700개</option>
        <option value="1200">확장 분석 1200개</option>
        <option value="1600">전체 근접 1600개</option>
      </select>

      <div id="limitGuide" class="limit-guide">
        <div class="limit-title">📘 기본 분석 700개</div>
        <div class="limit-desc">속도와 정확도의 균형이 가장 좋은 기본 모드입니다. 매일 확인용으로 추천합니다.</div>
      </div>

      <button onclick="runAnalyze()">🔥 오늘의 추천종목 분석 시작</button>
      <div class="install-tip">아이폰 홈화면에 추가하려면 Safari 하단 공유 버튼 → <b>홈 화면에 추가</b>를 누르세요.</div>
    </section>

    <div class="notice">⚠️ 투자 판단 보조용입니다. 실제 매수·매도는 본인 판단과 손절 기준이 필요합니다.</div>

    <div id="loading" class="loading">
      <div class="spinner"></div>
      <b>분석 중입니다</b>
      <p>처음 실행은 1~5분 정도 걸릴 수 있습니다.</p>
    </div>

    <div class="tabs">
      <div class="tab active" onclick="showTab('recommend', this)">🔥 추천</div>
      <div class="tab" onclick="showTab('watch', this)">👀 관심</div>
      <div class="tab" onclick="showTab('theme', this)">📊 테마</div>
      <div class="tab" onclick="showTab('portfolio', this); renderPortfolio();">💼 모의</div>
      <div class="tab" onclick="showTab('aiSim', this); renderAiSim();">🤖 AI</div>
    </div>

    <section id="recommend" class="section active"><h2>🔥 추천종목 TOP10</h2><div id="recommendList"></div></section>
    <section id="watch" class="section"><h2>👀 관심종목 TOP30</h2><div id="watchList"></div></section>
    <section id="theme" class="section"><h2>📊 테마별 흐름</h2><div id="themeList" class="theme-box"></div></section>

    <section id="aiSim" class="section">
      <h2>🤖 AI 자동투자 시뮬레이션</h2>

      <div class="ai-sim-hero">
        <div class="portfolio-mini">AI AUTONOMOUS PAPER TRADING</div>
        <h3>AI가 5개 종목으로 직접 투자합니다 🍃</h3>
        <p>AI가 추천 종목 5개를 고르고, 매일 가상 매수·매도 판단을 내려 수익과 손실을 시뮬레이션합니다.</p>

        <div class="portfolio-grid">
          <div><span>AI 총 자산</span><b id="aiTotal">-</b></div>
          <div><span>AI 현금</span><b id="aiCash">-</b></div>
          <div><span>AI 수익률</span><b id="aiReturn">-</b></div>
        </div>
      </div>

      <div class="ai-start-box">
        <div class="detail-title">💰 AI 초기 투자금 설정</div>
        <p>AI가 운용할 가상 투자금을 선택한 뒤 시작하세요. 시작 후 AI가 5개 종목을 선정하고 운용을 시작합니다.</p>

        <div class="ai-money-buttons">
          <button onclick="setAiStartAmount(1000000)">100만원</button>
          <button onclick="setAiStartAmount(10000000)">1000만원</button>
          <button onclick="setAiStartAmount(50000000)">5000만원</button>
          <button onclick="setAiStartAmount(100000000)">1억원</button>
        </div>

        <input id="aiStartAmount" class="trade-input ai-start-input" inputmode="numeric" value="10000000">

        <button class="ai-start-btn" onclick="aiStartSimulation()">🚀 AI 자동운용 시작</button>
        <div class="trade-helper">기존 AI 시뮬레이션이 있으면 새 투자금 기준으로 초기화 후 다시 시작됩니다.</div>
      </div>

      <div class="ai-sim-actions">
        <button onclick="aiPickFive()">🎯 5종목 갱신</button>
        <button onclick="aiRunPeriod(1)">🌞 1일</button>
        <button onclick="aiRunPeriod(7)">📆 1주일</button>
        <button onclick="aiRunPeriod(30)">🌙 1개월</button>
        <button onclick="aiRunPeriod(60)">🍃 2개월</button>
        <button onclick="aiRunPeriod(365)">🌳 1년</button>
        <button onclick="toggleAiAutoRun()" id="aiAutoBtn">⏸ 자동운용</button>
        <button onclick="aiResetSim()">🔄 초기화</button>
      </div>

      <div class="ai-portfolio-note" id="aiSimNote">
        🤖 분석을 먼저 실행한 뒤 AI 5종목 선정을 눌러주세요.
      </div>

      <div class="ai-chart-card">
        <div class="detail-title">📈 AI 자산 추이</div>
        <canvas id="aiEquityChart"></canvas>
      </div>

      <h2>🎯 AI 선택 5종목</h2>
      <div id="aiPickList"></div>

      <h2>💼 AI 보유 포트폴리오</h2>
      <div id="aiHoldingList"></div>

      <h2>🧾 AI 매매 판단 기록</h2>
      <div id="aiTradeLog"></div>
    </section>

    <section id="portfolio" class="section">
      <h2>💼 성일의 AI 모의투자</h2>

      <div class="portfolio-hero">
        <div class="portfolio-mini">SUNGIN AI PAPER TRADING</div>
        <h3>가상의 돈으로 투자 연습하기 🍃</h3>
        <p>실제 돈이 아닌 모의 자산으로 추천종목을 매수·매도하고, 수익률을 확인할 수 있습니다.</p>

        <div class="portfolio-grid">
          <div><span>총 자산</span><b id="pfTotal">-</b></div>
          <div><span>가상 현금</span><b id="pfCash">-</b></div>
          <div><span>총 수익률</span><b id="pfReturn">-</b></div>
        </div>
      </div>

      <div class="portfolio-actions">
        <button onclick="depositCash()">➕ 가상 입금</button>
        <button onclick="withdrawCash()">➖ 가상 출금</button>
        <button onclick="resetPortfolio()">🔄 초기화</button>
      </div>

      <div class="ai-portfolio-note" id="pfAiNote">
        🤖 AI 모의투자 비서가 보유 종목과 수익률을 분석해줍니다.
      </div>

      <h2>📌 보유 종목</h2>
      <div id="holdingList"></div>

      <h2>🧾 거래 내역</h2>
      <div id="tradeHistory"></div>
    </section>

    <div class="footer">K-Stock AI Trend WebApp<br>데이터 제공 상태에 따라 일부 종목은 누락될 수 있습니다.</div>
  </main>


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
          desc: "주요 종목 중심으로 빠르게 스캔합니다. 출근 전이나 잠깐 확인할 때 좋고, 속도가 가장 빠릅니다."
        },
        "700": {
          title: "📘 기본 분석 700개",
          desc: "속도와 정확도의 균형이 가장 좋은 기본 모드입니다. 매일 확인용으로 추천합니다."
        },
        "1200": {
          title: "🚀 확장 분석 1200개",
          desc: "중소형주와 테마주까지 넓게 확인합니다. 숨은 종목과 새로운 테마를 찾고 싶을 때 좋습니다."
        },
        "1600": {
          title: "🌌 전체 근접 1600개",
          desc: "코스피·코스닥 대부분을 최대한 넓게 분석합니다. 시간이 오래 걸릴 수 있지만 시장 전체 흐름 파악에 좋습니다."
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
              <div><span>현재가</span><b>${fmtPrice(item.price)}</b></div>
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

    function toggleTheme(theme) {
      const target = document.getElementById("theme-detail-" + btoa(unescape(encodeURIComponent(theme))).replace(/=/g, ""));
      if (!target) return;

      const isOpen = target.classList.contains("active");
      document.querySelectorAll(".theme-detail").forEach(x => x.classList.remove("active"));

      if (!isOpen) {
        target.classList.add("active");
      }
    }

    function renderThemeList(data) {
      const groups = data.themeGroups || {};
      return data.summary.map(t => {
        const key = btoa(unescape(encodeURIComponent(t.theme))).replace(/=/g, "");
        const items = groups[t.theme] || [];
        const stockHtml = items.map(item => makeThemeStockCard(item)).join("");

        return `
          <div class="theme-row clickable" onclick='toggleTheme(${JSON.stringify(t.theme)})'>
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
                <div><span>평가손익</span><b class="${h.profit >= 0 ? 'red' : 'blue'}">${fmtMoney(h.profit)}</b></div>
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
            ${h.profit !== undefined ? `<br>실현손익 <b class="${h.profit >= 0 ? 'red' : 'blue'}">${fmtMoney(h.profit)}</b>` : ""}
            <br><span style="color:#6b7280">${h.time}</span>
          </div>
        `).join("");
    }



    const AI_SIM_KEY = "sungil_ai_auto_invest_sim_v2";
    let aiEquityChart = null;

    function todayKey() {
      return new Date().toISOString().slice(0, 10);
    }

    function defaultAiSim(amount=10000000) {
      amount = Number(amount || 10000000);
      return {
        cash: amount,
        initialCash: amount,
        day: 0,
        picks: [],
        holdings: {},
        history: [],
        equity: [{day: 0, total: amount, cash: amount, returnRate: 0}],
        autoRun: true,
        started: false,
        lastAutoDate: null
      };
    }

    function loadAiSim() {
      try {
        const saved = localStorage.getItem(AI_SIM_KEY);
        return saved ? JSON.parse(saved) : defaultAiSim();
      } catch(e) {
        return defaultAiSim();
      }
    }

    function saveAiSim(sim) {
      localStorage.setItem(AI_SIM_KEY, JSON.stringify(sim));
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

    function aiStartSimulation() {
      if (!latestData || !latestData.all || latestData.all.length === 0) {
        alert("먼저 오늘의 추천종목 분석을 실행해주세요.");
        return;
      }

      const amount = getAiStartAmount();

      if (!confirm(`AI 자동운용을 ${fmtMoney(amount)}으로 시작할까요?\\n기존 AI 시뮬레이션은 초기화됩니다.`)) {
        return;
      }

      let sim = defaultAiSim(amount);
      sim.started = true;
      sim.autoRun = true;
      sim = updateAiPicks(sim, true);
      sim.history.unshift({
        day: sim.day,
        type: "AI 자동운용 시작",
        text: `초기 투자금 ${fmtMoney(amount)}으로 AI 자동운용을 시작했습니다. AI가 5개 종목을 선정하고 매일 조건에 따라 운용합니다.`,
        time: new Date().toLocaleString()
      });

      saveAiSim(sim);
      renderAiSim();
      alert("AI 자동운용이 시작되었습니다.");
    }

    function aiScoreForPick(item) {
      const score = Number(item.score || 0);
      const r5 = Number(item.return5 || 0);
      const vol = Number(item.volumePower || 0);
      const themeBonus = item.theme && item.theme !== "미분류" ? 8 : 0;
      const overheatPenalty = r5 >= 25 ? 18 : r5 >= 15 ? 8 : 0;
      return score + vol * 6 + themeBonus - overheatPenalty;
    }

    function aiPickReason(item) {
      const reasons = [];
      if (item.theme && item.theme !== "미분류") reasons.push(`${item.theme} 테마에 포함되어 시장 흐름과 연결성이 있습니다.`);
      if (Number(item.score) >= 70) reasons.push("AI 점수가 높아 가격 흐름과 거래량 조건이 우수합니다.");
      if (Number(item.volumePower) >= 1.5) reasons.push("거래량 강도가 높아 수급 유입 가능성이 있습니다.");
      if (Number(item.return5) >= 15) reasons.push("최근 상승률이 높아 매수 시점은 분할 접근이 필요합니다.");
      if (reasons.length === 0) reasons.push("종합 점수와 테마 분포를 기준으로 포트폴리오 균형 차원에서 선정되었습니다.");
      return reasons.join(" ");
    }

    function getAiCandidates() {
      if (!latestData) return [];
      const candidates = []
        .concat(latestData.recommend || [])
        .concat(latestData.watch || [])
        .concat(latestData.all || []);

      const unique = {};
      candidates.forEach(item => {
        if (!unique[item.code]) unique[item.code] = item;
      });

      return Object.values(unique)
        .map(item => ({...item, aiPickScore: aiScoreForPick(item)}))
        .sort((a,b) => b.aiPickScore - a.aiPickScore);
    }

    function updateAiPicks(sim, force=false) {
      const candidates = getAiCandidates();
      if (candidates.length === 0) return sim;

      const currentCodes = new Set((sim.picks || []).map(x => x.code));
      const top = candidates.slice(0, 5);

      if (force || !sim.picks || sim.picks.length === 0) {
        sim.picks = top.map(item => ({
          code: item.code,
          name: item.name,
          market: item.market,
          theme: item.theme,
          pickPrice: Number(item.price || 0),
          score: Number(item.score || 0),
          aiPickScore: Number(item.aiPickScore || 0),
          reason: aiPickReason(item)
        }));
        return sim;
      }

      // 매일 시장 점수에 따라 후보 5개를 자연스럽게 갱신합니다.
      // 단, 보유 종목은 갑자기 사라지지 않도록 우선 유지합니다.
      const holdingCodes = new Set(Object.keys(sim.holdings || {}));
      const kept = (sim.picks || []).filter(p => holdingCodes.has(p.code)).slice(0, 5);
      const keptCodes = new Set(kept.map(x => x.code));
      const fill = candidates
        .filter(item => !keptCodes.has(item.code))
        .slice(0, 5 - kept.length)
        .map(item => ({
          code: item.code,
          name: item.name,
          market: item.market,
          theme: item.theme,
          pickPrice: Number(item.price || 0),
          score: Number(item.score || 0),
          aiPickScore: Number(item.aiPickScore || 0),
          reason: aiPickReason(item)
        }));

      sim.picks = kept.concat(fill);
      return sim;
    }

    function aiPickFive() {
      if (!latestData || !latestData.all || latestData.all.length === 0) {
        alert("먼저 추천종목 분석을 실행해주세요.");
        return;
      }

      let sim = loadAiSim();
      if (!sim || !sim.equity) sim = defaultAiSim(getAiStartAmount());
      if (!sim.started) sim.started = true;
      sim = updateAiPicks(sim, true);

      sim.history.unshift({
        day: sim.day,
        type: "AI 5종목 선정/갱신",
        text: `AI가 ${sim.picks.map(x => x.name).join(", ")} 5개 종목을 선정했습니다. 시장 점수 변화에 따라 5개 종목은 고정이 아니라 갱신될 수 있습니다.`,
        time: new Date().toLocaleString()
      });

      saveAiSim(sim);
      renderAiSim();
      alert("AI가 5개 종목을 선정/갱신했습니다.");
    }

    function getLiveItemForAi(pick) {
      return getCurrentItem(pick.code) || pick;
    }

    function aiDecision(item, holding) {
      const score = Number(item.score || 0);
      const r5 = Number(item.return5 || 0);
      const vol = Number(item.volumePower || 0);
      const price = Number(item.price || item.pickPrice || 0);
      const profitRate = holding && holding.avgPrice > 0 ? ((price - holding.avgPrice) / holding.avgPrice * 100) : 0;

      if (!holding || holding.qty <= 0) {
        if (score >= 65 && r5 < 25 && vol >= 1.0) return {action:"BUY", weight:0.20, reason:"AI 점수와 거래량이 양호하고 과열이 심하지 않아 신규 편입합니다."};
        if (score >= 50 && vol >= 1.5) return {action:"BUY", weight:0.12, reason:"점수는 중간 이상이며 거래량이 강해 소액 편입합니다."};
        return {action:"WAIT", weight:0, reason:"현재는 신규 매수 조건이 부족하여 관찰합니다."};
      }

      if (profitRate <= -6) return {action:"SELL_ALL", weight:1, reason:`손실률 ${profitRate.toFixed(2)}%로 손절 기준에 접근해 전량 정리합니다.`};
      if (profitRate >= 12 || r5 >= 30) return {action:"SELL_HALF", weight:0.5, reason:`수익률 ${profitRate.toFixed(2)}% 또는 단기 과열 구간으로 절반 차익실현합니다.`};
      if (score >= 75 && profitRate > -3 && vol >= 1.4) return {action:"BUY_MORE", weight:0.10, reason:"추세와 거래량이 유지되어 비중을 소폭 늘립니다."};
      return {action:"HOLD", weight:0, reason:"보유 조건은 유지되지만 추가 매수/매도 신호는 강하지 않습니다."};
    }

    function aiRunSingleDay(sim, silent=false) {
      if (!sim.picks || sim.picks.length === 0) {
        sim = updateAiPicks(sim, true);
      }

      // 매일 시작 시 후보 5개 갱신
      sim = updateAiPicks(sim, false);

      sim.day += 1;
      const logs = [];

      sim.picks.forEach(pick => {
        const item = getLiveItemForAi(pick);
        const code = pick.code;
        const price = Number(item.price || pick.pickPrice || 0);
        if (price <= 0) return;

        const holding = sim.holdings[code];
        const decision = aiDecision(item, holding);

        if (decision.action === "BUY" || decision.action === "BUY_MORE") {
          const budget = Math.floor(sim.initialCash * decision.weight);
          const spend = Math.min(sim.cash, budget);
          const qty = Math.floor(spend / price);

          if (qty >= 1) {
            const amount = qty * price;
            const h = sim.holdings[code] || {
              code: code,
              name: pick.name,
              market: pick.market,
              theme: pick.theme,
              qty: 0,
              avgPrice: 0,
              invested: 0,
              lastPrice: price
            };
            const newQty = h.qty + qty;
            const newInvested = h.invested + amount;
            h.qty = newQty;
            h.invested = newInvested;
            h.avgPrice = Math.round(newInvested / newQty);
            h.lastPrice = price;
            sim.holdings[code] = h;
            sim.cash -= amount;
            logs.push({day: sim.day, type: decision.action === "BUY" ? "AI 매수" : "AI 추가매수", name: pick.name, code, qty, price, amount, text: decision.reason, time: new Date().toLocaleString()});
          } else {
            logs.push({day: sim.day, type: "AI 관찰", name: pick.name, code, text: "현금 부족 또는 1주 미만 금액으로 매수하지 않았습니다.", time: new Date().toLocaleString()});
          }
        } else if ((decision.action === "SELL_ALL" || decision.action === "SELL_HALF") && holding && holding.qty > 0) {
          const qty = decision.action === "SELL_ALL" ? holding.qty : Math.max(1, Math.floor(holding.qty / 2));
          const amount = Math.round(price * qty);
          const cost = Math.round(holding.avgPrice * qty);
          const profit = amount - cost;
          holding.qty -= qty;
          holding.invested -= cost;

          if (holding.qty <= 0) delete sim.holdings[code];
          else {
            holding.avgPrice = Math.round(holding.invested / holding.qty);
            holding.lastPrice = price;
            sim.holdings[code] = holding;
          }
          sim.cash += amount;
          logs.push({day: sim.day, type: decision.action === "SELL_ALL" ? "AI 전량매도" : "AI 절반매도", name: pick.name, code, qty, price, amount, profit, text: decision.reason, time: new Date().toLocaleString()});
        } else {
          logs.push({day: sim.day, type: decision.action === "WAIT" ? "AI 관찰" : "AI 보유", name: pick.name, code, text: decision.reason, time: new Date().toLocaleString()});
        }
      });

      sim.history = logs.concat(sim.history || []);
      const snapshot = calcAiSimSnapshot(sim);
      sim.equity.push({day: sim.day, total: snapshot.total, cash: sim.cash, returnRate: snapshot.totalReturn});
      return sim;
    }

    function aiRunDay() {
      aiRunPeriod(1);
    }

    function aiRunPeriod(days) {
      if (!latestData) {
        alert("먼저 오늘의 추천종목 분석을 실행해 최신 현재가를 불러와주세요.");
        return;
      }

      let sim = loadAiSim();
      if (!sim.started) {
        alert("먼저 AI 초기 투자금을 설정하고 'AI 자동운용 시작'을 눌러주세요.");
        return;
      }
      if (!sim.picks || sim.picks.length === 0) {
        sim = updateAiPicks(sim, true);
      }

      const maxDays = Math.min(Number(days || 1), 365);
      for (let i = 0; i < maxDays; i++) {
        sim = aiRunSingleDay(sim, true);
      }

      sim.lastAutoDate = todayKey();
      saveAiSim(sim);
      renderAiSim();
    }

    function aiRunFiveDays() {
      aiRunPeriod(5);
    }

    function toggleAiAutoRun() {
      const sim = loadAiSim();
      sim.autoRun = !sim.autoRun;
      saveAiSim(sim);
      renderAiSim();
    }

    function aiAutoRunIfNeeded() {
      if (!latestData) return;
      let sim = loadAiSim();
      if (!sim.started) return;
      if (!sim.autoRun) return;
      const today = todayKey();

      if (!sim.lastAutoDate) {
        sim.lastAutoDate = today;
        saveAiSim(sim);
        return;
      }

      if (sim.lastAutoDate !== today) {
        if (!sim.picks || sim.picks.length === 0) {
          sim = updateAiPicks(sim, true);
        }
        sim = aiRunSingleDay(sim, true);
        sim.lastAutoDate = today;
        sim.history.unshift({
          day: sim.day,
          type: "AI 자동 일일운용",
          text: "앱 접속 시 날짜가 바뀐 것을 확인해 AI가 하루 운용을 자동 실행했습니다.",
          time: new Date().toLocaleString()
        });
        saveAiSim(sim);
      }
    }

    function aiResetSim() {
      if (!confirm("AI 자동투자 시뮬레이션을 초기화할까요?")) return;
      saveAiSim(defaultAiSim());
      renderAiSim();
    }

    function calcAiSimSnapshot(sim) {
      let stockValue = 0;
      const holdings = Object.values(sim.holdings || {});
      holdings.forEach(h => {
        const item = getCurrentItem(h.code);
        const currentPrice = item ? Number(item.price || h.lastPrice || h.avgPrice) : Number(h.lastPrice || h.avgPrice);
        h.currentPrice = currentPrice;
        h.value = Math.round(currentPrice * h.qty);
        h.profit = Math.round((currentPrice - h.avgPrice) * h.qty);
        h.returnRate = h.invested > 0 ? (h.profit / h.invested * 100) : 0;
        stockValue += h.value;
      });
      const total = sim.cash + stockValue;
      const totalReturn = sim.initialCash > 0 ? ((total - sim.initialCash) / sim.initialCash * 100) : 0;
      return {holdings, stockValue, total, totalReturn};
    }

    function renderAiEquityChart(sim) {
      const canvas = document.getElementById("aiEquityChart");
      if (!canvas) return;
      const eq = sim.equity || [];
      if (aiEquityChart) aiEquityChart.destroy();

      aiEquityChart = new Chart(canvas, {
        type: "line",
        data: {
          labels: eq.map(x => "D+" + x.day),
          datasets: [{ label: "AI 총 자산", data: eq.map(x => x.total), tension: 0.35, fill: true, borderWidth: 3 }]
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { maxTicksLimit: 7 } },
            y: { ticks: { callback: value => Number(value).toLocaleString() } }
          }
        }
      });
    }

    function renderAiSim() {
      const sim = loadAiSim();
      const snap = calcAiSimSnapshot(sim);

      const totalEl = document.getElementById("aiTotal");
      if (!totalEl) return;

      const startInput = document.getElementById("aiStartAmount");
      if (startInput && sim.initialCash) startInput.value = Number(sim.initialCash).toLocaleString();

      document.getElementById("aiTotal").innerText = fmtMoney(snap.total);
      document.getElementById("aiCash").innerText = fmtMoney(sim.cash);
      document.getElementById("aiReturn").innerHTML = `<span class="${snap.totalReturn >= 0 ? 'red' : 'blue'}">${snap.totalReturn.toFixed(2)}%</span>`;

      const autoBtn = document.getElementById("aiAutoBtn");
      if (autoBtn) autoBtn.innerText = sim.autoRun ? "⏸ 자동운용 켜짐" : "▶️ 자동운용 꺼짐";

      const pickList = document.getElementById("aiPickList");
      if (!sim.picks || sim.picks.length === 0) {
        pickList.innerHTML = `<div class="empty-box">아직 AI가 5종목을 선정하지 않았습니다.<br>먼저 추천종목 분석 후 <b>AI 5종목 선정</b>을 눌러주세요.</div>`;
      } else {
        pickList.innerHTML = sim.picks.map((pick, idx) => {
          const item = getLiveItemForAi(pick);
          const holding = sim.holdings[pick.code];
          const decision = aiDecision(item, holding);
          const dClass = decision.action.includes("SELL") ? "ai-decision sell" : decision.action.includes("HOLD") || decision.action.includes("WAIT") ? "ai-decision hold" : "ai-decision";
          const actionText = {BUY:"매수 후보", BUY_MORE:"추가매수", SELL_ALL:"전량매도", SELL_HALF:"절반매도", HOLD:"보유", WAIT:"관찰"}[decision.action] || decision.action;

          return `
            <div class="ai-pick-card">
              <div class="ai-pick-head">
                <div>
                  <div class="ai-pick-name">#${idx + 1} ${pick.name}</div>
                  <div class="ai-pick-meta">${pick.market} · ${pick.code} · ${pick.theme}</div>
                </div>
                <span class="${dClass}">${actionText}</span>
              </div>
              <div class="ai-pick-grid">
                <div><span>현재가</span><b>${fmtPrice(item.price || pick.pickPrice)}</b></div>
                <div><span>AI점수</span><b>${item.score || pick.score}</b></div>
                <div><span>선정점수</span><b>${Number(pick.aiPickScore || 0).toFixed(1)}</b></div>
              </div>
              <div class="ai-reason-box">
                <b>선정 이유</b><br>${pick.reason}<br><br>
                <b>오늘 판단</b><br>${decision.reason}
              </div>
            </div>
          `;
        }).join("");
      }

      const holdingList = document.getElementById("aiHoldingList");
      if (snap.holdings.length === 0) {
        holdingList.innerHTML = `<div class="empty-box">AI가 아직 보유한 종목이 없습니다.<br><b>1일/1주일/1개월 운용</b>을 누르면 AI가 조건에 따라 매수합니다.</div>`;
      } else {
        holdingList.innerHTML = snap.holdings.map(h => `
          <div class="holding-card">
            <div class="holding-head">
              <div>
                <div class="holding-name">${h.name}</div>
                <div class="holding-meta">${h.market} · ${h.code} · ${h.theme}</div>
              </div>
              <div class="${h.profit >= 0 ? 'holding-profit' : 'holding-profit loss'}">${h.returnRate.toFixed(2)}%</div>
            </div>
            <div class="holding-grid">
              <div><span>보유수량</span><b>${h.qty}주</b></div>
              <div><span>평균단가</span><b>${fmtMoney(h.avgPrice)}</b></div>
              <div><span>현재가</span><b>${fmtMoney(h.currentPrice)}</b></div>
              <div><span>평가손익</span><b class="${h.profit >= 0 ? 'red' : 'blue'}">${fmtMoney(h.profit)}</b></div>
            </div>
          </div>
        `).join("");
      }

      const note = document.getElementById("aiSimNote");
      if (!sim.started) {
        note.innerText = "🤖 초기 투자금을 선택하고 AI 자동운용 시작을 누르면 시뮬레이션이 시작됩니다.";
      } else if (sim.picks.length === 0) {
        note.innerText = "🤖 AI가 아직 5종목을 선정하지 않았습니다. 5종목 선정/갱신을 눌러주세요. 5종목은 시장 점수에 따라 갱신됩니다.";
      } else {
        const best = snap.holdings.length ? [...snap.holdings].sort((a,b) => b.returnRate - a.returnRate)[0] : null;
        note.innerText = `🤖 AI 운용 ${sim.day}일차입니다. 초기 투자금은 ${fmtMoney(sim.initialCash)}이고 현재 수익률은 ${snap.totalReturn.toFixed(2)}%입니다. 자동운용은 ${sim.autoRun ? "켜짐" : "꺼짐"} 상태입니다. ${best ? "가장 좋은 보유 종목은 " + best.name + "입니다." : "아직 보유 종목이 없거나 매수 조건을 기다리는 중입니다."}`;
      }

      const history = sim.history || [];
      document.getElementById("aiTradeLog").innerHTML = history.length === 0
        ? `<div class="empty-box">AI 매매 기록이 없습니다.</div>`
        : history.slice(0, 60).map(h => `
          <div class="ai-log-card">
            <b>D+${h.day} · ${h.type}</b> ${h.name ? "· " + h.name + " (" + h.code + ")" : ""}<br>
            ${h.qty ? `수량 ${h.qty}주 · 단가 ${fmtMoney(h.price)} · 금액 ${fmtMoney(h.amount)}<br>` : ""}
            ${h.profit !== undefined ? `실현손익 <b class="${h.profit >= 0 ? 'red' : 'blue'}">${fmtMoney(h.profit)}</b><br>` : ""}
            ${h.text || ""}
            <br><span style="color:#6b7280">${h.time}</span>
          </div>
        `).join("");

      renderAiEquityChart(sim);
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
        const data = await res.json();
        latestData = data;
        document.getElementById("analyzedCount").innerText = data.analyzedCount || 0;
        document.getElementById("recommendList").innerHTML = data.recommend.map(item => makeCard(item, "recommend")).join("");
        document.getElementById("watchList").innerHTML = data.watch.map(item => makeCard(item, "watch")).join("");
        document.getElementById("themeList").innerHTML = renderThemeList(data);
        loading.style.display = "none";
        renderPortfolio();
        aiAutoRunIfNeeded();
        renderAiSim();
        window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (e) {
        loading.innerHTML = "<b>오류가 발생했습니다.</b><p>잠시 후 다시 실행해 주세요.</p>";
      }
    }
    window.addEventListener('load', () => { renderPortfolio(); renderAiSim(); });
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
