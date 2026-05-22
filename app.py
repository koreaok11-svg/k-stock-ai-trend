# -*- coding: utf-8 -*-
"""
성일의 AI 주식바람 - KIWOOM REAL AUTO SCALPING v148_CLEAN_INTEGRATED_STABLE
파일명: app_kiwoom_real_auto_scalping_v148_clean_integrated_stable.py

클린 통합본 핵심:
- 중복 route / 중복 inject / 누적 패치 제거
- Render 기동 안정화: FinanceDataReader, pandas, numpy 없어도 실행
- 키움 인증 실패 시 보유종목 0개로 덮어쓰기 금지
- 마지막 정상 보유 캐시 유지
- 급등 후보 카드 기본 축소, 클릭 시 상세 펼침
- 보유종목 카드에 AI 상향 목표가 / 트레일링 보호선 / 최고수익률 표시
- 인증 정상일 때만 실제 매수/매도 전송
- 텔레그램 연결확인/테스트/비동기 알림 큐
"""

import os
import re
import json
import time
import math
import queue
import secrets
import threading
from pathlib import Path
from datetime import datetime, timedelta, timezone

try:
    import requests
except Exception as e:
    raise RuntimeError("requests 패키지가 필요합니다. requirements.txt에 requests를 추가하세요.") from e

try:
    import pandas as pd
except Exception:
    pd = None

try:
    import numpy as np
except Exception:
    np = None

try:
    import FinanceDataReader as fdr
except Exception:
    fdr = None

from flask import Flask, jsonify, request, render_template_string, Response

APP_VERSION = "v148"
APP_NAME = "성일의 AI 주식바람"
APP_BADGE = "KIWOOM REAL AUTO v148"

app = Flask(__name__)
KST = timezone(timedelta(hours=9))

BASE_DIR = Path(os.getenv("APP_DATA_DIR", "/var/data" if os.path.isdir("/var/data") else "/tmp"))
try:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    BASE_DIR = Path("/tmp")

HOLDINGS_FILE = Path(os.getenv("SERVER_HOLDINGS_FILE", str(BASE_DIR / "sungil_holdings_clean.json")))
HOLDINGS_BACKUP_FILE = Path(os.getenv("SERVER_HOLDINGS_BACKUP_FILE", str(BASE_DIR / "sungil_holdings_last_good.json")))
TRADE_STATE_FILE = Path(os.getenv("TRADE_STATE_FILE", str(BASE_DIR / "sungil_trade_state_clean.json")))
CANDIDATE_CACHE_FILE = Path(os.getenv("CANDIDATE_CACHE_FILE", str(BASE_DIR / "sungil_candidates_cache.json")))
ALERT_LOG_FILE = Path(os.getenv("ALERT_LOG_FILE", str(BASE_DIR / "sungil_alert_log.json")))

FILE_LOCK = threading.RLock()
WATCH_LOCK = threading.RLock()
ORDER_LOCK = threading.RLock()
TELEGRAM_Q = queue.Queue(maxsize=200)

KIWOOM_BASE_URL = os.getenv("KIWOOM_BASE_URL", "https://api.kiwoom.com").rstrip("/")
KIWOOM_APP_KEY = os.getenv("KIWOOM_APP_KEY", "").strip()
KIWOOM_SECRET_KEY = (
    os.getenv("KIWOOM_SECRET_KEY", "")
    or os.getenv("KIWOOM_APP_SECRET", "")
    or os.getenv("KIWOOM_SECRET", "")
).strip()
KIWOOM_REAL_TRADING = os.getenv("KIWOOM_REAL_TRADING", "false").lower() == "true"
KIWOOM_DRY_RUN = os.getenv("KIWOOM_DRY_RUN", "true").lower() == "true"
KIWOOM_PRICE_REQUIRED = os.getenv("KIWOOM_PRICE_REQUIRED", "true").lower() == "true"
ORDER_CASH_SAFETY_RATE = float(os.getenv("ORDER_CASH_SAFETY_RATE", "0.96") or "0.96")
PRICE_DIFF_LIMIT = float(os.getenv("PRICE_DIFF_LIMIT", "0.015") or "0.015")
WATCH_INTERVAL = int(os.getenv("SERVER_WATCH_INTERVAL", "15") or "15")
CANDIDATE_REFRESH_SEC = int(os.getenv("CANDIDATE_REFRESH_SEC", "45") or "45")
CACHE_STALE_SEC = int(os.getenv("CACHE_STALE_SEC", "120") or "120")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

TOKEN_CACHE = {"token": "", "expires": 0, "last_error": ""}

THEME_MAP = {
    "삼성전자": "AI반도체/HBM", "SK하이닉스": "AI반도체/HBM", "한미반도체": "AI반도체/HBM",
    "제주반도체": "AI반도체/HBM", "SFA반도체": "AI반도체/HBM", "하나마이크론": "AI반도체/HBM",
    "대한전선": "전력설비/데이터센터", "HD현대일렉트릭": "전력설비/데이터센터",
    "효성중공업": "전력설비/데이터센터", "LS ELECTRIC": "전력설비/데이터센터", "삼성전기": "전력설비/데이터센터",
    "이수페타시스": "AI서버/PCB", "대덕전자": "AI서버/PCB", "심텍": "AI서버/PCB",
    "오이솔루션": "광통신/CPO", "라이트론": "광통신/CPO", "쏠리드": "광통신/CPO",
    "레인보우로보틱스": "로봇/피지컬AI", "두산로보틱스": "로봇/피지컬AI", "휴림로봇": "로봇/피지컬AI",
    "NAVER": "인터넷/플랫폼", "카카오": "인터넷/플랫폼", "삼성중공업": "조선/방산",
    "현대로템": "방산/우주항공", "한화에어로스페이스": "방산/우주항공", "대한항공": "항공/물류",
}
KEYWORD_THEMES = {
    "AI반도체/HBM": ["반도체", "하이닉스", "HBM", "마이크론", "리노", "ISC"],
    "전력설비/데이터센터": ["전력", "전기", "일렉트릭", "변압기", "전선", "중공업", "데이터센터"],
    "AI서버/PCB": ["PCB", "기판", "페타시스", "대덕", "심텍"],
    "광통신/CPO": ["광", "통신", "네트웍스", "오이솔루션", "쏠리드"],
    "로봇/피지컬AI": ["로봇", "로보", "휴림", "뉴로메카", "레인보우"],
    "방산/우주항공": ["방산", "우주", "항공", "로템", "한화"],
    "조선/방산": ["조선", "중공업", "선박"],
}
THEME_WEIGHT = {
    "AI반도체/HBM": 1.35, "전력설비/데이터센터": 1.30, "AI서버/PCB": 1.20,
    "광통신/CPO": 1.18, "로봇/피지컬AI": 1.15, "방산/우주항공": 1.14,
    "조선/방산": 1.08, "인터넷/플랫폼": 1.03, "기타/개별이슈": 0.96,
}
FALLBACK_STOCKS = [
    {"Code": "080220", "Name": "제주반도체", "Market": "KOSDAQ", "Close": 122800, "ChagesRatio": 4.24, "Amount": 93040000000, "Volume": 7800000, "Marcap": 420000000000},
    {"Code": "010140", "Name": "삼성중공업", "Market": "KOSPI", "Close": 29550, "ChagesRatio": 2.7, "Amount": 245450000000, "Volume": 12000000, "Marcap": 25000000000000},
    {"Code": "009150", "Name": "삼성전기", "Market": "KOSPI", "Close": 1262000, "ChagesRatio": 4.82, "Amount": 180000000000, "Volume": 140000, "Marcap": 9000000000000},
    {"Code": "001120", "Name": "LX인터내셔널", "Market": "KOSPI", "Close": 34400, "ChagesRatio": 3.2, "Amount": 56000000000, "Volume": 1550000, "Marcap": 1300000000000},
    {"Code": "000660", "Name": "SK하이닉스", "Market": "KOSPI", "Close": 226000, "ChagesRatio": 1.8, "Amount": 500000000000, "Volume": 2500000, "Marcap": 160000000000000},
    {"Code": "005930", "Name": "삼성전자", "Market": "KOSPI", "Close": 77000, "ChagesRatio": 1.2, "Amount": 800000000000, "Volume": 11000000, "Marcap": 460000000000000},
    {"Code": "298040", "Name": "효성중공업", "Market": "KOSPI", "Close": 415000, "ChagesRatio": 5.1, "Amount": 110000000000, "Volume": 300000, "Marcap": 3900000000000},
    {"Code": "001440", "Name": "대한전선", "Market": "KOSPI", "Close": 16500, "ChagesRatio": 3.8, "Amount": 92000000000, "Volume": 6000000, "Marcap": 2500000000000},
]

