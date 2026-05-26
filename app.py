# -*- coding: utf-8 -*-
"""
성일의 AI 주식바람 - KIWOOM REAL AUTO SCALPING v152 AI CANDIDATE CONDITIONS UPGRADE
파일명: app_kiwoom_real_auto_scalping_v152_ai_candidate_conditions_upgrade.py

목표:
- 누적 패치/중복 route/inject 제거
- 모바일 보기 좋은 컴팩트 UI
- 키움 인증 실패 메시지 1개만 표시
- 화면확인용 수동 보유표시 제거
- 실제 보유는 키움 REST 잔고 또는 마지막 정상 캐시만 표시
- 보유카드 직접 시장가 매도 버튼
- AI후보 축소 카드 + 터치 상세 펼침

v152 보강:
- AI 전략별 성과 누적 저장
- 실체결 기준 손익 계산용 매매 원장
- 1일/1주/1개월 전략 랭킹
- 시장역행 강세 점수
- 과열/추격매수/슬리피지 위험 감점
- 최소 주문금액/예수금 방어 강화
- 상태/보유/전략성과/매매로그 자동 백업
"""

import os, re, json, time, math, threading
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import requests
from flask import Flask, jsonify, request, render_template_string

try:
    import pandas as pd
except Exception:
    pd = None

try:
    import FinanceDataReader as fdr
except Exception:
    fdr = None


APP_VERSION = "v152"
APP_NAME = "성일의 AI 주식바람"
KST = timezone(timedelta(hours=9))
app = Flask(__name__)

BASE_DIR = Path(os.getenv("APP_DATA_DIR", "/var/data" if os.path.isdir("/var/data") else "/tmp"))
BASE_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = BASE_DIR / "sungil_trade_state_v152.json"
HOLDINGS_FILE = BASE_DIR / "sungil_holdings_v152.json"
HOLDINGS_BACKUP_FILE = BASE_DIR / "sungil_holdings_last_good_v152.json"
CANDIDATE_FILE = BASE_DIR / "sungil_candidates_v152.json"
PERFORMANCE_FILE = BASE_DIR / "sungil_strategy_performance_v152.json"
TRADE_LEDGER_FILE = BASE_DIR / "sungil_trade_ledger_v152.json"
BACKUP_DIR = BASE_DIR / "sungil_backups_v152"
try:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

DATA_LOCK = threading.RLock()
WATCH_LOCK = threading.RLock()

KIWOOM_BASE_URL = os.getenv("KIWOOM_BASE_URL", "https://api.kiwoom.com").rstrip("/")
KIWOOM_APP_KEY = os.getenv("KIWOOM_APP_KEY", "").strip()
KIWOOM_SECRET_KEY = (
    os.getenv("KIWOOM_SECRET_KEY", "")
    or os.getenv("KIWOOM_APP_SECRET", "")
    or os.getenv("KIWOOM_SECRET", "")
).strip()
KIWOOM_REAL_TRADING = os.getenv("KIWOOM_REAL_TRADING", "false").lower() == "true"
KIWOOM_DRY_RUN = os.getenv("KIWOOM_DRY_RUN", "true").lower() == "true"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

TOKEN_CACHE = {"token": "", "expires": 0, "last_error": ""}
WATCH_STATE = {"running": False, "thread": None, "last_check": "", "last_message": ""}

DEFAULT_STATE = {
    "auto_trade_enabled": False,
    "panic_stop": False,
    "daily_realized_pnl": 0,
    "trade_count_today": 0,
    "last_trade_date": "",
    "target_rate": 0.027,
    "stop_rate": -0.018,
    "profit_guard_rate": 0.012,
    "trailing_stop_rate": 0.011,
    "max_positions": 3,
    "min_order_cash": 50000,
    "min_ai_score": 60,
    "max_day_change": 12,
    "min_amount": 3000000000,
    "volume_keep_filter": 0.55,
    "index_weak_buy_scale": 0.5,
    "daily_max_loss": -30000,
    "last_status": "대기중",
    "last_status_time": "",
    "last_message": "",
    "last_kiwoom_debug": {},
    "last_telegram_status": "",
    "recent_alerts": [],
    "current_strategy": "AI후보형",
    "recommended_strategy": "AI후보형",
    "switch_buy_enabled": False,
    "rebuy_cooldown_minutes": 30,
    "last_sell_times": {},
    "index_risk_mode": "NORMAL",
}


THEME_MAP = {
    "제주반도체": "AI반도체/HBM", "삼성전자": "AI반도체/HBM", "SK하이닉스": "AI반도체/HBM",
    "한미반도체": "AI반도체/HBM", "SFA반도체": "AI반도체/HBM", "하나마이크론": "AI반도체/HBM",
    "대한광통신": "광통신/CPO", "오이솔루션": "광통신/CPO", "쏠리드": "광통신/CPO",
    "대한전선": "전력설비/데이터센터", "효성중공업": "전력설비/데이터센터",
    "HD현대일렉트릭": "전력설비/데이터센터", "LS ELECTRIC": "전력설비/데이터센터",
    "삼성전기": "전력설비/데이터센터", "이수페타시스": "AI서버/PCB",
}
FALLBACK_CANDIDATES = [
    {"market": "KOSDAQ", "code": "080220", "name": "제주반도체", "theme": "AI반도체/HBM", "price": 122800, "dayChange": 4.24, "amount": 93040000000, "score": 92.5},
    {"market": "KOSPI", "code": "010140", "name": "삼성중공업", "theme": "조선/방산", "price": 29550, "dayChange": 2.73, "amount": 110870000000, "score": 88.3},
    {"market": "KOSPI", "code": "009150", "name": "삼성전기", "theme": "전력설비/데이터센터", "price": 126200, "dayChange": 4.82, "amount": 245450000000, "score": 86.7},
]


def now_kst():
    return datetime.now(KST)


def now_text():
    return now_kst().strftime("%Y-%m-%d %H:%M:%S")


def safe_float(v, default=0.0):
    try:
        if v is None:
            return default
        if isinstance(v, str):
            v = v.replace(",", "").strip()
            if not v:
                return default
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except Exception:
        return default


def safe_int(v, default=0):
    try:
        return int(safe_float(v, default))
    except Exception:
        return default


def money(v):
    return f"{int(round(safe_float(v, 0))):,}원"


def pct(v):
    return f"{safe_float(v, 0):.2f}%"


def read_json(path, default):
    with DATA_LOCK:
        try:
            if Path(path).exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return default


def write_json(path, data):
    with DATA_LOCK:
        path = Path(path)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)




