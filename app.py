# -*- coding: utf-8 -*-
"""
성일의 AI 주식바람 - KIWOOM REAL AUTO SCALPING v169 CLEAN ASSET CENTER
파일명: app_kiwoom_real_auto_scalping_v169_clean_asset_center.py

목표:
- 앱/코드/로그/화면 버전을 APP_VERSION 하나로 통합 관리
- 패치노트/업데이트 이력을 앱 화면과 API에서 확인
- AI후보 감시, AI일일리포트, AI내투자평가, 매매조건, 전략성과 학습 유지
- 실전 매매 조건은 사용자 승인 후 적용하는 안전장치 유지

v161 보강:
- 실보유 파싱 복구 강화
- 키움 진단센터 화면 추가
- 현재가 출처/시간/가격나이 표시 강화
- TOP3 후보 비교 추가

v159 보강:
- 코드 상단 주석/파일명/상단 UI/상태 메시지 버전 불일치 해결
- /api/version 추가
- 상단에 현재버전·업데이트 이력 요약 표시
- 다음 업데이트부터 APP_VERSION 한 줄만 바꾸면 화면/로그/리포트가 통일되도록 개선
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


APP_VERSION = "v169"
APP_TITLE = f"성일의 AI 주식바람 - KIWOOM REAL AUTO {APP_VERSION}"
APP_FILE_NAME = "app_kiwoom_real_auto_scalping_v169_clean_asset_center.py"
APP_PATCH_NAME = "CLEAN_ASSET_CENTER"
UPDATE_HISTORY = [
    {"version": "v169", "title": "AI 자산운용센터 정리/경량화", "items": ["AI투자비서·헤지펀드·포트폴리오·자율운용을 AI 자산운용센터로 통합", "메뉴 약 30% 정리", "TOP3 비교 UI 축소 및 TOP5 집중감시 중심", "실보유 AI 분석센터 추가", "AI 펀드매니저/자산배분 제안", "매매복기 2.0 요약", "v168 API 호환 유지"]},
    {"version": "v168", "title": "AI 자산운용사 Ultimate", "items": ["AI후보100/집중감시10", "세력유입탐지", "시장온도계 PRO+", "급등10분전 탐지", "후보진화엔진2.0", "AI헤지펀드센터/투자비서/포트폴리오", "AI고점매도예측/수익극대화/자율운용매니저"]},
    {"version": "v167", "title": "AI 수익률 최적화 엔진", "items": ["AI 실전 복기센터", "AI 후보 진화엔진", "AI 시장온도계 PRO", "AI 동적 익절률", "AI 강도변화 알림", "수익률 최적화 진단 API"]},
    {"version": "v166", "title": "모바일 UI 통합/키움 안정화", "items": ["가로 스크롤 메뉴 제거", "3열 카드형 메뉴와 기능 설명 추가", "AI분석센터 개념 통합", "키움 진단센터 PRO 안내 강화", "AI시장온도계와 TOP3 비교 개선", "실보유/진단/후보 핵심 기능 접근성 개선"]},
    {"version": "v164", "title": "등록 IP 변수 누락 수정", "items": ["KIWOOM_REGISTERED_IPS 미정의 오류 수정", "Render/키움 등록 IP 비교 안전처리", "진단센터 오류가 나도 앱 화면 유지"]},
    {"version": "v163", "title": "키움 오류코드 자동해석/자가진단", "items": ["8050 등 키움 오류코드 자동 해석", "Render 현재 IP 표시", "키움 연동 건강도 점수", "원클릭 전체 진단 결과를 사용자 문장으로 변환", "진단 로그 자동 저장"]},
    {"version": "v162", "title": "키움 진단센터 PRO", "items": ["APP KEY/SECRET/ACCOUNT/TOKEN 상태 분리 표시", "지정단말기/추가인증/계좌조회/주문가능/실보유 조회 진단", "토큰 재발급/실보유 강제조회/전체 진단 실행 버튼", "최종 진단 결과와 조치 가이드 표시"]},
    {"version": "v161", "title": "실보유 파싱/진단센터/TOP3 후보비교", "items": ["키움 보유응답 다중 구조 파싱 강화", "키움 진단센터 화면 추가", "현재가 출처/시간/가격나이 표시 강화", "TOP3 후보 비교 카드 추가"]},
    {"version": "v160", "title": "키움 진단/보유 파싱 복구", "items": ["/api/auth_status 추가", "/api/status 500 오류 방지", "키움 보유종목 RAW 저장", "보유종목 응답구조 자동 파싱 강화", "상태 진단 API 추가"]},
    {"version": "v159", "title": "버전 통합관리", "items": ["코드/화면/로그 버전 표기 통일", "패치노트 화면 표시", "버전 확인 API 추가"]},
    {"version": "v158", "title": "AI리포트 런타임 안정화", "items": ["AI일일리포트 저장 오류 방어", "AI내투자평가 저장 오류 방어"]},
    {"version": "v157", "title": "AI일일리포트/내투자평가", "items": ["전날 시장 종합평가", "내 투자 평가", "투자방향 의견"]},
    {"version": "v156", "title": "AI추천 이유 설명", "items": ["추천 이유", "위험요소", "AI확신도", "진입타입"]},
]
APP_NAME = "성일의 AI 주식바람"
KST = timezone(timedelta(hours=9))
app = Flask(__name__)

BASE_DIR = Path(os.getenv("APP_DATA_DIR", "/var/data" if os.path.isdir("/var/data") else "/tmp"))
BASE_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = BASE_DIR / "sungil_trade_state_v159.json"
HOLDINGS_FILE = BASE_DIR / "sungil_holdings_v159.json"
HOLDINGS_BACKUP_FILE = BASE_DIR / "sungil_holdings_last_good_v159.json"
KIWOOM_RAW_HOLDINGS_FILE = BASE_DIR / "sungil_kiwoom_raw_holdings_debug.json"
KIWOOM_DIAG_LOG_FILE = BASE_DIR / "sungil_kiwoom_diagnosis_log_v163.json"
CANDIDATE_FILE = BASE_DIR / "sungil_candidates_v159.json"
PERFORMANCE_FILE = BASE_DIR / "sungil_strategy_performance_v159.json"
TRADE_LEDGER_FILE = BASE_DIR / "sungil_trade_ledger_v159.json"
DAILY_REPORT_FILE = BASE_DIR / "sungil_ai_daily_report_v159.json"
INVESTMENT_REVIEW_FILE = BASE_DIR / "sungil_ai_investment_review_v159.json"
V168_ULTIMATE_FILE = BASE_DIR / "sungil_v168_ultimate_report.json"
BACKUP_DIR = BASE_DIR / "sungil_backups_v159"
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
KIWOOM_ACCOUNT = (os.getenv("KIWOOM_ACCOUNT", "") or os.getenv("KIWOOM_ACCOUNT_NO", "") or os.getenv("ACCOUNT_NO", "")).strip()

# v164: 키움 REST 사이트에 등록한 허용 IP 목록(선택 환경변수)
# Render Environment에 KIWOOM_REGISTERED_IPS=74.220.49.11,74.220.49.246 형태로 넣으면
# 진단센터에서 현재 Render IP와 등록 IP 일치 여부를 비교합니다. 없으면 비교만 건너뜁니다.
def _parse_registered_ips_env():
    raw = (os.getenv("KIWOOM_REGISTERED_IPS", "") or os.getenv("KIWOOM_ALLOWED_IPS", "") or "").strip()
    if not raw:
        return []
    parts = re.split(r"[,;\s]+", raw)
    return [p.strip() for p in parts if p.strip()]

KIWOOM_REGISTERED_IPS = _parse_registered_ips_env()

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
    # v166: AI 고점매도/상승추세 보유 기능
    # 목표가 도달 후 바로 팔지 않고, 상승 강도에 따라 목표가를 계속 올린 뒤
    # 고점 대비 되돌림이 나오면 트레일링으로 수익을 보호합니다.
    "ai_peak_sell_enabled": True,
    "ai_peak_tight_trailing_enabled": True,
    "ai_peak_stage1_profit_rate": 0.045,
    "ai_peak_stage2_profit_rate": 0.070,
    "ai_peak_stage3_profit_rate": 0.100,
    "ai_peak_trailing_stage1": 0.009,
    "ai_peak_trailing_stage2": 0.007,
    "ai_peak_trailing_stage3": 0.0055,
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
    # v167: 수익률 최적화 엔진
    "profit_optimization_enabled": True,
    "market_temperature_pro_enabled": True,
    "candidate_evolution_enabled": True,
    "trade_review_enabled": True,
    "strength_alert_enabled": True,
    "strength_drop_alert_threshold": 12,
    "dynamic_take_profit_enabled": True,
    "dynamic_take_profit_normal": 0.027,
    "dynamic_take_profit_strong": 0.045,
    "dynamic_take_profit_super": 0.070,
    "dynamic_take_profit_limitup": 0.100,
    "market_temp_stop_buy_below": 25,
    "market_temp_reduce_buy_below": 45,
    "last_market_temperature": 0,
    "last_market_temperature_label": "대기",
    "last_review_summary": "",
    # v168: AI 자산운용사 Ultimate
    "v168_ultimate_enabled": True,
    "v168_watch_candidate_count": 100,
    "v168_focus_candidate_count": 10,
    "v168_pump_predict_enabled": True,
    "v168_money_flow_enabled": True,
    "v168_hedge_fund_center_enabled": True,
    "v168_ai_assistant_enabled": True,
    "v168_portfolio_manager_enabled": True,
    "v168_peak_sell_predict_enabled": True,
    "v168_profit_maximizer_enabled": True,
    "v168_autonomous_manager_enabled": False,
    "v168_auto_rotation_enabled": False,
    "v168_require_user_approval": True,
    "v168_last_ultimate_report": {},
    # v169: 메뉴 정리 / AI 자산운용센터 통합
    "v169_clean_asset_center_enabled": True,
    "v169_focus_candidate_count": 5,
    "v169_hide_duplicate_menus": True,
    "v169_unified_diagnosis_enabled": True,
    "v169_holdings_ai_analysis_enabled": True,
    "v169_fund_manager_enabled": True,
    "v169_review_2_enabled": True,
    "v169_last_asset_center_report": {},
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
        for p,label in [(STATE_FILE,'state'),(HOLDINGS_FILE,'holdings'),(HOLDINGS_BACKUP_FILE,'holdings_last_good'),(PERFORMANCE_FILE,'performance'),(TRADE_LEDGER_FILE,'trade_ledger'),(DAILY_REPORT_FILE,'daily_report'),(INVESTMENT_REVIEW_FILE,'investment_review')]:
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


def kiwoom_error_analysis(msg):
    """v163: 키움 오류 메시지를 사용자가 바로 이해할 수 있게 자동 해석합니다."""
    s = str(msg or "")
    low = s.lower()
    if "8050" in s or "지정단말" in s or "인증에 실패" in s:
        return {
            "code": "8050",
            "name": "지정단말기/IP 인증 실패",
            "category": "designated_device",
            "severity": "critical",
            "summary": "키움 토큰 발급이 지정단말기 또는 허용 IP 문제로 실패했습니다.",
            "action": "키움 REST API 사이트에서 Render 현재 IP 등록 여부를 확인하고, 영웅문S# 지정단말기/추가인증 상태를 확인한 뒤 토큰을 재발급하세요.",
            "steps": ["키움 REST API 사이트 접속", "IP 등록현황에서 Render 현재 IP 확인", "필요 시 기존 IP 삭제 후 새 IP 추가", "영웅문S# 지정단말기/추가인증 확인", "앱에서 토큰 재발급/전체진단 실행"],
        }
    if "8001" in s or "app key" in s or "appkey" in low or "키" in s and "오류" in s:
        return {"code": "8001", "name": "APP KEY 확인 필요", "category": "key_secret", "severity": "critical", "summary": "APP KEY가 누락되었거나 키움에 등록된 값과 다를 수 있습니다.", "action": "키움 REST API 사이트에서 App Key를 재다운로드 또는 재발급 후 Render KIWOOM_APP_KEY에 정확히 입력하세요.", "steps": ["App Key 재확인", "Render 환경변수 KIWOOM_APP_KEY 수정", "Render 재배포", "토큰 재발급"]}
    if "8002" in s or "secret" in low:
        return {"code": "8002", "name": "APP SECRET 확인 필요", "category": "key_secret", "severity": "critical", "summary": "APP SECRET이 누락되었거나 키움에 등록된 값과 다를 수 있습니다.", "action": "키움 REST API 사이트에서 App Secret을 재다운로드 또는 재발급 후 Render KIWOOM_APP_SECRET에 정확히 입력하세요.", "steps": ["App Secret 재확인", "Render 환경변수 KIWOOM_APP_SECRET 수정", "Render 재배포", "토큰 재발급"]}
    if "추가인증" in s or "보안" in s or "단말" in s:
        return {"code": "AUTH", "name": "추가인증/보안 확인 필요", "category": "additional_auth", "severity": "warning", "summary": "키움 계정의 추가인증 또는 보안 설정 확인이 필요합니다.", "action": "영웅문S#에서 지정단말기/추가인증 상태를 확인하세요.", "steps": ["영웅문S# 접속", "인증/보안 메뉴 확인", "지정단말기 또는 추가인증 완료", "토큰 재발급"]}
    if "계좌" in s and ("없" in s or "누락" in s or "account" in low):
        return {"code": "ACCOUNT", "name": "계좌번호 누락", "category": "account_missing", "severity": "critical", "summary": "Render 환경변수에 KIWOOM_ACCOUNT가 없거나 앱에서 인식하지 못합니다.", "action": "Render Environment에 KIWOOM_ACCOUNT 값을 추가하세요. 예: 66476264", "steps": ["Render Environment 이동", "KIWOOM_ACCOUNT 추가", "계좌번호 입력", "재배포", "전체 진단 실행"]}
    if "timeout" in low or "timed out" in low or "시간" in s and "초과" in s:
        return {"code": "TIMEOUT", "name": "키움/네트워크 응답 지연", "category": "timeout", "severity": "warning", "summary": "키움 서버 또는 Render 네트워크 응답이 지연되었습니다.", "action": "잠시 후 재시도하고 반복되면 Render 재배포 또는 키움 서버 상태를 확인하세요.", "steps": ["5초 후 재시도", "전체 진단 실행", "반복 시 Render 재배포"]}
    return {"code": "UNKNOWN", "name": "미분류 오류", "category": "unknown", "severity": "info", "summary": "키움 메시지를 자동 분류하지 못했습니다.", "action": "RAW 응답과 키움 상태 JSON을 확인하세요.", "steps": ["키움 상태 JSON 확인", "RAW 보유응답 확인", "Render 로그 확인"]}


def auth_message(msg):
    s = str(msg or "")
    if not KIWOOM_APP_KEY or not KIWOOM_SECRET_KEY:
        return "키움 환경변수 KIWOOM_APP_KEY / KIWOOM_APP_SECRET가 필요합니다."
    if s:
        a = kiwoom_error_analysis(s)
        if a.get("code") != "UNKNOWN":
            return f"키움 인증 실패({a.get('code')}/{a.get('name')})입니다. {a.get('action')}"
    return s or "키움 API 미확인"


def append_kiwoom_diag_log(item):
    try:
        logs = read_json(KIWOOM_DIAG_LOG_FILE, [])
        if not isinstance(logs, list):
            logs = []
        logs.insert(0, item)
        write_json(KIWOOM_DIAG_LOG_FILE, logs[:50])
    except Exception:
        pass


def get_render_public_ip():
    cached = read_state().get("render_public_ip", {})
    if isinstance(cached, dict) and cached.get("ip") and time.time() - safe_float(cached.get("ts"), 0) < 1800:
        return cached
    for url in ["https://api.ipify.org?format=json", "https://ifconfig.me/all.json"]:
        try:
            r = requests.get(url, timeout=3)
            txt = r.text.strip()
            ip = ""
            try:
                data = r.json()
                ip = data.get("ip") or data.get("ip_addr") or data.get("remote_addr") or ""
            except Exception:
                ip = txt if re.match(r"^\d+\.\d+\.\d+\.\d+$", txt) else ""
            if ip:
                state = read_state()
                state["render_public_ip"] = {"ip": ip, "source": url, "checked_at": now_text(), "ts": time.time()}
                write_state(state)
                return state["render_public_ip"]
        except Exception:
            pass
    return cached if isinstance(cached, dict) else {"ip": "", "source": "", "checked_at": "", "ts": 0}

def update_kiwoom_debug(stage, message="", http_status=0):
    analysis = kiwoom_error_analysis(message)
    state = read_state()
    state["last_kiwoom_debug"] = {
        "time": now_text(),
        "stage": stage,
        "http_status": http_status,
        "message": auth_message(message),
        "raw_message": str(message or "")[:1000],
        "analysis": analysis,
    }
    write_state(state)
    append_kiwoom_diag_log({"time": now_text(), "stage": stage, "http_status": http_status, "message": str(message or "")[:1000], "analysis": analysis})


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



def _walk_dicts(obj, depth=0, max_depth=8):
    """키움 REST 응답 구조가 바뀌어도 dict/list를 재귀적으로 훑습니다."""
    if depth > max_depth:
        return
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_dicts(v, depth + 1, max_depth)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_dicts(item, depth + 1, max_depth)


def _first_value(d, keys):
    if not isinstance(d, dict):
        return ""
    for k in keys:
        if k in d and d.get(k) not in (None, ""):
            return d.get(k)
    # 키 일부 포함 매칭도 허용
    for dk, v in d.items():
        sk = str(dk)
        if any(k in sk for k in keys) and v not in (None, ""):
            return v
    return ""


def _code_from_row(row):
    raw = json.dumps(row, ensure_ascii=False)
    val = _first_value(row, ["stk_cd", "stk_code", "code", "종목코드", "pdno", "isu_cd", "prdt_cd", "종목번호"])
    code = re.sub(r"[^0-9]", "", str(val or ""))
    if len(code) >= 6:
        return code[-6:]
    m = re.search(r"(?<!\d)(\d{6})(?!\d)", raw)
    return m.group(1) if m else ""


def _name_from_row(row, code=""):
    val = _first_value(row, ["stk_nm", "stk_name", "name", "종목명", "prdt_name", "item_nm", "isu_nm", "hts_kor_isnm"])
    name = str(val or "").strip()
    if name and name != code:
        return name
    return code or "종목명미확인"


def _numeric_from_row(row, keys):
    val = _first_value(row, keys)
    if val not in (None, ""):
        return abs(safe_float(str(val).replace("+", "").replace("-", ""), 0))
    return deep_find_number(row, keys)



def _is_probable_holding_row(row):
    """키움 응답 안에서 실제 보유종목 행인지 점수화해 판단합니다."""
    if not isinstance(row, dict):
        return False
    code = _code_from_row(row)
    if not code:
        return False
    qty = _numeric_from_row(row, [
        "rmnd_qty", "hldg_qty", "hold_qty", "jan_qty", "bal_qty", "qty", "quantity",
        "ord_psbl_qty", "trde_psbl_qty", "sell_qty", "poss_qty",
        "보유수량", "잔고수량", "평가수량", "가능수량", "매도가능수량", "주문가능수량"
    ])
    buy = _numeric_from_row(row, [
        "pchs_avg_pric", "pchs_avg_price", "pchs_avg_prc", "avg_prc", "avg_price", "buyPrice",
        "매입평균가격", "평균단가", "매입가", "매수가", "매입단가"
    ])
    cur = _numeric_from_row(row, [
        "cur_prc", "now_pric", "prpr", "stck_prpr", "lastPrice", "currentPrice", "price",
        "현재가", "평가가격", "기준가"
    ])
    pchs_amt = _numeric_from_row(row, ["pchs_amt", "pchs_amt_smtl", "buy_amt", "purchaseAmount", "매입금액", "매수금액"])
    evlt_amt = _numeric_from_row(row, ["evlt_amt", "evlt_amt_smtl", "evalAmount", "평가금액", "평가액"])
    # 종목코드가 있고, 수량 또는 매입/평가 관련 숫자가 있으면 보유 행으로 본다.
    return qty > 0 or buy > 0 or cur > 0 or pchs_amt > 0 or evlt_amt > 0


def _extract_possible_holding_rows(data):
    """output1/output2/data/list/응답 전체에서 보유 후보 행을 폭넓게 수집합니다."""
    rows = []
    if isinstance(data, dict):
        preferred_keys = [
            "output1", "output2", "output", "data", "list", "items", "acnt_evlt_remn_indv_tot",
            "stk_acnt_evlt_remn_indv_tot", "stk_acnt_evlt_remn", "account_eval", "holdings", "잔고", "보유"
        ]
        for key in preferred_keys:
            v = data.get(key)
            if isinstance(v, list):
                rows.extend([x for x in v if isinstance(x, dict)])
            elif isinstance(v, dict):
                rows.extend([v])
    for row in _walk_dicts(data, max_depth=10):
        if isinstance(row, dict):
            rows.append(row)
    # 중복 제거
    unique = []
    seen = set()
    for r in rows:
        raw = json.dumps(r, ensure_ascii=False, sort_keys=True)[:5000]
        if raw not in seen:
            seen.add(raw)
            unique.append(r)
    return unique


def parse_holdings(data):
    """키움 보유종목 응답 파서 v161.
    키움 REST 응답 구조가 output1/output2/data/list 등으로 달라져도 코드·수량·매입가를 자동 탐색합니다.
    """
    if not isinstance(data, (dict, list)):
        return []
    out = []
    for row in _extract_possible_holding_rows(data):
        if not _is_probable_holding_row(row):
            continue
        code = _code_from_row(row)
        if not code:
            continue
        qty = _numeric_from_row(row, [
            "rmnd_qty", "hldg_qty", "hold_qty", "jan_qty", "bal_qty", "qty", "quantity",
            "ord_psbl_qty", "trde_psbl_qty", "sell_qty", "poss_qty",
            "보유수량", "잔고수량", "평가수량", "가능수량", "매도가능수량", "주문가능수량"
        ])
        buy = _numeric_from_row(row, [
            "pchs_avg_pric", "pchs_avg_price", "pchs_avg_prc", "avg_prc", "avg_price", "buyPrice",
            "매입평균가격", "평균단가", "매입가", "매수가", "매입단가"
        ])
        cur = _numeric_from_row(row, [
            "cur_prc", "now_pric", "prpr", "stck_prpr", "lastPrice", "currentPrice", "price",
            "현재가", "평가가격", "기준가"
        ])
        pchs_amt = _numeric_from_row(row, ["pchs_amt", "pchs_amt_smtl", "buy_amt", "purchaseAmount", "매입금액", "매수금액"])
        evlt_amt = _numeric_from_row(row, ["evlt_amt", "evlt_amt_smtl", "evalAmount", "평가금액", "평가액"])
        pnl = _numeric_from_row(row, ["evltv_prft", "evlt_pfls_amt", "profit", "pnl", "평가손익", "손익"])
        name = _name_from_row(row, code)
        if qty <= 0 and buy > 0 and pchs_amt > 0:
            qty = max(1, int(pchs_amt // buy))
        if qty <= 0 and cur > 0 and evlt_amt > 0:
            qty = max(1, int(evlt_amt // cur))
        if qty <= 0:
            continue
        src = "KIWOOM"
        if cur <= 0:
            cur, src = get_trade_price(code, fallback=True)
        if buy <= 0:
            if pchs_amt > 0 and qty > 0:
                buy = pchs_amt / qty
            else:
                buy = cur
        if cur <= 0:
            cur = buy
            src = "CACHE"
        h = normalize_holding({
            "code": code,
            "name": name,
            "qty": int(qty),
            "buyPrice": int(buy or cur),
            "lastPrice": int(cur or buy),
            "priceSource": src,
            "lastCheckedAt": now_text(),
            "target": int((buy or cur) * (1 + safe_float(read_state().get('target_rate', 0.027), 0.027))),
            "stop": int((buy or cur) * (1 + safe_float(read_state().get('stop_rate', -0.018), -0.018))),
            "pnl": int(pnl) if pnl else None,
            "rawParseHint": "v161_auto_parser",
        })
        out.append(h)
    unique = {}
    for h in out:
        unique[str(h.get("code")).zfill(6)] = h
    return list(unique.values())


def kiwoom_raw_structure_summary(raw):
    """키움 RAW 응답 구조를 사용자가 이해하기 쉽게 요약합니다."""
    summary = {"top_keys": [], "list_paths": [], "probable_rows": 0, "codes_found": []}
    try:
        data = raw.get('raw') if isinstance(raw, dict) and 'raw' in raw else raw
        if isinstance(data, dict):
            summary['top_keys'] = list(data.keys())[:30]
        rows = _extract_possible_holding_rows(data)
        codes = []
        probable = 0
        for r in rows:
            c = _code_from_row(r)
            if c:
                codes.append(c)
            if _is_probable_holding_row(r):
                probable += 1
        summary['probable_rows'] = probable
        summary['codes_found'] = sorted(list(set(codes)))[:20]
        def walk_paths(obj, path='', depth=0):
            if depth > 5:
                return
            if isinstance(obj, dict):
                for k,v in obj.items():
                    p = f"{path}.{k}" if path else str(k)
                    if isinstance(v, list):
                        summary['list_paths'].append({"path": p, "len": len(v)})
                    walk_paths(v, p, depth+1)
            elif isinstance(obj, list):
                for i,x in enumerate(obj[:3]):
                    walk_paths(x, f"{path}[{i}]", depth+1)
        walk_paths(data)
    except Exception as e:
        summary['error'] = str(e)
    return summary


def holdings_fail_reason(raw_text, last_status=0):
    s = str(raw_text or "")
    if "8050" in s or "지정단말기" in s or "인증에 실패" in s:
        return auth_message(s)
    if "prfa_ch" in s or "fc_stk_krw" in s or "예수금" in s or "주문가능" in s:
        return "키움 서버 응답은 왔지만 보유종목 배열을 찾지 못했습니다. 계좌번호(KIWOOM_ACCOUNT) 누락, 조회구분, 또는 키움 보유응답 필드 변경 가능성이 있습니다. v160 RAW 진단파일에 원본을 저장했습니다."
    if last_status and int(last_status) != 200:
        return f"키움 보유 조회 HTTP {last_status} 응답입니다. 인증/권한/지정단말기 상태를 확인하세요."
    return "키움 응답은 받았지만 보유종목으로 해석할 수 있는 코드·수량 필드를 찾지 못했습니다."


def fetch_kiwoom_holdings():
    if not kiwoom_ready():
        return {"ok": False, "holdings": get_cached_holdings(), "message": auth_message(""), "source": "CACHE" if get_cached_holdings() else "NONE"}
    last = ""
    last_status = 0
    attempts = []
    # 키움 REST 계좌 API가 계정/조회구분에 따라 응답 형태가 달라지는 경우가 있어 여러 body를 순차 시도합니다.
    bodies = [
        {"qry_tp": "3"},
        {"qry_tp": "2"},
        {"qry_tp": "1"},
        {"dmst_stex_tp": "KRX", "qry_tp": "3"},
    ]
    if KIWOOM_ACCOUNT:
        bodies.insert(0, {"acc_no": KIWOOM_ACCOUNT, "qry_tp": "3"})
        bodies.insert(1, {"account_no": KIWOOM_ACCOUNT, "qry_tp": "3"})
    for api_id in ["kt00018", "kt00004", "kt00001"]:
        for body in bodies:
            try:
                st, data = kiwoom_post("/api/dostk/acnt", api_id, body, timeout=8)
                last_status = st
                last = str(data)[:1200]
                attempts.append({"time": now_text(), "api_id": api_id, "body": body, "http_status": st, "preview": last[:500]})
                try:
                    write_json(KIWOOM_RAW_HOLDINGS_FILE, {"time": now_text(), "api_id": api_id, "body": body, "http_status": st, "raw": data, "attempts": attempts})
                except Exception:
                    pass
                items = parse_holdings(data)
                if st == 200 and items:
                    write_json(HOLDINGS_FILE, items)
                    write_json(HOLDINGS_BACKUP_FILE, {"time": now_text(), "items": items, "raw_source": api_id})
                    update_kiwoom_debug("holdings_ok", f"키움 실보유 {len(items)}종목 조회 성공", st)
                    return {"ok": True, "holdings": items, "message": f"키움 실보유 {len(items)}종목 조회 성공", "source": "KIWOOM", "api_id": api_id}
                update_kiwoom_debug("holdings_parse_empty", holdings_fail_reason(last, st), st)
            except Exception as e:
                last = str(e)
                attempts.append({"time": now_text(), "api_id": api_id, "body": body, "http_status": 0, "preview": last[:500]})
                update_kiwoom_debug("holdings_exception", last)
    cached = get_cached_holdings()
    msg = holdings_fail_reason(last, last_status)
    return {"ok": False, "holdings": cached, "message": msg, "source": "CACHE" if cached else "EMPTY", "attempts": attempts[-5:]}

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
    # 급등/강세 수익 구간에서는 기존 목표가에서 즉시 매도하지 않고
    # AI가 상향목표를 계속 끌어올린 뒤, 고점 대비 되돌림이 발생하면 트레일링으로 익절합니다.
    ai_peak_on = bool(state_for_dynamic.get("ai_peak_sell_enabled", True))
    tight_on = bool(state_for_dynamic.get("ai_peak_tight_trailing_enabled", True))
    stage1 = safe_float(state_for_dynamic.get("ai_peak_stage1_profit_rate", 0.045), 0.045)
    stage2 = safe_float(state_for_dynamic.get("ai_peak_stage2_profit_rate", 0.070), 0.070)
    stage3 = safe_float(state_for_dynamic.get("ai_peak_stage3_profit_rate", 0.100), 0.100)
    base_trail_rate = safe_float(state_for_dynamic.get("trailing_stop_rate", 0.011), 0.011)
    adaptive_trail_rate = base_trail_rate
    ai_peak_stage = "기본 감시"
    if ai_peak_on and tight_on and profit_rate_decimal >= stage3:
        adaptive_trail_rate = min(adaptive_trail_rate, safe_float(state_for_dynamic.get("ai_peak_trailing_stage3", 0.0055), 0.0055))
        ai_peak_stage = "초강세 고점추적"
    elif ai_peak_on and tight_on and profit_rate_decimal >= stage2:
        adaptive_trail_rate = min(adaptive_trail_rate, safe_float(state_for_dynamic.get("ai_peak_trailing_stage2", 0.007), 0.007))
        ai_peak_stage = "강세 고점추적"
    elif ai_peak_on and tight_on and profit_rate_decimal >= stage1:
        adaptive_trail_rate = min(adaptive_trail_rate, safe_float(state_for_dynamic.get("ai_peak_trailing_stage1", 0.009), 0.009))
        ai_peak_stage = "목표상향 고점추적"
    elif buy and profit_rate_decimal >= min_profit:
        ai_peak_stage = "상향익절 준비"

    if dynamic_on and buy and (cur >= base_target or profit_rate_decimal >= min_profit):
        dynamic_target = max(dynamic_target, cur * (1 + boost_rate), base_target * (1 + boost_rate))
    trail = safe_float(h.get("trailingStopPrice"), 0)
    if dynamic_on and ai_peak_on and high >= base_target:
        trail = max(trail, high * (1 - adaptive_trail_rate))

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
        "aiPeakStage": ai_peak_stage,
        "aiTrailingRate": round(adaptive_trail_rate * 100, 2),
        "aiSellPlan": "AI 고점추적: 상승 중 목표가 상향, 고점 대비 되돌림 발생 시 트레일링 매도" if dynamic_on and ai_peak_on else "기본 목표/손절 감시",
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
        c = v167_apply_candidate_evolution(c)
        c["comment"] = "v167 수익률 최적화 후보입니다. 실제 매수 직전에는 키움 현재가·주문가능금액·수수료 버퍼를 다시 확인합니다. " + c.get('riskComment','')
        enriched.append(c)
    candidates = sorted(enriched, key=lambda x: safe_float(x.get('riskAdjustedScore', x.get('score',0))), reverse=True)[:limit]
    # v159: KRX 종가/캐시와 실제 주식앱 현재가 차이를 줄이기 위해 표시 직전 현재가 보정
    candidates = refresh_candidate_prices(candidates, force=True)
    scan_time = now_text()
    state = read_state()
    state['index_risk_mode']=idx_risk.get('mode','UNKNOWN')
    state['recommended_strategy'] = candidates[0].get('strategy','AI후보형') if candidates else state.get('recommended_strategy','AI후보형')
    temp_data = v167_market_temperature_data(candidates)
    state['last_market_temperature'] = temp_data.get('temperature', 0)
    state['last_market_temperature_label'] = temp_data.get('label', '대기')
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
        v167_review_trade_event(event)
        return {"ok": True, "message": "DRY_RUN: 실제 매도 전송 없이 성과/원장 기록", "dry_run": True, "review": ai_loss_review(event), "v167_review": read_state().get('last_review_summary','')}
    try:
        res = kiwoom_order("sell", code, qty)
        if res.get("ok"):
            remove_holding(code)
            event = append_trade_event({'side':'sell','code':code,'name':h.get('name'),'qty':qty,'fill_price':sell_price,'buy_price':h.get('buyPrice'),'pnl':int(pnl),'return_pct':round((pnl/buy_value*100) if buy_value else 0,2),'strategy':strategy,'reason':reason,'order_response':res})
            record_strategy_result(strategy, pnl, buy_value, reason, code, h.get('name'))
            v167_review_trade_event(event)
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




def v167_market_temperature_data(picks=None):
    """v167: 후보 품질/시장역행/지수위험을 점수화해 시장온도와 매수모드를 산출합니다."""
    try:
        picks = list(picks or cached_candidates()[:8])
    except Exception:
        picks = []
    avg_score = sum(safe_float(x.get('riskAdjustedScore', x.get('score')), 0) for x in picks) / max(1, len(picks))
    avg_reverse = sum(safe_float(x.get('marketReverseScore'), 0) for x in picks) / max(1, len(picks))
    avg_theme = sum(safe_float(x.get('themeStrengthScore'), 0) for x in picks) / max(1, len(picks))
    avg_overheat = sum(safe_float(x.get('overheatPenalty'), 0) for x in picks) / max(1, len(picks))
    state = read_state()
    index_mode = state.get('index_risk_mode', 'NORMAL')
    temp = avg_score * 0.58 + avg_reverse * 0.16 + avg_theme * 0.18 - avg_overheat * 0.8
    if index_mode == 'WEAK':
        temp -= 12
    elif index_mode == 'DANGER':
        temp -= 22
    elif index_mode == 'STRONG':
        temp += 8
    temp = max(0, min(100, temp))
    if temp >= 82:
        label, mode, guide = '초강세', '공격 가능', '강한 후보는 목표가를 더 길게 끌고 가되, 고점 대비 되돌림 매도로 수익을 보호합니다.'
    elif temp >= 65:
        label, mode, guide = '강세', '선별 매수', 'TOP3 후보 중심으로 진입하고 거래대금 유지율을 확인합니다.'
    elif temp >= 45:
        label, mode, guide = '중립', '보수 매수', '후보 점수가 높아도 과열/슬리피지 감점을 더 강하게 봅니다.'
    elif temp >= 25:
        label, mode, guide = '약세', '신규매수 축소', '기존 보유 리스크 관리와 빠른 손실 차단이 우선입니다.'
    else:
        label, mode, guide = '위험', '신규매수 중지', '시장온도가 낮아 자동 신규매수보다 관망/진단/보유관리 우선입니다.'
    return {'temperature': round(temp, 1), 'label': label, 'mode': mode, 'guide': guide, 'avg_score': round(avg_score,1), 'avg_reverse': round(avg_reverse,1), 'avg_theme': round(avg_theme,1), 'avg_overheat': round(avg_overheat,1), 'index_mode': index_mode, 'count': len(picks)}


def v167_dynamic_target_rate_for_candidate(c):
    """v167: 후보 강도에 따라 익절 목표를 동적으로 산출합니다."""
    state = read_state()
    base = safe_float(state.get('target_rate'), 0.027)
    if not state.get('dynamic_take_profit_enabled', True):
        return base, '기본 익절률'
    score = safe_float(c.get('riskAdjustedScore', c.get('score')), 0)
    reverse = safe_float(c.get('marketReverseScore'), 0)
    day = safe_float(c.get('dayChange'), 0)
    amount = safe_float(c.get('amount'), 0)
    temp = safe_float(state.get('last_market_temperature'), 0)
    if score >= 96 and reverse >= 15 and day >= 7 and amount >= 30_000_000_000 and temp >= 70:
        return safe_float(state.get('dynamic_take_profit_limitup'), 0.10), '초강세/상한가 패턴 후보'
    if score >= 92 and reverse >= 10 and day >= 4 and temp >= 60:
        return safe_float(state.get('dynamic_take_profit_super'), 0.07), '초강세 추세 후보'
    if score >= 85 and day >= 2.5:
        return safe_float(state.get('dynamic_take_profit_strong'), 0.045), '강세 후보'
    return safe_float(state.get('dynamic_take_profit_normal'), base), '일반 후보'


def v167_apply_candidate_evolution(c):
    """v167: 최근 성과가 좋은 전략/테마에 보수적 가중치를 더합니다."""
    c = dict(c or {})
    if not read_state().get('candidate_evolution_enabled', True):
        c['evolutionNote'] = '후보 진화엔진 OFF'
        return c
    try:
        ranks = strategy_rankings(7)
        best = ranks[0]['strategy'] if ranks else ''
    except Exception:
        best = ''
    bonus = 0
    notes = []
    if best and best in str(c.get('strategy','')):
        bonus += 3
        notes.append(f'최근 7일 우세전략({best}) 보너스')
    theme = str(c.get('theme',''))
    if any(x in theme for x in ['AI반도체', '전력설비', '데이터센터']):
        bonus += 2
        notes.append('최근 주도테마 관찰 보너스')
    if safe_float(c.get('overheatPenalty'), 0) >= 8:
        bonus -= 4
        notes.append('과열위험 감점')
    base = safe_float(c.get('riskAdjustedScore', c.get('score')), 0)
    c['v167EvolutionBonus'] = bonus
    c['riskAdjustedScore'] = round(max(0, min(120, base + bonus)), 2)
    c['evolutionNote'] = ' · '.join(notes) if notes else '성과 누적 대기: 기본 점수 유지'
    target_rate, reason = v167_dynamic_target_rate_for_candidate(c)
    p = safe_float(c.get('price'), 0)
    if p > 0:
        c['v167DynamicTargetRate'] = round(target_rate * 100, 2)
        c['target'] = int(p * (1 + target_rate))
        c['v167DynamicTargetReason'] = reason
    return c


def v167_review_trade_event(event):
    """v167: 매도 완료 이벤트를 AI 복기 문장으로 저장합니다."""
    try:
        pnl = safe_float(event.get('pnl'), 0)
        ret = safe_float(event.get('return_pct'), 0)
        reason = str(event.get('reason',''))
        name = event.get('name') or event.get('code') or '종목'
        if pnl > 0:
            summary = f'{name} 수익 확정 {ret:.2f}% · {reason} 매도. 강한 후보는 AI 고점추적/동적익절이 유효했는지 확인하세요.'
        else:
            summary = f'{name} 손실/본전 매도 {ret:.2f}% · 원인 후보: 진입지연, 시장온도 하락, 거래대금 유지율 약화, 과열 진입 여부 확인 필요.'
        review = {'time': now_text(), 'event': event, 'summary': summary, 'score': max(0, min(100, 60 + ret * 5))}
        reviews = read_json(REVIEW_FILE, [])
        if not isinstance(reviews, list):
            reviews = []
        reviews.insert(0, review)
        write_json(REVIEW_FILE, reviews[:100])
        state = read_state()
        state['last_review_summary'] = summary
        write_state(state)
        return review
    except Exception as e:
        return {'time': now_text(), 'summary': '복기 저장 실패: ' + str(e)[:120]}


def v167_strength_alert_for_holding(h):
    """v167: 보유종목 강도 하락 알림. 중복 알림을 줄이기 위해 종목별 최근 강도 캐시를 사용합니다."""
    try:
        state = read_state()
        if not state.get('strength_alert_enabled', True):
            return
        code = str(h.get('code','')).zfill(6)
        prev_map = state.get('holding_strength_map', {})
        if not isinstance(prev_map, dict):
            prev_map = {}
        cur_rate = safe_float(h.get('profitRate'), 0)
        # 수익률과 고점 대비 위치를 단순 강도로 사용
        high = safe_float(h.get('highestPrice'), 0)
        cur = safe_float(h.get('lastPrice'), 0)
        high_drop = ((high-cur)/high*100) if high else 0
        strength = max(0, min(100, 70 + cur_rate*4 - high_drop*5))
        prev = safe_float(prev_map.get(code), strength)
        drop = prev - strength
        threshold = safe_float(state.get('strength_drop_alert_threshold'), 12)
        if drop >= threshold:
            msg = f"⚠ AI 강도하락 감지: {h.get('name', code)} {prev:.1f}→{strength:.1f}. 고점 대비 {high_drop:.2f}% 밀림. 트레일링/익절 조건 확인"
            add_alert(msg)
            send_telegram(msg)
        prev_map[code] = round(strength, 1)
        state['holding_strength_map'] = prev_map
        write_state(state)
    except Exception:
        pass

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
                v167_strength_alert_for_holding(h)
                if h["activeDynamicTarget"] and h["lastPrice"] >= h["baseTarget"]:
                    h["aiHoldMode"] = True
                    h["aiTargetReason"] = "목표 도달 후 강세로 판단되어 AI 상향익절/트레일링 감시 중"
                if h["trailingStopPrice"] and h["lastPrice"] <= h["trailingStopPrice"]:
                    auto_sell_holding("ai_peak_trailing_stop", h, h["lastPrice"])
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



# ==============================
# v168 AI 자산운용사 Ultimate
# ==============================

def v168_market_temperature_pro_plus(picks=None):
    """시장온도계 PRO+: 후보 품질/역행강도/테마강도/과열감점/지수위험을 0~100점으로 환산합니다."""
    try:
        picks = list(picks or cached_candidates() or [])[:20]
        base = v167_market_temperature_data(picks)
        avg_money = sum(safe_float(x.get('amount'), 0) for x in picks[:10]) / max(1, min(10, len(picks)))
        money_bonus = min(8, avg_money / 100_000_000_000 * 2)
        top_conf = max([safe_float(x.get('aiConfidence'), 0) for x in picks[:10]] or [0])
        conf_bonus = min(8, top_conf / 100 * 8)
        temp = max(0, min(100, safe_float(base.get('temperature'), 0) + money_bonus + conf_bonus))
        if temp >= 90:
            label, mode = "초공격", "강한 후보는 고점추적 ON, 단 추격매수 금지"
        elif temp >= 80:
            label, mode = "공격", "TOP3/TOP10 중심 선별 진입"
        elif temp >= 60:
            label, mode = "중립강세", "매수 가능하지만 과열감점 확인"
        elif temp >= 40:
            label, mode = "방어", "신규매수 축소, 보유관리 우선"
        else:
            label, mode = "매수금지", "신규매수 중지, 키움/시장 진단 우선"
        return {
            "temperature": round(temp, 1),
            "label": label,
            "mode": mode,
            "base": base,
            "money_bonus": round(money_bonus, 1),
            "confidence_bonus": round(conf_bonus, 1),
            "guide": mode,
        }
    except Exception as e:
        return {"temperature": 0, "label": "진단오류", "mode": str(e)[:120], "guide": "시장온도 산출 오류"}


def v168_candidate_universe(limit=100):
    """AI후보100: 무거운 현재가 조회 없이 KRX/FDR 기반으로 넓은 후보군을 빠르게 구성합니다."""
    state = read_state()
    limit = max(10, min(150, safe_int(limit, 100)))
    rows = []
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
            df = df[(df["Close"] >= 1000) & (df["Amount"] >= 1_000_000_000) & (df["dayChange"] >= -2.0) & (df["dayChange"] <= safe_float(state.get("max_day_change", 12), 12) + 5)].copy()
            if not df.empty:
                df["theme"] = df["Name"].apply(classify_theme)
                df["amountRank"] = df["Amount"].rank(pct=True) * 100
                df["volumeRank"] = df["Volume"].rank(pct=True) * 100
                df["sweet"] = (100 - (df["dayChange"] - 3.2).abs() * 6).clip(lower=20, upper=100)
                df["baseScore"] = (df["amountRank"] * .42 + df["volumeRank"] * .25 + df["sweet"] * .33)
                df = df.sort_values("baseScore", ascending=False).head(limit)
                idx = get_index_risk(df)
                for _, r in df.iterrows():
                    c = {
                        "market": str(r.get("Market","")),
                        "code": str(r["Code"]).zfill(6),
                        "name": str(r["Name"]),
                        "theme": str(r["theme"]),
                        "price": int(safe_float(r["Close"], 0)),
                        "dayChange": round(safe_float(r["dayChange"], 0), 2),
                        "amount": int(safe_float(r["Amount"], 0)),
                        "score": round(safe_float(r["baseScore"], 0), 2),
                        "source": "KRX_WATCH_100",
                    }
                    c = enrich_candidate_risk(c, idx)
                    c = v168_enrich_candidate(c)
                    rows.append(c)
        except Exception:
            rows = []
    if not rows:
        base = cached_candidates() or get_market_candidates(limit=8)
        rows = [v168_enrich_candidate(dict(x)) for x in base]
    return sorted(rows, key=lambda x: safe_float(x.get("v168UltimateScore", x.get("riskAdjustedScore", x.get("score", 0))), 0), reverse=True)[:limit]


def v168_enrich_candidate(c):
    """세력유입/급등10분전/후보진화 2.0/고점매도 예상 점수를 후보에 추가합니다."""
    c = dict(c or {})
    day = safe_float(c.get("dayChange"), 0)
    amount = safe_float(c.get("amount"), 0)
    score = safe_float(c.get("riskAdjustedScore", c.get("score")), 0)
    reverse = safe_float(c.get("marketReverseScore"), 0)
    theme = str(c.get("theme",""))
    overheat = safe_float(c.get("overheatPenalty"), 0)
    slippage = safe_float(c.get("slippagePenalty"), 0)

    money_flow = min(100, amount / 100_000_000_000 * 18 + max(0, day) * 5 + (10 if any(k in theme for k in ["AI","반도체","전력","데이터센터","광통신"]) else 3))
    pump_10m = min(100, score * 0.45 + reverse * 0.22 + money_flow * 0.24 - overheat * 0.7 - slippage * 0.5)
    evolution2 = min(100, safe_float(c.get("v167EvolutionBonus"),0) * 4 + score * 0.65 + money_flow * 0.18)
    peak_sell = max(0, min(100, 45 + day * 5 + reverse * 0.5 - slippage * 0.8))
    ultimate = max(0, min(150, score * 0.52 + money_flow * 0.20 + pump_10m * 0.18 + evolution2 * 0.10 - overheat * 0.4))

    c.update({
        "v168MoneyFlowScore": round(money_flow, 1),
        "v168Pump10mScore": round(pump_10m, 1),
        "v168Evolution2Score": round(evolution2, 1),
        "v168PeakSellPredictScore": round(peak_sell, 1),
        "v168UltimateScore": round(ultimate, 2),
        "v168MoneyFlowNote": "세력유입 강함" if money_flow >= 80 else ("수급 관심" if money_flow >= 55 else "수급 대기"),
        "v168PumpNote": "10분 급등 전조 강함" if pump_10m >= 80 else ("급등 가능성 관찰" if pump_10m >= 60 else "급등 전조 약함"),
    })
    return c


def v168_build_ultimate_report(force=False):
    """v168 Ultimate 종합 리포트. 실전 주문은 하지 않고 분석/추천/승인대기만 수행합니다."""
    cached = read_json(V168_ULTIMATE_FILE, {})
    if isinstance(cached, dict) and cached.get("time") and not force:
        try:
            dt = datetime.strptime(cached["time"][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
            if (now_kst() - dt).total_seconds() < 60:
                return cached
        except Exception:
            pass

    watch_count = safe_int(read_state().get("v168_watch_candidate_count", 100), 100)
    focus_count = safe_int(read_state().get("v168_focus_candidate_count", 10), 10)
    universe = v168_candidate_universe(watch_count)
    focus = universe[:focus_count]
    top3 = universe[:3]
    money_flow_top5 = sorted(universe, key=lambda x: safe_float(x.get("v168MoneyFlowScore"),0), reverse=True)[:5]
    pump_top5 = sorted(universe, key=lambda x: safe_float(x.get("v168Pump10mScore"),0), reverse=True)[:5]
    temp = v168_market_temperature_pro_plus(focus or universe[:10])
    portfolio = v168_portfolio_manager_report()
    assistant = v168_ai_assistant_report(portfolio, temp, focus)
    autonomous = v168_autonomous_manager_report(temp, focus, portfolio)
    report = {
        "ok": True,
        "version": APP_VERSION,
        "time": now_text(),
        "watch_count": len(universe),
        "focus_count": len(focus),
        "top3": top3,
        "focus10": focus,
        "money_flow_top5": money_flow_top5,
        "pump_10m_top5": pump_top5,
        "market_temperature": temp,
        "portfolio": portfolio,
        "assistant": assistant,
        "autonomous_manager": autonomous,
        "safety": "자동교체매수/자율운용은 기본 승인대기입니다. 실제 주문은 사용자 승인 및 기존 실전매매 안전장치를 통과해야 합니다.",
    }
    write_json(V168_ULTIMATE_FILE, report)
    st = read_state()
    st["v168_last_ultimate_report"] = {"time": report["time"], "top": top3[0].get("name") if top3 else "", "temperature": temp.get("temperature"), "label": temp.get("label")}
    write_state(st)
    return report


def v168_portfolio_manager_report():
    holdings = read_holdings()
    total_eval = sum(safe_float(h.get("lastPrice"),0) * safe_float(h.get("qty"),0) for h in holdings)
    total_buy = sum(safe_float(h.get("buyPrice"),0) * safe_float(h.get("qty"),0) for h in holdings)
    pnl = total_eval - total_buy
    rate = (pnl / total_buy * 100) if total_buy else 0
    cash = get_cash_info()
    cash_amt = safe_float(cash.get("cash"), 0) if cash.get("ok") else 0
    total_asset = total_eval + cash_amt
    cash_ratio = (cash_amt / total_asset * 100) if total_asset else 0
    stock_ratio = 100 - cash_ratio if total_asset else 0
    target_cash = 25
    if read_state().get("index_risk_mode") in ["WEAK","DANGER"]:
        target_cash = 40
    elif safe_float(read_state().get("last_market_temperature"),0) >= 80:
        target_cash = 15
    opinion = "현금비중 적정" if abs(cash_ratio-target_cash) <= 8 else ("현금비중 과다: 강한 TOP3만 선별" if cash_ratio > target_cash else "주식비중 높음: 신규매수 축소 및 보유 리스크 점검")
    return {"holdings_count": len(holdings), "total_eval": int(total_eval), "total_buy": int(total_buy), "pnl": int(pnl), "rate": round(rate,2), "cash": int(cash_amt), "cash_ratio": round(cash_ratio,1), "stock_ratio": round(stock_ratio,1), "target_cash_ratio": target_cash, "opinion": opinion, "cash_status": cash}


def v168_ai_assistant_report(portfolio=None, temp=None, focus=None):
    portfolio = portfolio or v168_portfolio_manager_report()
    temp = temp or v168_market_temperature_pro_plus()
    focus = list(focus or [])
    score = 70
    if safe_float(temp.get("temperature"),0) >= 75: score += 10
    if safe_float(portfolio.get("rate"),0) > 0: score += 8
    if portfolio.get("holdings_count",0) <= safe_int(read_state().get("max_positions",3),3): score += 5
    score = max(0,min(100,score))
    weaknesses = []
    if safe_float(portfolio.get("cash_ratio"),0) < 10:
        weaknesses.append("현금비중이 낮아 급락 대응력이 약합니다.")
    if not focus:
        weaknesses.append("집중감시 후보가 부족합니다.")
    if not weaknesses:
        weaknesses.append("현재 큰 약점은 제한적입니다. 다만 추격매수는 금지합니다.")
    strengths = ["AI후보/키움진단/고점추적 구조가 연결되어 있습니다.", "시장온도에 따라 신규매수 강도를 조절할 수 있습니다."]
    direction = "TOP3와 급등예상 TOP5를 중심으로 선별하고, 실전주문 전 키움 현재가·주문가능금액을 재검증하세요."
    return {"investment_score": score, "strengths": strengths, "weaknesses": weaknesses, "direction": direction}


def v168_autonomous_manager_report(temp=None, focus=None, portfolio=None):
    state = read_state()
    temp = temp or v168_market_temperature_pro_plus(focus)
    focus = list(focus or [])
    portfolio = portfolio or v168_portfolio_manager_report()
    allowed = bool(state.get("v168_autonomous_manager_enabled", False))
    auto_rotation = bool(state.get("v168_auto_rotation_enabled", False))
    best = focus[0] if focus else {}
    action = "승인대기"
    reason = "실전매매 영향 기능은 사용자 승인 후 적용합니다."
    if safe_float(temp.get("temperature"),0) < safe_float(state.get("market_temp_stop_buy_below",25),25):
        action = "신규매수 중지 권고"
        reason = "시장온도가 낮아 신규매수보다 보유 리스크 관리가 우선입니다."
    elif best:
        action = "최우선 후보 감시"
        reason = f"{best.get('name')} 후보가 상위입니다. 급등예상/세력유입/키움 현재가를 확인하세요."
    return {"enabled": allowed, "auto_rotation_enabled": auto_rotation, "action": action, "reason": reason, "approval_required": bool(state.get("v168_require_user_approval", True)), "best_candidate": best}


def render_v168_ultimate_center():
    """v168: V168~V171 기능을 하나로 묶은 AI 자산운용사 Ultimate 요약 UI."""
    try:
        r = v168_build_ultimate_report()
        temp = r.get("market_temperature", {})
        top3 = r.get("top3", [])
        money5 = r.get("money_flow_top5", [])
        pump5 = r.get("pump_10m_top5", [])
        pf = r.get("portfolio", {})
        assistant = r.get("assistant", {})
        auto = r.get("autonomous_manager", {})
        def rows(items, key="v168UltimateScore"):
            out = []
            for i,x in enumerate(items,1):
                out.append(f"<div class='v168-row'><div><b>{i}. {html_escape(x.get('name','-'))}</b><small>{html_escape(x.get('theme',''))} · {html_escape(x.get('code',''))}</small></div><div><b>{safe_float(x.get(key),0):.1f}</b><small>{html_escape(x.get('v168PumpNote',''))}</small></div></div>")
            return ''.join(out) or "<div class='notice small'>데이터 대기중</div>"
        return f"""
        <section class="v168-center" id="v168-ultimate">
          <div class="v168-title"><h2>🏦 V169 AI 자산운용센터</h2><span class="v168-tag">V171 기능 통합</span></div>
          <p class="muted">AI후보100 · 집중감시10 · 세력유입 · 급등10분전 · 헤지펀드센터 · 고점매도예측 · 자율운용매니저를 통합 표시합니다.</p>
          <div class="v168-grid">
            <div><span>시장온도 PRO+</span><b>{safe_float(temp.get('temperature'),0):.0f}점 · {html_escape(temp.get('label','-'))}</b><small>{html_escape(temp.get('mode',''))}</small></div>
            <div><span>감시/집중</span><b>{r.get('watch_count',0)}개 / {r.get('focus_count',0)}개</b><small>AI후보100 · TOP10 집중감시</small></div>
            <div><span>총자산 추정</span><b>{money(pf.get('total_eval',0)+pf.get('cash',0))}</b><small>현금 {pf.get('cash_ratio',0)}% / 주식 {pf.get('stock_ratio',0)}%</small></div>
            <div><span>AI 투자점수</span><b>{assistant.get('investment_score',0)}점</b><small>{html_escape(pf.get('opinion',''))}</small></div>
          </div>
          <div class="v168-warn">실전 주문 영향 기능(자동교체매수·자율운용·고점매도)은 기본 승인대기 구조입니다. 직접 승인 전 자동 적용되지 않습니다.</div>
          <details open><summary>🏆 AI 추천 TOP3</summary><div class="v168-list">{rows(top3)}</div></details>
          <details><summary>💸 세력유입 TOP5</summary><div class="v168-list">{rows(money5,'v168MoneyFlowScore')}</div></details>
          <details><summary>🚀 급등 10분전 예상 TOP5</summary><div class="v168-list">{rows(pump5,'v168Pump10mScore')}</div></details>
          <details><summary>🧭 AI 자율운용 매니저</summary><div class="notice small"><b>{html_escape(auto.get('action',''))}</b><br>{html_escape(auto.get('reason',''))}</div></details>
          <div class="btn-row">
            <button onclick="callAndReload('/api/v168_refresh_ultimate')">V168 재분석</button>
            <a class="button dark" href="/api/v168_ultimate">JSON 확인</a>
          </div>
        </section>"""
    except Exception as e:
        return f"<section class='v168-center' id='v168-ultimate'><h2>🏦 V169 AI 자산운용센터</h2><div class='notice'>표시 오류: {html_escape(str(e))}</div></section>"

def render_version_summary():
    try:
        latest = UPDATE_HISTORY[0]
        items = "".join(f"<li>{html_escape(x)}</li>" for x in latest.get("items", []))
        history = "".join(
            f"<div class='version-row'><b>{html_escape(h.get('version',''))}</b><span>{html_escape(h.get('title',''))}</span></div>"
            for h in UPDATE_HISTORY[:4]
        )
        return f"""
        <div class="version-summary">
          <div><b>{APP_TITLE}</b></div>
          <div class="mini-line">파일: {APP_FILE_NAME} · 패치: {APP_PATCH_NAME}</div>
          <details>
            <summary>📌 업데이트 이력 보기 / 접기</summary>
            <div class="notice small">
              <b>{html_escape(latest.get('version'))} 핵심 변경</b>
              <ul>{items}</ul>
              {history}
            </div>
          </details>
        </div>"""
    except Exception:
        return f"<div class='version-summary'><b>{APP_TITLE}</b></div>"



def render_quick_status_bar():
    """v167: 앱 상단에서 핵심 상태를 한눈에 확인합니다."""
    try:
        state = read_state()
        picks_data = read_json(CANDIDATE_FILE, {})
        pick_count = len(picks_data.get("items", [])) if isinstance(picks_data, dict) else 0
        holdings_count = len(read_holdings())
        auto_txt = "ON" if state.get("auto_trade_enabled") else "OFF"
        profit = money(state.get("daily_realized_pnl", 0))
        trade_count = safe_int(state.get("trade_count_today"), 0)
        last_scan = state.get("last_candidate_scan_time") or "-"
        return f"""
        <div class="status-bar-v167">
          <div><span>🤖 후보</span><b>{pick_count}개</b></div>
          <div><span>💼 보유</span><b>{holdings_count}개</b></div>
          <div><span>💰 오늘손익</span><b>{profit}</b></div>
          <div><span>🔁 거래</span><b>{trade_count}회</b></div>
          <div><span>⚙️ 자동</span><b>{auto_txt}</b></div>
          <div><span>⏱ 스캔</span><b>{html_escape(last_scan)}</b></div>
        </div>"""
    except Exception as e:
        return f"<div class='status-bar-v167'><div><span>상태</span><b>표시 오류 {html_escape(str(e))}</b></div></div>"


def render_mobile_menu_cards():
    """v166: 모바일에서 가로 드래그 없이 보이는 3열 카드형 메뉴입니다."""
    items = [
        ("#v168-ultimate", "🏦", "AI자산운용", "후보100·급등예측"),
        ("#picks", "🤖", "AI후보", "실시간 후보·추천이유"),
        ("#profit-optimization", "🚀", "수익최적화", "복기·동적익절·시장온도"),
        ("#conditions", "🧭", "매매조건", "익절·손절·재매수"),
        ("#ai-upgrade", "🧠", "AI조건", "추천조건 승인 적용"),
        ("#analysis-center", "📊", "AI분석센터", "시장리포트·투자평가"),
        ("#kiwoom-diagnosis", "🔧", "키움진단", "토큰·계좌·지정단말기"),
        ("#holdings", "💼", "보유종목", "실보유·매도·AI판단"),
    ]
    cards = []
    for href, icon, title, desc in items:
        cards.append(f"<a href='{href}'><b>{icon} {html_escape(title)}</b><span>{html_escape(desc)}</span></a>")
    return f"""
    <div class="menu-grid-v167">
      {''.join(cards)}
    </div>
    <div class="menu-help-v167">
      <b>사용 순서 추천</b> ① AI후보 확인 → ② 키움진단 정상 확인 → ③ 매매조건 점검 → ④ 최우선 후보 매수/자동매매 실행
    </div>"""


def render_market_temperature(picks=None):
    """v166: 후보 품질과 지수위험을 합쳐 시장온도계를 표시합니다."""
    try:
        picks = list(picks or [])
        state = read_state()
        avg_conf = sum(safe_float(x.get("aiConfidence"), 0) for x in picks[:5]) / max(1, min(len(picks), 5))
        avg_reverse = sum(safe_float(x.get("marketReverseScore"), 0) for x in picks[:5]) / max(1, min(len(picks), 5))
        index_mode = state.get("index_risk_mode", "UNKNOWN")
        temp = avg_conf * 0.65 + min(30, avg_reverse * 0.35)
        if index_mode == "DANGER":
            temp -= 18
        elif index_mode == "WEAK":
            temp -= 8
        temp = max(0, min(100, temp))
        if temp >= 80:
            label, icon, msg = "매수 우호", "🔥", "강한 후보가 많습니다. 단, 추격매수는 금지하고 눌림·재돌파를 확인하세요."
        elif temp >= 65:
            label, icon, msg = "강세", "😊", "후보 품질이 양호합니다. TOP3 중심으로 감시하는 구간입니다."
        elif temp >= 45:
            label, icon, msg = "중립", "😐", "선별 진입이 필요합니다. 키움 가격확인과 거래대금 유지율을 확인하세요."
        elif temp >= 30:
            label, icon, msg = "약세", "⚠️", "신규매수 비중을 줄이고 실보유 리스크 관리가 우선입니다."
        else:
            label, icon, msg = "위험", "🚨", "자동매매보다 관망/진단/보유관리 우선 구간입니다."
        return f"""
        <div class="market-temp-v167">
          <div><span>{icon}</span><b>AI 시장온도 PRO {temp:.0f}점 · {label}</b></div>
          <p>{html_escape(msg)}</p>
          <small>지수위험 {html_escape(index_mode)} · 평균확신도 {avg_conf:.1f}% · 평균시장역행 {avg_reverse:.1f}</small>
        </div>"""
    except Exception as e:
        return f"<div class='market-temp-v167'><b>AI 시장온도 표시 오류</b><p>{html_escape(str(e))}</p></div>"


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
        peak_stage = h.get('aiPeakStage', '기본 감시')
        sell_plan = h.get('aiSellPlan', '')
        trail_rate = h.get('aiTrailingRate', '')
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
            <div><label>고점매도 단계</label><b>{peak_stage}</b></div>
            <div><label>되돌림 기준</label><b>{trail_rate}%</b></div>
            <div><label>수량/손익</label><b>{h['qty']}주 · {money(h['pnl'])}</b></div>
            <div><label>수익률</label><b class="red">{pct(h['profitRate'])}</b></div>
          </div>
          <div class="comment">{ai_note}<br>{sell_plan}<br>최근확인 {html_escape(h.get('lastCheckedAt','-'))} · {html_escape(h.get('priceSource','-'))}</div>
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
        <div class="mini-line">v167 동적익절 <b>{safe_float(c.get('v167DynamicTargetRate'), safe_float(read_state().get('target_rate'),0.027)*100):.2f}%</b> · {html_escape(c.get('v167DynamicTargetReason','기본 익절률'))}</div>
        <div class="mini-line">후보진화: {html_escape(c.get('evolutionNote','성과 누적 대기'))}</div>
        <div class="mini-line">거래대금 {html_escape(c.get('amountText','-'))} · 매수관찰 {money(c.get('buyZone'))}</div>
        <div class="mini-line">시장역행 {safe_float(c.get('marketReverseScore')):.1f} · 테마강도 {safe_float(c.get('themeStrengthScore')):.0f} · 과열감점 {safe_float(c.get('overheatPenalty')):.0f} · 슬리피지감점 {safe_float(c.get('slippagePenalty')):.0f}</div>
        <div class="mini-line">{html_escape(c.get('priceRefreshNote',''))}</div>
      </div>
    </div>"""