WATCH_STATE = {
    "running": False,
    "thread": None,
    "last_check": "",
    "best_code": "",
    "best_score": 0,
    "last_alerts": {},
}


def now_kst():
    return datetime.now(KST)


def fmt_time():
    return now_kst().strftime("%Y-%m-%d %H:%M:%S")


def safe_float(v, default=0.0):
    try:
        if v is None:
            return default
        if isinstance(v, str):
            v = v.replace(",", "").replace("+", "").strip()
            if v == "":
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
    try:
        return f"{int(round(safe_float(v, 0))):,}원"
    except Exception:
        return "0원"


def pct(v):
    try:
        return f"{safe_float(v, 0):.2f}%"
    except Exception:
        return "0.00%"


def atomic_write_json(path, data):
    with FILE_LOCK:
        path = Path(path)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    return True


def read_json(path, default):
    try:
        with FILE_LOCK:
            path = Path(path)
            if not path.exists():
                return default
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
    except Exception:
        return default


def read_holdings():
    data = read_json(HOLDINGS_FILE, [])
    return data if isinstance(data, list) else []


def write_holdings(items, backup_if_nonempty=True):
    items = items if isinstance(items, list) else []
    atomic_write_json(HOLDINGS_FILE, items)
    if backup_if_nonempty and items:
        atomic_write_json(HOLDINGS_BACKUP_FILE, {"items": items, "updated_at": fmt_time(), "source": "LAST_GOOD"})
    return True


def read_last_good_holdings():
    data = read_json(HOLDINGS_BACKUP_FILE, {})
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data.get("items"), data.get("updated_at", "")
    if isinstance(data, list):
        return data, ""
    return [], ""


def write_alert_log(msg, ok=True):
    logs = read_json(ALERT_LOG_FILE, [])
    if not isinstance(logs, list):
        logs = []
    logs.insert(0, {"time": fmt_time(), "ok": bool(ok), "message": str(msg)[:500]})
    logs = logs[:50]
    atomic_write_json(ALERT_LOG_FILE, logs)


TRADE_DEFAULTS = {
    "auto_trade_enabled": False,
    "panic_stop": False,
    "daily_realized_pnl": 0,
    "trade_count_today": 0,
    "last_trade_date": "",
    "last_status": "대기중",
    "last_status_time": "",
    "last_order_message": "",
    "last_candidate": None,
    "last_kiwoom_debug": {},
    "max_positions": 3,
    "min_order_cash": 50000,
    "daily_max_loss": -30000,
    "target_rate": 0.027,
    "stop_rate": -0.018,
    "profit_guard_rate": 0.012,
    "trailing_stop_rate": 0.011,
    "force_exit_time": "15:15",
    "max_trades_per_day": 10,
    "trade_log": [],
}


def read_trade_state():
    data = read_json(TRADE_STATE_FILE, {})
    state = dict(TRADE_DEFAULTS)
    if isinstance(data, dict):
        state.update(data)
    return state


def write_trade_state(state):
    merged = dict(TRADE_DEFAULTS)
    if isinstance(state, dict):
        merged.update(state)
    atomic_write_json(TRADE_STATE_FILE, merged)
    return True


def update_status(status, message="", candidate=None, extra=None):
    state = read_trade_state()
    state["last_status"] = str(status)
    state["last_status_time"] = fmt_time()
    state["last_order_message"] = str(message)[:800]
    if candidate is not None:
        state["last_candidate"] = candidate
    if extra:
        state.update(extra)
    write_trade_state(state)
    return state


def update_kiwoom_debug(stage, message="", code="", status=0, data=None):
    state = read_trade_state()
    state["last_kiwoom_debug"] = {
        "time": fmt_time(),
        "stage": str(stage),
        "code": str(code),
        "http_status": status,
        "message": kiwoom_help_message(message),
        "data": scrub_sensitive(data),
    }
    write_trade_state(state)


def scrub_sensitive(data):
    if not isinstance(data, dict):
        return str(data)[:500] if data is not None else None
    out = {}
    for k, v in list(data.items())[:30]:
        if str(k).lower() in ["token", "authorization", "appkey", "secretkey", "secret"]:
            continue
        out[str(k)] = str(v)[:300] if not isinstance(v, (dict, list)) else "..."
    return out


def kiwoom_help_message(msg):
    s = str(msg or "")
    if "8050" in s or "지정단말기" in s or "인증에 실패" in s:
        return "키움 인증 실패(8050/지정단말기)입니다. Render IP 등록, App Key/Secret 재발급/입력, 영웅문S# 지정단말기/추가인증 상태를 확인하세요."
    if "8001" in s or "8002" in s or "App Key" in s or "Secret" in s:
        return "키움 App Key/Secret 오류입니다. Render 환경변수 KIWOOM_APP_KEY / KIWOOM_SECRET_KEY 값을 확인하세요."
    return s[:700]


def market_is_open():
    n = now_kst()
    if n.weekday() >= 5:
        return False
    hm = n.hour * 100 + n.minute
    return 900 <= hm <= 1520


def kiwoom_ready():
    return bool(KIWOOM_APP_KEY and KIWOOM_SECRET_KEY)


def kiwoom_get_token():
    if TOKEN_CACHE["token"] and time.time() < TOKEN_CACHE["expires"]:
        return TOKEN_CACHE["token"]
    if not kiwoom_ready():
        msg = "KIWOOM_APP_KEY / KIWOOM_SECRET_KEY 환경변수가 비어 있습니다."
        TOKEN_CACHE["last_error"] = msg
        update_kiwoom_debug("token_env_missing", msg)
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
            data = {"raw": r.text[:500]}
        if r.status_code != 200 or not data.get("token"):
            msg = data.get("return_msg") or data.get("message") or str(data)[:500]
            TOKEN_CACHE["last_error"] = msg
            update_kiwoom_debug("token_fail", msg, status=r.status_code, data=data)
            raise RuntimeError("키움 토큰 발급 실패: " + str(msg))
        TOKEN_CACHE["token"] = data["token"]
        TOKEN_CACHE["expires"] = time.time() + 60 * 60 * 23
        TOKEN_CACHE["last_error"] = ""
        update_kiwoom_debug("token_ok", "토큰 발급 성공", status=r.status_code)
        return TOKEN_CACHE["token"]
    except Exception as e:
        TOKEN_CACHE["last_error"] = str(e)
        update_kiwoom_debug("token_exception", str(e))
        raise


def kiwoom_headers(api_id):
    token = kiwoom_get_token()
    return {
        "Content-Type": "application/json;charset=UTF-8",
        "authorization": "Bearer " + token,
        "cont-yn": "N",
        "next-key": "",
        "api-id": api_id,
    }


def parse_price(data):
    keys = ["cur_prc", "curPrice", "currentPrice", "now", "price", "stck_prpr", "현재가", "closePrice", "lastPrice"]
    if isinstance(data, dict):
        for k in keys:
            if k in data:
                p = abs(safe_float(str(data.get(k)).replace("-", "").replace("+", ""), 0))
                if p >= 10:
                    return p
        for v in data.values():
            p = parse_price(v)
            if p >= 10:
                return p
    elif isinstance(data, list):
        for x in data:
            p = parse_price(x)
            if p >= 10:
                return p
    return 0


