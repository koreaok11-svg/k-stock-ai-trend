# -*- coding: utf-8 -*-
"""
성일의 AI 주식바람 - KIWOOM REAL AUTO SCALPING v157 AI CANDIDATE CONDITIONS TABS FINAL
파일명: app_kiwoom_real_auto_scalping_v157_ai_candidate_conditions_tabs_final.py

목표:
- 누적 패치/중복 route/inject 제거
- 모바일 보기 좋은 컴팩트 UI
- 키움 인증 실패 메시지 1개만 표시
- 화면확인용 수동 보유표시 제거
- 실제 보유는 키움 REST 잔고 또는 마지막 정상 캐시만 표시
- 보유카드 직접 시장가 매도 버튼
- AI후보 축소 카드 + 터치 상세 펼침

v157 보강:
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


APP_VERSION = "v157"
APP_NAME = "성일의 AI 주식바람"
KST = timezone(timedelta(hours=9))
app = Flask(__name__)

BASE_DIR = Path(os.getenv("APP_DATA_DIR", "/var/data" if os.path.isdir("/var/data") else "/tmp"))
BASE_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = BASE_DIR / "sungil_trade_state_v157.json"
HOLDINGS_FILE = BASE_DIR / "sungil_holdings_v157.json"
HOLDINGS_BACKUP_FILE = BASE_DIR / "sungil_holdings_last_good_v157.json"
CANDIDATE_FILE = BASE_DIR / "sungil_candidates_v157.json"
PERFORMANCE_FILE = BASE_DIR / "sungil_strategy_performance_v157.json"
TRADE_LEDGER_FILE = BASE_DIR / "sungil_trade_ledger_v157.json"
BACKUP_DIR = BASE_DIR / "sungil_backups_v157"
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
    "dynamic_target_enabled": True,
    "dynamic_target_boost_rate": 0.012,
    "dynamic_target_min_profit_rate": 0.027,
    "dynamic_target_min_ai_score": 85,
    "candidate_scan_interval": 30,
    "candidate_price_warning_sec": 60,
    "last_candidate_scan_time": "",
    "last_candidate_scan_count": 0,
    "last_candidate_symbols": "",
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


def get_display_price(code):
    """AI후보 화면 표시용 현재가입니다.
    키움 인증 장애가 있어도 화면 현재가 괴리를 줄이기 위해 NAVER를 먼저 확인하고,
    실패 시 KIWOOM을 보조로 사용합니다. 실제 주문 전에는 별도로 KIWOOM 현재가를 재검증합니다.
    """
    p, src = get_naver_price(code)
    if p >= 10:
        return p, src
    try:
        p, src = get_kiwoom_price(code)
        if p >= 10:
            return p, src
    except Exception:
        pass
    return 0, "NONE"


def refresh_candidate_prices(items, force=True):
    """AI후보 카드의 현재가/목표가/손절가를 최신 표시가격 기준으로 보정합니다."""
    state = read_state()
    target_rate = safe_float(state.get("target_rate", 0.027), 0.027)
    stop_rate = safe_float(state.get("stop_rate", -0.018), -0.018)
    refreshed = []
    checked = now_text()
    for c in (items or []):
        c = dict(c or {})
        code = str(c.get("code", "")).zfill(6)
        old_price = safe_float(c.get("price"), 0)
        p, src = get_display_price(code) if code and force else (0, "NONE")
        if p >= 10:
            c["price"] = int(p)
            c["displayPrice"] = int(p)
            c["priceSource"] = src
            c["priceCheckedAt"] = checked
            c["priceDiffFromCache"] = int(p - old_price) if old_price else 0
            base = p
        else:
            base = old_price
            c.setdefault("priceSource", c.get("source", "KRX_FAST_CACHE"))
            c.setdefault("priceCheckedAt", c.get("scanTime") or checked)
            c.setdefault("priceDiffFromCache", 0)
        if base >= 10:
            c["target"] = int(base * (1 + target_rate))
            c["stop"] = int(base * (1 + stop_rate))
            c["buyZone"] = int(base * 0.995)
        c["priceRefreshNote"] = "실제 주문 직전에는 키움 현재가와 주문가능금액을 다시 검증합니다."
        refreshed.append(c)
    return refreshed


def candidate_price_age_seconds(c):
    try:
        t = str(c.get("priceCheckedAt") or c.get("scanTime") or c.get("time") or "")
        if not t:
            return 9999
        dt = datetime.strptime(t[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
        return max(0, int((now_kst() - dt).total_seconds()))
    except Exception:
        return 9999


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
    state_for_dynamic = read_state()
    profit_rate_decimal = ((cur - buy) / buy) if buy else 0
    dynamic_on = bool(state_for_dynamic.get("dynamic_target_enabled", True))
    boost_rate = safe_float(state_for_dynamic.get("dynamic_target_boost_rate", 0.012), 0.012)
    min_profit = safe_float(state_for_dynamic.get("dynamic_target_min_profit_rate", 0.027), 0.027)
    # 급등/강세 수익 구간에서는 기존 목표가에서 즉시 매도하지 않고 AI 상향목표와 트레일링 보호선을 올립니다.
    if dynamic_on and buy and (cur >= base_target or profit_rate_decimal >= min_profit):
        dynamic_target = max(dynamic_target, cur * (1 + boost_rate), base_target * (1 + boost_rate))
    trail = safe_float(h.get("trailingStopPrice"), 0)
    if dynamic_on and high >= base_target:
        trail = max(trail, high * (1 - safe_float(state_for_dynamic.get("trailing_stop_rate", 0.011), 0.011)))

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


def build_ai_reason(c, index_risk=None):
    """AI후보 선정 이유/위험요소/진입타입/확신도를 사람이 이해하기 쉽게 만듭니다."""
    c = dict(c or {})
    day = safe_float(c.get('dayChange'), 0)
    amt = safe_float(c.get('amount'), 0)
    score = safe_float(c.get('score'), 0)
    theme = str(c.get('theme') or '기타')
    market_avg = safe_float((index_risk or {}).get('avg'), 0)
    reverse = day - market_avg

    reasons = []
    risks = []
    entry_types = []

    if score >= 90:
        reasons.append('AI 기본점수가 매우 높습니다')
    elif score >= 80:
        reasons.append('AI 기본점수가 양호합니다')
    else:
        reasons.append('기본점수는 보통이나 조건 완화 구간에서 감시합니다')

    if amt >= 100_000_000_000:
        reasons.append('거래대금이 강해 수급 관심이 큽니다')
    elif amt >= 30_000_000_000:
        reasons.append('거래대금이 일정 수준 이상 유지됩니다')
    else:
        risks.append('거래대금이 상대적으로 작아 슬리피지 위험이 있습니다')

    if reverse >= 3:
        reasons.append('지수 대비 독립강세가 뚜렷합니다')
        entry_types.append('독립강세')
    elif reverse >= 1:
        reasons.append('시장 대비 상대강도가 좋습니다')

    if any(k in theme for k in ['AI','반도체','HBM','전력','광통신','데이터센터','PCB']):
        reasons.append(f'{theme} 테마 강도가 반영되었습니다')
        entry_types.append('테마추종')

    if 1.0 <= day <= 4.8:
        reasons.append('당일 상승률이 추격매수보다 건강한 구간입니다')
        entry_types.append('눌림/재상승 관찰')
    elif 4.8 < day <= 7.0:
        reasons.append('강한 상승 흐름이 유지되고 있습니다')
        entry_types.append('돌파관찰')
        risks.append('상승률이 높아 눌림 확인이 필요합니다')
    elif day > 7.0:
        risks.append('단기 급등 구간이라 추격매수 위험이 큽니다')
        entry_types.append('과열주의')
    elif day < 0.5:
        risks.append('상승 탄력이 아직 약합니다')

    if safe_float((index_risk or {}).get('avg'), 0) < -0.3 and day > 0:
        reasons.append('지수 약세에도 상승해 시장역행 후보입니다')

    if not entry_types:
        entry_types.append('AI감시')

    confidence = score * 0.45
    confidence += min(25, max(0, reverse) * 5)
    confidence += 15 if amt >= 100_000_000_000 else (9 if amt >= 30_000_000_000 else 2)
    confidence += 10 if any(k in theme for k in ['AI','반도체','전력','광통신','데이터센터']) else 3
    confidence -= 18 if day >= 10 else (10 if day >= 7 else (4 if day >= 5.5 else 0))
    confidence -= 12 if amt < 10_000_000_000 else 0
    confidence = max(0, min(100, confidence))

    if confidence >= 82:
        verdict = '우선 감시 후보입니다. 눌림 또는 재돌파 확인 시 매수 우선순위가 높습니다.'
    elif confidence >= 65:
        verdict = '관심 감시 후보입니다. 가격/거래대금 유지 여부를 더 확인합니다.'
    else:
        verdict = '보조 감시 후보입니다. 조건이 더 좋아질 때만 진입을 검토합니다.'

    return {
        'reasons': reasons[:6],
        'risks': risks[:5] or ['현재 큰 위험감점은 제한적입니다'],
        'entryType': ' / '.join(entry_types[:3]),
        'confidence': round(confidence, 1),
        'verdict': verdict,
    }


def render_badges(items, prefix='✅'):
    try:
        return ''.join(f'<span>{prefix} {html_escape(x)}</span>' for x in (items or []))
    except Exception:
        return ''

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
    explain = build_ai_reason(c, index_risk)
    c.update({'marketReverseScore': round(reverse_score,2),'themeStrengthScore': theme_strength,'overheatPenalty': overheat_penalty,'slippagePenalty': slippage_penalty,'indexRiskPenalty': index_penalty,'riskAdjustedScore': round(final,2),'strategy': strategy_from_candidate(c),'riskComment': f"시장역행 {reverse_score:.1f} · 과열감점 {overheat_penalty} · 슬리피지감점 {slippage_penalty} · 지수위험 {index_penalty}", 'aiReasons': explain.get('reasons', []), 'aiRisks': explain.get('risks', []), 'entryType': explain.get('entryType','AI감시'), 'aiConfidence': explain.get('confidence',0), 'aiVerdict': explain.get('verdict','AI 감시 후보입니다.')})
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
    # v157: KRX 종가/캐시와 실제 주식앱 현재가 차이를 줄이기 위해 표시 직전 현재가 보정
    candidates = refresh_candidate_prices(candidates, force=True)
    scan_time = now_text()
    state = read_state()
    state['index_risk_mode']=idx_risk.get('mode','UNKNOWN')
    state['recommended_strategy'] = candidates[0].get('strategy','AI후보형') if candidates else state.get('recommended_strategy','AI후보형')
    state['last_candidate_scan_time'] = scan_time
    state['last_candidate_price_time'] = scan_time
    state['last_candidate_scan_count'] = len(candidates)
    state['last_candidate_symbols'] = ' / '.join([str(x.get('name') or x.get('code')) for x in candidates[:3]])
    write_state(state)
    write_json(CANDIDATE_FILE, {"time": scan_time, "priceTime": scan_time, "items": candidates, "indexRisk": idx_risk, "scanInterval": safe_int(state.get('candidate_scan_interval',30),30)})
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
                    h["aiTargetReason"] = "목표 도달 후 강세로 판단되어 AI 상향익절/트레일링 감시 중"
                if h["trailingStopPrice"] and h["lastPrice"] <= h["trailingStopPrice"]:
                    auto_sell_holding("trailing_stop", h, h["lastPrice"])
                elif h["lastPrice"] <= h["stop"]:
                    auto_sell_holding("stop", h, h["lastPrice"])
                elif (not read_state().get("dynamic_target_enabled", True)) and h["lastPrice"] >= h["baseTarget"]:
                    auto_sell_holding("target", h, h["lastPrice"])
                updated.append(h)
            if updated:
                write_holdings(updated)
            WATCH_STATE["last_check"] = now_text()
            get_market_candidates(limit=8, min_score=60)
        except Exception as e:
            WATCH_STATE["last_message"] = str(e)[:200]
        time.sleep(max(10, safe_int(read_state().get("candidate_scan_interval", 30), 30)))


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
    age = candidate_price_age_seconds(c)
    stale = age > 60
    price_src = c.get('priceSource') or c.get('source','KRX_FAST_CACHE')
    checked = c.get('priceCheckedAt') or c.get('scanTime') or '-'
    diff = safe_float(c.get('priceDiffFromCache'), 0)
    diff_txt = f" · 캐시대비 {int(diff):+,}원" if diff else ""
    return f"""
    <div class="pick compact" onclick="toggleDetail('pick{idx}')">
      <div class="chips"><span>{html_escape(c.get('market',''))}</span><span>{c.get('code')}</span><span>{html_escape(c.get('theme',''))}</span><span>AI {safe_float(c.get('riskAdjustedScore', c.get('score'))):.1f}</span><span>역행 {safe_float(c.get('marketReverseScore')):.0f}</span><span>{html_escape(c.get('strategy','AI후보형'))}</span><span>확신 {safe_float(c.get('aiConfidence')):.0f}%</span><span>{html_escape(c.get('entryType','AI감시'))}</span></div>
      <h3>{html_escape(c.get('name'))}</h3>
      <div class="grid2">
        <div><label>현재가</label><b>{money(c.get('price'))}</b><small>{html_escape(price_src)} · {age}초 전</small></div>
        <div><label>당일 흐름</label><b>{pct(c.get('dayChange'))}</b></div>
        <div><label>목표가</label><b class="red">{money(c.get('target'))}</b></div>
        <div><label>손절가</label><b class="blue">{money(c.get('stop'))}</b></div>
      </div>
      <div class="price-meta {'stale' if stale else ''}">⏱ 가격확인 {html_escape(checked)} · {html_escape(price_src)}{html_escape(diff_txt)}{' · 오래된 가격일 수 있습니다' if stale else ''}</div>
      <div id="pick{idx}" class="detail">
        <div class="reason-title">🤖 AI 추천 이유</div>
        <div class="reason-tags">{render_badges(c.get('aiReasons'), '✅')}</div>
        <div class="reason-title">⚠️ 위험/감점 요소</div>
        <div class="risk-tags">{render_badges(c.get('aiRisks'), '⚠')}</div>
        <div class="ai-verdict">종합판단: {html_escape(c.get('aiVerdict','AI 감시 후보입니다.'))}</div>
        <div class="mini-line">진입타입 <b>{html_escape(c.get('entryType','AI감시'))}</b> · AI확신도 <b>{safe_float(c.get('aiConfidence')):.1f}%</b></div>
        <div class="mini-line">거래대금 {html_escape(c.get('amountText','-'))} · 매수관찰 {money(c.get('buyZone'))}</div>
        <div class="mini-line">시장역행 {safe_float(c.get('marketReverseScore')):.1f} · 테마강도 {safe_float(c.get('themeStrengthScore')):.0f} · 과열감점 {safe_float(c.get('overheatPenalty')):.0f} · 슬리피지감점 {safe_float(c.get('slippagePenalty')):.0f}</div>
        <div class="mini-line">{html_escape(c.get('priceRefreshNote',''))}</div>
      </div>
    </div>"""


def render_candidates():
    data = read_json(CANDIDATE_FILE, {})
    picks = (data.get("items") if isinstance(data, dict) else None) or cached_candidates()[:8]
    state = read_state()
    scan_time = data.get("time") if isinstance(data, dict) else state.get("last_candidate_scan_time", "")
    price_time = data.get("priceTime") if isinstance(data, dict) else state.get("last_candidate_price_time", "")
    scan_interval = safe_int(state.get("candidate_scan_interval", 30), 30)
    scan_count = len(picks)
    symbols = " / ".join([str(x.get("name") or x.get("code")) for x in picks[:3]]) if picks else "대기중"
    oldest_age = max([candidate_price_age_seconds(x) for x in picks] or [0])
    cards = "".join(render_candidate_card(c, i) for i, c in enumerate(picks))
    return f"""
    <section class="card" id="picks">
      <h2>🤖 AI후보</h2>
      <p class="muted">AI가 감시하는 후보입니다. 종목을 누르면 AI 추천 이유·위험요소·진입타입·확신도가 펼쳐집니다.</p>
      <div class="scan-status">
        <div><b>🔎 AI 분석 상태</b></div>
        <div>TOP 후보 분석 완료: <b>{scan_count}</b>개</div>
        <div>현재 감시 후보: <b>{html_escape(symbols)}</b></div>
        <div>최근 후보스캔: <b>{html_escape(scan_time or '-')}</b></div>
        <div>최근 가격확인: <b>{html_escape(price_time or '-')}</b> · 가격나이 <b>{oldest_age}</b>초</div>
        <div>다음 재스캔: <b id="scanCountdown">{scan_interval}</b>초 후</div>
      </div>
      <div class="btn-row">
        <button onclick="location.href='/api/refresh_candidates'">후보 즉시검색</button>
        <button class="dark" onclick="location.href='/api/refresh_candidate_prices'">현재가 새로고침</button>
        <button class="brown" onclick="location.href='/api/buy_best'">최우선 후보 매수</button>
      </div>
      <div class="notice small">표시가격은 NAVER/KIWOOM 보정값입니다. 실제 주문 직전에는 키움 현재가와 주문가능금액을 다시 검증합니다.</div>
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
        <button class="brown" onclick="location.href='/api/buy_best'">AI후보 즉시매수</button>
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
    switch_on = 'checked' if state.get('switch_buy_enabled') else ''
    return f"""
    <section class="card" id="conditions">
      <h2>🧭 매매조건</h2>
      <p class="muted">자동매매가 실제로 참고하는 조건입니다. 평소에는 요약만 보고, 수정이 필요할 때만 펼쳐서 저장하세요.</p>
      <div class="summary-grid">
        <div><span>익절 / 손절</span><b>+{safe_float(state.get('target_rate'),0.027)*100:.2f}% / {safe_float(state.get('stop_rate'),-0.018)*100:.2f}%</b></div>
        <div><span>AI 상향익절</span><b>{'ON' if state.get('dynamic_target_enabled', True) else 'OFF'} · +{safe_float(state.get('dynamic_target_boost_rate'),0.012)*100:.2f}%</b></div>
        <div><span>최소 AI 점수</span><b>{safe_float(state.get('min_ai_score'),60):.1f}</b></div>
        <div><span>최소 거래대금</span><b>{safe_int(state.get('min_amount'),3000000000)/100000000:.0f}억</b></div>
        <div><span>재매수 제한</span><b>{safe_float(state.get('rebuy_cooldown_minutes'),30):.0f}분</b></div>
      </div>
      <details>
        <summary>✍️ 매매조건 수정하기 / 접기</summary>
        <form method="post" action="/api/update_conditions">
          <div class="form-grid">
            <label>기본 익절률(%)<input name="target_rate" value="{safe_float(state.get('target_rate'),0.027)*100:.2f}"><small>예: 2.70 = +2.7%</small></label>
            <label>손절률(%)<input name="stop_rate" value="{safe_float(state.get('stop_rate'),-0.018)*100:.2f}"><small>예: -1.80 = -1.8%</small></label>
            <label>수익보호 되돌림(%)<input name="profit_guard_rate" value="{safe_float(state.get('profit_guard_rate'),0.012)*100:.2f}"></label>
            <label>트레일링 되돌림(%)<input name="trailing_stop_rate" value="{safe_float(state.get('trailing_stop_rate'),0.011)*100:.2f}"></label>
            <label>AI 상향익절 추가 목표(%)<input name="dynamic_target_boost_rate" value="{safe_float(state.get('dynamic_target_boost_rate'),0.012)*100:.2f}"><small>예: 1.20 = 목표 도달 후 현재가 대비 +1.2% 상향</small></label>
            <label>상향익절 시작 수익률(%)<input name="dynamic_target_min_profit_rate" value="{safe_float(state.get('dynamic_target_min_profit_rate'),0.027)*100:.2f}"><small>이 수익률 이상이면 AI가 목표가를 끌어올릴 수 있습니다.</small></label>
            <label>AI후보 자동갱신 주기(초)<input name="candidate_scan_interval" value="{safe_int(state.get('candidate_scan_interval'),30)}"><small>예: 30 = 30초마다 후보 재스캔</small></label>
            <label>최소 AI 점수<input name="min_ai_score" value="{safe_float(state.get('min_ai_score'),60):.1f}"></label>
            <label>최대 당일 등락률(%)<input name="max_day_change" value="{safe_float(state.get('max_day_change'),12):.1f}"></label>
            <label>최소 거래대금(원)<input name="min_amount" value="{safe_int(state.get('min_amount'),3000000000)}"></label>
            <label>최소 주문금액(원)<input name="min_order_cash" value="{safe_int(state.get('min_order_cash'),50000)}"></label>
            <label>최대 보유종목<input name="max_positions" value="{safe_int(state.get('max_positions'),3)}"></label>
            <label>매도 후 재매수 제한(분)<input name="rebuy_cooldown_minutes" value="{safe_float(state.get('rebuy_cooldown_minutes'),30):.0f}"></label>
            <label>거래대금/거래량 유지율<input name="volume_keep_filter" value="{safe_float(state.get('volume_keep_filter'),0.55):.2f}"></label>
            <label>지수 약세 신규매수 비중<input name="index_weak_buy_scale" value="{safe_float(state.get('index_weak_buy_scale'),0.5):.2f}"></label>
          </div>
          <label class="check"><input type="checkbox" name="dynamic_target_enabled" {'checked' if state.get('dynamic_target_enabled', True) else ''}> 급등/강세 종목 AI 상향익절 허용</label>
          <label class="check"><input type="checkbox" name="switch_buy_enabled" {switch_on}> 전환매수 허용</label>
          <div class="btn-row"><button type="submit">매매조건 저장</button><a class="button dark" href="/api/reset_conditions">기본조건 복원</a></div>
        </form>
      </details>
      <details><summary>조건 설명 보기 / 접기</summary><div class="notice small">
        최소 AI 점수와 최소 거래대금이 높을수록 후보가 줄고 안정성이 올라갑니다.<br>
        최대 당일 등락률은 과열/추격매수 방지용입니다.<br>
        AI 상향익절은 목표가 도달 후에도 시장역행점수·거래대금·상승흐름이 좋으면 목표가를 더 올리고 트레일링으로 보호합니다.<br>
        전환매수는 기본 OFF이며, 허용 시에도 매도 후 재매수 제한과 지수 위험도를 함께 확인합니다.
      </div></details>
    </section>"""