def render_top3_comparison(picks):
    top3 = list(picks or [])[:3]
    if not top3:
        return '<div class="notice small">TOP3 후보 비교 대기중입니다.</div>'
    rows = []
    for i, c in enumerate(top3, 1):
        rows.append(f"""
        <div class="strategy-card {'best' if i==1 else ''}">
          <span class="tag">TOP {i}</span>
          <h3>{html_escape(c.get('name'))}</h3>
          <div class="summary-grid">
            <div><span>AI점수</span><b>{safe_float(c.get('riskAdjustedScore', c.get('score'))):.1f}</b></div>
            <div><span>현재가/출처</span><b>{money(c.get('price'))}</b><small>{html_escape(c.get('priceSource') or c.get('source','-'))}</small></div>
            <div><span>시장역행</span><b>{safe_float(c.get('marketReverseScore')):.1f}</b></div>
            <div><span>테마/전략</span><b>{html_escape(c.get('theme','-'))}</b><small>{html_escape(c.get('strategy','AI후보형'))}</small></div>
            <div><span>동적익절</span><b>{safe_float(c.get('v167DynamicTargetRate'), safe_float(read_state().get('target_rate'),0.027)*100):.2f}%</b><small>{html_escape(c.get('v167DynamicTargetReason','기본'))}</small></div>
          </div>
          <div class="mini-line">추천: {html_escape(' · '.join((c.get('aiReasons') or [])[:2]) or c.get('aiVerdict','AI후보'))}</div>
          <div class="mini-line">위험: {html_escape(' · '.join((c.get('aiRisks') or [])[:2]) or '특이 위험 낮음')}</div>
        </div>""")
    return f"""
    <details open class="top3-box">
      <summary>🏆 TOP3 후보 비교 보기 / 접기</summary>
      <div class="notice small">AI점수, 시장역행, 가격출처, 테마강도를 한 번에 비교합니다. 최우선 매수는 TOP1을 기준으로 하되 주문 직전 키움 현재가를 다시 확인합니다.</div>
      {''.join(rows)}
    </details>"""

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
      {render_market_temperature(picks)}
      {render_top3_comparison(picks)}
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
        <div><span>AI 고점매도</span><b>{'ON' if state.get('ai_peak_sell_enabled', True) else 'OFF'} · 고점추적</b></div>
        <div><span>최소 AI 점수</span><b>{safe_float(state.get('min_ai_score'),60):.1f}</b></div>
        <div><span>최소 거래대금</span><b>{safe_int(state.get('min_amount'),3000000000)/100000000:.0f}억</b></div>
        <div><span>재매수 제한</span><b>{safe_float(state.get('rebuy_cooldown_minutes'),30):.0f}분</b></div>
        <div><span>시장온도</span><b>{safe_float(state.get('last_market_temperature'),0):.0f}점 · {html_escape(state.get('last_market_temperature_label','대기'))}</b></div>
        <div><span>동적 익절률</span><b>{'ON' if state.get('dynamic_take_profit_enabled', True) else 'OFF'} · 강세/초강세 자동상향</b></div>
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
            <label>v167 일반 동적익절(%)<input name="dynamic_take_profit_normal" value="{safe_float(state.get('dynamic_take_profit_normal'),0.027)*100:.2f}"><small>일반 후보 기본 목표</small></label>
            <label>v167 강세 동적익절(%)<input name="dynamic_take_profit_strong" value="{safe_float(state.get('dynamic_take_profit_strong'),0.045)*100:.2f}"><small>강한 후보 목표</small></label>
            <label>v167 초강세 동적익절(%)<input name="dynamic_take_profit_super" value="{safe_float(state.get('dynamic_take_profit_super'),0.070)*100:.2f}"><small>초강세 후보 목표</small></label>
            <label>v167 상한가패턴 목표(%)<input name="dynamic_take_profit_limitup" value="{safe_float(state.get('dynamic_take_profit_limitup'),0.100)*100:.2f}"><small>매우 강한 추세 후보 목표</small></label>
            <label>상향익절 시작 수익률(%)<input name="dynamic_target_min_profit_rate" value="{safe_float(state.get('dynamic_target_min_profit_rate'),0.027)*100:.2f}"><small>이 수익률 이상이면 AI가 목표가를 끌어올릴 수 있습니다.</small></label>
            <label>고점추적 1단계 수익률(%)<input name="ai_peak_stage1_profit_rate" value="{safe_float(state.get('ai_peak_stage1_profit_rate'),0.045)*100:.2f}"><small>예: 4.50 = 수익 4.5%부터 되돌림 기준을 조금 좁힘</small></label>
            <label>고점추적 2단계 수익률(%)<input name="ai_peak_stage2_profit_rate" value="{safe_float(state.get('ai_peak_stage2_profit_rate'),0.070)*100:.2f}"><small>예: 7.00 = 강세구간</small></label>
            <label>고점추적 3단계 수익률(%)<input name="ai_peak_stage3_profit_rate" value="{safe_float(state.get('ai_peak_stage3_profit_rate'),0.100)*100:.2f}"><small>예: 10.00 = 초강세구간</small></label>
            <label>1단계 되돌림 매도폭(%)<input name="ai_peak_trailing_stage1" value="{safe_float(state.get('ai_peak_trailing_stage1'),0.009)*100:.2f}"><small>예: 0.90 = 고점 대비 -0.9% 밀리면 매도</small></label>
            <label>2단계 되돌림 매도폭(%)<input name="ai_peak_trailing_stage2" value="{safe_float(state.get('ai_peak_trailing_stage2'),0.007)*100:.2f}"></label>
            <label>3단계 되돌림 매도폭(%)<input name="ai_peak_trailing_stage3" value="{safe_float(state.get('ai_peak_trailing_stage3'),0.0055)*100:.2f}"></label>
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
          <label class="check"><input type="checkbox" name="ai_peak_sell_enabled" {'checked' if state.get('ai_peak_sell_enabled', True) else ''}> AI 고점매도 허용</label>
          <label class="check"><input type="checkbox" name="ai_peak_tight_trailing_enabled" {'checked' if state.get('ai_peak_tight_trailing_enabled', True) else ''}> 수익률 구간별 되돌림 자동 조절</label>
          <label class="check"><input type="checkbox" name="switch_buy_enabled" {switch_on}> 전환매수 허용</label>
          <div class="btn-row"><button type="submit">매매조건 저장</button><a class="button dark" href="/api/reset_conditions">기본조건 복원</a></div>
        </form>
      </details>
      <details><summary>조건 설명 보기 / 접기</summary><div class="notice small">
        최소 AI 점수와 최소 거래대금이 높을수록 후보가 줄고 안정성이 올라갑니다.<br>
        최대 당일 등락률은 과열/추격매수 방지용입니다.<br>
        AI 상향익절은 목표가 도달 후에도 시장역행점수·거래대금·상승흐름이 좋으면 목표가를 더 올리고 트레일링으로 보호합니다.<br>
        AI 고점매도는 정확한 최고점을 예측하는 기능이 아니라, 최고가를 계속 기록하면서 수익률이 커질수록 되돌림 허용폭을 좁혀 고점 근처에서 수익을 보호하는 기능입니다.<br>
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




