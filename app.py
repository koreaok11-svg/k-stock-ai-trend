
import os
from datetime import datetime

import pandas as pd
import yfinance as yf
from pykrx import stock
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
    today = datetime.now().strftime("%Y%m%d")
    rows = []
    for market, suffix in [("KOSPI", ".KS"), ("KOSDAQ", ".KQ")]:
        tickers = stock.get_market_ticker_list(today, market=market)
        for t in tickers:
            rows.append({
                "market": market,
                "code": t,
                "name": stock.get_market_ticker_name(t),
                "ticker": t + suffix
            })

    df = pd.DataFrame(rows)
    if limit:
        df = df.head(int(limit))
    return df

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

        theme = THEME_MAP.get(row["name"], "미분류")
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
    if category == "추천":
        text = "현재 전체 분석 종목 중 상위권입니다. 주가 흐름, 거래량, 추세가 동시에 강한 편입니다."
    elif category == "관심":
        text = "관심권 종목입니다. 눌림목과 거래대금 유지 여부를 확인하는 전략이 좋습니다."
    else:
        text = "관찰 단계입니다."

    if item["theme"] != "미분류":
        text += f" 관련 테마는 {item['theme']}입니다."
    else:
        text += " 테마는 자동 분류되지 않았으므로 별도 확인이 필요합니다."

    if item["return5"] >= 20:
        text += " 최근 5일 상승률이 커서 추격매수는 주의가 필요합니다."
    if item["return20"] >= 40:
        text += " 최근 20일 상승률이 높아 단기 과열 여부를 확인해야 합니다."
    if item["volumePower"] >= 2:
        text += " 최근 거래량이 평소보다 크게 증가해 시장 관심이 붙은 상태입니다."
    return text

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/analyze")
def api_analyze():
    limit = int(request.args.get("limit", "700"))
    limit = max(100, min(limit, 1600))

    rows = get_market_df(limit=limit)
    results = []
    for _, row in rows.iterrows():
        item = analyze_one(row)
        if item:
            results.append(item)

    if not results:
        return jsonify({"updated": datetime.now().strftime("%Y-%m-%d %H:%M"), "analyzedCount": 0, "summary": [], "recommend": [], "watch": [], "all": []})

    df = pd.DataFrame(results).sort_values("score", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    df["category"] = "관찰"
    df.loc[:9, "category"] = "추천"
    df.loc[10:39, "category"] = "관심"

    records = df.to_dict(orient="records")
    for item in records:
        item["opinion"] = make_opinion(item, item["category"])

    theme_summary = (
        df.groupby("theme")
        .agg(avgScore=("score", "mean"), maxScore=("score", "max"), count=("name", "count"))
        .sort_values("avgScore", ascending=False)
        .reset_index()
    )

    summary = []
    for _, row in theme_summary.head(8).iterrows():
        summary.append({"theme": row["theme"], "avgScore": round(float(row["avgScore"]), 2), "maxScore": round(float(row["maxScore"]), 2), "count": int(row["count"])})

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

    function makeCard(item, type) {
      const rankClass = type === "watch" ? "rank watch-rank" : "rank";
      return `
        <div class="card">
          <div class="top-line">
            <span class="${rankClass}">#${item.rank} ${item.category}</span>
            <span class="market">${item.market}</span>
            <span class="market">${item.code}</span>
          </div>
          <div class="name">${item.name}</div>
          <div class="theme">${item.theme}</div>
          <div class="grid">
            <div class="metric"><span>현재가</span><b>${fmtPrice(item.price)}</b></div>
            <div class="metric"><span>종합점수</span><b>${item.score}</b></div>
            <div class="metric"><span>5일 수익률</span>${fmtRate(item.return5)}</div>
            <div class="metric"><span>20일 수익률</span>${fmtRate(item.return20)}</div>
            <div class="metric"><span>거래량강도</span><b>${item.volumePower}</b></div>
            <div class="metric"><span>추세강도</span><b>${item.trendPower}</b></div>
          </div>
          <div class="opinion">💬 ${item.opinion}</div>
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