def build_ai_condition_report():
    """최근 매매 원장과 전략 성과를 바탕으로 추천 조건을 만듭니다. 자동 적용하지 않습니다."""
    state = read_state()
    ledger = read_ledger()
    sells = [x for x in ledger if str(x.get('side','')).lower() == 'sell']
    wins = [x for x in sells if safe_float(x.get('pnl'), 0) > 0]
    losses = [x for x in sells if safe_float(x.get('pnl'), 0) <= 0]
    win_rate = round(len(wins) / max(1, len(sells)) * 100, 1)
    avg_pnl = int(sum(safe_float(x.get('pnl'),0) for x in sells) / max(1, len(sells)))
    recommended = dict(state)
    confidence = '낮음' if len(sells) < 5 else ('보통' if len(sells) < 20 else '높음')
    mode = '관찰 유지' if len(sells) < 5 else '조건 개선'
    reasons = []
    if len(sells) < 5:
        reasons.append('아직 매도 완료 표본이 5건 미만이라 조건을 크게 바꾸면 과최적화 위험이 큽니다.')
    if win_rate < 45 and len(sells) >= 5:
        recommended['min_ai_score'] = min(95, max(safe_float(state.get('min_ai_score'),60), 70))
        recommended['max_day_change'] = min(safe_float(state.get('max_day_change'),12), 8)
        reasons.append('승률이 낮아 최소 AI점수와 과열 제한을 보수적으로 조정합니다.')
    if losses and abs(sum(safe_float(x.get('pnl'),0) for x in losses)) > sum(safe_float(x.get('pnl'),0) for x in wins):
        recommended['stop_rate'] = max(safe_float(state.get('stop_rate'),-0.018), -0.015)
        recommended['rebuy_cooldown_minutes'] = max(safe_float(state.get('rebuy_cooldown_minutes'),30), 40)
        reasons.append('손실 합계가 커서 손절폭과 재매수 제한을 강화합니다.')
    if win_rate >= 60 and avg_pnl > 0 and len(sells) >= 10:
        recommended['target_rate'] = min(0.04, safe_float(state.get('target_rate'),0.027) + 0.003)
        recommended['profit_guard_rate'] = max(0.01, safe_float(state.get('profit_guard_rate'),0.012))
        recommended['dynamic_target_enabled'] = True
        recommended['dynamic_target_boost_rate'] = min(0.018, max(safe_float(state.get('dynamic_target_boost_rate'),0.012), 0.012))
        reasons.append('승률과 평균손익이 양호해 기본 익절 목표와 AI 상향익절을 함께 사용할 수 있습니다.')
    if not reasons:
        reasons.append('현재 조건을 유지하되, 시장역행 점수·슬리피지 감점·재매수 제한을 계속 관찰합니다.')
    current_score = round(25 + min(40, win_rate*0.4) + (10 if avg_pnl > 0 else 0) + min(20, len(sells)*1.5), 1)
    rec_score = round(current_score + (4 if recommended != state else 0), 1)
    return {
        'reviewed_at': now_text(), 'confidence': confidence, 'mode': mode,
        'sell_count': len(sells), 'win_rate': win_rate, 'avg_pnl': avg_pnl,
        'current': state, 'recommended': recommended, 'current_score': current_score,
        'recommended_score': rec_score, 'reasons': reasons,
        'best_strategy': (strategy_rankings(7)[0]['strategy'] if strategy_rankings(7) else state.get('current_strategy','AI후보형')),
    }