def backup_json_file(path, label):
    """상태/보유/성과 파일을 자동 백업합니다. 최근 30개만 유지합니다."""
    try:
        path = Path(path)
        if not path.exists():
            return False
        ts = now_kst().strftime("%Y%m%d_%H%M%S")
        dst = BACKUP_DIR / f"{label}_{ts}.json"
        dst.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        old = sorted(BACKUP_DIR.glob(f"{label}_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        for x in old[30:]:
            try: x.unlink()
            except Exception: pass
        return True
    except Exception:
        return False


def auto_backup_all():
    try:
        for p,label in [(STATE_FILE,'state'),(HOLDINGS_FILE,'holdings'),(HOLDINGS_BACKUP_FILE,'holdings_last_good'),(PERFORMANCE_FILE,'performance'),(TRADE_LEDGER_FILE,'trade_ledger')]:
            backup_json_file(p,label)
        return True
    except Exception:
        return False

def read_state():
    state = dict(DEFAULT_STATE)
    saved = read_json(STATE_FILE, {})
    if isinstance(saved, dict):
        state.update(saved)
    return state


def write_state(state):
    write_json(STATE_FILE, state)


def set_status(status, message="", extra=None):
    state = read_state()
    state["last_status"] = status
    state["last_status_time"] = now_text()
    state["last_message"] = str(message or "")[:800]
    if extra:
        state.update(extra)
    write_state(state)
    return state


def add_alert(text):
    state = read_state()
    alerts = state.get("recent_alerts", [])
    alerts.insert(0, {"time": now_kst().strftime("%H:%M:%S"), "text": str(text)[:200]})
    state["recent_alerts"] = alerts[:5]
    write_state(state)


def auth_message(msg):
    s = str(msg or "")
    if "8050" in s or "지정단말기" in s or "인증에 실패" in s:
        return "키움 인증 실패(8050/지정단말기)입니다. Render IP 등록, App Key/Secret 재발급·입력, 영웅문S# 지정단말기/추가인증 상태를 확인하세요."
    if "App Key" in s or "Secret" in s or "8001" in s or "8002" in s:
        return "키움 App Key/Secret 확인이 필요합니다. Render 환경변수를 다시 확인하세요."
    if not KIWOOM_APP_KEY or not KIWOOM_SECRET_KEY:
        return "키움 환경변수 KIWOOM_APP_KEY / KIWOOM_SECRET_KEY가 필요합니다."
    return s or "키움 API 미확인"


def update_kiwoom_debug(stage, message="", http_status=0):
    state = read_state()
    state["last_kiwoom_debug"] = {
        "time": now_text(),
        "stage": stage,
        "http_status": http_status,
        "message": auth_message(message),
    }
    write_state(state)


def kiwoom_ready():
    return bool(KIWOOM_APP_KEY and KIWOOM_SECRET_KEY)


def get_kiwoom_token():
    if TOKEN_CACHE["token"] and time.time() < TOKEN_CACHE["expires"]:
        return TOKEN_CACHE["token"]
    if not kiwoom_ready():
        msg = auth_message("")
        update_kiwoom_debug("env_missing", msg)
        raise RuntimeError(msg)
    try:
        r = requests.post(
            KIWOOM_BASE_URL + "/oauth2/token",
            json={"grant_type": "client_credentials", "appkey": KIWOOM_APP_KEY, "secretkey": KIWOOM_SECRET_KEY},
            headers={"Content-Type": "application/json;charset=UTF-8"},
            timeout=8,
        )
        try:
            data = r.json() if r.text else {}
        except Exception:
            data = {"raw": r.text[:300]}
        token = data.get("token")
        if r.status_code != 200 or not token:
            msg = data.get("return_msg") or data.get("message") or str(data)[:300]
            update_kiwoom_debug("token_fail", msg, r.status_code)
            raise RuntimeError(auth_message(msg))
        TOKEN_CACHE.update({"token": token, "expires": time.time() + 23 * 3600, "last_error": ""})
        update_kiwoom_debug("token_ok", "키움 토큰 정상", r.status_code)
        return token
    except Exception as e:
        TOKEN_CACHE["last_error"] = str(e)
        update_kiwoom_debug("token_exception", str(e))
        raise


def kiwoom_post(path, api_id, body=None, timeout=8):
    token = get_kiwoom_token()
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "authorization": "Bearer " + token,
        "cont-yn": "N",
        "next-key": "",
        "api-id": api_id,
    }
    r = requests.post(KIWOOM_BASE_URL + path, json=body or {}, headers=headers, timeout=timeout)
    try:
        data = r.json() if r.text else {}
    except Exception:
        data = {"raw": r.text[:1000]}
    return r.status_code, data


def deep_find_number(obj, keywords):
    best = 0
    if isinstance(obj, dict):
        for k, v in obj.items():
            if any(w in str(k) for w in keywords):
                val = abs(safe_float(str(v).replace("+", "").replace("-", ""), 0))
                best = max(best, val)
            best = max(best, deep_find_number(v, keywords))
    elif isinstance(obj, list):
        for item in obj:
            best = max(best, deep_find_number(item, keywords))
    return best


def parse_price(data):
    return deep_find_number(data, ["cur_prc", "현재가", "currentPrice", "stck_prpr", "closePrice", "lastPrice"])


def get_kiwoom_price(code):
    code = str(code).zfill(6)
    try:
        st, data = kiwoom_post("/api/dostk/stkinfo", "ka10001", {"stk_cd": code}, timeout=5)
        p = parse_price(data)
        if st == 200 and p >= 10:
            return p, "KIWOOM"
        update_kiwoom_debug("price_fail", str(data)[:300], st)
    except Exception as e:
        update_kiwoom_debug("price_exception", str(e))
    return 0, "NONE"


def get_naver_price(code):
    code = str(code).zfill(6)
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"}
    for url in [f"https://m.stock.naver.com/api/stock/{code}/basic", f"https://api.stock.naver.com/stock/{code}/basic"]:
        try:
            r = requests.get(url, headers=headers, timeout=3)
            if r.status_code == 200:
                data = r.json()
                for key in ["closePrice", "now", "lastPrice", "currentPrice"]:
                    if key in data:
                        p = safe_float(str(data[key]).replace(",", ""))
                        if p >= 10:
                            return p, "NAVER"
        except Exception:
            pass
    return 0, "NONE"


def get_trade_price(code, fallback=True):
    p, src = get_kiwoom_price(code)
    if p >= 10:
        return p, src
    if fallback:
        return get_naver_price(code)
    return 0, "NONE"


def parse_cash(data):
    orderable = deep_find_number(data, ["주문가능", "매수가능", "ord_psbl", "buy_psbl", "available", "avail"])
    deposit = deep_find_number(data, ["예수금", "deposit", "dpst", "cash", "현금"])
    return int(orderable or deposit or 0)


def get_cash_info():
    if not kiwoom_ready():
        return {"ok": False, "cash": 0, "source": "NONE", "message": auth_message("")}
    endpoints = [("kt00001", {"qry_tp": "3"}), ("kt00004", {"qry_tp": "3"}), ("kt00018", {"qry_tp": "3"})]
    last = ""
    for api_id, body in endpoints:
        try:
            st, data = kiwoom_post("/api/dostk/acnt", api_id, body, timeout=7)
            cash = parse_cash(data)
            if st == 200 and cash > 0:
                return {"ok": True, "cash": cash, "source": "KIWOOM", "message": "키움 주문가능금액 조회 성공"}
            last = str(data)[:300]
            update_kiwoom_debug("cash_fail", last, st)
        except Exception as e:
            last = str(e)
            update_kiwoom_debug("cash_exception", last)
    return {"ok": False, "cash": 0, "source": "NONE", "message": auth_message(last)}


def parse_holdings(data):
    if not isinstance(data, dict):
        return []
    lists = []
    for v in data.values():
        if isinstance(v, list):
            lists.append(v)
        elif isinstance(v, dict):
            for vv in v.values():
                if isinstance(vv, list):
                    lists.append(vv)
    out = []
    for arr in lists:
        for item in arr:
            if not isinstance(item, dict):
                continue
            raw = json.dumps(item, ensure_ascii=False)
            code = ""
            for key in ["stk_cd", "code", "종목코드", "pdno"]:
                if key in item:
                    code = re.sub(r"[^0-9]", "", str(item.get(key, ""))).zfill(6)
                    break
            if not code or code == "000000":
                m = re.search(r"\b(\d{6})\b", raw)
                code = m.group(1) if m else ""
            name = ""
            for key in ["stk_nm", "name", "종목명", "prdt_name"]:
                if key in item:
                    name = str(item.get(key, "")).strip()
                    break
            qty = deep_find_number(item, ["보유수량", "poss_qty", "hldg_qty", "qty", "수량"])
            buy = deep_find_number(item, ["평균단가", "매입가", "pchs_avg", "buyPrice", "매수가"])
            if code and qty > 0:
                cur, src = get_trade_price(code, fallback=True)
                if cur <= 0:
                    cur = buy
                    src = "CACHE"
                h = normalize_holding({
                    "code": code, "name": name or code, "qty": int(qty), "buyPrice": int(buy or cur),
                    "lastPrice": int(cur), "priceSource": src, "lastCheckedAt": now_text(),
                    "target": int((buy or cur) * 1.027), "stop": int((buy or cur) * 0.982),
                })
                out.append(h)
    # 중복 제거
    unique = {}
    for h in out:
        unique[h["code"]] = h
    return list(unique.values())


def fetch_kiwoom_holdings():
    if not kiwoom_ready():
        return {"ok": False, "holdings": [], "message": auth_message(""), "source": "NONE"}
    last = ""
    for api_id in ["kt00018", "kt00004", "kt00001"]:
        try:
            st, data = kiwoom_post("/api/dostk/acnt", api_id, {"qry_tp": "3"}, timeout=8)
            items = parse_holdings(data)
            if st == 200 and items:
                write_json(HOLDINGS_FILE, items)
                write_json(HOLDINGS_BACKUP_FILE, {"time": now_text(), "items": items})
                return {"ok": True, "holdings": items, "message": f"키움 실보유 {len(items)}종목 조회 성공", "source": "KIWOOM"}
            last = str(data)[:300]
            update_kiwoom_debug("holdings_empty_or_fail", last, st)
        except Exception as e:
            last = str(e)
            update_kiwoom_debug("holdings_exception", last)
    cached = get_cached_holdings()
    return {"ok": False, "holdings": cached, "message": auth_message(last) if last else "키움 보유 조회 실패", "source": "CACHE" if cached else "EMPTY"}


def get_cached_holdings():
    data = read_json(HOLDINGS_BACKUP_FILE, {})
    if isinstance(data, dict) and isinstance(data.get("items"), list) and data["items"]:
        return data["items"]
    items = read_json(HOLDINGS_FILE, [])
    return items if isinstance(items, list) else []


def normalize_holding(h):
    h = dict(h or {})
    buy = safe_float(h.get("buyPrice") or h.get("buy") or h.get("avgPrice"), 0)
    cur = safe_float(h.get("lastPrice") or h.get("price") or buy, 0)
    qty = safe_int(h.get("qty") or h.get("quantity"), 0)
    target = safe_float(h.get("target"), buy * 1.027 if buy else cur * 1.027)
    stop = safe_float(h.get("stop"), buy * 0.982 if buy else cur * 0.982)

    high = max(safe_float(h.get("highestPrice"), 0), cur, buy)
    base_target = safe_float(h.get("baseTarget"), target)
    dynamic_target = safe_float(h.get("activeDynamicTarget"), 0)
    if cur > base_target:
        dynamic_target = max(dynamic_target, cur * 1.012)
    trail = safe_float(h.get("trailingStopPrice"), 0)
    if high > base_target:
        trail = max(trail, high * (1 - safe_float(read_state().get("trailing_stop_rate", 0.011), 0.011)))

    h.update({
        "code": str(h.get("code", "")).zfill(6),
        "name": h.get("name") or h.get("code", ""),
        "qty": qty,
        "buyPrice": int(buy),
        "lastPrice": int(cur),
        "target": int(target),
        "stop": int(stop),
        "baseTarget": int(base_target),
        "activeDynamicTarget": int(dynamic_target) if dynamic_target else 0,
        "trailingStopPrice": int(trail) if trail else 0,
        "highestPrice": int(high),
        "profitRate": ((cur - buy) / buy * 100) if buy else 0,
        "pnl": int((cur - buy) * qty) if buy and qty else 0,
    })
    return h


def read_holdings():
    return [normalize_holding(h) for h in get_cached_holdings()]


def write_holdings(items):
    items = [normalize_holding(h) for h in (items or []) if safe_int(h.get("qty"), 0) > 0]
    write_json(HOLDINGS_FILE, items)
    if items:
        write_json(HOLDINGS_BACKUP_FILE, {"time": now_text(), "items": items})


def remove_holding(code):
    code = str(code).zfill(6)
    items = [h for h in read_holdings() if str(h.get("code")).zfill(6) != code]
    write_holdings(items)
    return items


def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "텔레그램 환경변수가 없습니다."
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": True},
            timeout=5,
        )
        ok = r.status_code == 200
        return ok, "발송 성공" if ok else r.text[:300]
    except Exception as e:
        return False, str(e)



