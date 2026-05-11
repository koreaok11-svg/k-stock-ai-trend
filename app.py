
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
    "AI반도체/HBM": [
        "반도체", "하이닉스", "HBM", "메모리", "디램", "낸드", "파운드리",
        "테크윙", "리노", "ISC", "HPSP", "원익", "주성", "이오테크닉스",
        "한미반도체", "하나마이크론", "가온칩스", "오픈엣지"
    ],
    "반도체장비/소재": [
        "소부장", "실리콘", "웨이퍼", "식각", "증착", "포토", "테스트",
        "프로브", "쿼츠", "세라믹", "테스", "피에스케이", "유진테크",
        "동진쎄미켐", "솔브레인", "티씨케이", "원익QnC"
    ],
    "전력설비/데이터센터": [
        "전력", "전기", "일렉트릭", "변압기", "케이블", "전선", "중공업",
        "효성", "LS", "대한전선", "제룡", "산일", "가온전선", "현대일렉트릭"
    ],
    "광통신/CPO": [
        "광", "통신", "CPO", "네트웍스", "솔루션", "라이트론", "오이솔루션",
        "쏠리드", "케이엠더블유", "다산"
    ],
    "AI서버/PCB": [
        "PCB", "기판", "써키트", "페타시스", "대덕", "심텍", "티엘비",
        "코리아써키트", "서버"
    ],
    "로봇/피지컬AI": [
        "로봇", "로보", "자동화", "뉴로메카", "레인보우", "두산로보틱스",
        "에스피지", "로보티즈", "휴림"
    ],
    "2차전지/배터리": [
        "배터리", "전지", "2차전지", "리튬", "양극재", "음극재", "전해액",
        "분리막", "에코프로", "엘앤에프", "포스코퓨처엠", "천보", "대주전자재료",
        "나노신소재", "코스모", "금양"
    ],
    "자동차/자율주행": [
        "자동차", "모비스", "만도", "HL", "현대차", "기아", "자율주행",
        "카메라", "센서", "전장", "모트렉스", "칩스앤미디어"
    ],
    "바이오/제약": [
        "바이오", "제약", "헬스", "셀트리온", "삼성바이오", "유한양행",
        "한미약품", "알테오젠", "HLB", "레고켐", "리가켐", "보로노이",
        "에이비엘", "오스코텍", "휴젤", "메디톡스"
    ],
    "방산/우주항공": [
        "방산", "항공", "우주", "한화에어로", "한국항공우주", "LIG",
        "현대로템", "쎄트렉아이", "인텔리안", "켄코아", "제노코"
    ],
    "조선/해운": [
        "조선", "해양", "중공업", "미포", "한화오션", "삼성중공업",
        "HD현대중공업", "팬오션", "HMM", "대한해운"
    ],
    "원전/전력인프라": [
        "원전", "원자력", "두산에너빌리티", "한전기술", "우진", "비에이치아이",
        "보성파워텍", "우리기술"
    ],
    "화장품/미용": [
        "화장품", "코스맥스", "한국콜마", "아모레", "클리오", "실리콘투",
        "브이티", "마녀공장", "토니모리", "잉글우드랩"
    ],
    "엔터/콘텐츠": [
        "엔터", "하이브", "JYP", "YG", "SM", "스튜디오", "콘텐츠", "드라마",
        "CJ ENM", "NEW", "덱스터", "래몽래인"
    ],
    "게임/웹툰": [
        "게임", "넷마블", "엔씨", "크래프톤", "펄어비스", "컴투스",
        "위메이드", "카카오게임즈", "웹툰"
    ],
    "금융/증권": [
        "금융", "은행", "증권", "보험", "카드", "KB", "신한", "하나금융",
        "우리금융", "삼성증권", "키움", "미래에셋"
    ],
    "친환경/수소": [
        "수소", "풍력", "태양광", "친환경", "연료전지", "두산퓨얼셀",
        "씨에스윈드", "한화솔루션", "OCI"
    ],
    "음식료/소비재": [
        "식품", "푸드", "농심", "삼양", "오리온", "CJ제일제당", "빙그레",
        "하이트", "롯데칠성", "동원"
    ],
    "건설/인프라": [
        "건설", "시멘트", "레미콘", "현대건설", "GS건설", "대우건설",
        "DL이앤씨", "삼표", "쌍용C&E"
    ],
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

WEIGHT = {
    "AI반도체/HBM": 1.35,
    "전력설비/데이터센터": 1.30,
    "광통신/CPO": 1.25,
    "AI서버/PCB": 1.18,
    "원전/전력인프라": 1.15,
    "로봇/피지컬AI": 1.10,
    "미분류": 1.00,
}