def render_daily_report_section_safe():
    try:
        return render_daily_report_section()
    except Exception as e:
        return f"""
        <section class="card" id="daily-report">
          <h2>📰 AI 일일리포트</h2>
          <div class="notice">AI일일리포트 생성 중 오류가 발생했습니다. 앱은 계속 동작합니다.<br>{html_escape(str(e))}</div>
          <div class="btn-row"><button onclick="location.href='/api/refresh_daily_report'">AI일일리포트 새로작성</button></div>
        </section>"""


def render_investment_review_section_safe():
    try:
        return render_investment_review_section()
    except Exception as e:
        return f"""
        <section class="card" id="my-review">
          <h2>🧾 AI 내투자평가</h2>
          <div class="notice">AI내투자평가 생성 중 오류가 발생했습니다. 앱은 계속 동작합니다.<br>{html_escape(str(e))}</div>
          <div class="btn-row"><button onclick="location.href='/api/refresh_investment_review'">내투자평가 새로작성</button></div>
        </section>"""




def render_v167_profit_center():
    """v167: 수익률 최적화 엔진 요약 카드."""
    try:
        state = read_state()
        picks = cached_candidates()[:8]
        temp = v167_market_temperature_data(picks)
        reviews = read_json(REVIEW_FILE, [])
        last_review = reviews[0].get('summary') if isinstance(reviews, list) and reviews else state.get('last_review_summary','복기 데이터 대기중')
        top = picks[0] if picks else {}
        top_rate = safe_float(top.get('v167DynamicTargetRate'), safe_float(state.get('target_rate'),0.027)*100)
        return f"""
        <section class="card" id="profit-optimization">
          <h2>🚀 v167 수익률 최적화 엔진</h2>
          <p class="muted">실전 복기, 후보 진화, 시장온도계 PRO, 동적 익절률, 강도변화 알림을 한 화면에서 확인합니다.</p>
          <div class="summary-grid">
            <div><span>시장온도 PRO</span><b>{temp['temperature']:.0f}점 · {html_escape(temp['label'])}</b><small>{html_escape(temp['mode'])}</small></div>
            <div><span>TOP1 동적익절</span><b>{top_rate:.2f}%</b><small>{html_escape(top.get('name','후보 대기'))}</small></div>
            <div><span>후보진화</span><b>{'ON' if state.get('candidate_evolution_enabled', True) else 'OFF'}</b><small>성과 좋은 전략/테마 가중</small></div>
            <div><span>강도변화 알림</span><b>{'ON' if state.get('strength_alert_enabled', True) else 'OFF'}</b><small>{safe_float(state.get('strength_drop_alert_threshold'),12):.0f}점 하락시 알림</small></div>
          </div>
          <div class="notice small"><b>AI 시장판단</b><br>{html_escape(temp['guide'])}<br>평균AI {temp['avg_score']} · 시장역행 {temp['avg_reverse']} · 테마강도 {temp['avg_theme']} · 지수위험 {html_escape(temp['index_mode'])}</div>
          <div class="notice small"><b>최근 실전복기</b><br>{html_escape(last_review)}</div>
          <div class="btn-row">
            <a class="button" href="/api/v167_profit_optimization">수익률 엔진 JSON</a>
            <a class="button dark" href="/api/v167_review_center">실전 복기센터</a>
          </div>
        </section>"""
    except Exception as e:
        return f"<section class='card'><h2>🚀 v167 수익률 최적화 엔진</h2><div class='notice'>표시 오류: {html_escape(str(e))}</div></section>"