def get_kiwoom_live_price(code):
    code = str(code).zfill(6)
    try:
        r = requests.post(
            KIWOOM_BASE_URL + "/api/dostk/stkinfo",
            json={"stk_cd": code},
            headers=kiwoom_headers("ka10001"),
            timeout=7,
        )
        data = r.json() if r.text else {}
        p = parse_price(data)
        if r.status_code == 200 and p >= 10:
            update_kiwoom_debug("price_ok", f"{code} 현재가 {p}", code=code, status=r.status_code)
            return p
        msg = data.get("return_msg") or data.get("message") or str(data)[:500]
        update_kiwoom_debug("price_fail", msg, code=code, status=r.status_code, data=data)
    except Exception as e:
        update_kiwoom_debug("price_exception", str(e), code=code)
    return 0


def get_naver_live_price(code):
    code = str(code).zfill(6)
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"}
    urls = [f"https://m.stock.naver.com/api/stock/{code}/basic", f"https://api.stock.naver.com/stock/{code}/basic"]
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=3)
            if r.status_code == 200 and r.text:
                data = r.json()
                for k in ["closePrice", "now", "lastPrice", "currentPrice"]:
                    if k in data:
                        p = safe_float(str(data[k]).replace(",", ""), 0)
                        if p >= 10:
                            return p
        except Exception:
            pass
    try:
        r = requests.get(f"https://finance.naver.com/item/main.naver?code={code}", headers=headers, timeout=3)
        m = re.search(r'<p class="no_today">[\s\S]*?<span class="blind">([\d,]+)</span>', r.text)
        if m:
            p = safe_float(m.group(1).replace(",", ""), 0)
            if p >= 10:
                return p
    except Exception:
        pass
    return 0


def get_trade_live_price(code, fallback=True):
    p = get_kiwoom_live_price(code)
    if p >= 10:
        return p, "KIWOOM"
    if fallback:
        p2 = get_naver_live_price(code)
        if p2 >= 10:
            return p2, "NAVER"
    return 0, "NONE"


def parse_cash(data):
    if not isinstance(data, (dict, list)):
        return 0
    order_keys = ["ord_psbl", "buy_psbl", "주문가능", "매수가능", "현금주문가능", "ord_alow", "available", "avail"]
    deposit_keys = ["예수금", "dpst", "deposit", "cash", "현금", "추정인출", "인출가능"]

    def deep(obj, keys):
        best = 0
        if isinstance(obj, dict):
            for k, v in obj.items():
                if any(w in str(k) for w in keys):
                    best = max(best, abs(safe_float(v, 0)))
                best = max(best, deep(v, keys))
        elif isinstance(obj, list):
            for x in obj:
                best = max(best, deep(x, keys))
        return best

    return deep(data, order_keys) or deep(data, deposit_keys)


def get_kiwoom_cash():
    if not kiwoom_ready():
        return {"ok": False, "cash": 0, "source": "NONE", "message": "키움 환경변수 미설정"}
    endpoints = [
        ("/api/dostk/acnt", "kt00001", {"qry_tp": os.getenv("KIWOOM_CASH_QRY_TP", "3")}),
        ("/api/dostk/acnt", "kt00004", {"qry_tp": os.getenv("KIWOOM_CASH_QRY_TP", "3")}),
        ("/api/dostk/acnt", "kt00018", {"qry_tp": os.getenv("KIWOOM_CASH_QRY_TP", "3")}),
    ]
    last = ""
    for path, api_id, body in endpoints:
        try:
            r = requests.post(KIWOOM_BASE_URL + path, json=body, headers=kiwoom_headers(api_id), timeout=7)
            data = r.json() if r.text else {}
            cash = parse_cash(data)
            if r.status_code == 200 and cash > 0:
                update_kiwoom_debug("cash_ok", f"주문가능금액 {cash}", status=r.status_code)
                return {"ok": True, "cash": cash, "source": "KIWOOM", "message": "키움 주문가능금액 조회 성공"}
            last = data.get("return_msg") or data.get("message") or str(data)[:500]
            update_kiwoom_debug("cash_fail", last, status=r.status_code, data=data)
        except Exception as e:
            last = str(e)
            update_kiwoom_debug("cash_exception", last)
    return {"ok": False, "cash": 0, "source": "NONE", "message": last or "키움 주문가능금액 조회 실패"}


def find_list_candidates(obj):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                joined = " ".join(str(x) for item in v[:2] for x in item.keys())
                if any(w in joined for w in ["종목", "stk", "qty", "보유", "현재가", "매입"]):
                    found.append(v)
            found += find_list_candidates(v)
    elif isinstance(obj, list):
        for x in obj:
            found += find_list_candidates(x)
    return found


def parse_kiwoom_holdings(data):
    lists = find_list_candidates(data)
    out = []
    for rows in lists:
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = str(
                row.get("stk_cd") or row.get("code") or row.get("종목코드") or row.get("pdno") or row.get("isu_cd") or ""
            )
            code = re.sub(r"[^0-9]", "", code).zfill(6)
            name = str(row.get("stk_nm") or row.get("name") or row.get("종목명") or row.get("isu_nm") or "").strip()
            qty = (
                row.get("rmnd_qty") or row.get("hldg_qty") or row.get("qty") or row.get("보유수량") or row.get("수량") or row.get("ord_psbl_qty")
            )
            buy = (
                row.get("avg_prc") or row.get("pchs_avg_pric") or row.get("buyPrice") or row.get("매입가") or row.get("평균단가") or row.get("매입평균가")
            )
            cur = row.get("cur_prc") or row.get("now") or row.get("현재가") or row.get("lastPrice")
            q = safe_float(qty, 0)
            b = abs(safe_float(buy, 0))
            c = abs(safe_float(cur, 0))
            if code and code != "000000" and q > 0:
                target = round(b * (1 + safe_float(read_trade_state().get("target_rate"), 0.027))) if b else 0
                stop = round(b * (1 + safe_float(read_trade_state().get("stop_rate"), -0.018))) if b else 0
                out.append(normalize_holding({
                    "code": code, "name": name or code, "qty": int(q), "buyPrice": b,
                    "lastPrice": c, "target": target, "stop": stop,
                    "source": "KIWOOM", "lastCheckedAt": fmt_time(),
                }))
    uniq = {}
    for h in out:
        uniq[h["code"]] = h
    return list(uniq.values())


def fetch_kiwoom_holdings():
    if not kiwoom_ready():
        return {"ok": False, "items": [], "message": "키움 환경변수 미설정", "auth_failure": True}
    endpoints = [
        ("/api/dostk/acnt", "kt00018", {"qry_tp": "2"}),
        ("/api/dostk/acnt", "kt00004", {"qry_tp": "2"}),
        ("/api/dostk/acnt", "kt00001", {"qry_tp": "2"}),
    ]
    last = ""
    for path, api_id, body in endpoints:
        try:
            r = requests.post(KIWOOM_BASE_URL + path, json=body, headers=kiwoom_headers(api_id), timeout=8)
            data = r.json() if r.text else {}
            if r.status_code == 200:
                items = parse_kiwoom_holdings(data)
                update_kiwoom_debug("holdings_ok", f"보유 {len(items)}개 조회", status=r.status_code)
                return {"ok": True, "items": items, "message": f"키움 보유 {len(items)}개 조회", "empty": len(items) == 0}
            last = data.get("return_msg") or data.get("message") or str(data)[:500]
            update_kiwoom_debug("holdings_fail", last, status=r.status_code, data=data)
        except Exception as e:
            last = str(e)
            update_kiwoom_debug("holdings_exception", last)
    auth_failure = any(w in last for w in ["8050", "인증", "지정단말기", "token", "토큰", "App Key"])
    return {"ok": False, "items": [], "message": kiwoom_help_message(last), "auth_failure": auth_failure}