STRATEGIES = ["AI후보형", "안정형", "테마추종형", "가치형", "공격형"]

def strategy_from_candidate(c):
    score = safe_float(c.get('score'), 0)
    day = safe_float(c.get('dayChange'), 0)
    amt = safe_float(c.get('amount'), 0)
    theme = str(c.get('theme',''))
    if day >= 5.5 and score >= 90:
        return "공격형"
    if "AI" in theme or "전력" in theme or "광통신" in theme:
        return "테마추종형"
    if amt >= 100_000_000_000 and day <= 4.5:
        return "안정형"
    if day <= 2.0 and amt >= 50_000_000_000:
        return "가치형"
    return "AI후보형"

def read_ledger():
    data = read_json(TRADE_LEDGER_FILE, [])
    return data if isinstance(data, list) else []

def write_ledger(items):
    write_json(TRADE_LEDGER_FILE, items[-500:])
    backup_json_file(TRADE_LEDGER_FILE, 'trade_ledger')

def append_trade_event(event):
    items = read_ledger()
    event = dict(event or {})
    event.setdefault('time', now_text())
    event.setdefault('date', now_kst().strftime('%Y-%m-%d'))
    items.append(event)
    write_ledger(items)
    return event

def read_performance():
    data = read_json(PERFORMANCE_FILE, {})
    if not isinstance(data, dict):
        data = {}
    for s in STRATEGIES:
        data.setdefault(s, {'trades':0,'wins':0,'losses':0,'realized_pnl':0,'total_return_pct':0.0,'avg_pnl':0.0,'history':[]})
    return data

def write_performance(data):
    write_json(PERFORMANCE_FILE, data)
    backup_json_file(PERFORMANCE_FILE, 'performance')

def record_strategy_result(strategy, pnl, buy_value=0, reason='sell', code='', name=''):
    strategy = strategy if strategy in STRATEGIES else 'AI후보형'
    pnl = safe_float(pnl,0); buy_value=safe_float(buy_value,0)
    ret = (pnl / buy_value * 100) if buy_value else 0
    perf = read_performance(); row = perf[strategy]
    row['trades'] = int(row.get('trades',0)) + 1
    row['wins'] = int(row.get('wins',0)) + (1 if pnl > 0 else 0)
    row['losses'] = int(row.get('losses',0)) + (1 if pnl <= 0 else 0)
    row['realized_pnl'] = safe_float(row.get('realized_pnl',0)) + pnl
    row['total_return_pct'] = safe_float(row.get('total_return_pct',0)) + ret
    row['avg_pnl'] = row['realized_pnl'] / max(1,row['trades'])
    hist = row.setdefault('history', [])
    hist.insert(0, {'time':now_text(),'date':now_kst().strftime('%Y-%m-%d'),'code':code,'name':name,'pnl':int(pnl),'return_pct':round(ret,2),'reason':reason})
    row['history'] = hist[:300]
    write_performance(perf)
    return row