def _diag_color(ok):
    if ok is True:
        return "🟢"
    if ok is False:
        return "🔴"
    return "🟡"


def render_kiwoom_diagnosis_section():
    try:
        auth = build_auth_status(check_token=False)
        raw = read_json(KIWOOM_RAW_HOLDINGS_FILE, {})
        summary = kiwoom_raw_structure_summary(raw) if raw else {}
        cached = get_cached_holdings()
        last_debug = auth.get('last_kiwoom_debug') or {}
        token_ok = auth.get('token_ok')
        designated = auth.get('designated_device_ok')
        additional = auth.get('additional_auth_ok')
        account_ok = auth.get('env',{}).get('KIWOOM_ACCOUNT')
        raw_rows = summary.get('probable_rows', 0) if isinstance(summary, dict) else 0
        codes = ', '.join(summary.get('codes_found', [])[:6]) if isinstance(summary, dict) else ''
        analysis = auth.get('token_analysis') or last_debug.get('analysis') or kiwoom_error_analysis(last_debug.get('raw_message') or auth.get('token_message'))
        render_ip = auth.get('render_public_ip') or {}
        health = auth.get('health_score', 0)
        final_status = '정상 사용 가능' if (auth.get('env',{}).get('KIWOOM_APP_KEY') and auth.get('env',{}).get('KIWOOM_APP_SECRET') and account_ok and token_ok) else '확인 필요'
        final_class = 'ok-pill' if final_status == '정상 사용 가능' else 'warn-pill'
        ip_line = f"Render 현재 IP: {html_escape(render_ip.get('ip') or '확인 필요')}"
        if KIWOOM_REGISTERED_IPS:
            ip_line += f" / 등록IP환경변수: {html_escape(', '.join(KIWOOM_REGISTERED_IPS))}"
        else:
            ip_line += " / 키움 사이트 등록 IP와 직접 비교하세요"
        steps_html = ''.join(f"<li>{html_escape(x)}</li>" for x in (analysis.get('steps') or [])[:5])

        return f"""
        <section class="card" id="kiwoom-diagnosis">
          <h2>🔧 키움 진단센터 PRO v167</h2>
          <p class="muted">APP KEY·SECRET·ACCOUNT·TOKEN·지정단말기·추가인증·계좌조회를 한 화면에서 확인하고, 오류코드를 자동 해석합니다.</p>
          <div class="notice small"><b>키움 연동 건강도: {health}점</b><br>{ip_line}</div>
          <div class="summary-grid">
            <div><span>APP KEY</span><b>{'🟢 입력 완료' if auth.get('env',{}).get('KIWOOM_APP_KEY') else '🔴 없음'}</b></div>
            <div><span>APP SECRET</span><b>{'🟢 입력 완료' if auth.get('env',{}).get('KIWOOM_APP_SECRET') else '🔴 없음'}</b></div>
            <div><span>ACCOUNT</span><b>{'🟢 ' + html_escape(auth.get('env',{}).get('KIWOOM_ACCOUNT_DISPLAY','')) if account_ok else '🔴 KIWOOM_ACCOUNT 없음'}</b></div>
            <div><span>TOKEN</span><b>{'🟢 발급/캐시 정상' if token_ok else '🔴 실패 또는 미확인'}</b></div>
            <div><span>지정단말기</span><b>{_diag_color(designated)} {'정상' if designated is True else '확인필요' if designated is False else '미확인'}</b></div>
            <div><span>추가인증</span><b>{_diag_color(additional)} {'정상' if additional is True else '확인필요' if additional is False else '미확인'}</b></div>
            <div><span>계좌조회/주문가능</span><b>{'🟢 확인가능' if token_ok and account_ok else '🔴 확인필요'}</b></div>
            <div><span>실보유조회</span><b>{'🟢 ' + str(len(cached)) + '종목 캐시' if cached else '🟡 보유/파싱 확인필요'}</b></div>
            <div><span>RAW 후보행</span><b>{raw_rows}개</b></div>
            <div><span>최종판정</span><b class="{final_class}">{final_status}</b></div>
          </div>
          <div class="notice small">
            <b>오류코드 자동해석</b><br>
            코드/분류: {html_escape(analysis.get('code','UNKNOWN'))} / {html_escape(analysis.get('name','미분류'))}<br>
            원인: {html_escape(analysis.get('summary','-'))}<br>
            조치: {html_escape(analysis.get('action','-'))}
            <ol>{steps_html}</ol>
          </div>
          <div class="notice small">
            최근 키움 메시지: {html_escape(last_debug.get('message') or auth.get('token_message','-'))}<br>
            RAW에서 찾은 코드: {html_escape(codes or '없음')}
          </div>
          <div class="btn-row">
            <a class="button" href="/api/v163_token_refresh">토큰 재발급/진단</a>
            <a class="button dark" href="/api/v163_full_diagnosis">전체 진단 실행</a>
            <a class="button brown" href="/api/holdings?force=1">실보유 강제조회</a>
            <a class="button light" href="/api/kiwoom_raw_holdings">RAW 보유응답</a>
            <a class="button light" href="/api/v163_diagnosis_log">진단로그</a>
          </div>
        </section>"""
    except Exception as e:
        return f"<section class='card' id='kiwoom-diagnosis'><h2>🧪 키움 진단센터 PRO</h2><div class='notice'>진단센터 표시 오류: {html_escape(str(e))}</div></section>"