def render_ai_upgrade_section():
    report = build_ai_condition_report()
    st = report['current']; rc = report['recommended']
    def rate(v): return f"{safe_float(v,0)*100:.2f}%"
    rows = [
        ('기본 익절률', rate(st.get('target_rate')), rate(rc.get('target_rate'))),
        ('손절률', rate(st.get('stop_rate')), rate(rc.get('stop_rate'))),
        ('최소 AI 점수', f"{safe_float(st.get('min_ai_score'),0):.1f}", f"{safe_float(rc.get('min_ai_score'),0):.1f}"),
        ('수익보호 되돌림', rate(st.get('profit_guard_rate')), rate(rc.get('profit_guard_rate'))),
        ('재매수 제한', f"{safe_float(st.get('rebuy_cooldown_minutes'),0):.0f}분", f"{safe_float(rc.get('rebuy_cooldown_minutes'),0):.0f}분"),
        ('전환매수', 'ON' if st.get('switch_buy_enabled') else 'OFF', 'ON' if rc.get('switch_buy_enabled') else 'OFF'),
    ]
    cards = ''.join(f"<div><span>{html_escape(a)}</span><b>{html_escape(b)} → {html_escape(c)}</b></div>" for a,b,c in rows)
    reasons = ''.join(f"<li>{html_escape(x)}</li>" for x in report['reasons'])
    return f"""
    <section class="card" id="ai-upgrade">
      <h2>🧠 AI 조건 업그레이드</h2>
      <details open>
        <summary>AI 조건 추천구조 설명 보기</summary>
        <div class="notice small">
          최근 실제 매수/매도 원장과 전략성과를 기준으로 승률, 평균손익, 손실패턴, 재매수 제한, 지수 위험을 확인합니다.<br>
          AI는 조건을 자동으로 바꾸지 않고 추천만 만듭니다. <b>추천조건 적용</b>을 눌러야 매매조건에 반영됩니다.
        </div>
      </details>
      <div class="upgrade-box">
        <div><span class="pill-warn">신뢰도 {html_escape(report['confidence'])}</span> <span class="pill-ok">추천전략 {html_escape(report['best_strategy'])}</span></div>
        <div class="summary-grid">
          <div><span>분석모드</span><b>{html_escape(report['mode'])}</b></div>
          <div><span>매도완료</span><b>{report['sell_count']}건</b></div>
          <div><span>승률</span><b>{report['win_rate']}%</b></div>
          <div><span>평균손익</span><b>{money(report['avg_pnl'])}</b></div>
        </div>
        <h3>AI 추천 조건</h3>
        <div class="summary-grid">{cards}</div>
        <h3>적용 이유</h3><ul class="reason-list">{reasons}</ul>
        <div class="btn-row">
          <button type="button" onclick="callAndReload('/api/ai_reanalyze_conditions')">AI 재분석</button>
          <button type="button" onclick="callAndReload('/api/apply_ai_recommended_conditions')">추천조건 적용</button>
          <button class="dark" type="button" onclick="callAndReload('/api/keep_conditions')">기존조건 유지</button>
        </div>
        <p class="muted">안전장치: 자동 적용은 하지 않습니다. 사용자가 승인 버튼을 눌렀을 때만 실전 조건이 바뀝니다.</p>
      </div>
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



def _top_theme_summary(items):
    themes = {}
    for c in items or []:
        t = str(c.get('theme') or '기타')
        row = themes.setdefault(t, {'theme': t, 'count': 0, 'amount': 0, 'avg_change': 0, 'score': 0})
        row['count'] += 1
        row['amount'] += safe_float(c.get('amount'), 0)
        row['avg_change'] += safe_float(c.get('dayChange'), 0)
        row['score'] += safe_float(c.get('riskAdjustedScore', c.get('score', 0)), 0)
    out=[]
    for r in themes.values():
        if r['count']:
            r['avg_change'] = round(r['avg_change']/r['count'], 2)
            r['score'] = round(r['score']/r['count'], 1)
            out.append(r)
    return sorted(out, key=lambda x:(x['score'], x['amount']), reverse=True)[:5]


def build_ai_daily_report(force=False):
    """전날 기준 AI 일일 리포트. 실제 과거 데이터 API가 없으면 최신 KRX/캐시를 기반으로 전일 복기형 리포트를 만듭니다."""
    cached = read_json(DAILY_REPORT_FILE, {})
    today = now_kst().strftime('%Y-%m-%d')
    if cached.get('date') == today and not force:
        return cached
    try:
        items = get_market_candidates(limit=12)
    except Exception:
        data = read_json(CANDIDATE_FILE, {})
        items = data.get('items', []) if isinstance(data, dict) else []
    idx = read_state().get('index_risk_mode', 'UNKNOWN')
    themes = _top_theme_summary(items)
    total_amount = sum(safe_float(x.get('amount'), 0) for x in items)
    avg_change = round(sum(safe_float(x.get('dayChange'), 0) for x in items) / max(1, len(items)), 2)
    strong = [x for x in items if safe_float(x.get('riskAdjustedScore', x.get('score',0))) >= 80]
    risk_notes=[]
    if idx in ['WEAK','DANGER']:
        risk_notes.append('지수 약세 구간이므로 신규매수는 시장역행 점수가 높은 후보 위주로 축소 접근이 좋습니다.')
    if any(safe_float(x.get('overheatPenalty'),0) >= 10 for x in items):
        risk_notes.append('일부 후보는 단기 급등/과열 감점이 있어 추격매수보다 눌림 확인이 필요합니다.')
    if not risk_notes:
        risk_notes.append('과열 위험은 제한적이나 실시간 가격과 거래대금 유지 여부 확인이 필요합니다.')
    report = {
        'date': today,
        'base_day': '전일 기준 자동 리포트',
        'created_at': now_text(),
        'index_risk': idx,
        'candidate_count': len(items),
        'total_amount_text': f"{total_amount/100000000:.1f}억",
        'avg_change': avg_change,
        'themes': themes,
        'top_candidates': items[:5],
        'strong_count': len(strong),
        'summary': f"AI후보 {len(items)}개 기준 평균 등락률 {avg_change:.2f}%, 주요 거래대금 합계 {total_amount/100000000:.1f}억 수준입니다. 강한 후보는 {len(strong)}개로 분류됩니다.",
        'opinion': '오늘은 거래대금이 유지되고 시장역행 점수가 높은 종목을 우선 감시하는 방향이 좋습니다. 테마가 강하더라도 고점 근처 후보는 추격매수보다 눌림 후 재돌파 확인이 안전합니다.',
        'risk_notes': risk_notes,
    }
    write_json(DAILY_REPORT_FILE, report)
    return report


def build_ai_investment_review(force=False):
    cached = read_json(INVESTMENT_REVIEW_FILE, {})
    today = now_kst().strftime('%Y-%m-%d')
    if cached.get('date') == today and not force:
        return cached
    holdings = read_holdings()
    ledger = read_ledger()[:50]
    perf1 = strategy_rankings(1)
    perf7 = strategy_rankings(7)
    total_value = sum(safe_float(h.get('lastPrice'),0)*safe_float(h.get('qty'),0) for h in holdings)
    total_buy = sum(safe_float(h.get('buyPrice'),0)*safe_float(h.get('qty'),0) for h in holdings)
    total_pnl = sum(safe_float(h.get('pnl'),0) for h in holdings)
    total_rate = (total_pnl / total_buy * 100) if total_buy else 0
    risk_flags=[]
    if len(holdings) == 0:
        risk_flags.append('현재 앱에서 확인되는 보유종목이 없습니다. 키움 인증/잔고동기화 상태를 먼저 확인하세요.')
    if len(holdings) >= safe_int(read_state().get('max_positions'),3):
        risk_flags.append('보유종목 수가 설정 한도에 가까워 신규매수보다 보유관리 우선이 좋습니다.')
    if total_rate < -2:
        risk_flags.append('전체 평가손익률이 손실권입니다. 신규매수보다 손절/비중 축소 기준을 먼저 점검하세요.')
    elif total_rate > 3:
        risk_flags.append('수익권입니다. AI 상향목표와 트레일링 보호선을 함께 확인하는 것이 좋습니다.')
    if not risk_flags:
        risk_flags.append('현재 포트폴리오 위험은 중립입니다. 시장상태에 따라 신규매수 비중을 조절하세요.')
    best_strategy = perf7[0]['strategy'] if perf7 else (perf1[0]['strategy'] if perf1 else read_state().get('current_strategy','AI후보형'))
    direction = '보유종목은 목표가/트레일링 보호선 기준으로 관리하고, 신규 진입은 AI후보 중 시장역행·거래대금 유지 후보로 제한하는 방향을 권장합니다.'
    if read_state().get('index_risk_mode') in ['WEAK','DANGER']:
        direction = '지수 약세 구간입니다. 신규매수는 축소하고, 이미 수익 중인 보유종목은 트레일링 보호선 중심으로 관리하는 것이 좋습니다.'
    report = {
        'date': today,
        'created_at': now_text(),
        'holdings_count': len(holdings),
        'total_value': int(total_value),
        'total_buy': int(total_buy),
        'total_pnl': int(total_pnl),
        'total_rate': round(total_rate,2),
        'best_strategy': best_strategy,
        'rank_1d': perf1[:3],
        'rank_1w': perf7[:3],
        'recent_trades': ledger[:5],
        'risk_flags': risk_flags,
        'direction': direction,
        'summary': f"현재 확인 보유 {len(holdings)}종목, 평가손익 {int(total_pnl):,}원({total_rate:.2f}%)입니다. 최근 성과 기준 우선 전략은 {best_strategy}입니다.",
    }
    write_json(INVESTMENT_REVIEW_FILE, report)
    return report


def render_daily_report_section():
    r = build_ai_daily_report()
    theme_rows = ''.join(f"<li><b>{html_escape(x.get('theme'))}</b> · 평균등락 {x.get('avg_change')}% · AI강도 {x.get('score')} · 거래대금 {safe_float(x.get('amount'))/100000000:.1f}억</li>" for x in r.get('themes', [])) or '<li>테마 데이터 대기중</li>'
    pick_rows = ''.join(f"<li><b>{html_escape(x.get('name'))}</b> · {html_escape(x.get('theme',''))} · AI {safe_float(x.get('riskAdjustedScore',x.get('score'))):.1f} · {pct(x.get('dayChange'))}</li>" for x in r.get('top_candidates', [])) or '<li>후보 데이터 대기중</li>'
    risk_rows = ''.join(f"<li>{html_escape(x)}</li>" for x in r.get('risk_notes', []))
    return f"""
    <section class="card" id="daily-report">
      <h2>📰 AI 일일리포트</h2>
      <p class="muted">전날 기준 시장 흐름을 복기하고 오늘 감시 방향을 제시합니다.</p>
      <div class="btn-row"><button onclick="location.href='/api/refresh_daily_report'">AI일일리포트 새로작성</button></div>
      <div class="summary-grid">
        <div><span>작성시간</span><b>{html_escape(r.get('created_at','-'))}</b></div>
        <div><span>지수위험</span><b>{html_escape(r.get('index_risk','UNKNOWN'))}</b></div>
        <div><span>AI후보 수</span><b>{r.get('candidate_count',0)}개</b></div>
        <div><span>거래대금 합계</span><b>{html_escape(r.get('total_amount_text','-'))}</b></div>
      </div>
      <div class="ai-verdict">{html_escape(r.get('summary',''))}</div>
      <details open><summary>상승/강세 테마 분석</summary><div class="notice small"><ul>{theme_rows}</ul></div></details>
      <details><summary>오늘 관심 후보 의견</summary><div class="notice small"><ul>{pick_rows}</ul><p>{html_escape(r.get('opinion',''))}</p></div></details>
      <details><summary>위험요소/주의사항</summary><div class="notice small"><ul>{risk_rows}</ul></div></details>
    </section>"""


def render_investment_review_section():
    r = build_ai_investment_review()
    risk_rows = ''.join(f"<li>{html_escape(x)}</li>" for x in r.get('risk_flags', []))
    rank_rows = ''.join(f"<li><b>{html_escape(x.get('strategy'))}</b> · 손익 {money(x.get('pnl'))} · 승률 {x.get('win_rate')}% · {x.get('trades')}회</li>" for x in r.get('rank_1w', [])) or '<li>전략 성과 데이터 대기중</li>'
    return f"""
    <section class="card" id="my-review">
      <h2>🧾 AI 내투자평가</h2>
      <p class="muted">보유종목, 매매원장, 전략성과를 기준으로 현재 투자상태를 평가합니다.</p>
      <div class="btn-row"><button onclick="location.href='/api/refresh_investment_review'">내투자평가 새로작성</button></div>
      <div class="summary-grid">
        <div><span>보유종목</span><b>{r.get('holdings_count',0)}개</b></div>
        <div><span>평가손익</span><b class="{'red' if safe_float(r.get('total_pnl'))>=0 else 'blue'}">{money(r.get('total_pnl'))}</b></div>
        <div><span>전체수익률</span><b>{pct(r.get('total_rate'))}</b></div>
        <div><span>추천전략</span><b>{html_escape(r.get('best_strategy','-'))}</b></div>
      </div>
      <div class="ai-verdict">{html_escape(r.get('summary',''))}</div>
      <details open><summary>투자방향 의견</summary><div class="notice small">{html_escape(r.get('direction',''))}</div></details>
      <details><summary>위험/개선 포인트</summary><div class="notice small"><ul>{risk_rows}</ul></div></details>
      <details><summary>최근 우수 전략</summary><div class="notice small"><ul>{rank_rows}</ul></div></details>
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
        daily_report=render_daily_report_section(),
        my_review=render_investment_review_section(),
        performance=render_performance_section(),
        ai_upgrade=render_ai_upgrade_section(),
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
.reason-title{font-weight:900;margin:10px 0 6px;color:#203b2d}.reason-tags,.risk-tags{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 8px}.reason-tags span,.risk-tags span{background:#fff;border:1px solid #dbe8d5;border-radius:999px;padding:6px 9px;font-size:13px;font-weight:800}.risk-tags span{border-color:#ffd1a6;background:#fff7ed}.ai-verdict{background:#fff;border-left:4px solid var(--green);border-radius:12px;padding:10px;margin:8px 0;font-weight:800}.mini-line{font-size:13px;color:#5b6b5c;margin-top:5px}
details summary{cursor:pointer;background:var(--pale);border-radius:18px;padding:14px;font-weight:900}.alerts{margin:8px 0 0;padding-left:20px;color:#5b513d}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.form-grid label{font-weight:900;color:#334155}.form-grid input{width:100%;margin-top:6px;border:1px solid #dbe8d5;border-radius:14px;padding:12px;font-size:15px;background:#fbfdff}.check{display:block;margin:12px 0;font-weight:900}.button.dark{background:var(--dark)}
.scan-status{background:#f4f8ff;border:1px dashed #bfd3ef;border-radius:20px;padding:15px;margin:12px 0;color:#334155;font-weight:700}.scan-status b{color:#0f172a}
.summary-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:12px 0}.summary-grid div{background:#f8fbff;border:1px solid #e3ebf4;border-radius:16px;padding:12px}.summary-grid span{display:block;color:var(--muted);font-size:12px}.summary-grid b{font-size:20px}.upgrade-box{border:1px solid #dce8dc;border-radius:22px;padding:16px;margin:12px 0;background:#fbfffb}.strategy-card{border:1px solid #dfe8f2;border-radius:20px;padding:14px;margin:10px 0;background:#fff}.strategy-card.best{border-color:#9bd4ad;background:#f4fff6}.strategy-card .tag{float:right;border-radius:999px;background:#eaf2ff;color:#2d6cdf;padding:5px 10px;font-weight:900;font-size:12px}.reason-list{color:#667085}.reason-list li{margin:6px 0}.pill-warn{display:inline-block;border-radius:999px;background:#fff4d5;color:#8a5a00;padding:6px 10px;font-weight:900}.pill-ok{display:inline-block;border-radius:999px;background:#e8fff0;color:#10803d;padding:6px 10px;font-weight:900}.price-meta{margin-top:10px;padding:10px 12px;border-radius:14px;background:#eef8e9;color:#385c42;font-size:13px;font-weight:800}.price-meta.stale{background:#fff4d5;color:#8a5a00}
@media(max-width:430px){body{font-size:15px}.form-grid{grid-template-columns:1fr}.wrap{padding:10px 10px 70px}.hero h1{font-size:28px}.card{padding:18px;border-radius:24px}.card h2{font-size:24px}.grid2 b{font-size:18px}button{font-size:15px;padding:12px 15px}.nav a{font-size:14px;padding:9px 12px}}
</style>
<script>
function toggleDetail(id){const el=document.getElementById(id); if(el){el.classList.toggle('open')}}
async function manualSell(code){
 if(!confirm(code+' 시장가 매도를 요청할까요? 실제 주문 전 키움 인증 상태를 확인합니다.')) return;
 const r=await fetch('/api/manual_sell?code='+encodeURIComponent(code));
 const j=await r.json(); alert(j.message||JSON.stringify(j)); location.reload();
}
async function callAndReload(url){
 const r=await fetch(url); const j=await r.json().catch(()=>({message:'완료'})); alert(j.message||JSON.stringify(j)); location.reload();
}
function startScanCountdown(){
 const el=document.getElementById('scanCountdown'); if(!el) return;
 let n=parseInt(el.textContent||'30');
 setInterval(()=>{ n=Math.max(0,n-1); el.textContent=n; if(n<=0){ el.textContent='갱신대기'; } },1000);
}
document.addEventListener('DOMContentLoaded',startScanCountdown);
</script>
</head><body>
<div class="wrap">
  <div class="hero">
    <span class="badge">🌿 KIWOOM REAL AUTO {{version}}</span>
    <h1>{{app_name}}</h1>
    <p>키움 REST API 연동 · AI후보 감시 · 추천이유 설명 · 목표/손절/트레일링 · 전략성과 학습</p>
  </div>
  <div class="nav">
    <a href="#picks">🤖 AI후보</a><a href="#daily-report">📰 AI일일리포트</a><a href="#my-review">🧾 AI내투자평가</a><a href="#conditions">🧭 매매조건</a><a href="#ai-upgrade">🧠 AI조건</a><a href="#holdings">💼 보유</a><a href="#trade">⚙️ 자동</a><a href="#performance">📊 AI전략</a><a href="#alerts">📨 알림</a>
  </div>
  {{candidates|safe}}
  {{daily_report|safe}}
  {{my_review|safe}}
  {{conditions|safe}}
  {{ai_upgrade|safe}}
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


@app.route("/api/refresh_candidates")
def api_refresh_candidates():
    items = get_market_candidates(limit=8)
    set_status("AI후보 즉시검색", f"AI후보 {len(items)}개를 즉시 검색하고 현재가를 보정했습니다.")
    return render_page()


@app.route("/api/refresh_candidate_prices")
def api_refresh_candidate_prices():
    data = read_json(CANDIDATE_FILE, {})
    items = data.get("items") if isinstance(data, dict) else []
    if not items:
        items = get_market_candidates(limit=8)
    items = refresh_candidate_prices(items, force=True)
    price_time = now_text()
    if isinstance(data, dict):
        data["items"] = items
        data["priceTime"] = price_time
        data.setdefault("time", price_time)
        data["scanInterval"] = safe_int(read_state().get("candidate_scan_interval",30),30)
    else:
        data = {"time": price_time, "priceTime": price_time, "items": items, "scanInterval": safe_int(read_state().get("candidate_scan_interval",30),30)}
    write_json(CANDIDATE_FILE, data)
    state = read_state()
    state["last_candidate_price_time"] = price_time
    state["last_candidate_scan_count"] = len(items)
    write_state(state)
    set_status("AI후보 현재가 새로고침", f"AI후보 {len(items)}개 현재가를 새로 확인했습니다.")
    return render_page()


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
    state["dynamic_target_boost_rate"] = pct_to_rate("dynamic_target_boost_rate", 0.012)
    state["dynamic_target_min_profit_rate"] = pct_to_rate("dynamic_target_min_profit_rate", 0.027)
    state["candidate_scan_interval"] = max(10, safe_int(request.form.get("candidate_scan_interval"), 30))
    state["min_ai_score"] = safe_float(request.form.get("min_ai_score"), 60)
    state["max_day_change"] = safe_float(request.form.get("max_day_change"), 12)
    state["min_amount"] = safe_int(request.form.get("min_amount"), 3000000000)
    state["min_order_cash"] = safe_int(request.form.get("min_order_cash"), 50000)
    state["max_positions"] = safe_int(request.form.get("max_positions"), 3)
    state["rebuy_cooldown_minutes"] = safe_float(request.form.get("rebuy_cooldown_minutes"), 30)
    state["volume_keep_filter"] = safe_float(request.form.get("volume_keep_filter"), 0.55)
    state["index_weak_buy_scale"] = safe_float(request.form.get("index_weak_buy_scale"), 0.5)
    state["dynamic_target_enabled"] = bool(request.form.get("dynamic_target_enabled"))
    state["switch_buy_enabled"] = bool(request.form.get("switch_buy_enabled"))
    write_state(state)
    set_status("매매조건 저장", "v157 매매조건 탭에서 수정한 조건을 저장했습니다. 다음 AI후보 검색과 주문 판단부터 반영됩니다.")
    return render_page()

@app.route("/api/reset_conditions")
def api_reset_conditions():
    state = read_state()
    for k in ["target_rate","stop_rate","profit_guard_rate","trailing_stop_rate","dynamic_target_enabled","dynamic_target_boost_rate","dynamic_target_min_profit_rate","candidate_scan_interval","min_ai_score","max_day_change","min_amount","min_order_cash","max_positions","rebuy_cooldown_minutes","volume_keep_filter","index_weak_buy_scale","switch_buy_enabled"]:
        state[k] = DEFAULT_STATE[k]
    write_state(state)
    set_status("기본조건 복원", "매매조건을 v157 기본값으로 복원했습니다.")
    return render_page()


@app.route("/api/ai_reanalyze_conditions")
def api_ai_reanalyze_conditions():
    report = build_ai_condition_report()
    set_status("AI 조건 재분석", f"신뢰도 {report['confidence']} · 추천전략 {report['best_strategy']}")
    return jsonify({"ok": True, "message": "AI 조건 재분석 완료", "report": report})

@app.route("/api/apply_ai_recommended_conditions")
def api_apply_ai_recommended_conditions():
    report = build_ai_condition_report()
    state = read_state()
    rec = report.get('recommended', {})
    keys = ["target_rate","stop_rate","profit_guard_rate","trailing_stop_rate","dynamic_target_enabled","dynamic_target_boost_rate","dynamic_target_min_profit_rate","candidate_scan_interval","min_ai_score","max_day_change","min_amount","min_order_cash","max_positions","rebuy_cooldown_minutes","volume_keep_filter","index_weak_buy_scale","switch_buy_enabled"]
    for k in keys:
        if k in rec:
            state[k] = rec[k]
    state['current_strategy'] = report.get('best_strategy') or state.get('current_strategy','AI후보형')
    state['last_ai_condition_report'] = report
    write_state(state)
    set_status("AI 추천조건 적용", "사용자 승인으로 AI 추천 매매조건을 적용했습니다.")
    return jsonify({"ok": True, "message": "AI 추천조건 적용 완료", "applied_strategy": state.get('current_strategy')})

@app.route("/api/keep_conditions")
def api_keep_conditions():
    report = build_ai_condition_report()
    state = read_state()
    state['last_ai_condition_report'] = report
    write_state(state)
    set_status("기존조건 유지", "AI 추천은 참고만 하고 기존 매매조건을 유지했습니다.")
    return jsonify({"ok": True, "message": "기존조건 유지 완료"})


@app.route("/api/refresh_daily_report")
def api_refresh_daily_report():
    r = build_ai_daily_report(force=True)
    set_status("AI일일리포트 작성", r.get('summary',''))
    return render_page()

@app.route("/api/refresh_investment_review")
def api_refresh_investment_review():
    r = build_ai_investment_review(force=True)
    set_status("AI 내투자평가 작성", r.get('summary',''))
    return render_page()

@app.route("/api/ai_daily_report")
def api_ai_daily_report():
    return jsonify({"ok": True, "report": build_ai_daily_report(force=str(request.args.get('force','0'))=='1')})

@app.route("/api/ai_investment_review")
def api_ai_investment_review():
    return jsonify({"ok": True, "review": build_ai_investment_review(force=str(request.args.get('force','0'))=='1')})

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