def strategy_rankings(days=1):
    cutoff = now_kst() - timedelta(days=int(days))
    perf = read_performance(); ranks=[]
    for s,row in perf.items():
        hist=[]
        for h in row.get('history',[]):
            try:
                t = datetime.strptime(h.get('time','1970-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S').replace(tzinfo=KST)
                if t >= cutoff:
                    hist.append(h)
            except Exception:
                pass
        trades=len(hist); wins=sum(1 for h in hist if safe_float(h.get('pnl'))>0); pnl=sum(safe_float(h.get('pnl')) for h in hist); ret=sum(safe_float(h.get('return_pct')) for h in hist)
        ranks.append({'strategy':s,'trades':trades,'wins':wins,'win_rate':round(wins/max(1,trades)*100,1),'pnl':int(pnl),'return_pct':round(ret,2),'avg_pnl':int(pnl/max(1,trades))})
    return sorted(ranks, key=lambda x:(x['pnl'],x['win_rate'],x['return_pct']), reverse=True)

def ai_loss_review(event):
    pnl=safe_float(event.get('pnl'),0); ret=safe_float(event.get('return_pct'),0); reason=str(event.get('reason',''))
    if pnl >= 0:
        return '익절/수익 거래입니다. 동일 조건의 거래대금 유지율과 진입 타이밍을 복기하세요.'
    if 'stop' in reason:
        return '손절 거래입니다. 진입 후 거래대금 유지 실패 또는 고점 근처 추격매수 가능성을 점검하세요.'
    if ret <= -2:
        return '손실폭이 큽니다. 슬리피지/호가 얇음/지수 약세에서 신규매수 축소 규칙을 강화하는 것이 좋습니다.'
    return '소폭 손실입니다. 매도 후 재매수 제한과 과열 감점이 정상 적용되었는지 확인하세요.'

def get_index_risk(df=None):
    try:
        if df is not None and pd is not None and not df.empty and 'dayChange' in df.columns:
            kospi = safe_float(df[df['Market']=='KOSPI']['dayChange'].mean(),0) if 'Market' in df.columns else 0
            kosdaq = safe_float(df[df['Market']=='KOSDAQ']['dayChange'].mean(),0) if 'Market' in df.columns else 0
            avg = (kospi + kosdaq) / 2
            if avg < -1.0:
                mode='DANGER'
            elif avg < -0.3:
                mode='WEAK'
            else:
                mode='NORMAL'
            return {'kospi':round(kospi,2),'kosdaq':round(kosdaq,2),'avg':round(avg,2),'mode':mode}
    except Exception:
        pass
    return {'kospi':0,'kosdaq':0,'avg':0,'mode':'UNKNOWN'}

def enrich_candidate_risk(c, index_risk=None):
    c=dict(c or {})
    day=safe_float(c.get('dayChange'),0); amt=safe_float(c.get('amount'),0); score=safe_float(c.get('score'),0)
    theme=str(c.get('theme','기타'))
    index_risk=index_risk or {'avg':0,'mode':'UNKNOWN'}
    market_avg=safe_float(index_risk.get('avg'),0)
    reverse=max(0, day - market_avg)
    theme_strength=8 if any(k in theme for k in ['AI','반도체','전력','광통신','데이터센터']) else 3
    reverse_score=min(100, max(0, reverse*12 + theme_strength + (10 if amt>=50_000_000_000 else 0)))
    overheat_penalty = 18 if day >= 10 else (10 if day >= 7 else (5 if day >= 5.5 else 0))
    slippage_penalty = 18 if amt < 10_000_000_000 else (8 if amt < 30_000_000_000 else 0)
    if day >= 7 and amt < 50_000_000_000:
        slippage_penalty += 10
    index_penalty = 8 if index_risk.get('mode')=='WEAK' else (15 if index_risk.get('mode')=='DANGER' else 0)
    final=max(0, min(150, score + reverse_score*0.18 - overheat_penalty - slippage_penalty - index_penalty))
    c.update({'marketReverseScore': round(reverse_score,2),'themeStrengthScore': theme_strength,'overheatPenalty': overheat_penalty,'slippagePenalty': slippage_penalty,'indexRiskPenalty': index_penalty,'riskAdjustedScore': round(final,2),'strategy': strategy_from_candidate(c),'riskComment': f"시장역행 {reverse_score:.1f} · 과열감점 {overheat_penalty} · 슬리피지감점 {slippage_penalty} · 지수위험 {index_penalty}"})
    return c

def classify_theme(name):
    if name in THEME_MAP:
        return THEME_MAP[name]
    if "반도체" in name:
        return "AI반도체/HBM"
    if "전기" in name or "전선" in name or "일렉" in name:
        return "전력설비/데이터센터"
    if "통신" in name or "광" in name:
        return "광통신/CPO"
    return "기타/개별이슈"


def get_market_candidates(limit=8, min_score=None):
    state_for_filter = read_state()
    if min_score is None:
        min_score = safe_float(state_for_filter.get("min_ai_score", 60), 60)
    max_day_change = safe_float(state_for_filter.get("max_day_change", 12), 12)
    min_amount = safe_float(state_for_filter.get("min_amount", 3_000_000_000), 3_000_000_000)
    candidates = []
    if fdr and pd:
        try:
            df = fdr.StockListing("KRX")
            df = df[df["Market"].isin(["KOSPI", "KOSDAQ"])].copy()
            for col in ["Close", "Volume", "Amount", "Marcap"]:
                df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)
            ch_col = "ChagesRatio" if "ChagesRatio" in df.columns else ("Change" if "Change" in df.columns else None)
            df["dayChange"] = pd.to_numeric(df[ch_col], errors="coerce").fillna(0) if ch_col else 0
            df["Code"] = df["Code"].astype(str).str.zfill(6)
            df["Name"] = df["Name"].astype(str)
            bad = ["ETF", "ETN", "스팩", "SPAC", "KODEX", "TIGER", "인버스", "레버리지"]
            df = df[~df["Name"].str.upper().apply(lambda n: any(x.upper() in n for x in bad))]
            df = df[(df["Close"] >= 1000) & (df["Amount"] >= min_amount) & (df["dayChange"] >= 0.2) & (df["dayChange"] <= max_day_change)].copy()
            if not df.empty:
                df["theme"] = df["Name"].apply(classify_theme)
                df["amountRank"] = df["Amount"].rank(pct=True) * 100
                df["volumeRank"] = df["Volume"].rank(pct=True) * 100
                df["sweet"] = (100 - (df["dayChange"] - 3.5).abs() * 7).clip(lower=30, upper=100)
                df["score"] = (df["amountRank"] * .45 + df["volumeRank"] * .25 + df["sweet"] * .30)
                df = df[df["score"] >= min_score].sort_values("score", ascending=False).head(limit)
                for _, r in df.iterrows():
                    candidates.append({
                        "market": str(r.get("Market", "")),
                        "code": str(r["Code"]).zfill(6),
                        "name": str(r["Name"]),
                        "theme": str(r["theme"]),
                        "price": int(safe_float(r["Close"], 0)),
                        "dayChange": round(safe_float(r["dayChange"], 0), 2),
                        "amount": int(safe_float(r["Amount"], 0)),
                        "score": round(safe_float(r["score"], 0), 2),
                        "source": "KRX_FAST_CACHE",
                    })
        except Exception:
            candidates = []

    if not candidates:
        candidates = [dict(x, source="FALLBACK") for x in FALLBACK_CANDIDATES]

    idx_risk = get_index_risk(df if 'df' in locals() else None)
    enriched=[]
    for c in candidates:
        p = safe_float(c["price"], 0)
        c["target"] = int(p * 1.035)
        c["stop"] = int(p * 0.975)
        c["buyZone"] = int(p * 0.995)
        c["amountText"] = f"{safe_float(c.get('amount'), 0) / 100000000:.1f}억"
        c = enrich_candidate_risk(c, idx_risk)
        c["comment"] = "화면 후보는 KRX/캐시 기준입니다. 실제 매수 직전에는 키움 현재가·주문가능금액·수수료 버퍼를 다시 확인합니다. " + c.get('riskComment','')
        enriched.append(c)
    candidates = sorted(enriched, key=lambda x: safe_float(x.get('riskAdjustedScore', x.get('score',0))), reverse=True)[:limit]
    state = read_state(); state['index_risk_mode']=idx_risk.get('mode','UNKNOWN'); state['recommended_strategy'] = candidates[0].get('strategy','AI후보형') if candidates else state.get('recommended_strategy','AI후보형'); write_state(state)
    write_json(CANDIDATE_FILE, {"time": now_text(), "items": candidates, "indexRisk": idx_risk})
    return candidates