# ==============================
# v169 AI 자산운용센터 정리/경량화 패치
# ==============================

def v169_analyze_holding(h):
    """보유종목별 보유/추가매수/매도 점수와 목표/손절 의견을 간단히 산출합니다."""
    h = normalize_holding(h)
    profit = safe_float(h.get("profitRate"), 0)
    ai_stage = str(h.get("aiPeakStage", ""))
    price_src = str(h.get("priceSource", "CACHE"))
    hold_score = 55 + min(30, max(-20, profit * 4))
    if "고점추적" in ai_stage:
        hold_score += 10
    if price_src == "KIWOOM":
        hold_score += 5
    sell_score = 35
    if profit <= -2:
        sell_score += 25
    if h.get("trailingStopPrice") and safe_float(h.get("lastPrice"),0) <= safe_float(h.get("trailingStopPrice"),0) * 1.003:
        sell_score += 25
    add_score = max(0, min(100, hold_score - 15 if profit >= 0 else hold_score - 30))
    hold_score = max(0, min(100, hold_score))
    sell_score = max(0, min(100, sell_score))
    if sell_score >= 70:
        opinion = "매도/리스크 점검 우선"
    elif hold_score >= 75:
        opinion = "보유 유지 우세"
    elif add_score >= 65:
        opinion = "소액 추가매수는 가능하나 키움 현재가 확인 필요"
    else:
        opinion = "관망"
    return {
        "code": h.get("code"), "name": h.get("name"),
        "profitRate": round(profit, 2),
        "hold_score": round(hold_score, 1),
        "add_score": round(add_score, 1),
        "sell_score": round(sell_score, 1),
        "target": h.get("activeDynamicTarget") or h.get("target"),
        "stop": h.get("stop"),
        "trailingStopPrice": h.get("trailingStopPrice", 0),
        "opinion": opinion,
        "stage": ai_stage,
    }