def normalize_holding(h):
    h = dict(h or {})
    code = re.sub(r"[^0-9]", "", str(h.get("code", ""))).zfill(6)
    h["code"] = code
    h["name"] = str(h.get("name") or code)
    h["qty"] = safe_int(h.get("qty"), 0)
    h["buyPrice"] = safe_float(h.get("buyPrice"), 0)
    h["lastPrice"] = safe_float(h.get("lastPrice"), 0)
    if h["lastPrice"] <= 0 and code != "000000":
        h["lastPrice"] = get_naver_live_price(code)
        if h["lastPrice"] > 0:
            h["priceSource"] = "NAVER"
    target_rate = safe_float(read_trade_state().get("target_rate"), 0.027)
    stop_rate = safe_float(read_trade_state().get("stop_rate"), -0.018)
    if safe_float(h.get("target"), 0) <= 0 and h["buyPrice"] > 0:
        h["target"] = round(h["buyPrice"] * (1 + target_rate))
    if safe_float(h.get("stop"), 0) <= 0 and h["buyPrice"] > 0:
        h["stop"] = round(h["buyPrice"] * (1 + stop_rate))
    return update_trailing_fields(h)


def update_trailing_fields(h):
    h = dict(h or {})
    buy = safe_float(h.get("buyPrice"), 0)
    cur = safe_float(h.get("lastPrice"), 0)
    target = safe_float(h.get("target"), 0)
    stop = safe_float(h.get("stop"), 0)
    state = read_trade_state()
    trail_rate = safe_float(state.get("trailing_stop_rate"), 0.011)
    if buy <= 0 or cur <= 0:
        return h
    high = max(safe_float(h.get("highestPrice"), 0), cur)
    high_profit = ((high - buy) / buy * 100) if buy else 0
    dynamic_target = safe_float(h.get("activeDynamicTarget"), 0)
    ai_hold = False
    reason = ""
    if target > 0 and cur >= target:
        ai_hold = True
        dynamic_target = max(dynamic_target, round(high * 1.015), round(target * 1.02))
        trailing_stop = max(stop, round(high * (1 - trail_rate)))
        reason = "기본 목표가를 돌파했지만 강세로 판단되어 AI 상향 목표/트레일링 보호선으로 추적 중입니다."
    else:
        trailing_stop = safe_float(h.get("trailingStopPrice"), 0) or stop
        reason = "기본 목표/손절 사이 관찰 구간입니다."
    h["highestPrice"] = high
    h["highestProfitPct"] = round(high_profit, 2)
    h["activeDynamicTarget"] = dynamic_target
    h["trailingStopPrice"] = trailing_stop
    h["aiHoldMode"] = ai_hold
    h["aiHoldReason"] = reason
    return h


def sync_holdings_from_kiwoom(force=False):
    res = fetch_kiwoom_holdings()
    if res.get("ok"):
        items = [normalize_holding(x) for x in res.get("items", [])]
        if items:
            write_holdings(items, backup_if_nonempty=True)
            update_status("키움 실보유 동기화 완료", f"보유 {len(items)}개")
            return {"ok": True, "items": items, "source": "KIWOOM", "message": f"키움 보유 {len(items)}개 동기화"}
        # 키움이 정상 응답으로 0개를 준 경우에만 기존 파일을 비워도 되지만,
        # 사용자가 혼동하지 않도록 장중/인증 애매할 때는 백업 유지.
        if force:
            write_holdings([], backup_if_nonempty=False)
            return {"ok": True, "items": [], "source": "KIWOOM_EMPTY", "message": "키움 정상 응답: 보유 0개"}
        last_items, updated = read_last_good_holdings()
        return {"ok": True, "items": last_items, "source": "LAST_GOOD_AFTER_EMPTY", "message": f"키움 0개 응답, 마지막 정상 캐시 유지 {updated}"}
    # 실패 시 절대 빈 리스트로 덮어쓰지 않음
    items = read_holdings()
    source = "LOCAL_CACHE"
    if not items:
        items, updated = read_last_good_holdings()
        source = "LAST_GOOD"
    msg = res.get("message") or "키움 보유 조회 실패"
    update_status("키움 API 확인 필요", msg)
    return {"ok": False, "items": [normalize_holding(x) for x in items], "source": source, "message": msg, "auth_failure": res.get("auth_failure", False)}


def classify_theme(name):
    name = str(name)
    if name in THEME_MAP:
        return THEME_MAP[name]
    for theme, kws in KEYWORD_THEMES.items():
        if any(kw in name for kw in kws):
            return theme
    return "기타/개별이슈"


def get_market_rows(limit=900):
    rows = []
    if fdr is not None and pd is not None:
        try:
            df = fdr.StockListing("KRX")
            if df is not None and len(df) > 0:
                for _, r in df.head(limit).iterrows():
                    rows.append({
                        "Code": str(r.get("Code", "")).zfill(6),
                        "Name": str(r.get("Name", "")),
                        "Market": str(r.get("Market", "")),
                        "Close": safe_float(r.get("Close"), 0),
                        "ChagesRatio": safe_float(r.get("ChagesRatio", r.get("Change", 0)), 0),
                        "Amount": safe_float(r.get("Amount"), 0),
                        "Volume": safe_float(r.get("Volume"), 0),
                        "Marcap": safe_float(r.get("Marcap"), 0),
                    })
        except Exception as e:
            update_status("KRX 조회 실패", str(e))
    if not rows:
        rows = [dict(x) for x in FALLBACK_STOCKS]
    return rows