def cached_candidates():
    data = read_json(CANDIDATE_FILE, {})
    if isinstance(data, dict) and data.get("items"):
        return data["items"]
    return get_market_candidates()


def market_is_open():
    n = now_kst()
    if n.weekday() >= 5:
        return False
    return 900 <= n.hour * 100 + n.minute <= 1520


def auto_sell_holding(reason, holding, cur_price=None):
    h = normalize_holding(holding)
    code, qty = h["code"], h["qty"]
    if qty <= 0:
        return {"ok": False, "message": "매도 수량이 없습니다."}
    if not KIWOOM_REAL_TRADING:
        return {"ok": False, "message": "KIWOOM_REAL_TRADING=true 필요. 실제 주문은 전송하지 않았습니다."}
    sell_price = safe_float(cur_price or h.get('lastPrice') or h.get('buyPrice'), 0)
    buy_value = safe_float(h.get('buyPrice'),0) * qty
    pnl = (sell_price - safe_float(h.get('buyPrice'),0)) * qty
    strategy = h.get('strategy') or read_state().get('current_strategy','AI후보형')
    if KIWOOM_DRY_RUN:
        event = append_trade_event({'side':'sell','dry_run':True,'code':code,'name':h.get('name'), 'qty':qty,'fill_price':sell_price,'buy_price':h.get('buyPrice'), 'pnl':int(pnl),'return_pct':round((pnl/buy_value*100) if buy_value else 0,2),'strategy':strategy,'reason':reason})
        record_strategy_result(strategy, pnl, buy_value, reason, code, h.get('name'))
        return {"ok": True, "message": "DRY_RUN: 실제 매도 전송 없이 성과/원장 기록", "dry_run": True, "review": ai_loss_review(event)}
    try:
        res = kiwoom_order("sell", code, qty)
        if res.get("ok"):
            remove_holding(code)
            event = append_trade_event({'side':'sell','code':code,'name':h.get('name'),'qty':qty,'fill_price':sell_price,'buy_price':h.get('buyPrice'),'pnl':int(pnl),'return_pct':round((pnl/buy_value*100) if buy_value else 0,2),'strategy':strategy,'reason':reason,'order_response':res})
            record_strategy_result(strategy, pnl, buy_value, reason, code, h.get('name'))
            state = read_state(); state.setdefault('last_sell_times',{})[code]=time.time(); write_state(state)
            send_telegram(f"매도 요청: {h['name']} {qty}주 / 사유 {reason} / 손익 {int(pnl):,}원")
        return res
    except Exception as e:
        return {"ok": False, "message": auth_message(str(e))}


def kiwoom_order(side, code, qty):
    api_id = "kt10000" if side == "buy" else "kt10001"
    body = {"dmst_stex_tp": "KRX", "stk_cd": str(code).zfill(6), "ord_qty": str(int(qty)), "ord_uv": "", "trde_tp": "3", "cond_uv": ""}
    st, data = kiwoom_post("/api/dostk/ordr", api_id, body, timeout=8)
    return {"ok": st == 200 and str(data.get("return_code", "0")) in ["0", ""], "status": st, "response": data}


def watch_loop():
    while WATCH_STATE.get("running"):
        try:
            items = read_holdings()
            updated = []
            for h in items:
                cur, src = get_trade_price(h["code"], fallback=True)
                if cur >= 10:
                    h["lastPrice"] = int(cur)
                    h["priceSource"] = src
                    h["lastCheckedAt"] = now_text()
                h = normalize_holding(h)
                if h["activeDynamicTarget"] and h["lastPrice"] >= h["baseTarget"]:
                    h["aiHoldMode"] = True
                if h["trailingStopPrice"] and h["lastPrice"] <= h["trailingStopPrice"]:
                    auto_sell_holding("trailing_stop", h, h["lastPrice"])
                elif h["lastPrice"] <= h["stop"]:
                    auto_sell_holding("stop", h, h["lastPrice"])
                updated.append(h)
            if updated:
                write_holdings(updated)
            WATCH_STATE["last_check"] = now_text()
            get_market_candidates(limit=8, min_score=60)
        except Exception as e:
            WATCH_STATE["last_message"] = str(e)[:200]
        time.sleep(20)


def ensure_watch():
    with WATCH_LOCK:
        WATCH_STATE["running"] = True
        t = WATCH_STATE.get("thread")
        if t is None or not t.is_alive():
            t = threading.Thread(target=watch_loop, daemon=True)
            WATCH_STATE["thread"] = t
            t.start()