def v169_fund_manager_report(portfolio=None, temp=None, focus=None):
    """성일 AI 펀드매니저: 현금/테마/종목수 기준 자산배분 제안."""
    portfolio = portfolio or v168_portfolio_manager_report()
    temp = temp or v168_market_temperature_pro_plus(focus)
    holdings = read_holdings()
    focus = list(focus or [])
    temp_score = safe_float(temp.get("temperature"), 0)
    if temp_score >= 80:
        target_cash = 15
        mode = "공격 운용"
    elif temp_score >= 60:
        target_cash = 25
        mode = "균형 운용"
    elif temp_score >= 40:
        target_cash = 40
        mode = "방어 운용"
    else:
        target_cash = 60
        mode = "현금방어"
    themes = {}
    for x in list(focus[:5]) + holdings:
        th = str(x.get("theme") or classify_theme(str(x.get("name",""))))
        themes[th] = themes.get(th, 0) + 1
    theme_rank = sorted(themes.items(), key=lambda kv: kv[1], reverse=True)[:4]
    allocation = []
    remain = max(0, 100 - target_cash)
    if theme_rank:
        base = max(10, int(remain / max(1, len(theme_rank))))
        for th, _ in theme_rank:
            allocation.append({"theme": th, "weight": base})
    else:
        allocation = [{"theme": "AI후보 TOP5", "weight": remain}]
    return {
        "mode": mode,
        "target_cash_ratio": target_cash,
        "current_cash_ratio": portfolio.get("cash_ratio", 0),
        "allocation": allocation,
        "opinion": f"시장온도 {temp_score:.0f}점 기준 {mode}. 목표 현금비중은 {target_cash}%입니다.",
    }


def v169_review_2_report():
    """매매복기 2.0: 최근 거래를 요일/시간/전략 단위로 요약합니다."""
    ledger = read_ledger()[-100:]
    if not ledger:
        return {"summary": "최근 매매기록이 부족합니다.", "by_strategy": [], "by_hour": [], "by_weekday": []}
    by_strategy, by_hour, by_weekday = {}, {}, {}
    for e in ledger:
        pnl = safe_float(e.get("pnl"), 0)
        strategy = str(e.get("strategy") or "AI후보형")
        try:
            dt = datetime.strptime(str(e.get("time",""))[:19], "%Y-%m-%d %H:%M:%S")
            hour = f"{dt.hour:02d}시"
            weekday = ["월","화","수","목","금","토","일"][dt.weekday()]
        except Exception:
            hour, weekday = "미확인", "미확인"
        for box, key in [(by_strategy, strategy), (by_hour, hour), (by_weekday, weekday)]:
            row = box.setdefault(key, {"trades":0,"wins":0,"pnl":0})
            row["trades"] += 1
            row["wins"] += 1 if pnl > 0 else 0
            row["pnl"] += pnl
    def pack(box):
        out=[]
        for k,v in box.items():
            trades=max(1,v["trades"])
            out.append({"name": k, "trades": v["trades"], "win_rate": round(v["wins"]/trades*100,1), "pnl": int(v["pnl"])})
        return sorted(out, key=lambda x:(x["pnl"],x["win_rate"]), reverse=True)[:6]
    return {"summary": f"최근 {len(ledger)}건 기준 복기입니다.", "by_strategy": pack(by_strategy), "by_hour": pack(by_hour), "by_weekday": pack(by_weekday)}


def v169_build_asset_center_report(force=False):
    """v169: v168의 여러 센터를 AI 자산운용센터 하나로 통합한 경량 리포트."""
    base = v168_build_ultimate_report(force=force)
    focus = (base.get("focus10") or [])[:safe_int(read_state().get("v169_focus_candidate_count",5),5)]
    temp = base.get("market_temperature") or v168_market_temperature_pro_plus(focus)
    portfolio = base.get("portfolio") or v168_portfolio_manager_report()
    holdings_analysis = [v169_analyze_holding(h) for h in read_holdings()]
    fund = v169_fund_manager_report(portfolio, temp, focus)
    review2 = v169_review_2_report()
    report = {
        "ok": True,
        "version": APP_VERSION,
        "time": now_text(),
        "watch_count": base.get("watch_count",0),
        "focus_count": len(focus),
        "focus_top5": focus,
        "money_flow_top5": base.get("money_flow_top5", [])[:5],
        "pump_10m_top5": base.get("pump_10m_top5", [])[:5],
        "market_temperature": temp,
        "portfolio": portfolio,
        "fund_manager": fund,
        "holdings_ai": holdings_analysis,
        "review_2": review2,
        "removed_or_hidden": ["AI투자비서 단독메뉴", "TOP3 비교 단독표시", "중복 진단 API 메뉴"],
        "compatibility": "v168 API는 호환 유지, 화면은 v169 AI 자산운용센터 중심으로 정리",
    }
    st = read_state()
    st["v169_last_asset_center_report"] = {"time": report["time"], "focus_count": report["focus_count"], "temperature": temp.get("temperature"), "label": temp.get("label")}
    write_state(st)
    return report


def render_v168_ultimate_center():
    """v169: 기존 v168 Ultimate 영역을 AI 자산운용센터로 통합 표시합니다."""
    try:
        r = v169_build_asset_center_report()
        temp = r.get("market_temperature", {})
        focus = r.get("focus_top5", [])
        money5 = r.get("money_flow_top5", [])
        pump5 = r.get("pump_10m_top5", [])
        pf = r.get("portfolio", {})
        fund = r.get("fund_manager", {})
        holdings_ai = r.get("holdings_ai", [])
        review2 = r.get("review_2", {})
        def rows(items, key="v168UltimateScore"):
            out = []
            for i,x in enumerate(items,1):
                out.append(f"<div class='v168-row'><div><b>{i}. {html_escape(x.get('name','-'))}</b><small>{html_escape(x.get('theme',''))} · {html_escape(x.get('code',''))}</small></div><div><b>{safe_float(x.get(key),0):.1f}</b><small>{html_escape(x.get('v168PumpNote') or x.get('v168MoneyFlowNote') or '')}</small></div></div>")
            return ''.join(out) or "<div class='notice small'>데이터 대기중</div>"
        holding_rows = ''.join(
            f"<div class='v168-row'><div><b>{html_escape(x.get('name','-'))}</b><small>수익률 {safe_float(x.get('profitRate'),0):.2f}% · {html_escape(x.get('stage',''))}</small></div><div><b>보유 {x.get('hold_score',0)}</b><small>매도 {x.get('sell_score',0)} · {html_escape(x.get('opinion',''))}</small></div></div>"
            for x in holdings_ai
        ) or "<div class='notice small'>보유종목 분석 대기중</div>"
        alloc_rows = ''.join(f"<span>{html_escape(a.get('theme'))} {a.get('weight')}%</span>" for a in fund.get('allocation', []))
        review_rows = ''.join(f"<span>{html_escape(x.get('name'))} 승률 {x.get('win_rate')}% / {money(x.get('pnl'))}</span>" for x in review2.get('by_strategy', [])[:4]) or '<span>복기 데이터 대기</span>'
        return f"""
        <section class="v168-center" id="asset-center">
          <div class="v168-title"><h2>🏦 V169 AI 자산운용센터</h2><span class="v168-tag">메뉴 30% 정리</span></div>
          <p class="muted">AI투자비서·헤지펀드센터·포트폴리오관리·자율운용매니저를 하나로 통합했습니다. 화면은 TOP5 집중감시와 실보유 AI 판단 중심으로 정리했습니다.</p>
          <div class="v168-grid">
            <div><span>시장온도</span><b>{safe_float(temp.get('temperature'),0):.0f}점 · {html_escape(temp.get('label','-'))}</b><small>{html_escape(temp.get('mode',''))}</small></div>
            <div><span>감시/집중</span><b>{r.get('watch_count',0)}개 / TOP{r.get('focus_count',0)}</b><small>후보100 유지 · 화면은 TOP5 중심</small></div>
            <div><span>자산/현금</span><b>{money(pf.get('total_eval',0)+pf.get('cash',0))}</b><small>현금 {pf.get('cash_ratio',0)}% → 목표 {fund.get('target_cash_ratio',0)}%</small></div>
            <div><span>펀드매니저</span><b>{html_escape(fund.get('mode','-'))}</b><small>{html_escape(fund.get('opinion',''))}</small></div>
          </div>
          <div class="v168-warn">중복 메뉴 정리: AI투자비서/TOP3 비교/중복 진단 메뉴는 숨김 처리하고, 기존 API 호환은 유지했습니다. 실전 주문 영향 기능은 승인대기 구조를 유지합니다.</div>
          <details open><summary>🏆 집중감시 TOP5</summary><div class="v168-list">{rows(focus)}</div></details>
          <details><summary>💸 세력유입 TOP5</summary><div class="v168-list">{rows(money5,'v168MoneyFlowScore')}</div></details>
          <details><summary>🚀 급등 10분전 TOP5</summary><div class="v168-list">{rows(pump5,'v168Pump10mScore')}</div></details>
          <details open><summary>💼 실보유 AI 분석센터</summary><div class="v168-list">{holding_rows}</div></details>
          <details><summary>🧭 AI 펀드매니저 자산배분</summary><div class="chips">{alloc_rows}</div><div class="notice small">{html_escape(fund.get('opinion',''))}</div></details>
          <details><summary>📘 매매복기 2.0</summary><div class="chips">{review_rows}</div><div class="notice small">{html_escape(review2.get('summary',''))}</div></details>
          <div class="btn-row">
            <button onclick="callAndReload('/api/v169_refresh_asset_center')">V169 재분석</button>
            <a class="button dark" href="/api/v169_asset_center">JSON 확인</a>
          </div>
        </section>"""
    except Exception as e:
        return f"<section class='v168-center' id='asset-center'><h2>🏦 V169 AI 자산운용센터</h2><div class='notice'>표시 오류: {html_escape(str(e))}</div></section>"