def get_market_df(limit=700):
    krx = fdr.StockListing("KRX")

    krx = krx[krx["Market"].isin(["KOSPI", "KOSDAQ"])].copy()

    krx["Code"] = krx["Code"].astype(str).str.zfill(6)
    krx["Name"] = krx["Name"].astype(str)
    krx["Market"] = krx["Market"].astype(str)

    if limit:
        krx = krx.head(int(limit))

    return krx

def analyze_one(row):
    try:
        data = yf.download(row["ticker"], period="3mo", interval="1d", progress=False, auto_adjust=True, threads=False)
        if data.empty or len(data) < 25:
            return None

        close = data["Close"]
        volume = data["Volume"]

        price = float(close.iloc[-1])
        r5 = (price / float(close.iloc[-6]) - 1) * 100
        r20 = (price / float(close.iloc[-21]) - 1) * 100

        v20 = float(volume.tail(20).mean())
        volume_power = float(volume.tail(5).mean()) / v20 if v20 > 0 else 0

        ma5 = float(close.tail(5).mean())
        ma20 = float(close.tail(20).mean())
        trend_power = ma5 / ma20 if ma20 > 0 else 1

        theme = classify_theme(row["name"])
        score = (r5 * 0.25 + r20 * 0.43 + volume_power * 10 * 0.22 + trend_power * 10 * 0.10) * WEIGHT.get(theme, 1.0)

        return {
            "market": row["market"],
            "code": row["code"],
            "name": row["name"],
            "theme": theme,
            "price": round(price, 0),
            "return5": round(r5, 2),
            "return20": round(r20, 2),
            "volumePower": round(volume_power, 2),
            "trendPower": round(trend_power, 3),
            "score": round(score, 2),
        }
    except Exception:
        return None

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

    return jsonify({
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "analyzedCount": len(records),
        "summary": summary,
        "recommend": records[:10],
        "watch": records[10:40],
        "all": records[:120],
    })


