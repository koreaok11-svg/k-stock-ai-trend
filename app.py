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
    .tabs { position:sticky; top:0; z-index:20; display:grid; grid-template-columns:repeat(3,1fr); gap:8px; background:rgba(255,250,240,.82); backdrop-filter:blur(12px); padding:10px 0; margin-top:10px; }
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
      background:
        linear-gradient(
          180deg,
          #fff7d8 0%,
          #dff6d6 45%,
          #cfe8ff 100%
        );
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
      background:
        radial-gradient(circle,
          #fff6b0,
          #ffd76f
        );
      box-shadow:
        0 0 80px rgba(255,220,120,.8);
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

    .cloud:before,
    .cloud:after{
      content:"";
      position:absolute;
      background:rgba(255,255,255,.7);
      border-radius:50%;
    }

    .cloud:before{
      width:70px;
      height:70px;
      left:20px;
      top:-30px;
    }

    .cloud:after{
      width:90px;
      height:90px;
      right:20px;
      top:-45px;
    }

    .cloud1{
      top:18%;
      left:-200px;
      animation:cloudMove 18s linear infinite;
    }

    .cloud2{
      top:28%;
      left:-250px;
      transform:scale(.7);
      animation:cloudMove 22s linear infinite;
    }

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
      <select id="limit">
        <option value="400">빠른 분석 400개</option>
        <option value="700" selected>기본 분석 700개</option>
        <option value="1200">확장 분석 1200개</option>
        <option value="1600">전체 근접 1600개</option>
      </select>
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
    </div>

    <section id="recommend" class="section active"><h2>🔥 추천종목 TOP10</h2><div id="recommendList"></div></section>
    <section id="watch" class="section"><h2>👀 관심종목 TOP30</h2><div id="watchList"></div></section>
    <section id="theme" class="section"><h2>📊 테마별 흐름</h2><div id="themeList" class="theme-box"></div></section>

    <div class="footer">K-Stock AI Trend WebApp<br>데이터 제공 상태에 따라 일부 종목은 누락될 수 있습니다.</div>
  </main>

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

      return `
        <div class="card premium-card">
          <div class="top-line">
            <span class="${rankClass}">#${item.rank} ${item.category}</span>
            <span class="market">${item.market}</span>
            <span class="market">${item.code}</span>
            ${badgeLevel(item)}
          </div>

          <div class="name">${item.name}</div>
          <div class="theme">${item.theme}</div>

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

          <button class="chart-btn" onclick='showChart(${safeItemForClick(item)})'>📈 차트 보기</button>
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


    async function runAnalyze() {
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
        window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (e) {
        loading.innerHTML = "<b>오류가 발생했습니다.</b><p>잠시 후 다시 실행해 주세요.</p>";
      }
    }

    window.addEventListener("load", () => {
      setTimeout(() => {
        const loading = document.getElementById("sunriseLoading");
        if (loading) {
          loading.classList.add("hide");
        }
      }, 1500);
    });

  </script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