def render_mobile_menu_cards():
    """v169: 사용 빈도 중심으로 메뉴를 30% 줄인 카드형 메뉴."""
    items = [
        ("#asset-center", "🏦", "AI자산운용", "TOP5·실보유·펀드"),
        ("#picks", "🤖", "AI후보", "추천이유·급등감시"),
        ("#conditions", "🧭", "매매조건", "익절·손절·고점매도"),
        ("#analysis-center", "📊", "AI분석", "리포트·복기·전략"),
        ("#kiwoom-diagnosis", "🔧", "키움진단", "토큰·계좌·실보유"),
        ("#holdings", "💼", "보유/매도", "실보유·수동매도"),
    ]
    cards = []
    for href, icon, title, desc in items:
        cards.append(f"<a href='{href}'><b>{icon} {html_escape(title)}</b><span>{html_escape(desc)}</span></a>")
    return f"""
    <div class="menu-grid-v167 menu-grid-v169">
      {''.join(cards)}
    </div>
    <div class="menu-help-v167">
      <b>v169 정리 방향</b> AI투자비서·헤지펀드·포트폴리오·자율운용은 <b>AI자산운용센터</b> 하나로 통합했습니다. 사용 순서: AI자산운용 → AI후보 → 키움진단 → 매매조건 → 보유/매도.
    </div>"""