HTML = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#111827">
  <title>K-Stock AI Trend</title>
  <style>
    :root { --bg:#f3f4f6; --card:#fff; --text:#111827; --sub:#6b7280; --blue:#2563eb; --red:#dc2626; --dark:#111827; --line:#e5e7eb; --yellow:#fffbeb; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif; }
    .app { max-width:820px; margin:0 auto; padding:16px 14px 110px; }
    .hero { background:linear-gradient(135deg,#111827,#1d4ed8); color:white; border-radius:30px; padding:24px; box-shadow:0 16px 34px rgba(0,0,0,.25); margin-top:8px; }
    .mini { font-size:12px; letter-spacing:1.2px; opacity:.85; font-weight:800; }
    h1 { font-size:31px; line-height:1.16; margin:8px 0 8px; }
    .hero p { margin:0 0 18px; opacity:.92; line-height:1.5; font-size:15px; }
    .hero-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
    .hero-grid div { background:rgba(255,255,255,.14); border-radius:18px; padding:12px 8px; text-align:center; }
    .hero-grid b { display:block; font-size:23px; }
    .hero-grid span { display:block; font-size:12px; opacity:.9; margin-top:2px; }
    .control { background:white; border-radius:24px; padding:16px; margin:16px 0; box-shadow:0 8px 22px rgba(0,0,0,.08); }
    .control label { font-weight:900; font-size:15px; }
    select { width:100%; margin-top:8px; border:1px solid var(--line); border-radius:15px; padding:12px; font-size:16px; background:#f9fafb; }
    button { width:100%; margin-top:14px; border:none; border-radius:18px; padding:16px; font-size:17px; font-weight:900; color:white; background:linear-gradient(135deg,#ef4444,#f97316); box-shadow:0 10px 20px rgba(239,68,68,.25); }
    button:active { transform:scale(.99); }
    .notice { background:var(--dark); color:white; border-radius:20px; padding:14px; line-height:1.55; font-size:14px; margin:12px 0; }
    .loading { display:none; background:white; border-radius:22px; padding:22px; text-align:center; margin:14px 0; box-shadow:0 8px 22px rgba(0,0,0,.08); }
    .spinner { width:42px; height:42px; border:5px solid #e5e7eb; border-top-color:var(--blue); border-radius:50%; animation:spin 1s linear infinite; margin:0 auto 12px; }
    @keyframes spin { to { transform:rotate(360deg); } }
    .tabs { position:sticky; top:0; z-index:20; display:grid; grid-template-columns:repeat(3,1fr); gap:8px; background:rgba(243,244,246,.92); backdrop-filter:blur(12px); padding:10px 0; margin-top:10px; }
    .tab { background:white; color:var(--sub); border-radius:999px; padding:10px 8px; font-weight:900; font-size:13px; text-align:center; border:1px solid var(--line); }
    .tab.active { background:var(--dark); color:white; }
    h2 { font-size:25px; margin:24px 0 12px; }
    .theme-box,.card { background:var(--card); border-radius:24px; box-shadow:0 8px 22px rgba(0,0,0,.09); border:1px solid var(--line); }
    .theme-box { padding:12px; }
    .theme-row { padding:13px 10px; border-bottom:1px solid var(--line); }
    .theme-row:last-child { border-bottom:none; }
    .theme-row b { display:block; font-size:17px; }
    .theme-row span { display:block; color:var(--sub); font-size:13px; margin-top:3px; }
    .card { padding:18px; margin:14px 0; }
    .top-line { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
    .rank { background:#ef4444; color:white; padding:6px 12px; border-radius:999px; font-weight:900; font-size:14px; }
    .watch-rank { background:#2563eb; }
    .market { background:#e5e7eb; color:#374151; padding:6px 10px; border-radius:999px; font-weight:800; font-size:13px; }
    .name { font-size:28px; font-weight:900; margin:12px 0 6px; }
    .theme { display:inline-block; background:#eef2ff; color:#3730a3; border-radius:999px; padding:6px 11px; font-size:13px; font-weight:800; }
    .grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:14px; }
    .metric { background:#f9fafb; border-radius:16px; padding:12px; }
    .metric span { display:block; color:var(--sub); font-size:12px; }
    .metric b { display:block; font-size:19px; margin-top:4px; }
    .red { color:var(--red); } .blue { color:var(--blue); }
    .opinion { background:var(--yellow); border-radius:16px; padding:13px; margin-top:14px; line-height:1.55; color:#374151; font-size:14px; }
    .section { display:none; } .section.active { display:block; }
    .footer { color:var(--sub); font-size:12px; text-align:center; margin-top:28px; line-height:1.5; }
    .install-tip { background:#ecfeff; color:#164e63; border-radius:18px; padding:13px; line-height:1.5; font-size:14px; margin-top:12px; border:1px solid #a5f3fc; }
    .premium-card {
  position: relative;
  overflow: hidden;
}

.premium-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 5px;
  background: linear-gradient(90deg, #ef4444, #f97316, #2563eb);
}

.name-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-top: 10px;
}

.score-circle {
  min-width: 78px;
  height: 78px;
  border-radius: 22px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: white;
  box-shadow: 0 10px 24px rgba(0,0,0,.18);
}

.score-circle small {
  font-size: 11px;
  opacity: .9;
}

.score-circle b {
  font-size: 24px;
  line-height: 1.1;
}

.score-hot {
  background: linear-gradient(135deg, #dc2626, #f97316);
}

.score-mid {
  background: linear-gradient(135deg, #2563eb, #4f46e5);
}

.score-low {
  background: linear-gradient(135deg, #6b7280, #111827);
}

.grade {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 900;
}

.grade.strong {
  background: #fee2e2;
  color: #991b1b;
}

.grade.normal {
  background: #dbeafe;
  color: #1e40af;
}

.grade.watch {
  background: #f3f4f6;
  color: #374151;
}

.premium-grid {
  margin-top: 16px;
}

.ai-box {
  margin-top: 15px;
  background: linear-gradient(135deg, #111827, #1e3a8a);
  color: white;
  border-radius: 18px;
  padding: 15px;
  line-height: 1.55;
}

.ai-box p {
  margin: 7px 0 0;
  font-size: 14px;
  opacity: .95;
}

.ai-title {
  font-weight: 900;
  font-size: 15px;
}

.detail-box {
  margin-top: 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  padding: 14px;
}

.detail-title {
  font-weight: 900;
  margin-bottom: 8px;
  font-size: 15px;
}

.detail-box ul {
  margin: 0;
  padding-left: 18px;
}

.detail-box li {
  margin: 6px 0;
  line-height: 1.5;
  font-size: 14px;
  color: #374151;
}

.strategy-box {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.risk-box {
  background: #fffbeb;
  border-color: #fde68a;
}

@media (max-width: 480px) {
  .name-row {
    align-items: stretch;
  }

  .score-circle {
    min-width: 70px;
    height: 70px;
    border-radius: 20px;
  }

  .score-circle b {
    font-size: 21px;
  }

  .name {
    font-size: 25px;
  }
}
body {
  background:
    radial-gradient(circle at top left, #fff7d6 0, transparent 32%),
    radial-gradient(circle at top right, #dff7e8 0, transparent 30%),
    linear-gradient(180deg, #fffaf0 0%, #eef8ee 55%, #f7efe3 100%);
  color: #243025;
}

.hero {
  background: linear-gradient(135deg, #6fa87a, #8fbf91, #f2c879);
  color: #23301f;
  box-shadow: 0 18px 40px rgba(105, 140, 92, .28);
  border: 1px solid rgba(255,255,255,.65);
}

.hero p,
.mini {
  color: #2f3b29;
  opacity: .95;
}

.hero-grid div {
  background: rgba(255,255,255,.45);
  color: #243025;
  backdrop-filter: blur(10px);
}

.control,
.card,
.theme-box {
  background: rgba(255, 255, 248, .86);
  border: 1px solid rgba(255,255,255,.9);
  box-shadow: 0 18px 38px rgba(98, 126, 86, .18);
  backdrop-filter: blur(12px);
}

button {
  background: linear-gradient(135deg, #e9a95b, #f5c16c, #9fcf8f);
  color: #2f2a1e;
  box-shadow: 0 12px 26px rgba(190, 142, 75, .28);
}

.notice {
  background: #48634d;
  color: #fffdf4;
}

.tab {
  background: rgba(255,255,248,.9);
  color: #63705f;
  border: 1px solid rgba(180, 200, 160, .45);
}

.tab.active {
  background: linear-gradient(135deg, #526b4f, #7fa36f);
  color: #fffdf5;
}

.rank {
  background: #e98b58;
}

.watch-rank {
  background: #78a978;
}

.market {
  background: #eef2df;
  color: #4c5c47;
}

.theme {
  background: #fff3c7;
  color: #74622a;
}

.metric {
  background: rgba(250, 248, 235, .9);
}

.premium-card::before {
  background: linear-gradient(90deg, #f0b86a, #9bcf8f, #88b7d6);
}

.ai-box {
  background: linear-gradient(135deg, #5d7758, #8aaa73);
  color: #fffdf4;
}

.detail-box {
  background: rgba(255, 252, 236, .9);
  border-color: #eadfbf;
}

.strategy-box {
  background: #eef8e8;
  border-color: #cfe7c5;
}

.risk-box {
  background: #fff4d6;
  border-color: #efd18d;
}

.score-hot {
  background: linear-gradient(135deg, #e68a54, #f0bd68);
}

.score-mid {
  background: linear-gradient(135deg, #7fa36f, #9fcf8f);
}

.score-low {
  background: linear-gradient(135deg, #8f9d82, #5c6b55);
}

.grade.strong {
  background: #ffe5ca;
  color: #9c4f23;
}

.grade.normal {
  background: #e6f4dc;
  color: #3f6b35;
}

.grade.watch {
  background: #f4eddc;
  color: #6b5b3f;
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

  <script>
    function showTab(id, el) {
      document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.getElementById(id).classList.add('active');
      el.classList.add('active');
    }

    function fmtPrice(v) { return (v === null || v === undefined) ? "-" : Number(v).toLocaleString() + "원"; }

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

function badgeLevel(item) {
  if (item.score >= 70) return '<span class="grade strong">강한 후보</span>';
  if (item.score >= 50) return '<span class="grade normal">관심 후보</span>';
  return '<span class="grade watch">관찰 필요</span>';
}

function listHtml(arr) {
  if (!arr || arr.length === 0) return "";
  return arr.map(x => `<li>${x}</li>`).join("");
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
        <div class="metric">
          <span>현재가</span>
          <b>${fmtPrice(item.price)}</b>
        </div>

        <div class="metric">
          <span>AI 점수</span>
          <b>${item.score}</b>
        </div>

        <div class="metric">
          <span>5일 수익률</span>
          ${fmtRate(item.return5)}
        </div>

        <div class="metric">
          <span>20일 수익률</span>
          ${fmtRate(item.return20)}
        </div>

        <div class="metric">
          <span>거래량강도</span>
          <b>${item.volumePower}</b>
        </div>

        <div class="metric">
          <span>추세강도</span>
          <b>${item.trendPower}</b>
        </div>
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

    </div>
  `;
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
        document.getElementById("analyzedCount").innerText = data.analyzedCount || 0;
        document.getElementById("recommendList").innerHTML = data.recommend.map(item => makeCard(item, "recommend")).join("");
        document.getElementById("watchList").innerHTML = data.watch.map(item => makeCard(item, "watch")).join("");
        document.getElementById("themeList").innerHTML = data.summary.map(t => `
          <div class="theme-row">
            <b>${t.theme}</b>
            <span>평균점수 ${t.avgScore} · 최고점수 ${t.maxScore} · 종목수 ${t.count}개</span>
          </div>
        `).join("");
        loading.style.display = "none";
        window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (e) {
        loading.innerHTML = "<b>오류가 발생했습니다.</b><p>잠시 후 다시 실행해 주세요.</p>";
      }
    }
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