def html_escape(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_holdings_section():
    res = fetch_kiwoom_holdings()
    items = res.get("holdings") or read_holdings()
    if not items:
        msg = res.get("message") or "표시 가능한 보유 캐시가 없습니다."
        return f"""
        <section class="card" id="holdings">
          <h2>💼 키움 실보유 자동 동기화</h2>
          <p class="muted">키움 실제 잔고 기준으로 표시합니다. 인증 실패 시 마지막 정상 캐시를 유지합니다.</p>
          <div class="btn-row">
            <button onclick="location.href='/api/refresh_holdings'">실보유 새로고침</button>
            <button class="dark" onclick="location.href='/api/status'">API 확인</button>
          </div>
          <div class="notice">{html_escape(msg)}</div>
          <div class="notice small">화면확인용 수동 표시는 제거했습니다. 실제 보유 조회 또는 마지막 정상 캐시만 표시합니다.</div>
        </section>"""
    cards = []
    for h in items:
        h = normalize_holding(h)
        dynamic = h.get("activeDynamicTarget", 0)
        trail = h.get("trailingStopPrice", 0)
        ai_note = "AI HOLD · 강세 유지 시 목표가 상향/트레일링 보호" if dynamic else "목표/손절 감시 중"
        cards.append(f"""
        <div class="holding-card">
          <div class="topline"><b>{html_escape(h['name'])}</b><span>{h['code']}</span></div>
          <div class="grid2">
            <div><label>매수가</label><b>{money(h['buyPrice'])}</b></div>
            <div><label>현재가</label><b>{money(h['lastPrice'])}</b></div>
            <div><label>기존 목표가</label><b class="red">{money(h['baseTarget'])}</b></div>
            <div><label>손절가</label><b class="blue">{money(h['stop'])}</b></div>
            <div><label>AI 상향목표</label><b class="red">{money(dynamic) if dynamic else '-'}</b></div>
            <div><label>트레일링 보호</label><b class="blue">{money(trail) if trail else '-'}</b></div>
            <div><label>수량/손익</label><b>{h['qty']}주 · {money(h['pnl'])}</b></div>
            <div><label>수익률</label><b class="red">{pct(h['profitRate'])}</b></div>
          </div>
          <div class="comment">{ai_note}<br>최근확인 {html_escape(h.get('lastCheckedAt','-'))} · {html_escape(h.get('priceSource','-'))}</div>
          <button class="sell" onclick="manualSell('{h['code']}')">시장가 매도</button>
        </div>""")
    return f"""
    <section class="card" id="holdings">
      <h2>💼 키움 실보유 자동 동기화</h2>
      <p class="muted">표시 보유 {len(items)}종목 · 출처 {html_escape(res.get('source','CACHE'))}</p>
      <div class="btn-row">
        <button onclick="location.href='/api/refresh_holdings'">실보유 새로고침</button>
        <button class="dark" onclick="location.href='/api/status'">API 확인</button>
      </div>
      {''.join(cards)}
    </section>"""


def render_candidate_card(c, idx):
    return f"""
    <div class="pick compact" onclick="toggleDetail('pick{idx}')">
      <div class="chips"><span>{html_escape(c.get('market',''))}</span><span>{c.get('code')}</span><span>{html_escape(c.get('theme',''))}</span><span>AI {safe_float(c.get('riskAdjustedScore', c.get('score'))):.1f}</span><span>역행 {safe_float(c.get('marketReverseScore')):.0f}</span><span>{html_escape(c.get('strategy','AI후보형'))}</span></div>
      <h3>{html_escape(c.get('name'))}</h3>
      <div class="grid2">
        <div><label>현재가</label><b>{money(c.get('price'))}</b><small>{html_escape(c.get('source','KRX_FAST_CACHE'))}</small></div>
        <div><label>당일 흐름</label><b>{pct(c.get('dayChange'))}</b></div>
        <div><label>목표가</label><b class="red">{money(c.get('target'))}</b></div>
        <div><label>손절가</label><b class="blue">{money(c.get('stop'))}</b></div>
      </div>
      <div id="pick{idx}" class="detail">
        거래대금 {html_escape(c.get('amountText','-'))} · 매수관찰 {money(c.get('buyZone'))}<br>
        시장역행점수 {safe_float(c.get('marketReverseScore')):.1f} · 테마강도 {safe_float(c.get('themeStrengthScore')):.0f} · 과열감점 {safe_float(c.get('overheatPenalty')):.0f} · 슬리피지감점 {safe_float(c.get('slippagePenalty')):.0f}<br>
        {html_escape(c.get('comment',''))}
      </div>
    </div>"""


def render_candidates():
    picks = cached_candidates()[:8]
    cards = "".join(render_candidate_card(c, i) for i, c in enumerate(picks))
    return f"""
    <section class="card" id="picks">
      <h2>👀 AI 추천 감시 후보</h2>
      <p class="muted">후보는 축소 표시됩니다. 종목을 누르면 상세정보가 펼쳐집니다.</p>
      {cards}
    </section>"""


def render_trade_section():
    state = read_state()
    cash = get_cash_info()
    status_badge = "🟢 키움 API 정상" if cash.get("ok") else "🟡 키움 API 미확인"
    if "8050" in str(cash.get("message")):
        status_badge = "🔴 키움 API 확인 필요"
    return f"""
    <section class="card" id="trade">
      <h2>🤖 키움 실전 자동매매</h2>
      <div class="notice">
        상태: <b>{'ON' if state.get('auto_trade_enabled') else 'OFF'}</b> · <span class="badge">{status_badge}</span><br>
        키움 주문가능금액은 실제 주문 직전에 다시 확인합니다.
      </div>
      <div class="comment">현재전략: <b>{html_escape(state.get('current_strategy','AI후보형'))}</b> · 추천전략: <b>{html_escape(state.get('recommended_strategy','AI후보형'))}</b> · 지수위험: <b>{html_escape(state.get('index_risk_mode','UNKNOWN'))}</b></div>
      <div class="btn-row">
        <button onclick="location.href='/api/auto_on'">자동매매 ON</button>
        <button onclick="location.href='/api/auto_off'">OFF</button>
        <button class="brown" onclick="location.href='/api/buy_best'">AI 즉시매수</button>
        <button class="dark" onclick="location.href='/api/panic_stop'">긴급정지</button>
      </div>
      <details>
        <summary>🔎 상세 진행내용 보기 / 숨기기</summary>
        <div class="notice small">
          최근: {html_escape(state.get('last_status','-'))} · {html_escape(state.get('last_status_time','-'))}<br>
          {html_escape(state.get('last_message',''))}<br>
          {html_escape(cash.get('message',''))}
        </div>
      </details>
    </section>"""






def render_conditions_section():
    state = read_state()
    def val(k, default=''):
        return html_escape(state.get(k, default))
    switch_on = 'checked' if state.get('switch_buy_enabled') else ''
    return f"""
    <section class="card" id="conditions">
      <h2>🧭 매매조건</h2>
      <p class="muted">현재 자동매매가 사용하는 조건입니다. 값 수정 후 저장하면 다음 AI후보 검색과 매수 판단부터 반영됩니다.</p>
      <form method="post" action="/api/update_conditions">
        <div class="form-grid">
          <label>기본 익절률(%)<input name="target_rate" value="{safe_float(state.get('target_rate'),0.027)*100:.2f}"></label>
          <label>손절률(%)<input name="stop_rate" value="{safe_float(state.get('stop_rate'),-0.018)*100:.2f}"></label>
          <label>수익보호 되돌림(%)<input name="profit_guard_rate" value="{safe_float(state.get('profit_guard_rate'),0.012)*100:.2f}"></label>
          <label>트레일링 되돌림(%)<input name="trailing_stop_rate" value="{safe_float(state.get('trailing_stop_rate'),0.011)*100:.2f}"></label>
          <label>최소 AI 점수<input name="min_ai_score" value="{safe_float(state.get('min_ai_score'),60):.1f}"></label>
          <label>최대 당일 등락률(%)<input name="max_day_change" value="{safe_float(state.get('max_day_change'),12):.1f}"></label>
          <label>최소 거래대금(원)<input name="min_amount" value="{safe_int(state.get('min_amount'),3000000000)}"></label>
          <label>최소 주문금액(원)<input name="min_order_cash" value="{safe_int(state.get('min_order_cash'),50000)}"></label>
          <label>최대 보유종목<input name="max_positions" value="{safe_int(state.get('max_positions'),3)}"></label>
          <label>매도 후 재매수 제한(분)<input name="rebuy_cooldown_minutes" value="{safe_float(state.get('rebuy_cooldown_minutes'),30):.0f}"></label>
          <label>거래대금/거래량 유지율<input name="volume_keep_filter" value="{safe_float(state.get('volume_keep_filter'),0.55):.2f}"></label>
          <label>지수 약세 신규매수 비중<input name="index_weak_buy_scale" value="{safe_float(state.get('index_weak_buy_scale'),0.5):.2f}"></label>
        </div>
        <label class="check"><input type="checkbox" name="switch_buy_enabled" {switch_on}> 전환매수 허용</label>
        <div class="btn-row"><button type="submit">매매조건 저장</button><a class="button dark" href="/api/reset_conditions">기본조건 복원</a></div>
      </form>
      <details><summary>조건 설명 보기 / 접기</summary><div class="notice small">
        최소 AI 점수와 최소 거래대금이 높을수록 후보가 줄고, 낮을수록 후보가 많아집니다.<br>
        과열/추격매수 방지는 최대 당일 등락률과 슬리피지 감점으로 적용됩니다.<br>
        전환매수는 기본 OFF이며, 사용자가 허용한 경우에만 기존 보유보다 강한 후보로 갈아타는 판단을 합니다.
      </div></details>
    </section>"""

def render_performance_section():
    r1=strategy_rankings(1); r7=strategy_rankings(7); r30=strategy_rankings(30)
    def rows(ranks):
        if not ranks:
            return '<li>성과 기록 없음</li>'
        return ''.join(f"<li><b>{html_escape(x['strategy'])}</b> · 손익 {money(x['pnl'])} · 승률 {x['win_rate']}% · {x['trades']}회</li>" for x in ranks[:5])
    ledger=read_ledger()[:5]
    reviews=''.join(f"<li>{html_escape(e.get('name',''))} {html_escape(e.get('side',''))} · {money(e.get('pnl',0)) if 'pnl' in e else money(0)} · {html_escape(ai_loss_review(e)) if safe_float(e.get('pnl',0))<0 else ''}</li>" for e in ledger) or '<li>최근 매매 원장 없음</li>'
    return f"""
    <section class="card" id="performance">
      <h2>📊 AI 전략성과/복기</h2>
      <p class="muted">실체결가 또는 주문 응답 기준으로 매매 원장을 저장하고 전략별 성과를 누적합니다.</p>
      <div class="grid2">
        <div><label>최근 1일 1위</label><b>{html_escape(r1[0]['strategy']) if r1 else '-'}</b></div>
        <div><label>최근 1주 1위</label><b>{html_escape(r7[0]['strategy']) if r7 else '-'}</b></div>
        <div><label>최근 1개월 1위</label><b>{html_escape(r30[0]['strategy']) if r30 else '-'}</b></div>
        <div><label>백업</label><b>자동</b></div>
      </div>
      <details><summary>전략 랭킹 자세히 보기</summary><div class="notice small"><b>1일</b><ul>{rows(r1)}</ul><b>1주</b><ul>{rows(r7)}</ul><b>1개월</b><ul>{rows(r30)}</ul></div></details>
      <details><summary>AI 복기 최근 매매</summary><div class="notice small"><ul>{reviews}</ul></div></details>
    </section>"""

def render_alert_center():
    state = read_state()
    alerts = state.get("recent_alerts", [])
    rows = "".join(f"<li>{html_escape(a.get('time',''))} · {html_escape(a.get('text',''))}</li>" for a in alerts) or "<li>최근 알림 없음</li>"
    return f"""
    <section class="card">
      <h2>📨 실전 알림센터</h2>
      <p class="muted">매수·매도·손절·오류 발생 시 텔레그램으로 알립니다.</p>
      <div class="btn-row">
        <button onclick="location.href='/api/telegram_test'">테스트알림</button>
      </div>
      <ul class="alerts">{rows}</ul>
    </section>"""


def render_page():
    state = read_state()
    return render_template_string(TEMPLATE,
        version=APP_VERSION,
        app_name=APP_NAME,
        holdings=render_holdings_section(),
        trade=render_trade_section(),
        candidates=render_candidates(),
        conditions=render_conditions_section(),
        performance=render_performance_section(),
        alerts=render_alert_center(),
        auto_on=state.get("auto_trade_enabled"),
    )


TEMPLATE = """
<!doctype html><html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{{app_name}} {{version}}</title>
<style>
:root{--bg:#eef7e8;--card:#fffefb;--ink:#203b2d;--muted:#667085;--green:#5c9b68;--pale:#eef8e9;--cream:#fff4d5;--dark:#2e4960;--brown:#a76b29;--red:#d12e35;--blue:#246fe0}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(90deg,#eaf5e6,#fff9db);font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;color:var(--ink);font-size:16px;line-height:1.45}
.wrap{max-width:760px;margin:0 auto;padding:18px 14px 80px}.hero{padding:16px 4px 8px}.badge{display:inline-block;background:var(--pale);border-radius:999px;padding:8px 14px;font-weight:800;color:#3d6b43}.hero h1{font-size:34px;line-height:1.05;margin:16px 0 10px}.hero p{font-size:17px;color:var(--muted);margin:0}
.nav{position:sticky;top:0;z-index:50;background:rgba(244,250,237,.92);backdrop-filter:blur(10px);display:flex;gap:8px;overflow-x:auto;padding:10px 2px 12px;border-bottom:1px solid #dbe8d5}.nav a{flex:0 0 auto;text-decoration:none;color:#285139;background:var(--pale);border-radius:999px;padding:10px 14px;font-weight:800;white-space:nowrap}
.card{background:rgba(255,255,255,.93);border:1px solid #dbe8d5;border-radius:28px;padding:22px;margin:16px 0;box-shadow:0 8px 24px rgba(32,59,45,.06)}.card h2{font-size:27px;margin:0 0 14px}.muted{color:var(--muted);font-size:16px}.notice{background:var(--cream);border-radius:20px;padding:16px;margin:12px 0;color:#6a5938}.notice.small{font-size:14px}
.btn-row{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0}button,.button{border:0;border-radius:18px;padding:13px 18px;background:var(--green);color:white;font-weight:900;font-size:16px;text-decoration:none}button.dark{background:var(--dark)}button.brown{background:var(--brown)}button.sell{background:#cf3d35;width:100%;margin-top:10px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}.grid2>div{background:#fff8e9;border-radius:18px;padding:13px;text-align:center;min-width:0}.grid2 label{display:block;color:var(--muted);font-size:13px}.grid2 b{font-size:20px}.grid2 small{display:block;color:var(--muted);font-size:12px}.red{color:var(--red)}.blue{color:var(--blue)}
.holding-card,.pick{border:1px solid #e2ead9;border-radius:22px;padding:16px;margin:12px 0;background:#fffef8}.topline{display:flex;justify-content:space-between;gap:8px;font-size:22px}.topline span{font-size:14px;background:var(--pale);border-radius:999px;padding:6px 10px}.comment{background:var(--pale);border-radius:16px;padding:12px;margin-top:10px;color:#43654a}
.chips{display:flex;flex-wrap:wrap;gap:7px}.chips span{background:var(--pale);border-radius:999px;padding:6px 10px;font-size:13px;font-weight:800}.pick h3{font-size:28px;margin:12px 0}.detail{display:none;background:var(--pale);border-radius:16px;padding:12px;margin-top:10px;color:#43654a}.detail.open{display:block}
details summary{cursor:pointer;background:var(--pale);border-radius:18px;padding:14px;font-weight:900}.alerts{margin:8px 0 0;padding-left:20px;color:#5b513d}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.form-grid label{font-weight:900;color:#334155}.form-grid input{width:100%;margin-top:6px;border:1px solid #dbe8d5;border-radius:14px;padding:12px;font-size:15px;background:#fbfdff}.check{display:block;margin:12px 0;font-weight:900}.button.dark{background:var(--dark)}
@media(max-width:430px){body{font-size:15px}.form-grid{grid-template-columns:1fr}.wrap{padding:10px 10px 70px}.hero h1{font-size:28px}.card{padding:18px;border-radius:24px}.card h2{font-size:24px}.grid2 b{font-size:18px}button{font-size:15px;padding:12px 15px}.nav a{font-size:14px;padding:9px 12px}}
</style>
<script>
function toggleDetail(id){const el=document.getElementById(id); if(el){el.classList.toggle('open')}}
async function manualSell(code){
 if(!confirm(code+' 시장가 매도를 요청할까요? 실제 주문 전 키움 인증 상태를 확인합니다.')) return;
 const r=await fetch('/api/manual_sell?code='+encodeURIComponent(code));
 const j=await r.json(); alert(j.message||JSON.stringify(j)); location.reload();
}
</script>
</head><body>
<div class="wrap">
  <div class="hero">
    <span class="badge">🌿 KIWOOM REAL AUTO {{version}}</span>
    <h1>{{app_name}}</h1>
    <p>키움 REST API 연동 · AI후보 감시 · 실보유 동기화 · 목표/손절/트레일링 · 전략성과 학습</p>
  </div>
  <div class="nav">
    <a href="#picks">🤖 AI후보</a><a href="#conditions">🧭 매매조건</a><a href="#holdings">💼 보유</a><a href="#trade">⚙️ 자동</a><a href="#performance">📊 AI전략</a><a href="#alerts">📨 알림</a>
  </div>
  {{candidates|safe}}
  {{conditions|safe}}
  {{holdings|safe}}
  {{trade|safe}}
  {{performance|safe}}
  <div id="alerts">{{alerts|safe}}</div>
</div>
</body></html>
"""


@app.route("/")
def index():
    ensure_watch()
    return render_page()


@app.route("/api/status")
def api_status():
    cash = get_cash_info()
    return jsonify({"ok": cash.get("ok"), "version": APP_VERSION, "cash": cash, "state": read_state(), "watch": WATCH_STATE})


@app.route("/api/refresh_holdings")
def api_refresh_holdings():
    res = fetch_kiwoom_holdings()
    set_status("실보유 새로고침", res.get("message", ""))
    return render_page()


@app.route("/api/holdings")
def api_holdings():
    res = fetch_kiwoom_holdings()
    return jsonify(res)


@app.route("/api/candidates")
def api_candidates():
    return jsonify({"ok": True, "items": get_market_candidates()})


@app.route("/api/auto_on")
def api_auto_on():
    state = read_state()
    state["auto_trade_enabled"] = True
    state["panic_stop"] = False
    write_state(state)
    set_status("실전 자동매매 ON", "화면 즉시 반영 완료. 잔고/가격 확인은 백그라운드에서 진행됩니다.")
    return render_page()


@app.route("/api/auto_off")
def api_auto_off():
    state = read_state()
    state["auto_trade_enabled"] = False
    write_state(state)
    set_status("자동매매 OFF", "자동매매를 중지했습니다.")
    return render_page()


@app.route("/api/panic_stop")
def api_panic_stop():
    state = read_state()
    state["auto_trade_enabled"] = False
    state["panic_stop"] = True
    write_state(state)
    set_status("긴급정지", "자동매매와 주문 요청을 중지했습니다.")
    add_alert("긴급정지 실행")
    return render_page()


@app.route("/api/buy_best")
def api_buy_best():
    picks = get_market_candidates(limit=8)
    picks = sorted(picks, key=lambda x: safe_float(x.get('riskAdjustedScore', x.get('score',0))), reverse=True)[:1]
    if not picks:
        msg = "매수 후보가 없습니다."
        set_status("매수 보류", msg)
        return jsonify({"ok": False, "message": msg})
    pick = picks[0]
    state = read_state()
    last_sell = safe_float(state.get('last_sell_times',{}).get(str(pick.get('code')).zfill(6),0),0)
    cooldown = safe_float(state.get('rebuy_cooldown_minutes',30),30) * 60
    if last_sell and time.time() - last_sell < cooldown:
        msg = "매도 후 재매수 제한 시간입니다."
        set_status("매수 보류", msg, {"last_candidate": pick})
        return jsonify({"ok": False, "message": msg, "candidate": pick})
    if state.get('index_risk_mode') in ['WEAK','DANGER'] and safe_float(pick.get('marketReverseScore'),0) < 60:
        msg = "지수 약세 구간입니다. 시장역행 점수가 부족해 신규매수를 축소합니다."
        set_status("매수 보류", msg, {"last_candidate": pick})
        return jsonify({"ok": False, "message": msg, "candidate": pick})
    if not state.get("auto_trade_enabled"):
        msg = "자동매매 OFF 상태입니다."
        set_status("매수 보류", msg, {"last_candidate": pick})
        return jsonify({"ok": False, "message": msg, "candidate": pick})
    cur, src = get_trade_price(pick["code"], fallback=False)
    if cur < 10:
        msg = "키움 현재가 확인 실패로 주문하지 않습니다."
        set_status("매수 보류", msg, {"last_candidate": pick})
        return jsonify({"ok": False, "message": msg, "candidate": pick})
    cash = get_cash_info()
    if not cash.get("ok") or safe_float(cash.get("cash"), 0) < max(safe_float(cur), safe_float(read_state().get("min_order_cash", 50000))):
        msg = "키움 주문가능금액 확인 실패 또는 부족으로 주문하지 않습니다."
        set_status("매수 보류", msg, {"last_candidate": pick})
        return jsonify({"ok": False, "message": msg, "candidate": pick, "cash": cash})
    qty = int(safe_float(cash.get("cash"), 0) * 0.96 // cur)
    if qty <= 0:
        msg = "주문 가능 수량이 없습니다."
        return jsonify({"ok": False, "message": msg})
    if not KIWOOM_REAL_TRADING or KIWOOM_DRY_RUN:
        msg = f"DRY/RUN 또는 실전주문 비활성: {pick['name']} {qty}주 주문 전송 안 함"
        append_trade_event({'side':'buy','dry_run':True,'code':pick['code'],'name':pick['name'],'qty':qty,'fill_price':int(cur),'strategy':pick.get('strategy','AI후보형'),'candidate_score':pick.get('riskAdjustedScore',pick.get('score'))})
        set_status("매수 테스트", msg, {"last_candidate": pick, "current_strategy": pick.get('strategy','AI후보형')})
        return jsonify({"ok": True, "dry_run": True, "message": msg})
    res = kiwoom_order("buy", pick["code"], qty)
    if res.get('ok'):
        append_trade_event({'side':'buy','code':pick['code'],'name':pick['name'],'qty':qty,'fill_price':int(cur),'strategy':pick.get('strategy','AI후보형'),'candidate_score':pick.get('riskAdjustedScore',pick.get('score')),'order_response':res})
    set_status("매수 요청", str(res)[:400], {"last_candidate": pick, "current_strategy": pick.get('strategy','AI후보형')})
    return jsonify(res)


@app.route("/api/manual_sell")
def api_manual_sell():
    code = str(request.args.get("code", "")).zfill(6)
    h = next((x for x in read_holdings() if str(x.get("code")).zfill(6) == code), None)
    if not h:
        return jsonify({"ok": False, "message": "보유 캐시에서 종목을 찾지 못했습니다."})
    res = auto_sell_holding("manual", h)
    return jsonify({"ok": bool(res.get("ok")), "message": res.get("message") or str(res)[:300], "result": res})



@app.route("/api/strategy_performance")
def api_strategy_performance():
    return jsonify({"ok": True, "performance": read_performance(), "rank_1d": strategy_rankings(1), "rank_1w": strategy_rankings(7), "rank_1m": strategy_rankings(30), "ledger": read_ledger()[:50]})


@app.route("/api/backup_now")
def api_backup_now():
    ok = auto_backup_all()
    return jsonify({"ok": ok, "message": "백업 완료" if ok else "백업 실패"})


@app.route("/api/ai_review")
def api_ai_review():
    ledger = read_ledger()[:20]
    return jsonify({"ok": True, "reviews": [{"event": e, "review": ai_loss_review(e)} for e in ledger]})




@app.route("/api/update_conditions", methods=["POST"])
def api_update_conditions():
    state = read_state()
    def pct_to_rate(name, default):
        return safe_float(request.form.get(name), default*100) / 100
    state["target_rate"] = pct_to_rate("target_rate", 0.027)
    state["stop_rate"] = pct_to_rate("stop_rate", -0.018)
    state["profit_guard_rate"] = pct_to_rate("profit_guard_rate", 0.012)
    state["trailing_stop_rate"] = pct_to_rate("trailing_stop_rate", 0.011)
    state["min_ai_score"] = safe_float(request.form.get("min_ai_score"), 60)
    state["max_day_change"] = safe_float(request.form.get("max_day_change"), 12)
    state["min_amount"] = safe_int(request.form.get("min_amount"), 3000000000)
    state["min_order_cash"] = safe_int(request.form.get("min_order_cash"), 50000)
    state["max_positions"] = safe_int(request.form.get("max_positions"), 3)
    state["rebuy_cooldown_minutes"] = safe_float(request.form.get("rebuy_cooldown_minutes"), 30)
    state["volume_keep_filter"] = safe_float(request.form.get("volume_keep_filter"), 0.55)
    state["index_weak_buy_scale"] = safe_float(request.form.get("index_weak_buy_scale"), 0.5)
    state["switch_buy_enabled"] = bool(request.form.get("switch_buy_enabled"))
    write_state(state)
    set_status("매매조건 저장", "AI후보 검색과 주문 판단 조건을 업데이트했습니다.")
    return render_page()

@app.route("/api/reset_conditions")
def api_reset_conditions():
    state = read_state()
    for k in ["target_rate","stop_rate","profit_guard_rate","trailing_stop_rate","min_ai_score","max_day_change","min_amount","min_order_cash","max_positions","rebuy_cooldown_minutes","volume_keep_filter","index_weak_buy_scale","switch_buy_enabled"]:
        state[k] = DEFAULT_STATE[k]
    write_state(state)
    set_status("기본조건 복원", "매매조건을 v152 기본값으로 복원했습니다.")
    return render_page()

@app.route("/api/telegram_test")
def api_telegram_test():
    ok, msg = send_telegram(f"{APP_NAME} {APP_VERSION} 텔레그램 테스트 알림 {now_text()}")
    add_alert("텔레그램 테스트 " + ("성공" if ok else "실패"))
    state = read_state()
    state["last_telegram_status"] = msg
    write_state(state)
    return jsonify({"ok": ok, "message": msg})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