def render_page():
    state = read_state()
    return render_template_string(TEMPLATE,
        version=APP_VERSION,
        app_name=APP_NAME,
        holdings=render_holdings_section(),
        trade=render_trade_section(),
        candidates=render_candidates(),
        profit_center=render_v167_profit_center(),
        conditions=render_conditions_section(),
        daily_report=render_daily_report_section_safe(),
        my_review=render_investment_review_section_safe(),
        performance=render_performance_section(),
        ai_upgrade=render_ai_upgrade_section(),
        alerts=render_alert_center(),
        auto_on=state.get("auto_trade_enabled"),
        version_summary=render_version_summary(),
        quick_status_bar=render_quick_status_bar(),
        menu_cards=render_mobile_menu_cards(),
        kiwoom_diagnosis=render_kiwoom_diagnosis_section(),
        v168_ultimate=render_v168_ultimate_center(),
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
.version-summary{margin-top:12px;background:rgba(255,255,255,.72);border:1px solid #dbe8d5;border-radius:18px;padding:12px;color:#33523c}.version-summary details summary{margin-top:8px;padding:10px;border-radius:14px}.version-row{display:flex;gap:10px;align-items:center;margin:6px 0}.version-row b{min-width:48px;color:#2d6cdf}.version-row span{color:#4b5563}
.status-bar-v167{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0}.status-bar-v167 div{background:#fff;border:1px solid #dbe8d5;border-radius:16px;padding:10px;text-align:center}.status-bar-v167 span{display:block;color:var(--muted);font-size:12px}.status-bar-v167 b{font-size:15px;color:#183b2a}.menu-grid-v167{position:sticky;top:0;z-index:50;background:rgba(244,250,237,.94);backdrop-filter:blur(10px);display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:10px 0 12px;border-bottom:1px solid #dbe8d5}.menu-grid-v167 a{text-decoration:none;color:#285139;background:var(--pale);border:1px solid #d5e5ce;border-radius:18px;padding:10px 8px;min-height:68px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}.menu-grid-v167 b{font-size:14px}.menu-grid-v167 span{font-size:11px;color:#64748b;margin-top:4px;line-height:1.25}.menu-help-v167{background:#f4f8ff;border:1px solid #dbeafe;border-radius:16px;padding:12px;margin:10px 0;color:#334155;font-size:13px}.market-temp-v167{background:linear-gradient(90deg,#f0fff4,#fff7dc);border:1px solid #dbe8d5;border-radius:20px;padding:15px;margin:12px 0}.market-temp-v167 div{display:flex;gap:8px;align-items:center}.market-temp-v167 span{font-size:24px}.market-temp-v167 b{font-size:19px}.market-temp-v167 p{margin:8px 0;color:#385c42}.market-temp-v167 small{color:#667085}.nav{display:none}.nav a{display:none}
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
.menu-grid-v169{grid-template-columns:repeat(2,1fr)!important}.menu-grid-v169 a{min-height:72px}
@media(max-width:430px){body{font-size:15px}.form-grid{grid-template-columns:1fr}.wrap{padding:10px 10px 70px}.hero h1{font-size:28px}.card{padding:18px;border-radius:24px}.card h2{font-size:24px}.grid2 b{font-size:18px}button{font-size:15px;padding:12px 15px}.menu-grid-v167{grid-template-columns:repeat(3,1fr);gap:6px}.menu-grid-v167 a{padding:9px 4px;min-height:64px}.menu-grid-v167 b{font-size:13px}.menu-grid-v167 span{font-size:10.5px}.status-bar-v167{grid-template-columns:repeat(2,1fr)}}

.status-bar-v167{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0}.status-bar-v167 div{background:#fff;border:1px solid #dce7d6;border-radius:14px;padding:10px}.status-bar-v167 span{display:block;color:var(--muted);font-size:12px}.status-bar-v167 b{font-size:15px}.menu-grid-v167{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0 14px}.menu-grid-v167 a{text-decoration:none;color:var(--ink);background:var(--pale);border-radius:16px;padding:11px 8px;text-align:center;border:1px solid #dce7d6}.menu-grid-v167 b{display:block;font-size:14px}.menu-grid-v167 span{display:block;color:var(--muted);font-size:11px;margin-top:3px}.menu-help-v167,.market-temp-v167{background:#eef8e9;border:1px solid #d8ead4;border-radius:18px;padding:12px;margin:10px 0;color:var(--ink)}.market-temp-v167 b{font-size:18px}.market-temp-v167 p{margin:6px 0}.market-temp-v167 small{color:var(--muted)}

.v168-center{background:linear-gradient(135deg,#f7fff7,#fff9e8);border:1px solid #d7ead5;border-radius:28px;padding:20px;margin:16px 0;box-shadow:0 8px 24px rgba(32,59,45,.06)}
.v168-title{display:flex;justify-content:space-between;gap:8px;align-items:center;flex-wrap:wrap}.v168-title h2{margin:0;font-size:26px}.v168-tag{border-radius:999px;background:#e8fff0;color:#0f7a3d;padding:7px 10px;font-weight:900;font-size:12px}
.v168-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:12px 0}.v168-grid div{background:#fff;border:1px solid #e3eadf;border-radius:18px;padding:12px}.v168-grid span{display:block;color:#667085;font-size:12px}.v168-grid b{font-size:19px;color:#203b2d}
.v168-list{display:grid;gap:8px}.v168-row{background:#fff;border:1px solid #e3eadf;border-radius:16px;padding:11px;display:flex;justify-content:space-between;gap:8px;align-items:center}.v168-row small{display:block;color:#667085}.v168-warn{background:#fff4d5;border:1px solid #ffd27b;border-radius:16px;padding:12px;margin:10px 0;color:#715100;font-weight:800}
@media(max-width:430px){.v168-grid{grid-template-columns:1fr}.v168-title h2{font-size:23px}.v168-row{display:block}}

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
    {{version_summary|safe}}
  </div>
  {{quick_status_bar|safe}}
  {{menu_cards|safe}}
  {{v168_ultimate|safe}}
  {{candidates|safe}}
  {{conditions|safe}}
  {{ai_upgrade|safe}}
  <section class="card" id="analysis-center">
    <h2>📊 AI분석센터</h2>
    <p class="muted">전일 시장리포트, 내 투자평가, 전략랭킹을 한 곳에서 확인합니다.</p>
    <details open><summary>📰 시장리포트</summary>{{daily_report|safe}}</details>
    <details><summary>🧾 내투자평가</summary>{{my_review|safe}}</details>
    <details><summary>📊 전략랭킹</summary>{{performance|safe}}</details>
  </section>
  {{kiwoom_diagnosis|safe}}
  {{holdings|safe}}
  {{trade|safe}}
  <div id="alerts">{{alerts|safe}}</div>
</div>
</body></html>
"""


@app.route("/")
def index():
    ensure_watch()
    return render_page()


def safe_watch_state():
    return {
        "running": bool(WATCH_STATE.get("running")),
        "last_check": WATCH_STATE.get("last_check", ""),
        "last_message": WATCH_STATE.get("last_message", ""),
        "thread_alive": bool(WATCH_STATE.get("thread") and WATCH_STATE.get("thread").is_alive()),
    }


def _mask_account_for_display(acc):
    a = str(acc or "").strip()
    if not a:
        return ""
    digits = re.sub(r"\D", "", a)
    if len(digits) >= 8:
        return digits[:4] + "-" + digits[4:]
    return a


def _diag_badge(ok, label_ok, label_bad):
    return ("🟢 " + label_ok) if ok else ("🔴 " + label_bad)


def _classify_kiwoom_problem(message):
    return kiwoom_error_analysis(message).get("category", "unknown")


def _diag_health_score(result_or_auth):
    score = 0
    keys = []
    if isinstance(result_or_auth, dict) and "checks" in result_or_auth:
        checks = result_or_auth.get("checks", {})
        weights = {"app_key":15, "secret":15, "account":15, "token":25, "designated_device":10, "additional_auth":5, "cash":10, "holdings":5}
        for k,w in weights.items():
            ok = checks.get(k, {}).get("ok")
            if ok is True:
                score += w
            keys.append(k)
    else:
        env = result_or_auth.get("env", {}) if isinstance(result_or_auth, dict) else {}
        score += 15 if env.get("KIWOOM_APP_KEY") else 0
        score += 15 if env.get("KIWOOM_APP_SECRET") else 0
        score += 15 if env.get("KIWOOM_ACCOUNT") else 0
        score += 25 if result_or_auth.get("token_ok") else 0
    return max(0, min(100, int(score)))


def build_auth_status(check_token=False):
    env = {
        "KIWOOM_APP_KEY": bool(KIWOOM_APP_KEY),
        "KIWOOM_APP_SECRET": bool(KIWOOM_SECRET_KEY),
        "KIWOOM_ACCOUNT": bool(KIWOOM_ACCOUNT),
        "KIWOOM_ACCOUNT_DISPLAY": _mask_account_for_display(KIWOOM_ACCOUNT),
        "KIWOOM_REAL_TRADING": KIWOOM_REAL_TRADING,
        "KIWOOM_DRY_RUN": KIWOOM_DRY_RUN,
    }
    token_ok = False
    token_message = TOKEN_CACHE.get("last_error", "") or "토큰 미확인"
    token_problem = "unknown"
    if check_token:
        try:
            get_kiwoom_token()
            token_ok = True
            token_message = "키움 토큰 정상"
            token_problem = "none"
        except Exception as e:
            token_message = auth_message(str(e))
            token_problem = _classify_kiwoom_problem(token_message)
    elif TOKEN_CACHE.get("token") and time.time() < TOKEN_CACHE.get("expires", 0):
        token_ok = True
        token_message = "캐시 토큰 정상"
        token_problem = "none"
    else:
        token_problem = _classify_kiwoom_problem(token_message)

    last_debug = read_state().get("last_kiwoom_debug", {})
    last_msg = last_debug.get("message", token_message)
    problem = _classify_kiwoom_problem(last_msg or token_message)
    account_warning = "" if KIWOOM_ACCOUNT else "KIWOOM_ACCOUNT 환경변수가 없으면 계좌조회/보유조회/주문이 EMPTY 또는 실패로 나올 수 있습니다."

    # v162 PRO 상태 분리: token 상태를 기반으로 지정단말기/추가인증을 추정 표시합니다.
    designated_device_ok = None
    additional_auth_ok = None
    if token_ok:
        designated_device_ok = True
        additional_auth_ok = True
    elif problem == "designated_device":
        designated_device_ok = False
        additional_auth_ok = None
    elif problem == "additional_auth":
        designated_device_ok = None
        additional_auth_ok = False

    render_ip = get_render_public_ip()
    analysis = kiwoom_error_analysis(last_msg or token_message)
    auth_result = {
        "ok": bool(KIWOOM_APP_KEY and KIWOOM_SECRET_KEY),
        "authenticated": token_ok,
        "token_ok": token_ok,
        "token_message": token_message,
        "token_problem": token_problem,
        "token_analysis": analysis,
        "env": env,
        "account_warning": account_warning,
        "last_kiwoom_debug": last_debug,
        "designated_device_ok": designated_device_ok,
        "additional_auth_ok": additional_auth_ok,
        "render_public_ip": render_ip,
        "registered_ips_env": KIWOOM_REGISTERED_IPS,
        "ip_match_env": bool(render_ip.get("ip") and render_ip.get("ip") in KIWOOM_REGISTERED_IPS) if KIWOOM_REGISTERED_IPS else None,
        "health_score": 0,
        "version": APP_VERSION,
    }
    auth_result["health_score"] = _diag_health_score(auth_result)
    return auth_result


def run_kiwoom_full_diagnosis():
    """v163: 키움 상태를 원클릭으로 점검하고 오류코드를 자동 해석합니다. 실주문은 하지 않습니다."""
    result = {
        "version": APP_VERSION,
        "time": now_text(),
        "checks": {},
        "final_status": "UNKNOWN",
        "summary": "진단 대기",
        "action": "",
        "health_score": 0,
        "render_public_ip": get_render_public_ip(),
        "registered_ips_env": KIWOOM_REGISTERED_IPS,
        "error_analysis": {},
    }
    result["checks"]["app_key"] = {"ok": bool(KIWOOM_APP_KEY), "label": "APP KEY", "message": "입력 완료" if KIWOOM_APP_KEY else "Render 환경변수 KIWOOM_APP_KEY 누락"}
    result["checks"]["secret"] = {"ok": bool(KIWOOM_SECRET_KEY), "label": "APP SECRET", "message": "입력 완료" if KIWOOM_SECRET_KEY else "Render 환경변수 KIWOOM_APP_SECRET 누락"}
    result["checks"]["account"] = {"ok": bool(KIWOOM_ACCOUNT), "label": "ACCOUNT", "message": _mask_account_for_display(KIWOOM_ACCOUNT) if KIWOOM_ACCOUNT else "Render 환경변수 KIWOOM_ACCOUNT 누락"}

    ip = result["render_public_ip"].get("ip") if isinstance(result.get("render_public_ip"), dict) else ""
    ip_msg = f"Render 현재 IP {ip or '확인실패'}"
    if KIWOOM_REGISTERED_IPS:
        ip_msg += " / 등록IP환경변수 " + ", ".join(KIWOOM_REGISTERED_IPS)
        ip_ok = bool(ip and ip in KIWOOM_REGISTERED_IPS)
    else:
        ip_ok = None
        ip_msg += " / 키움 사이트 등록 IP는 화면에서 직접 비교하세요"
    result["checks"]["render_ip"] = {"ok": ip_ok, "label": "Render IP", "message": ip_msg}

    token_ok = False
    token_msg = ""
    try:
        get_kiwoom_token()
        token_ok = True
        token_msg = "토큰 발급 성공"
    except Exception as e:
        token_msg = auth_message(str(e))
    analysis = kiwoom_error_analysis(token_msg)
    result["error_analysis"] = analysis
    result["checks"]["token"] = {"ok": token_ok, "label": "TOKEN", "message": token_msg, "analysis": analysis}

    problem = analysis.get("category")
    if token_ok:
        result["checks"]["designated_device"] = {"ok": True, "label": "지정단말기", "message": "토큰 발급 성공 기준 정상"}
        result["checks"]["additional_auth"] = {"ok": True, "label": "추가인증", "message": "토큰 발급 성공 기준 정상"}
    elif problem == "designated_device":
        result["checks"]["designated_device"] = {"ok": False, "label": "지정단말기", "message": "8050 지정단말기/IP 인증 실패 가능성"}
        result["checks"]["additional_auth"] = {"ok": None, "label": "추가인증", "message": "토큰 실패로 확인 불가. 영웅문S# 보안/추가인증도 함께 확인"}
    elif problem == "additional_auth":
        result["checks"]["designated_device"] = {"ok": None, "label": "지정단말기", "message": "토큰 실패로 확인 불가"}
        result["checks"]["additional_auth"] = {"ok": False, "label": "추가인증", "message": "영웅문S# 추가인증/보안 설정 확인 필요"}
    else:
        result["checks"]["designated_device"] = {"ok": None, "label": "지정단말기", "message": "토큰 실패로 확인 불가"}
        result["checks"]["additional_auth"] = {"ok": None, "label": "추가인증", "message": "토큰 실패로 확인 불가"}

    cash_info = {"ok": False, "message": "토큰 또는 계좌번호 확인 후 점검"}
    holdings_info = {"ok": False, "holdings": [], "message": "토큰 또는 계좌번호 확인 후 점검"}
    if token_ok:
        try:
            cash_info = get_cash_info()
        except Exception as e:
            cash_info = {"ok": False, "message": auth_message(str(e)), "analysis": kiwoom_error_analysis(str(e))}
        try:
            holdings_info = fetch_kiwoom_holdings()
        except Exception as e:
            holdings_info = {"ok": False, "holdings": [], "message": auth_message(str(e)), "analysis": kiwoom_error_analysis(str(e))}

    result["checks"]["cash"] = {"ok": bool(cash_info.get("ok")), "label": "계좌조회/주문가능", "message": cash_info.get("message") or f"주문가능금액 {format_won(cash_info.get('cash',0))}"}
    result["checks"]["holdings"] = {"ok": bool(holdings_info.get("ok")), "label": "실보유조회", "message": holdings_info.get("message") or f"{len(holdings_info.get('holdings',[]))}종목"}

    result["health_score"] = _diag_health_score(result)
    all_required = ["app_key", "secret", "account", "token", "cash"]
    if all(result["checks"].get(k, {}).get("ok") is True for k in all_required):
        result["final_status"] = "NORMAL" if result["checks"].get("holdings", {}).get("ok") is True else "PARTIAL"
        result["summary"] = "키움 인증/계좌조회 정상" if result["final_status"] == "PARTIAL" else "키움 인증/계좌/보유조회 정상"
        result["action"] = "AI 자동매매 사용 가능. 단, 보유가 0종목이면 MTS 실제 보유 여부를 확인하세요."
    else:
        result["final_status"] = "NEED_CHECK"
        if not KIWOOM_ACCOUNT:
            result["summary"] = "계좌번호 환경변수 누락"
            result["action"] = "Render Environment에 KIWOOM_ACCOUNT를 추가하세요. 예: 66476264"
        elif not token_ok:
            result["summary"] = analysis.get("name") or "토큰 발급 실패"
            result["action"] = analysis.get("action") or "App Key/Secret, Render IP 등록, 지정단말기/추가인증 상태를 확인하세요."
        elif not cash_info.get("ok"):
            result["summary"] = "계좌조회/주문가능금액 조회 실패"
            result["action"] = "계좌번호 형식, API 권한, 키움 응답 메시지를 확인하세요."
        elif not holdings_info.get("ok"):
            result["summary"] = "실보유 조회 또는 파싱 실패"
            result["action"] = "RAW 보유응답을 확인해 파싱 구조를 보정하세요."
        else:
            result["summary"] = "일부 항목 확인 필요"
            result["action"] = "아래 상세 진단을 확인하세요."
    append_kiwoom_diag_log({"time": now_text(), "stage": "full_diagnosis", "result": {"final_status": result["final_status"], "summary": result["summary"], "health_score": result["health_score"], "error_analysis": result.get("error_analysis")}})
    return result



@app.route("/api/status")
def api_status():
    try:
        cash = get_cash_info()
    except Exception as e:
        cash = {"ok": False, "cash": 0, "source": "ERROR", "message": auth_message(str(e))}
    try:
        state = read_state()
    except Exception as e:
        state = {"last_status": "상태파일 오류", "last_message": str(e)}
    return jsonify({
        "ok": bool(cash.get("ok")),
        "version": APP_VERSION,
        "title": APP_TITLE,
        "file_name": APP_FILE_NAME,
        "patch_name": APP_PATCH_NAME,
        "cash": cash,
        "state": state,
        "watch": safe_watch_state(),
        "auth": build_auth_status(check_token=False),
    })


@app.route("/api/version")
def api_version():
    return jsonify({
        "ok": True,
        "version": APP_VERSION,
        "title": APP_TITLE,
        "file_name": APP_FILE_NAME,
        "patch_name": APP_PATCH_NAME,
        "update_history": UPDATE_HISTORY,
    })


@app.route("/api/auth_status")
def api_auth_status():
    check = str(request.args.get("check", "0")).lower() in ("1", "true", "yes")
    return jsonify(build_auth_status(check_token=check))


@app.route("/api/kiwoom_status")
def api_kiwoom_status():
    auth = build_auth_status(check_token=True)
    raw_exists = KIWOOM_RAW_HOLDINGS_FILE.exists()
    cached = get_cached_holdings()
    return jsonify({
        "ok": True,
        "version": APP_VERSION,
        "auth": auth,
        "cached_holdings_count": len(cached),
        "raw_holdings_debug_saved": raw_exists,
        "raw_holdings_debug_file": str(KIWOOM_RAW_HOLDINGS_FILE),
        "last_kiwoom_debug": read_state().get("last_kiwoom_debug", {}),
        "raw_structure_summary": kiwoom_raw_structure_summary(read_json(KIWOOM_RAW_HOLDINGS_FILE, {})),
        "guide": "token_ok가 true인데 holdings가 EMPTY이면 보유종목 파싱/계좌번호/조회구분 문제일 가능성이 큽니다. v161은 RAW 구조 요약과 후보행 개수를 함께 표시합니다.",
    })



@app.route("/api/v163_full_diagnosis")
@app.route("/api/v162_full_diagnosis")
def api_v163_full_diagnosis():
    return jsonify(run_kiwoom_full_diagnosis())


@app.route("/api/v163_token_refresh")
@app.route("/api/v162_token_refresh")
def api_v163_token_refresh():
    TOKEN_CACHE.update({"token": "", "expires": 0, "last_error": ""})
    return jsonify(build_auth_status(check_token=True))


@app.route("/api/v163_diagnosis_log")
def api_v163_diagnosis_log():
    return jsonify({"ok": True, "version": APP_VERSION, "logs": read_json(KIWOOM_DIAG_LOG_FILE, [])[:50]})


@app.route("/api/kiwoom_raw_holdings")
def api_kiwoom_raw_holdings():
    data = read_json(KIWOOM_RAW_HOLDINGS_FILE, {"ok": False, "message": "아직 저장된 키움 RAW 보유응답이 없습니다. /api/holdings 또는 실보유 새로고침을 먼저 실행하세요."})
    return jsonify(data)


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
    state["dynamic_take_profit_normal"] = pct_to_rate("dynamic_take_profit_normal", 0.027)
    state["dynamic_take_profit_strong"] = pct_to_rate("dynamic_take_profit_strong", 0.045)
    state["dynamic_take_profit_super"] = pct_to_rate("dynamic_take_profit_super", 0.070)
    state["dynamic_take_profit_limitup"] = pct_to_rate("dynamic_take_profit_limitup", 0.100)
    state["ai_peak_stage1_profit_rate"] = pct_to_rate("ai_peak_stage1_profit_rate", 0.045)
    state["ai_peak_stage2_profit_rate"] = pct_to_rate("ai_peak_stage2_profit_rate", 0.070)
    state["ai_peak_stage3_profit_rate"] = pct_to_rate("ai_peak_stage3_profit_rate", 0.100)
    state["ai_peak_trailing_stage1"] = pct_to_rate("ai_peak_trailing_stage1", 0.009)
    state["ai_peak_trailing_stage2"] = pct_to_rate("ai_peak_trailing_stage2", 0.007)
    state["ai_peak_trailing_stage3"] = pct_to_rate("ai_peak_trailing_stage3", 0.0055)
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
    state["dynamic_take_profit_enabled"] = bool(request.form.get("dynamic_take_profit_enabled"))
    state["ai_peak_sell_enabled"] = bool(request.form.get("ai_peak_sell_enabled"))
    state["ai_peak_tight_trailing_enabled"] = bool(request.form.get("ai_peak_tight_trailing_enabled"))
    state["switch_buy_enabled"] = bool(request.form.get("switch_buy_enabled"))
    write_state(state)
    set_status("매매조건 저장", "v161 매매조건 탭에서 수정한 조건을 저장했습니다. 다음 AI후보 검색과 주문 판단부터 반영됩니다.")
    return render_page()

@app.route("/api/reset_conditions")
def api_reset_conditions():
    state = read_state()
    for k in ["target_rate","stop_rate","profit_guard_rate","trailing_stop_rate","dynamic_target_enabled","dynamic_target_boost_rate","dynamic_target_min_profit_rate","ai_peak_sell_enabled","ai_peak_tight_trailing_enabled","ai_peak_stage1_profit_rate","ai_peak_stage2_profit_rate","ai_peak_stage3_profit_rate","ai_peak_trailing_stage1","ai_peak_trailing_stage2","ai_peak_trailing_stage3","candidate_scan_interval","min_ai_score","max_day_change","min_amount","min_order_cash","max_positions","rebuy_cooldown_minutes","volume_keep_filter","index_weak_buy_scale","switch_buy_enabled","profit_optimization_enabled","market_temperature_pro_enabled","candidate_evolution_enabled","trade_review_enabled","strength_alert_enabled","strength_drop_alert_threshold","dynamic_take_profit_enabled","dynamic_take_profit_normal","dynamic_take_profit_strong","dynamic_take_profit_super","dynamic_take_profit_limitup","market_temp_stop_buy_below","market_temp_reduce_buy_below","v168_ultimate_enabled","v168_watch_candidate_count","v168_focus_candidate_count","v168_pump_predict_enabled","v168_money_flow_enabled","v168_hedge_fund_center_enabled","v168_ai_assistant_enabled","v168_portfolio_manager_enabled","v168_peak_sell_predict_enabled","v168_profit_maximizer_enabled","v168_autonomous_manager_enabled","v168_auto_rotation_enabled","v168_require_user_approval"]:
        state[k] = DEFAULT_STATE[k]
    write_state(state)
    set_status("기본조건 복원", "매매조건을 v159 기본값으로 복원했습니다.")
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
    
    try:
        r = build_ai_daily_report(force=True)
        set_status("AI일일리포트 작성", r.get('summary',''))
    except Exception as e:
        set_status("AI일일리포트 오류", str(e))
    return render_page()

@app.route("/api/refresh_investment_review")
def api_refresh_investment_review():
    
    try:
        r = build_ai_investment_review(force=True)
        set_status("AI 내투자평가 작성", r.get('summary',''))
    except Exception as e:
        set_status("AI 내투자평가 오류", str(e))
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




@app.route("/api/v167_profit_optimization")
def api_v167_profit_optimization():
    picks = cached_candidates()[:8]
    temp = v167_market_temperature_data(picks)
    top3 = []
    for c in picks[:3]:
        rate, reason = v167_dynamic_target_rate_for_candidate(c)
        top3.append({
            "code": c.get("code"), "name": c.get("name"),
            "score": safe_float(c.get("riskAdjustedScore", c.get("score")),0),
            "dynamic_target_rate_pct": round(rate*100,2),
            "dynamic_target_reason": reason,
            "evolution_note": c.get("evolutionNote",""),
            "market_reverse_score": c.get("marketReverseScore",0),
            "theme": c.get("theme",""),
        })
    state = read_state()
    return jsonify({"ok": True, "version": APP_VERSION, "market_temperature": temp, "top3": top3, "settings": {
        "dynamic_take_profit_enabled": state.get("dynamic_take_profit_enabled", True),
        "candidate_evolution_enabled": state.get("candidate_evolution_enabled", True),
        "strength_alert_enabled": state.get("strength_alert_enabled", True),
    }})

@app.route("/api/v167_review_center")
def api_v167_review_center():
    reviews = read_json(REVIEW_FILE, [])
    return jsonify({"ok": True, "version": APP_VERSION, "reviews": reviews[:50], "last_summary": read_state().get("last_review_summary", "")})


@app.route("/api/v168_ultimate")
def api_v168_ultimate():
    return jsonify(v168_build_ultimate_report(force=str(request.args.get("force","0"))=="1"))


@app.route("/api/v168_refresh_ultimate")
def api_v168_refresh_ultimate():
    r = v168_build_ultimate_report(force=True)
    set_status("V168 Ultimate 재분석", f"감시 {r.get('watch_count',0)}개 / 집중 {r.get('focus_count',0)}개 / 시장온도 {r.get('market_temperature',{}).get('temperature',0)}점")
    return render_page()


@app.route("/api/v168_candidate_center")
def api_v168_candidate_center():
    r = v168_build_ultimate_report(force=str(request.args.get("force","0"))=="1")
    return jsonify({"ok": True, "version": APP_VERSION, "watch100": r.get("top3", []) + r.get("focus10", [])[3:], "focus10": r.get("focus10", []), "money_flow_top5": r.get("money_flow_top5", []), "pump_10m_top5": r.get("pump_10m_top5", [])})


@app.route("/api/v168_asset_manager")
def api_v168_asset_manager():
    r = v168_build_ultimate_report(force=str(request.args.get("force","0"))=="1")
    return jsonify({"ok": True, "version": APP_VERSION, "portfolio": r.get("portfolio", {}), "assistant": r.get("assistant", {}), "market_temperature": r.get("market_temperature", {})})


@app.route("/api/v168_autonomous_manager")
def api_v168_autonomous_manager():
    r = v168_build_ultimate_report(force=str(request.args.get("force","0"))=="1")
    return jsonify({"ok": True, "version": APP_VERSION, "autonomous_manager": r.get("autonomous_manager", {}), "safety": r.get("safety")})


@app.route("/api/v168_rotation_recommendation")
def api_v168_rotation_recommendation():
    """자동교체매수 추천만 제공합니다. 실제 교체매수는 사용자 승인과 별도 주문 안전장치가 필요합니다."""
    r = v168_build_ultimate_report(force=True)
    holdings = read_holdings()
    best = (r.get("focus10") or [{}])[0]
    holding_scores = []
    for h in holdings:
        holding_scores.append({"code": h.get("code"), "name": h.get("name"), "profitRate": h.get("profitRate"), "aiHoldMode": h.get("aiHoldMode", False)})
    return jsonify({"ok": True, "version": APP_VERSION, "recommendation": {"best_new_candidate": best, "current_holdings": holding_scores, "action": "승인대기", "message": "신규후보가 보유종목보다 강할 때 교체매수를 추천합니다. 실전 주문은 자동 실행하지 않습니다."}})


@app.route("/api/v169_asset_center")
def api_v169_asset_center():
    return jsonify(v169_build_asset_center_report(force=str(request.args.get("force","0"))=="1"))


@app.route("/api/v169_refresh_asset_center")
def api_v169_refresh_asset_center():
    r = v169_build_asset_center_report(force=True)
    set_status("V169 자산운용센터 재분석", f"집중 TOP{r.get('focus_count',0)} / 시장온도 {r.get('market_temperature',{}).get('temperature',0)}점 / {r.get('fund_manager',{}).get('mode','')}")
    return render_page()


@app.route("/api/v169_holdings_ai")
def api_v169_holdings_ai():
    return jsonify({"ok": True, "version": APP_VERSION, "holdings_ai": [v169_analyze_holding(h) for h in read_holdings()]})


@app.route("/api/v169_review2")
def api_v169_review2():
    return jsonify({"ok": True, "version": APP_VERSION, "review_2": v169_review_2_report()})

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