def score_candidate(row, cash=500000):
    name = str(row.get("Name", ""))
    code = str(row.get("Code", "")).zfill(6)
    price = safe_float(row.get("Close"), 0)
    change = safe_float(row.get("ChagesRatio"), 0)
    amount = safe_float(row.get("Amount"), 0)
    volume = safe_float(row.get("Volume"), 0)
    marcap = safe_float(row.get("Marcap"), 0)
    theme = classify_theme(name)
    weight = THEME_WEIGHT.get(theme, 0.96)
    amount_score = min(100, amount / 1_000_000_000 * 2.2)
    volume_score = min(100, math.log10(max(volume, 10)) * 16)
    if 1.0 <= change <= 5.0:
        change_score = 95
    elif 5.0 < change <= 9.0:
        change_score = 78
    elif 0.2 <= change < 1.0:
        change_score = 55
    else:
        change_score = 42
    marcap_score = min(100, math.log10(max(marcap, 10)) * 5)
    score = (amount_score * 0.35 + volume_score * 0.22 + change_score * 0.28 + marcap_score * 0.15) * weight
    score = round(max(0, min(150, score)), 2)
    qty_possible = int(cash // price) if price > 0 else 0
    return {
        "code": code, "name": name, "market": str(row.get("Market", "")), "theme": theme,
        "price": round(price), "priceSource": "KRX_FAST_CACHE" if fdr is not None else "LOCAL_FALLBACK",
        "dayChange": round(change, 2), "amount": round(amount), "volume": round(volume),
        "score": score, "qtyPossible": qty_possible, "buyZone": round(price * 0.995),
        "target": round(price * 1.035), "stop": round(price * 0.975),
        "comment": "빠른 후보 화면은 캐시 기준입니다. 실제 매수 직전에는 키움 현재가/주문가능금액을 다시 확인합니다.",
    }


def build_candidates(force=False, min_score=60, max_items=10):
    cache = read_json(CANDIDATE_CACHE_FILE, {})
    now = time.time()
    if not force and isinstance(cache, dict) and cache.get("items") and now - safe_float(cache.get("ts"), 0) < CANDIDATE_REFRESH_SEC:
        return cache
    rows = get_market_rows()
    picks = [score_candidate(r) for r in rows]
    picks = [p for p in picks if p["price"] >= 1000 and 0.1 <= p["dayChange"] <= 12 and p["amount"] >= 3_000_000_000 and p["score"] >= min_score]
    if not picks and min_score > 45:
        picks = [score_candidate(r) for r in rows]
        picks = [p for p in picks if p["price"] >= 1000 and 0.0 <= p["dayChange"] <= 15 and p["amount"] >= 1_000_000_000 and p["score"] >= 45]
    picks = sorted(picks, key=lambda x: x["score"], reverse=True)[:max_items]
    data = {"ok": True, "items": picks, "updated_at": fmt_time(), "ts": now, "source": "FDR_KRX" if fdr else "LOCAL_FALLBACK"}
    atomic_write_json(CANDIDATE_CACHE_FILE, data)
    return data


def send_telegram_direct(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 미설정"
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=6,
        )
        if r.status_code == 200:
            return True, "sent"
        return False, r.text[:500]
    except Exception as e:
        return False, str(e)


def enqueue_telegram(text):
    try:
        TELEGRAM_Q.put_nowait(text)
        return True
    except Exception:
        return False


def telegram_worker():
    while True:
        text = TELEGRAM_Q.get()
        ok, msg = send_telegram_direct(text)
        write_alert_log(msg if ok else "텔레그램 실패: " + msg, ok)
        TELEGRAM_Q.task_done()


def kiwoom_order(side, code, qty, price=0, order_type="market"):
    if not KIWOOM_REAL_TRADING:
        return {"ok": False, "message": "KIWOOM_REAL_TRADING=true 환경변수가 필요합니다."}
    if KIWOOM_DRY_RUN:
        return {"ok": True, "dry_run": True, "message": "DRY_RUN 상태라 실제 주문은 전송하지 않았습니다."}
    code = str(code).zfill(6)
    qty = int(qty)
    if qty <= 0:
        return {"ok": False, "message": "주문 수량 오류"}
    api_id = "kt10000" if side == "buy" else "kt10001"
    trde_tp = "3" if order_type == "market" else "0"
    body = {"dmst_stex_tp": "KRX", "stk_cd": code, "ord_qty": str(qty), "ord_uv": "" if trde_tp == "3" else str(int(price)), "trde_tp": trde_tp, "cond_uv": ""}
    try:
        r = requests.post(KIWOOM_BASE_URL + "/api/dostk/ordr", json=body, headers=kiwoom_headers(api_id), timeout=8)
        data = r.json() if r.text else {}
        ok = r.status_code == 200 and str(data.get("return_code", "0")) in ["0", ""]
        return {"ok": ok, "status": r.status_code, "response": data, "request": body, "message": data.get("return_msg") or data.get("message") or str(data)[:300]}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def auto_sell_holding(reason, h, cur=0):
    h = normalize_holding(h)
    if not market_is_open():
        return {"ok": False, "message": "정규장 시간이 아닙니다."}
    if not kiwoom_ready():
        return {"ok": False, "message": "키움 인증정보가 없어 매도 전송 잠금"}
    with ORDER_LOCK:
        res = kiwoom_order("sell", h["code"], h["qty"], 0, "market")
        if res.get("ok"):
            remove_holding(h["code"])
            enqueue_telegram(f"✅ <b>시장가 매도 요청</b>\n{h['name']}({h['code']})\n수량 {h['qty']}주\n사유: {reason}")
        return res


def remove_holding(code):
    code = str(code).zfill(6)
    items = [x for x in read_holdings() if str(x.get("code", "")).zfill(6) != code]
    write_holdings(items, backup_if_nonempty=True)
    return items


def check_one_holding(h):
    h = normalize_holding(h)
    code = h.get("code")
    cur, src = get_trade_live_price(code, fallback=True)
    if cur >= 10:
        h["lastPrice"] = cur
        h["priceSource"] = src
        h["lastCheckedAt"] = fmt_time()
    h = update_trailing_fields(h)
    cur = safe_float(h.get("lastPrice"), 0)
    target = safe_float(h.get("target"), 0)
    stop = safe_float(h.get("stop"), 0)
    trailing_stop = safe_float(h.get("trailingStopPrice"), 0)
    if cur > 0 and trailing_stop > 0 and cur <= trailing_stop and safe_float(h.get("highestProfitPct"), 0) >= 1.0:
        enqueue_telegram(f"⚠️ <b>트레일링 보호선 근접/이탈</b>\n{h['name']}({code})\n현재가 {money(cur)}\n보호선 {money(trailing_stop)}")
    elif cur > 0 and stop > 0 and cur <= stop:
        enqueue_telegram(f"⚠️ <b>손절가 이탈</b>\n{h['name']}({code})\n현재가 {money(cur)} / 손절가 {money(stop)}")
    elif cur > 0 and target > 0 and cur >= target:
        enqueue_telegram(f"🎯 <b>목표가 도달</b>\n{h['name']}({code})\n현재가 {money(cur)} / 목표가 {money(target)}")
    return h


def watch_loop():
    last_candidate = 0
    while WATCH_STATE.get("running"):
        try:
            items = read_holdings()
            if items:
                new_items = [check_one_holding(h) for h in items]
                write_holdings(new_items, backup_if_nonempty=True)
            if time.time() - last_candidate > CANDIDATE_REFRESH_SEC:
                build_candidates(force=True)
                last_candidate = time.time()
            WATCH_STATE["last_check"] = fmt_time()
        except Exception as e:
            print("watch_loop error:", e, flush=True)
        time.sleep(WATCH_INTERVAL)


def ensure_watch_running():
    with WATCH_LOCK:
        WATCH_STATE["running"] = True
        t = WATCH_STATE.get("thread")
        if t is None or not t.is_alive():
            t = threading.Thread(target=watch_loop, daemon=True)
            WATCH_STATE["thread"] = t
            t.start()
    return True


def auth_status_light():
    state = read_trade_state()
    dbg = state.get("last_kiwoom_debug", {}) or {}
    msg = dbg.get("message") or TOKEN_CACHE.get("last_error") or ""
    if not kiwoom_ready():
        return {"level": "red", "label": "키움 환경변수 필요", "message": "KIWOOM_APP_KEY / KIWOOM_SECRET_KEY 미설정"}
    if "8050" in msg or "인증 실패" in msg or "지정단말기" in msg:
        return {"level": "red", "label": "키움 API 확인 필요", "message": msg}
    if TOKEN_CACHE.get("token"):
        return {"level": "green", "label": "키움 API 정상", "message": "토큰 캐시 정상"}
    return {"level": "yellow", "label": "키움 API 미확인", "message": "상태확인 또는 새로고침을 눌러 확인하세요."}


def render_candidate_card(p, idx=0):
    return f"""
    <div class="candidate-card" onclick="toggleDetail('cand-{idx}')">
      <div class="tags"><span>{p.get('market')}</span><span>{p.get('code')}</span><span>{p.get('theme')}</span><span>AI {p.get('score')}</span></div>
      <h3>{p.get('name')}</h3>
      <div class="grid2 compact">
        <div><small>현재가</small><b>{money(p.get('price'))}</b><em>{p.get('priceSource')}</em></div>
        <div><small>당일 흐름</small><b>{pct(p.get('dayChange'))}</b></div>
        <div><small>목표가</small><b class="red">{money(p.get('target'))}</b></div>
        <div><small>손절가</small><b class="blue">{money(p.get('stop'))}</b></div>
      </div>
      <div class="hint">🔎 종목을 누르면 상세정보를 펼칩니다.</div>
      <div id="cand-{idx}" class="detail hidden">
        <p><b>거래대금:</b> {safe_float(p.get('amount'))/100000000:.1f}억</p>
        <p><b>매수관찰:</b> {money(p.get('buyZone'))} / <b>가능수량:</b> {p.get('qtyPossible')}주</p>
        <p>{p.get('comment')}</p>
      </div>
    </div>
    """


def render_holding_card(h, idx=0):
    h = normalize_holding(h)
    buy = safe_float(h.get("buyPrice"), 0)
    cur = safe_float(h.get("lastPrice"), 0)
    qty = safe_float(h.get("qty"), 0)
    pnl = (cur - buy) * qty if buy and cur and qty else 0
    rate = ((cur - buy) / buy * 100) if buy and cur else 0
    ai_hold = bool(h.get("aiHoldMode"))
    sell_disabled = "" if kiwoom_ready() else "disabled"
    return f"""
    <div class="holding-card">
      <div class="holding-head">
        <h3>{h.get('name')} ({h.get('code')})</h3>
        <button class="danger" onclick="manualSell('{h.get('code')}')" {sell_disabled}>시장가 매도</button>
      </div>
      <p class="sub">상태: {'⚡ AI HOLD/트레일링' if ai_hold else '감시중'} · 가격출처 {h.get('priceSource','-')} · 최근확인 {h.get('lastCheckedAt','-')}</p>
      <div class="grid2">
        <div><small>실제 매수가</small><b>{money(buy)}</b></div>
        <div><small>실시간 현재가</small><b>{money(cur)}</b></div>
        <div><small>기본 목표가</small><b class="red">{money(h.get('target'))}</b></div>
        <div><small>손절가</small><b class="blue">{money(h.get('stop'))}</b></div>
        <div><small>AI 상향 목표가</small><b class="red">{money(h.get('activeDynamicTarget'))}</b></div>
        <div><small>트레일링 보호선</small><b class="blue">{money(h.get('trailingStopPrice'))}</b></div>
        <div><small>최고가/최고수익률</small><b>{money(h.get('highestPrice'))} / {pct(h.get('highestProfitPct'))}</b></div>
        <div><small>수량/평가손익</small><b>{int(qty)}주 / {money(pnl)} ({pct(rate)})</b></div>
      </div>
      <div class="comment">AI 코멘트: {h.get('aiHoldReason') or '관찰 구간입니다.'}</div>
    </div>
    """


def page_html():
    state = read_trade_state()
    auth = auth_status_light()
    holdings = read_holdings()
    candidates = build_candidates(force=False).get("items", [])
    alert_logs = read_json(ALERT_LOG_FILE, [])
    status_color = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(auth["level"], "🟡")
    holding_html = "".join(render_holding_card(h, i) for i, h in enumerate(holdings))
    if not holdings:
        last_items, upd = read_last_good_holdings()
        if last_items:
            holding_html = f"<div class='notice'>현재 키움 직접조회는 실패했지만 마지막 정상 보유캐시({upd})를 표시합니다.</div>" + "".join(render_holding_card(h, i) for i, h in enumerate(last_items))
        else:
            holding_html = f"<div class='notice'>표시 가능한 보유 캐시가 없습니다. 키움 인증 정상화 후 새로고침하거나, 아래 수동 표시로 UI만 확인할 수 있습니다.</div>{manual_holding_form()}"
    cand_html = "".join(render_candidate_card(p, i) for i, p in enumerate(candidates)) or "<div class='notice'>후보가 없습니다. 필터를 낮추거나 잠시 후 새로고침하세요.</div>"
    logs_html = "".join(f"<div class='log'>{'✅' if x.get('ok') else '⚠️'} {x.get('time')} · {x.get('message')}</div>" for x in alert_logs[:5]) or "<div class='log'>최근 알림 없음</div>"
    auto_on = "ON" if state.get("auto_trade_enabled") else "OFF"

    return f"""
<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{APP_NAME} {APP_VERSION}</title>
<style>
body{{margin:0;background:linear-gradient(120deg,#f6faef,#eef8ee);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#20372c}}
.wrap{{max-width:880px;margin:0 auto;padding:34px 18px 80px}}
.badge{{display:inline-block;background:#e4f3df;border-radius:999px;padding:10px 18px;font-weight:900;color:#426d49}}
h1{{font-size:44px;line-height:1.1;margin:22px 0 10px}} h2{{font-size:34px;margin:18px 0}} h3{{font-size:30px;margin:8px 0 10px}}
.card{{background:#fff;border-radius:28px;padding:28px;margin:26px 0;box-shadow:0 2px 14px rgba(60,80,50,.08)}}
.nav{{position:sticky;top:0;background:rgba(245,250,238,.92);backdrop-filter:blur(8px);z-index:5;padding:12px 0;display:flex;gap:12px;overflow:auto}}
.nav button,.btn{{border:0;border-radius:24px;padding:18px 24px;font-size:20px;font-weight:900;background:#eaf5e5;color:#2e5935}}
.btn.primary{{background:#5c9868;color:#fff}} .btn.dark{{background:#2d465b;color:#fff}} .btn.brown{{background:#a66a28;color:#fff}} .danger{{background:#ffe3e3;color:#b42323;border:0;border-radius:18px;padding:14px 18px;font-weight:900}}
input{{width:100%;box-sizing:border-box;border:1px solid #d8e5d0;border-radius:18px;padding:16px;font-size:20px;margin:8px 0 14px}}
.notice{{background:#fff6d9;border-radius:22px;padding:20px;margin:14px 0;color:#6a5a36;font-size:20px;line-height:1.5}}
.status-pill{{display:inline-block;border-radius:999px;padding:10px 16px;background:#f8d7da;color:#b42323;font-weight:900}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:14px}} .grid2>div{{background:#fbf6e8;border-radius:20px;padding:18px;text-align:center}}
.grid2 small{{display:block;color:#6d7489;font-size:15px}} .grid2 b{{display:block;font-size:22px;margin-top:8px}} .grid2 em{{display:block;color:#6d7489;font-style:normal;font-size:14px}}
.compact b{{font-size:21px}} .red{{color:#d3272d}} .blue{{color:#2d6cdf}}
.candidate-card,.holding-card{{background:#fffdf7;border:1px solid #e4e8d6;border-radius:26px;padding:22px;margin:18px 0}}
.tags span{{display:inline-block;background:#e9f4df;border-radius:999px;padding:8px 12px;margin:4px;font-weight:800;color:#6b5d3d}}
.hint,.comment{{background:#eaf8dd;border-radius:18px;padding:16px;margin-top:14px;font-weight:800;color:#416f45;line-height:1.5}}
.detail{{background:#fff7df;border-radius:18px;padding:14px;margin-top:12px;line-height:1.5}} .hidden{{display:none}}
.holding-head{{display:flex;justify-content:space-between;gap:10px;align-items:center}} .sub{{color:#687086;font-size:16px}}
.log{{background:#fffdf7;border:1px solid #eadfbf;border-radius:14px;padding:12px;margin:8px 0}}
details summary{{cursor:pointer;font-size:22px;font-weight:900;background:#eaf5e5;border-radius:18px;padding:18px}}
@media(max-width:600px){{h1{{font-size:38px}}h2{{font-size:32px}}.grid2{{grid-template-columns:1fr 1fr}}.wrap{{padding:24px 14px}}.card{{padding:22px}}}}
</style></head><body><div class="wrap">
<div class="badge">🌿 {APP_BADGE}</div>
<h1>{APP_NAME}</h1>
<p style="font-size:22px;color:#697287">키움 REST API 연동 · AI 최종 1종목 자동매수 · 목표/손절 자동매도 · 텔레그램 알림</p>
<div class="nav">
<button onclick="location.hash='setting'">⚙️ 설정</button><button onclick="location.hash='candidate'">⚡ 단타AI</button><button onclick="location.hash='holdings'">💼 보유</button><button onclick="location.hash='auto'">🤖 자동</button><button onclick="location.hash='alert'">📨 알림</button>
</div>

<section id="setting" class="card">
<h2>⚙️ 단타AI 필터 설정</h2>
<details><summary>🔎 필터 조건 보기 / 접기</summary>
<p>후보 필터는 화면 후보를 고르는 조건입니다. 실제 매수 직전에는 키움 현재가와 주문가능금액을 다시 확인합니다.</p>
<label>최소 AI 점수</label><input id="minScore" value="60">
<label>최대 당일 등락률(%)</label><input id="maxChange" value="12">
<label>최소 거래대금(원)</label><input id="minAmount" value="3000000000">
</details>
<button class="btn primary" onclick="refreshCandidates()">필터 적용/새로고침</button>
<button class="btn dark" onclick="nextCandidate()">다음 단타 후보 보기</button>
<button class="btn brown" onclick="testTelegram()">텔레그램 테스트 알림</button>
</section>

<section id="candidate" class="card"><h2>👀 급등 예상 감시 후보</h2><div id="candidateBox">{cand_html}</div></section>

<section id="holdings" class="card">
<h2>💼 키움 실보유 자동 동기화</h2>
<p style="font-size:21px;color:#697287">키움 실제 잔고 기준으로 표시합니다. 인증 실패 시 마지막 정상 캐시를 유지합니다.</p>
<button class="btn primary" onclick="syncHoldings()">키움 실보유 새로고침</button>
<button class="btn dark" onclick="diagnose()">API 직접 확인</button>
<button class="btn" onclick="clearScreen()">화면만 초기화</button>
<div id="holdingStatus" class="notice">표시 보유 {len(holdings)}종목 · 최근확인 {fmt_time()}</div>
<div id="holdingBox">{holding_html}</div>
</section>

<section id="auto" class="card">
<h2>🤖 키움 실전 자동매매</h2>
<div class="notice">상태: <b>{auto_on}</b> · <span class="status-pill">{status_color} {auth['label']}</span><br>키움 주문가능금액은 실제 주문 직전에 다시 확인합니다.<br>{auth['message']}</div>
<button class="btn primary" onclick="setAuto(1)">실전 자동매매 ON</button>
<button class="btn" onclick="setAuto(0)">자동매매 OFF</button>
<button class="btn brown" onclick="buyBest()">AI 최종 1종목 즉시매수</button>
<button class="btn dark" onclick="panic()">긴급정지</button>
<div id="autoStatus" class="notice">최근: {state.get('last_status')} · {state.get('last_status_time')}<br>{state.get('last_order_message')}</div>
<details><summary>🔎 상세 진행내용 보기 / 숨기기</summary>
<div class="notice">
<b>실전 운영 대시보드</b><br>
<span class="status-pill">{status_color} {auth['label']}</span><br>
오늘 실현손익/거래횟수는 앱 자동매매 기록 기준입니다. MTS 직접 매매 내역까지 가져오려면 키움 일별체결 API 연동이 추가로 필요합니다.
</div>
</details>
</section>

<section id="alert" class="card">
<h2>📨 실전 알림센터</h2>
<div class="notice"><b>이 기능은 무엇인가요?</b><br>매수·매도·손절·목표가 도달·키움 API 오류 발생 시 텔레그램으로 바로 알려주는 실전 모니터링 알림 기능입니다.</div>
<button class="btn primary" onclick="checkTelegram()">연결확인</button>
<button class="btn brown" onclick="testTelegram()">테스트알림</button>
<button class="btn dark" onclick="ensureWatch()">실전감시 ON</button>
<div id="telegramStatus" class="notice">{logs_html}</div>
</section>
</div>
<script>
function q(id){{return document.getElementById(id)}}
function toggleDetail(id){{let e=q(id); if(e)e.classList.toggle('hidden')}}
async function fetchJson(url, opt){{try{{let r=await fetch(url,opt||{{}}); return await r.json()}}catch(e){{return {{ok:false,message:String(e)}}}}}}
async function refreshCandidates(){{q('candidateBox').innerHTML='<div class="notice">후보 갱신중...</div>';let d=await fetchJson('/api/candidates?force=1&minScore='+q('minScore').value+'&maxChange='+q('maxChange').value+'&minAmount='+q('minAmount').value);q('candidateBox').innerHTML=d.html||'<div class="notice">'+(d.message||'후보 없음')+'</div>'}}
async function nextCandidate(){{await refreshCandidates(); location.hash='candidate'}}
async function syncHoldings(){{q('holdingStatus').innerHTML='키움 실보유 조회중...';let d=await fetchJson('/api/holdings/sync?force=1');q('holdingStatus').innerHTML=d.message||'완료'; if(d.html)q('holdingBox').innerHTML=d.html}}
async function diagnose(){{let d=await fetchJson('/api/diagnose');q('autoStatus').innerHTML='<pre style="white-space:pre-wrap">'+JSON.stringify(d,null,2)+'</pre>'}}
async function clearScreen(){{q('holdingStatus').innerHTML='화면 표시만 초기화했습니다. 실제 키움 잔고는 변경되지 않습니다.'}}
async function setAuto(v){{q('autoStatus').innerHTML='화면 반영 완료 / 서버 저장 확인중...';let d=await fetchJson('/api/auto?enabled='+v);q('autoStatus').innerHTML=d.message||'완료'}}
async function panic(){{let d=await fetchJson('/api/panic');q('autoStatus').innerHTML=d.message||'긴급정지'}}
async function buyBest(){{let d=await fetchJson('/api/buy_best');q('autoStatus').innerHTML=d.message||JSON.stringify(d)}}
async function manualSell(code){{if(!confirm(code+' 시장가 매도 요청할까요? 실제 주문 전송은 키움 인증 정상일 때만 가능합니다.'))return;let d=await fetchJson('/api/holdings/sell?code='+code);alert(d.message||JSON.stringify(d));}}
async function testTelegram(){{let d=await fetchJson('/api/telegram/test');q('telegramStatus').innerHTML=d.message||JSON.stringify(d)}}
async function checkTelegram(){{let d=await fetchJson('/api/telegram/check');q('telegramStatus').innerHTML=d.message||JSON.stringify(d)}}
async function ensureWatch(){{let d=await fetchJson('/api/watch/start');q('telegramStatus').innerHTML=d.message||'실전감시 시작'}}
</script></body></html>
"""


def manual_holding_form():
    return """
    <div class="notice" style="border:2px dashed #cfe2c8">
    <b>🧪 보유카드/매도버튼 화면 확인용 수동 표시</b><br>
    실제 키움 잔고를 바꾸지 않습니다. 키움 인증 실패 시 매도 전송은 잠깁니다.
    <input id="mhName" placeholder="종목명 예: 제주반도체">
    <input id="mhCode" placeholder="종목코드 예: 080220">
    <input id="mhQty" placeholder="수량 예: 2">
    <input id="mhBuy" placeholder="매수가 예: 109450">
    <button class="btn primary" onclick="manualHolding()">화면에 보유카드 표시</button>
    </div>
    <script>
    async function manualHolding(){
      const p={name:q('mhName').value,code:q('mhCode').value,qty:q('mhQty').value,buyPrice:q('mhBuy').value};
      let d=await fetchJson('/api/holdings/manual',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
      q('holdingStatus').innerHTML=d.message||'수동 표시 완료'; if(d.html)q('holdingBox').innerHTML=d.html;
    }
    </script>
    """


@app.route("/")
def index():
    ensure_watch_running()
    return render_template_string(page_html())


@app.route("/api/health")
def api_health():
    return jsonify({"ok": True, "version": APP_VERSION, "time": fmt_time()})


@app.route("/api/diagnose")
def api_diagnose():
    state = read_trade_state()
    return jsonify({
        "ok": True,
        "version": APP_VERSION,
        "time": fmt_time(),
        "kiwoom_ready": kiwoom_ready(),
        "auth": auth_status_light(),
        "token_cached": bool(TOKEN_CACHE.get("token")),
        "fdr_available": fdr is not None,
        "pandas_available": pd is not None,
        "numpy_available": np is not None,
        "holdings_count": len(read_holdings()),
        "last_good_count": len(read_last_good_holdings()[0]),
        "last_kiwoom_debug": state.get("last_kiwoom_debug"),
    })


@app.route("/api/candidates")
def api_candidates():
    force = request.args.get("force", "0") == "1"
    min_score = safe_float(request.args.get("minScore", 60), 60)
    max_change = safe_float(request.args.get("maxChange", 12), 12)
    min_amount = safe_float(request.args.get("minAmount", 3_000_000_000), 3_000_000_000)
    data = build_candidates(force=force, min_score=min_score)
    items = []
    for p in data.get("items", []):
        if safe_float(p.get("dayChange"), 0) <= max_change and safe_float(p.get("amount"), 0) >= min_amount:
            items.append(p)
    html = "".join(render_candidate_card(p, i) for i, p in enumerate(items))
    if not html:
        html = "<div class='notice'>조건에 맞는 후보가 없습니다. 조건을 낮춰보세요.</div>"
    return jsonify({"ok": True, "items": items, "html": html, "updated_at": data.get("updated_at"), "source": data.get("source")})


@app.route("/api/holdings/sync")
def api_holdings_sync():
    force = request.args.get("force", "0") == "1"
    res = sync_holdings_from_kiwoom(force=force)
    items = [normalize_holding(x) for x in res.get("items", [])]
    html = "".join(render_holding_card(h, i) for i, h in enumerate(items))
    if not html:
        html = f"<div class='notice'>{res.get('message','표시 가능한 보유가 없습니다.')}</div>" + manual_holding_form()
    return jsonify({"ok": res.get("ok"), "items": items, "html": html, "message": res.get("message"), "source": res.get("source")})


@app.route("/api/holdings")
def api_holdings():
    items = read_holdings()
    if not items:
        items, _ = read_last_good_holdings()
    items = [normalize_holding(x) for x in items]
    return jsonify({"ok": True, "items": items, "count": len(items)})


@app.route("/api/holdings/manual", methods=["POST"])
def api_holdings_manual():
    data = request.get_json(silent=True) or {}
    h = normalize_holding(data)
    if not h.get("name") or h.get("code") == "000000" or h.get("qty") <= 0:
        return jsonify({"ok": False, "message": "종목명/코드/수량을 확인하세요."})
    items = read_holdings()
    items = [x for x in items if str(x.get("code", "")).zfill(6) != h["code"]]
    items.append(h)
    write_holdings(items, backup_if_nonempty=True)
    html = "".join(render_holding_card(x, i) for i, x in enumerate(items))
    return jsonify({"ok": True, "message": "화면 확인용 보유카드를 표시했습니다. 실제 키움 잔고 변경은 아닙니다.", "html": html})


@app.route("/api/holdings/sell")
def api_holding_sell():
    code = str(request.args.get("code", "")).zfill(6)
    item = None
    for h in read_holdings():
        if str(h.get("code", "")).zfill(6) == code:
            item = h
            break
    if not item:
        return jsonify({"ok": False, "message": "보유카드에서 종목을 찾지 못했습니다."})
    if not kiwoom_ready():
        return jsonify({"ok": False, "message": "키움 인증정보가 없어 매도 전송이 잠겨 있습니다."})
    res = auto_sell_holding("수동 시장가 매도", item)
    return jsonify(res)


@app.route("/api/auto")
def api_auto():
    enabled = request.args.get("enabled", "0") in ["1", "true", "yes", "on"]
    state = read_trade_state()
    state["auto_trade_enabled"] = enabled
    if enabled:
        state["panic_stop"] = False
    write_trade_state(state)
    ensure_watch_running()
    msg = f"실전 자동매매 {'ON' if enabled else 'OFF'} · 화면 즉시 반영 완료. 잔고/가격 확인은 백그라운드에서 진행됩니다."
    update_status(f"실전 자동매매 {'ON' if enabled else 'OFF'}", msg)
    return jsonify({"ok": True, "enabled": enabled, "message": msg})


@app.route("/api/panic")
def api_panic():
    state = read_trade_state()
    state["auto_trade_enabled"] = False
    state["panic_stop"] = True
    write_trade_state(state)
    msg = "긴급정지 완료. 자동매매 OFF, 신규 주문 금지."
    update_status("긴급정지", msg)
    enqueue_telegram("🛑 <b>긴급정지</b>\n자동매매 OFF / 신규 주문 금지")
    return jsonify({"ok": True, "message": msg})


@app.route("/api/buy_best")
def api_buy_best():
    state = read_trade_state()
    if not state.get("auto_trade_enabled"):
        return jsonify({"ok": False, "message": "자동매매 OFF 상태입니다."})
    if not market_is_open():
        return jsonify({"ok": False, "message": "정규장 시간이 아닙니다."})
    candidates = build_candidates(force=False).get("items", [])
    if not candidates:
        return jsonify({"ok": False, "message": "AI 후보가 없습니다."})
    p = candidates[0]
    code = p["code"]
    live, src = get_trade_live_price(code, fallback=True)
    if live <= 0:
        return jsonify({"ok": False, "message": "주문 직전 현재가 확인 실패"})
    cash = get_kiwoom_cash()
    if not cash.get("ok"):
        return jsonify({"ok": False, "message": "키움 주문가능금액 확인 실패: " + cash.get("message", "")})
    order_cash = safe_float(cash.get("cash"), 0) * ORDER_CASH_SAFETY_RATE
    qty = int(order_cash // live)
    if qty <= 0:
        return jsonify({"ok": False, "message": "주문 가능 수량이 0입니다."})
    gap = abs(safe_float(p.get("price"), 0) - live) / live
    if gap > PRICE_DIFF_LIMIT:
        return jsonify({"ok": False, "message": f"AI 후보가격과 키움 현재가 차이 {gap*100:.2f}%로 매수 보류"})
    with ORDER_LOCK:
        res = kiwoom_order("buy", code, qty, 0, "market")
    if res.get("ok"):
        h = normalize_holding({"code": code, "name": p["name"], "qty": qty, "buyPrice": live, "lastPrice": live, "source": "AUTO_BUY"})
        items = read_holdings()
        items = [x for x in items if str(x.get("code", "")).zfill(6) != code]
        items.append(h)
        write_holdings(items, backup_if_nonempty=True)
        enqueue_telegram(f"✅ <b>AI 자동매수 요청</b>\n{p['name']}({code})\n수량 {qty}주\n현재가 {money(live)}")
    return jsonify(res)


@app.route("/api/telegram/check")
def api_telegram_check():
    ok = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    msg = "텔레그램 환경변수 설정 완료" if ok else "TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 없습니다."
    return jsonify({"ok": ok, "message": msg})


@app.route("/api/telegram/test")
def api_telegram_test():
    ok, msg = send_telegram_direct(f"✅ {APP_NAME} {APP_VERSION} 텔레그램 테스트 알림\n시간: {fmt_time()}")
    write_alert_log("텔레그램 테스트 성공" if ok else msg, ok)
    return jsonify({"ok": ok, "message": "텔레그램 테스트 성공" if ok else "텔레그램 실패: " + msg})


@app.route("/api/watch/start")
def api_watch_start():
    ensure_watch_running()
    return jsonify({"ok": True, "message": "실전 감시 백그라운드가 실행 중입니다."})


@app.route("/api/render_ip")
def api_render_ip():
    info = {"ok": False, "ip": "", "message": "확인 실패"}
    for url in ["https://api.ipify.org", "https://ifconfig.me/ip"]:
        try:
            r = requests.get(url, timeout=4)
            if r.status_code == 200 and r.text.strip():
                info = {"ok": True, "ip": r.text.strip(), "source": url, "message": "이 IP를 키움 REST API 허용 IP에 등록하세요."}
                break
        except Exception:
            pass
    return jsonify(info)


def start_background():
    try:
        threading.Thread(target=telegram_worker, daemon=True).start()
    except Exception:
        pass
    try:
        ensure_watch_running()
    except Exception:
        pass


start_background()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
