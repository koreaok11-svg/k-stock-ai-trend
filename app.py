# -*- coding: utf-8 -*-
"""
성일의 AI 주식바람 - KIWOOM REAL AUTO SCALPING v130_SCROLL_FIX_CACHE_FALLBACK_REALIZED_NOTE
파일명: app_kiwoom_real_auto_scalping_v131_auto_relax_candidate_cache_fix.py

실전 운영용 경량화 버전입니다.

v131 보강:
- 후보가 없을 때 조건 자동 완화
- 금액/수량 조건 때문에 후보가 모두 사라지지 않도록 표시 후보 유지
- 마지막 정상 후보 캐시 우선 표시
- 실제 주문 직전에는 키움 현재가/주문가능금액 재확인 유지

유지 기능:
- 키움 REST 실전 자동매매
- 키움 현재가/예수금/잔고 동기화
- AI 단타 후보 선정
- 장상태 AI
- 중복매수 방지
- API 실패 시 주문금지
- 체결강도/거래대금 급증 필터
- 손실복구 모드
- 시간대별 전략
- 목표가/손절가/트레일링 감시
- 텔레그램 알림

경량화:
- 긴 설명 주석 축소
- 개발용 테스트 API 일부 제거
- 빈 줄 정리
"""

import os, re, json, time, math, threading
from pathlib import Path
from datetime import datetime, timedelta, timezone
import requests
import pandas as pd
import numpy as np
import FinanceDataReader as fdr
from flask import Flask, jsonify, request, render_template_string, Response

app = Flask(__name__)
KST = timezone(timedelta(hours=9))

BASE_DIR = Path(os.getenv("APP_DATA_DIR", "/var/data" if os.path.isdir("/var/data") else "/tmp"))
try:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    BASE_DIR = Path("/tmp")

def now_kst(): return datetime.now(KST)
def safe_float(v, default=0.0):
    try:
        if v is None: return default
        if isinstance(v, str): v=v.replace(',','').strip() or default
        f=float(v)
        return default if math.isnan(f) or math.isinf(f) else f
    except Exception: return default
def safe_int(v, default=0):
    try: return int(safe_float(v, default))
    except Exception: return default

def normalize_rate_input(v, default=0.0):
    """
    수익률 입력값을 자동 변환합니다.
    - 5    -> 0.05  (+5%)
    - -5   -> -0.05 (-5%)
    - 0.025 -> 0.025 (+2.5%)
    """
    r = safe_float(v, default)
    if abs(r) >= 1:
        r = r / 100.0
    return r

def rate_to_percent_text(v):
    r = safe_float(v, 0)
    return f"{r*100:.2f}%"

def safe_json(obj):
    if isinstance(obj, dict): return {str(k): safe_json(v) for k,v in obj.items()}
    if isinstance(obj, list): return [safe_json(v) for v in obj]
    if isinstance(obj, (np.integer,)): return int(obj)
    if isinstance(obj, (np.floating, float)): return safe_float(obj)
    return obj

THEME_MAP={
 '삼성전자':'AI반도체/HBM','SK하이닉스':'AI반도체/HBM','한미반도체':'AI반도체/HBM','하나마이크론':'AI반도체/HBM','제주반도체':'AI반도체/HBM','SFA반도체':'AI반도체/HBM',
 'HD현대일렉트릭':'전력설비/데이터센터','LS ELECTRIC':'전력설비/데이터센터','효성중공업':'전력설비/데이터센터','대한전선':'전력설비/데이터센터',
 '이수페타시스':'AI서버/PCB','대덕전자':'AI서버/PCB','심텍':'AI서버/PCB','오이솔루션':'광통신/CPO','라이트론':'광통신/CPO','쏠리드':'광통신/CPO',
 '레인보우로보틱스':'로봇/피지컬AI','두산로보틱스':'로봇/피지컬AI','휴림로봇':'로봇/피지컬AI','로보티즈':'로봇/피지컬AI','뉴로메카':'로봇/피지컬AI',
 'LG씨엔에스':'AI/클라우드/IT서비스','LG CNS':'AI/클라우드/IT서비스','삼성에스디에스':'AI/클라우드/IT서비스','삼성SDS':'AI/클라우드/IT서비스','현대오토에버':'AI/클라우드/IT서비스','포스코DX':'AI/클라우드/IT서비스',
 'NAVER':'인터넷/플랫폼','카카오':'인터넷/플랫폼','안랩':'보안/소프트웨어','더존비즈온':'보안/소프트웨어','루닛':'의료AI/디지털헬스','뷰노':'의료AI/디지털헬스',
 '폴레드':'육아/키즈','아가방컴퍼니':'육아/키즈','제로투세븐':'육아/키즈','F&F':'패션/의류','휠라홀딩스':'패션/의류','BGF리테일':'유통/플랫폼','GS리테일':'유통/플랫폼'}
AUTO_THEME_KEYWORDS={'AI반도체/HBM':['반도체','하이닉스','HBM','마이크론','리노','ISC'],'전력설비/데이터센터':['전력','전기','일렉트릭','변압기','전선','중공업','LS'],'AI서버/PCB':['PCB','기판','써키트','페타시스','대덕','심텍'],'광통신/CPO':['광','통신','네트웍스','라이트론','오이솔루션','쏠리드'],'로봇/피지컬AI':['로봇','로보','휴림','뉴로메카','레인보우'],'AI/클라우드/IT서비스':['CNS','씨엔에스','SDS','오토에버','DX','클라우드','IT서비스','AX'],'보안/소프트웨어':['보안','소프트웨어','시큐어','안랩','더존'],'인터넷/플랫폼':['NAVER','네이버','카카오','플랫폼'],'유통/플랫폼':['리테일','쇼핑','백화점','마트','편의점','유통'],'패션/의류':['패션','의류','브랜드','휠라'],'육아/키즈':['육아','유아','키즈','아가방','제로투세븐','폴레드'],'바이오/제약':['바이오','제약','셀트리온','HLB'],'방산/우주항공':['방산','우주','항공','한화에어로','현대로템','LIG']}
WEIGHT={'AI반도체/HBM':1.35,'전력설비/데이터센터':1.30,'광통신/CPO':1.22,'AI서버/PCB':1.18,'로봇/피지컬AI':1.12,'AI/클라우드/IT서비스':1.10,'의료AI/디지털헬스':1.08,'보안/소프트웨어':1.06,'인터넷/플랫폼':1.04,'유통/플랫폼':1.02,'패션/의류':1.02,'육아/키즈':1.02,'기타/개별이슈':0.96}
STOCK_CODE_FALLBACK={'휴림로봇':'090710','제주반도체':'080220','SFA반도체':'036540','하나마이크론':'067310','두산로보틱스':'454910','SK하이닉스':'000660','삼성전자':'005930'}

def classify_theme(name):
    name=str(name)
    if name in THEME_MAP: return THEME_MAP[name]
    for theme,kws in AUTO_THEME_KEYWORDS.items():
        if any(kw in name for kw in kws): return theme
    return '기타/개별이슈'
def normalize_theme(t): return t if t and t!='미분류' else '기타/개별이슈'
_MARKET_CACHE={'time':0,'df':None}
def get_market_df(limit=700, cache_sec=60):
    now=time.time()
    if _MARKET_CACHE['df'] is not None and now-_MARKET_CACHE['time']<cache_sec:
        df=_MARKET_CACHE['df'].copy()
    else:
        df=fdr.StockListing('KRX')
        df=df[df['Market'].isin(['KOSPI','KOSDAQ'])].copy()
        df['Code']=df['Code'].astype(str).str.zfill(6); df['Name']=df['Name'].astype(str); df['Market']=df['Market'].astype(str)
        _MARKET_CACHE.update({'time':now,'df':df.copy()})
    return df.head(int(limit)).copy() if limit else df

def get_live_price(code):
    code=str(code).zfill(6)
    if code=='000000' or not code.isdigit(): return 0
    headers={'User-Agent':'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)','Accept':'application/json,text/html,*/*','Referer':'https://m.stock.naver.com/'}
    for url in [f'https://m.stock.naver.com/api/stock/{code}/basic', f'https://api.stock.naver.com/stock/{code}/basic']:
        try:
            r=requests.get(url,headers=headers,timeout=3)
            if r.status_code==200 and r.text:
                data=r.json()
                for key in ['closePrice','now','lastPrice','currentPrice']:
                    if key in data:
                        p=safe_float(str(data[key]).replace(',',''))
                        if p>=10: return p
        except Exception: pass
    try:
        r=requests.get(f'https://finance.naver.com/item/main.naver?code={code}',headers={'User-Agent':'Mozilla/5.0'},timeout=3)
        m=re.search(r'<p class="no_today">[\s\S]*?<span class="blind">([\d,]+)</span>',r.text)
        if m:
            p=safe_float(m.group(1).replace(',',''))
            if p>=10: return p
    except Exception: pass
    return 0

def resolve_code_by_name(name):
    name=str(name or '').strip()
    if not name: return ''
    if name in STOCK_CODE_FALLBACK: return STOCK_CODE_FALLBACK[name]
    try:
        df=get_market_df(limit=3000)
        exact=df[df['Name']==name]
        if not exact.empty: return str(exact.iloc[0]['Code']).zfill(6)
        contains=df[df['Name'].str.contains(name,case=False,na=False)]
        if not contains.empty: return str(contains.iloc[0]['Code']).zfill(6)
    except Exception: pass
    return ''
def normalize_holding(h):
    code=str(h.get('code','') or '').strip().zfill(6)
    if not code or code=='000000' or not code.isdigit(): code=resolve_code_by_name(h.get('name','')) or code
    h['code']=code
    return h

def ai_comment(cur,buy,target,stop,qty=0):
    cur,buy,target,stop,qty=map(safe_float,[cur,buy,target,stop,qty])
    if cur<=0 or buy<=0: return 'AI 판단: 현재가 확인이 불안정합니다. HTS/MTS 현재가를 먼저 확인하세요.'
    rate=(cur-buy)/buy*100; pnl=(cur-buy)*qty
    if stop and cur<=stop: return f'AI 판단: 손절가를 이탈했습니다. 현재 수익률 {rate:.2f}%, 평가손익 {pnl:,.0f}원입니다. 단타 기준에서는 리스크 축소가 우선입니다.'
    if target and cur>=target: return f'AI 판단: 목표가에 도달했습니다. 현재 수익률 {rate:.2f}%, 평가손익 {pnl:,.0f}원입니다. 전량 또는 부분익절 검토 구간입니다.'
    if rate>=2: return f'AI 판단: 수익권입니다. 목표가까지 약 {((target-cur)/cur*100 if target else 0):.2f}% 남았습니다. 거래량 유지 여부를 확인하세요.'
    if rate<=-1.5: return f'AI 판단: 손실권입니다. 손절가까지 약 {((cur-stop)/cur*100 if stop else 0):.2f}% 여유가 있습니다. 원칙 대응이 필요합니다.'
    return f'AI 판단: 관찰 구간입니다. 현재 수익률 {rate:.2f}%이며 목표가/손절가 사이에서 움직이고 있습니다.'

def send_telegram_message(text):
    token=os.getenv('TELEGRAM_BOT_TOKEN','').strip(); chat_id=os.getenv('TELEGRAM_CHAT_ID','').strip()
    if not token or not chat_id: return False,'TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.'
    try:
        r=requests.post(f'https://api.telegram.org/bot{token}/sendMessage',json={'chat_id':chat_id,'text':text,'parse_mode':'HTML','disable_web_page_preview':True},timeout=8)
        return (True,'sent') if r.status_code==200 else (False,r.text[:500])
    except Exception as e: return False,str(e)

HOLDINGS_FILE=os.getenv('SERVER_HOLDINGS_FILE','/tmp/sungil_holdings_v109.json')
WATCH_STATE={'running':False,'thread':None,'last_alerts':{},'last_check':'','last_prices':{},'best_code':'','best_score':0}
WATCH_LOCK=threading.Lock(); WATCH_INTERVAL=int(os.getenv('SERVER_WATCH_INTERVAL','20')); BEST_PICK_GAP=float(os.getenv('BEST_PICK_MIN_SCORE_GAP','3.0'))
def read_holdings():
    try:
        if os.path.exists(HOLDINGS_FILE):
            with open(HOLDINGS_FILE,'r',encoding='utf-8') as f: data=json.load(f); return data if isinstance(data,list) else []
    except Exception: pass
    return []
def write_holdings(items):
    try:
        with open(HOLDINGS_FILE,'w',encoding='utf-8') as f: json.dump(items or [],f,ensure_ascii=False,indent=2)
        return True
    except Exception: return False

def send_holding_alert(kind,h,cur):
    h=normalize_holding(h); code=h.get('code','')
    if not code or code=='000000' or cur<10: return False
    key=f"{kind}_{code}_{now_kst().strftime('%Y-%m-%d')}"
    if WATCH_STATE['last_alerts'].get(key): return False
    name=h.get('name',code); buy=safe_float(h.get('buyPrice',0)); qty=safe_float(h.get('qty',0)); target=safe_float(h.get('target',0)); stop=safe_float(h.get('stop',0)); pnl=(cur-buy)*qty if buy and qty else 0; rate=((cur-buy)/buy*100) if buy else 0
    title='🎯 <b>보유종목 목표가 도달</b>' if kind=='target' else '⚠️ <b>보유종목 손절가 이탈</b>'
    msg=f"{title}\n종목: <b>{name}</b> ({code})\n매수가: {buy:,.0f}원\n현재가: {cur:,.0f}원\n목표가: {target:,.0f}원\n손절가: {stop:,.0f}원\n수량: {qty:,.0f}주\n평가손익: {pnl:,.0f}원 ({rate:.2f}%)\n\n{ai_comment(cur,buy,target,stop,qty)}\n\n※ 자동매매가 아닙니다. 실제 주문 전 HTS/MTS 현재가·호가·거래대금을 최종 확인하세요."
    WATCH_STATE['last_alerts'][key]=True
    ok,_=send_telegram_message(msg); return ok

_LAST_RENDER_IP_INFO = {
    "ip": "",
    "checked_at": "",
    "ok": False,
    "message": "not checked"
}

def get_render_public_ip(force=False):
    """
    Render 서버가 외부로 API 호출할 때 사용하는 공인 IP를 확인합니다.
    이 IP를 키움 REST API 사이트의 허용/지정 IP에 등록해야
    키움 토큰/현재가/예수금/주문 API가 정상 동작합니다.
    """
    global _LAST_RENDER_IP_INFO

    try:
        if not force and _LAST_RENDER_IP_INFO.get("ok") and _LAST_RENDER_IP_INFO.get("ip"):
            return _LAST_RENDER_IP_INFO

        ip = ""
        source = ""

        # 1순위: ipify
        try:
            r = requests.get("https://api.ipify.org", timeout=7)
            if r.status_code == 200 and r.text.strip():
                ip = r.text.strip()
                source = "api.ipify.org"
        except Exception:
            pass

        # 2순위: ifconfig.me
        if not ip:
            try:
                r = requests.get("https://ifconfig.me/ip", timeout=7)
                if r.status_code == 200 and r.text.strip():
                    ip = r.text.strip()
                    source = "ifconfig.me"
            except Exception:
                pass

        if ip:
            _LAST_RENDER_IP_INFO = {
                "ok": True,
                "ip": ip,
                "source": source,
                "checked_at": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
                "message": "이 IP를 키움 REST API 사이트의 서버/허용/지정 IP에 등록하세요."
            }
            return _LAST_RENDER_IP_INFO

        _LAST_RENDER_IP_INFO = {
            "ok": False,
            "ip": "",
            "source": "NONE",
            "checked_at": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
            "message": "공인 IP 확인 실패"
        }
        return _LAST_RENDER_IP_INFO

    except Exception as e:
        _LAST_RENDER_IP_INFO = {
            "ok": False,
            "ip": "",
            "source": "ERROR",
            "checked_at": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
            "message": str(e)
        }
        return _LAST_RENDER_IP_INFO

def print_render_public_ip_on_startup():
    """
    Render Logs에 공인 IP를 출력합니다.
    Logs에서 아래 문구를 찾아 복사하면 됩니다.
    RENDER_PUBLIC_IP = xxx.xxx.xxx.xxx
    """
    try:
        info = get_render_public_ip(force=True)
        if info.get("ok"):
            print("=" * 70, flush=True)
            print("RENDER_PUBLIC_IP =", info.get("ip"), flush=True)
            print("KIWOOM REST 지정/허용 IP에 위 IP를 등록하세요.", flush=True)
            print("IP_CHECK_SOURCE =", info.get("source"), flush=True)
            print("IP_CHECK_TIME =", info.get("checked_at"), flush=True)
            print("=" * 70, flush=True)
        else:
            print("=" * 70, flush=True)
            print("RENDER_PUBLIC_IP_CHECK_FAILED =", info.get("message"), flush=True)
            print("=" * 70, flush=True)
    except Exception as e:
        print("RENDER_PUBLIC_IP_CHECK_EXCEPTION =", e, flush=True)

try:
    @app.route("/api/render_ip")
    def api_render_ip():
        force = str(request.args.get("force", "0")).lower() in ["1", "true", "yes"]
        return jsonify(get_render_public_ip(force=force))
except Exception:
    pass

def v109_clamp(v, lo=0, hi=100):
    try:
        return max(lo, min(hi, safe_float(v, 0)))
    except Exception:
        return lo

def v109_get_orderbook_metrics(code):
    """
    호가잔량/매수압력 조회.
    실제 키움 호가 API 필드명이 계정/문서 버전에 따라 다를 수 있어 여러 키를 방어적으로 탐색합니다.
    실패 시 0을 반환하고, 후보 점수는 기존 거래대금/거래량 기반 추정치로 보정됩니다.
    """
    code = str(code).zfill(6)
    result = {"bid_total": 0, "ask_total": 0, "bid_ask_ratio": 0, "orderbook_source": "NONE"}
    try:
        if not kiwoom_ready():
            return result
        token = kiwoom_get_token()
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": "Bearer " + token,
            "cont-yn": "N",
            "next-key": "",
            "api-id": "ka10004"
        }
        body = {"stk_cd": code}
        r = requests.post(KIWOOM_BASE_URL + "/api/dostk/stkinfo", json=body, headers=headers, timeout=5)
        try:
            data = r.json() if r.text else {}
        except Exception:
            data = {"raw": r.text[:1000]}

        bid_keys = ["tot_bid_req", "tot_bid_qty", "bid_total", "매수호가총잔량", "buy_total_qty"]
        ask_keys = ["tot_ask_req", "tot_ask_qty", "ask_total", "매도호가총잔량", "sell_total_qty"]

        def deep_find_number(obj, keys):
            if isinstance(obj, dict):
                for k in keys:
                    if k in obj:
                        n = abs(safe_float(str(obj.get(k, "")).replace(",", "").replace("+", "").replace("-", ""), 0))
                        if n > 0:
                            return n
                for v in obj.values():
                    n = deep_find_number(v, keys)
                    if n > 0:
                        return n
            elif isinstance(obj, list):
                for item in obj:
                    n = deep_find_number(item, keys)
                    if n > 0:
                        return n
            return 0

        bid = deep_find_number(data, bid_keys)
        ask = deep_find_number(data, ask_keys)
        ratio = round(bid / ask, 3) if ask > 0 else 0
        if bid > 0 or ask > 0:
            result.update({"bid_total": bid, "ask_total": ask, "bid_ask_ratio": ratio, "orderbook_source": "KIWOOM"})
        return result
    except Exception as e:
        try:
            update_kiwoom_debug("orderbook_exception", code, 0, str(e))
        except Exception:
            pass
        return result

def v109_estimate_execution_strength(row):
    """
    체결강도 실제 API가 없을 때 쓰는 추정값.
    거래량순위/거래대금순위/당일등락률이 높을수록 강한 체결로 추정합니다.
    """
    amount_rank = safe_float(row.get("amountRank", 0))
    volume_rank = safe_float(row.get("volumeRank", 0))
    day_change = safe_float(row.get("dayChange", 0))
    base = 80 + amount_rank * 0.35 + volume_rank * 0.35 + max(0, day_change) * 3.0
    return round(v109_clamp(base, 50, 200), 2)

def v109_calculate_scalping_score(row, price, orderbook=None):
    """
    v109 최종 스캘핑 점수.
    - 기존 후보 점수
    - 거래량 급증
    - 거래대금
    - 등락률 스윗스팟
    - 체결강도 추정/실제값
    - 호가잔량 매수우위
    - 테마가중치
    를 통합하여 100점 만점으로 환산합니다.
    """
    orderbook = orderbook or {}
    base_score = safe_float(row.get("score", 0))
    amount_rank = safe_float(row.get("amountRank", 0))
    volume_rank = safe_float(row.get("volumeRank", 0))
    day_change = safe_float(row.get("dayChange", 0))
    theme = normalize_theme(row.get("theme", "기타/개별이슈"))
    theme_weight = WEIGHT.get(theme, 1.0)

    # 등락률: 너무 낮으면 힘 부족, 너무 높으면 추격 위험
    if 1.0 <= day_change <= 4.5:
        change_score = 92
    elif 4.5 < day_change <= 7.5:
        change_score = 82
    elif 7.5 < day_change <= 12:
        change_score = 68
    elif 0.2 <= day_change < 1.0:
        change_score = 55
    else:
        change_score = 40

    # 거래량/거래대금 급증 점수
    volume_spike_score = v109_clamp(volume_rank * 0.6 + amount_rank * 0.4, 0, 100)

    # 체결강도
    execution_strength = v109_estimate_execution_strength(row)
    if execution_strength >= 150:
        execution_score = 100
    elif execution_strength >= 130:
        execution_score = 85
    elif execution_strength >= 110:
        execution_score = 70
    else:
        execution_score = 50

    # 호가잔량 매수압력
    bid_ask_ratio = safe_float(orderbook.get("bid_ask_ratio", 0))
    if bid_ask_ratio >= 1.8:
        orderbook_score = 100
    elif bid_ask_ratio >= 1.4:
        orderbook_score = 85
    elif bid_ask_ratio >= 1.1:
        orderbook_score = 70
    elif bid_ask_ratio > 0:
        orderbook_score = 45
    else:
        # 실제 호가 API가 없으면 거래량/거래대금 기반으로 보수 추정
        orderbook_score = v109_clamp((volume_rank + amount_rank) / 2 * 0.75, 20, 75)

    raw = (
        base_score * 0.30 +
        volume_spike_score * 0.22 +
        execution_score * 0.18 +
        orderbook_score * 0.15 +
        change_score * 0.15
    ) * min(theme_weight, 1.25)

    final_score = round(v109_clamp(raw, 0, 100), 2)

    reasons = []
    if volume_spike_score >= 80: reasons.append("거래량/거래대금 급증")
    if execution_strength >= 130: reasons.append("체결강도 강함")
    if bid_ask_ratio >= 1.3: reasons.append("호가 매수잔량 우위")
    if 1.0 <= day_change <= 7.5: reasons.append("단타 진입 적정 등락률")
    if theme_weight >= 1.18: reasons.append("강한 시장 테마")
    if day_change > 12: reasons.append("급등 과열 주의")
    if not reasons: reasons.append("관찰 필요")

    if final_score >= 88:
        status = "최우선 자동진입 후보"
    elif final_score >= 80:
        status = "자동매수 후보"
    elif final_score >= 70:
        status = "관심감시"
    else:
        status = "대기"

    return {
        "aiScoreV109": final_score,
        "legacyScore": round(base_score, 2),
        "volumeSpikeScore": round(volume_spike_score, 2),
        "executionStrength": execution_strength,
        "executionScore": round(execution_score, 2),
        "bidAskRatio": round(bid_ask_ratio, 3),
        "bidTotal": safe_float(orderbook.get("bid_total", 0)),
        "askTotal": safe_float(orderbook.get("ask_total", 0)),
        "orderbookSource": orderbook.get("orderbook_source", "ESTIMATE"),
        "orderbookScore": round(orderbook_score, 2),
        "scalpingStatus": status,
        "scalpingReasons": reasons,
        "orderPriority": final_score
    }

def score_candidates(limit=700,cash=500000,min_qty=5,max_change=7,min_amount=1000000000,min_score=70):
    df=get_market_df(limit=limit)
    if df is None or df.empty: return []
    df=df.copy(); cc='ChagesRatio' if 'ChagesRatio' in df.columns else ('Change' if 'Change' in df.columns else None)
    for col in ['Close','Volume','Amount','Marcap']: df[col]=pd.to_numeric(df.get(col,0),errors='coerce').fillna(0)
    df['dayChange']=pd.to_numeric(df[cc],errors='coerce').fillna(0) if cc else 0
    df['Name']=df['Name'].astype(str); df['Code']=df['Code'].astype(str).str.zfill(6)
    exclude=['스팩','SPAC','ETF','ETN','인버스','레버리지','KODEX','TIGER','KBSTAR','ARIRANG','HANARO']
    df=df[~df['Name'].str.upper().apply(lambda n:any(x.upper() in n for x in exclude) or n.endswith('우'))].copy()
    df=df[(df['Close']>=10)&(df['Amount']>=min_amount)&(df['dayChange']>=0.2)&(df['dayChange']<=max_change)].copy()
    if df.empty: return []
    df['theme']=df['Name'].apply(classify_theme).apply(normalize_theme); df['amountRank']=df['Amount'].rank(pct=True)*100; df['volumeRank']=df['Volume'].rank(pct=True)*100; df['marcapRank']=df['Marcap'].rank(pct=True)*100; df['sweetSpot']=(100-(df['dayChange']-3.5).abs()*8).clip(lower=20,upper=100); df['themeWeight']=df['theme'].apply(lambda x:WEIGHT.get(x,1.0)); df['score']=(df['amountRank']*.34+df['volumeRank']*.25+df['marcapRank']*.15+df['sweetSpot']*.26)*df['themeWeight']
    df=df[df['score']>=min_score].sort_values('score',ascending=False)
    # v127 FAST UI: 필터/다음 후보 조회는 기본적으로 KRX 캐시 데이터로 빠르게 표시합니다.
    # 키움 현재가/호가는 주문 직전과 상태 확인에서 별도 검증하여 속도와 안전성을 분리합니다.
    fast_mode = False
    try:
        fast_mode = str(request.args.get('fast','0')).lower() in ['1','true','yes','fast']
    except Exception:
        fast_mode = False
    out=[]
    head_n = 8 if fast_mode else 20
    for _,row in df.head(head_n).iterrows():
        p=safe_float(row['Close']); qty=int(cash//p) if p else 0
        if qty<min_qty: continue
        code = str(row['Code']).zfill(6)
        src = 'KRX_FAST' if fast_mode else 'KRX'
        if not fast_mode:
            live_p, src = get_trade_live_price(code, fallback=True)
            if live_p >= 10:
                p = live_p
                qty = int(cash // p) if p else 0
            if qty < min_qty:
                continue
            orderbook = v109_get_orderbook_metrics(code)
        else:
            orderbook = {}
        v109_ai = v109_calculate_scalping_score(row, p, orderbook)
        base_pick = {'code':code,'name':str(row['Name']),'market':str(row.get('Market','')),'theme':normalize_theme(row['theme']),'price':round(p),'priceSource':src,'score':v109_ai['aiScoreV109'],'dayChange':round(safe_float(row['dayChange']),2),'amount':round(safe_float(row['Amount'])),'qtyPossible':qty,'buyZone':round(p*.995),'target':round(p*1.035),'stop':round(p*.975),'comment':f"v109 스캘핑 AI: {v109_ai['scalpingStatus']} · {', '.join(v109_ai['scalpingReasons'])}. 현재가는 {src} 기준입니다. KRX_FAST는 빠른 화면조회용이며 실제 주문 전 키움 현재가로 재검증합니다."}
        base_pick.update(v109_ai)
        out.append(base_pick)
    return out

def best_pick_from_params(args=None):
    args=args or {}; cash=safe_float(args.get('cash',500000),500000); min_qty=safe_int(args.get('minQty',5),5); max_change=safe_float(args.get('maxChange',7),7); min_amount=safe_float(args.get('minAmount',1000000000),1000000000); min_score=safe_float(args.get('minScore',70),70)
    picks=score_candidates(cash=cash,min_qty=min_qty,max_change=max_change,min_amount=min_amount,min_score=min_score)
    ranges=[]
    for part in str(args.get('priceRanges','')).split(','):
        try:
            a,b=part.split('-'); ranges.append((safe_float(a),safe_float(b)))
        except Exception: pass
    if ranges: picks=[p for p in picks if any(lo<=p['price']<=hi for lo,hi in ranges)]
    picks=sorted(picks, key=lambda x: safe_float(x.get('orderPriority', x.get('aiScoreV109', x.get('score', 0)))), reverse=True)
    return (picks[0] if picks else None), picks

def send_better_pick_alert(pick,old_score=0):
    if not pick: return False
    msg=f"🚨 <b>더 좋은 단타 후보 발견</b>\n종목: <b>{pick['name']}</b> ({pick['code']})\n테마: {pick['theme']}\n현재가: {pick['price']:,.0f}원\nAI 점수: {pick['score']:.2f}\n당일 흐름: {pick['dayChange']:.2f}%\n거래대금: {pick['amount']/100000000:,.1f}억원\n매수관찰가: {pick['buyZone']:,.0f}원\n목표가: {pick['target']:,.0f}원\n손절가: {pick['stop']:,.0f}원\n\nAI 코멘트: 기존 후보보다 점수가 {pick['score']-old_score:.2f}점 높습니다. 바로 추격매수보다 호가·거래량 유지 여부를 확인하세요.\n\n※ 자동매매가 아닙니다. 실제 주문 전 HTS/MTS 현재가·호가·거래대금을 최종 확인하세요."
    ok,_=send_telegram_message(msg); return ok

def check_better_pick():
    pick,_=best_pick_from_params({})
    if not pick: return
    old_code=WATCH_STATE.get('best_code',''); old_score=safe_float(WATCH_STATE.get('best_score',0))
    if old_code and pick['code']!=old_code and pick['score']>=old_score+BEST_PICK_GAP: send_better_pick_alert(pick,old_score)
    WATCH_STATE['best_code']=pick['code']; WATCH_STATE['best_score']=pick['score']

def check_one_holding(h):
    h=normalize_holding(h); code=h.get('code','')
    if not code or code=='000000': h['priceError']='종목코드를 확인해 주세요.'; return h
    cur, price_src = get_trade_live_price(code, fallback=True)
    if cur<10: h['priceError']='현재가 자동조회 실패. 다음 주기에 재시도합니다.'; return h
    h['lastPrice']=cur; h['priceSource']=price_src; h['lastCheckedAt']=now_kst().strftime('%Y-%m-%d %H:%M:%S'); h.pop('priceError',None); WATCH_STATE['last_prices'][code]=cur
    target=safe_float(h.get('target',0)); stop=safe_float(h.get('stop',0))
    if target and cur>=target: auto_sell_holding('target',h,cur)
    if stop and cur<=stop: auto_sell_holding('stop',h,cur)
    return h

def watch_loop():
    last_best=0
    while WATCH_STATE.get('running'):
        try:
            holdings=[check_one_holding(h) for h in read_holdings()]; write_holdings(holdings); WATCH_STATE['last_check']=now_kst().strftime('%Y-%m-%d %H:%M:%S')
            if time.time()-last_best>60:
                check_better_pick()
                if AUTO_BUY_IN_WATCH_LOOP:
                    auto_buy_best_pick()
                last_best=time.time()
        except Exception as e: print('watch loop error:',e)
        time.sleep(WATCH_INTERVAL)
def ensure_watch_running():
    with WATCH_LOCK:
        WATCH_STATE['running']=True; t=WATCH_STATE.get('thread')
        if t is None or not t.is_alive():
            t=threading.Thread(target=watch_loop,daemon=True); WATCH_STATE['thread']=t; t.start()
    return True

TRADE_STATE_FILE = os.getenv("TRADE_STATE_FILE", "/tmp/sungil_trade_state_v109.json")
KIWOOM_BASE_URL = os.getenv("KIWOOM_BASE_URL", "https://api.kiwoom.com").rstrip("/")
KIWOOM_APP_KEY = os.getenv("KIWOOM_APP_KEY", "").strip()
KIWOOM_SECRET_KEY = (os.getenv("KIWOOM_SECRET_KEY", "") or os.getenv("KIWOOM_APP_SECRET", "") or os.getenv("KIWOOM_SECRET", "")).strip()
KIWOOM_REAL_TRADING = os.getenv("KIWOOM_REAL_TRADING", "false").lower() == "true"
KIWOOM_DRY_RUN = os.getenv("KIWOOM_DRY_RUN", "true").lower() == "true"
AUTO_BUY_IN_WATCH_LOOP = os.getenv("AUTO_BUY_IN_WATCH_LOOP", "false").lower() == "true"
AUTO_REBUY_AFTER_SELL = os.getenv("AUTO_REBUY_AFTER_SELL", "true").lower() == "true"
ORDER_CASH_SAFETY_RATE = safe_float(os.getenv("ORDER_CASH_SAFETY_RATE", "0.96"), 0.96)

PRICE_DIFF_LIMIT = safe_float(os.getenv("PRICE_DIFF_LIMIT", "0.01"), 0.01)
KIWOOM_PRICE_REQUIRED = os.getenv("KIWOOM_PRICE_REQUIRED", "true").lower() == "true"

TRADE_DEFAULTS = {
    "auto_trade_enabled": False,
    # v109 cash multi fix: 화면 입력 총투자금이 아니라 키움 예수금/주문가능금액을 우선 사용합니다.
    "max_total_cash": 500000,
    "max_order_cash": 450000,
    "cash_buffer": 50000,
    "max_positions": 3,
    "min_order_cash": 50000,
    "daily_max_loss": -30000,
    "target_rate": 0.027,
    "stop_rate": -0.018,
    "cooldown_minutes": 30,
    "same_stock_cooldown": {},
    "daily_realized_pnl": 0,
    "trade_log": [],
    "last_buy_code": "",
    "last_buy_time": "",
    "panic_stop": False,
    "last_status": "대기중",
    "last_status_time": "",
    "last_order_message": "",
    "last_candidate": None,
    "last_telegram_status": "",
    "last_kiwoom_debug": {},
    "latest_ui_pick": None,
    "latest_ui_args": {},
    "scalp_mode": True,
    "max_trades_per_day": 10,
    "profit_guard_rate": 0.012,
    "trailing_stop_rate": 0.011,
    "force_exit_time": "15:15",
    "trade_count_today": 0,
    "last_trade_date": ""
}
_TOKEN_CACHE = {"token": "", "expires": 0}

def kiwoom_auth_help_message(msg):
    """
    키움 인증 실패 메시지를 사용자가 조치하기 쉬운 문장으로 변환합니다.
    """
    s = str(msg or "")
    if "8050" in s or "지정단말기" in s or "인증에 실패" in s:
        return (
            "키움 인증 실패입니다. 조치 필요: "
            "1) 키움 REST API 사이트에서 Render 서버 IP가 등록되어 있는지 확인, "
            "2) 계좌 App Key/App Secret을 새로 다운로드해 Render 환경변수에 정확히 입력, "
            "3) 영웅문S# 인증/보안에서 단말기 지정 또는 추가인증 상태 확인, "
            "4) 저장 후 Render 재배포가 필요합니다."
        )
    if "8001" in s or "8002" in s or "App Key" in s or "Secret" in s:
        return "App Key 또는 Secret Key 검증 실패입니다. Render 환경변수 KIWOOM_APP_KEY / KIWOOM_SECRET_KEY 또는 KIWOOM_APP_SECRET 값을 다시 확인하세요."
    return s

def update_kiwoom_debug(stage, code="", status=0, message="", data=None):
    """
    키움 API 실패 원인을 앱 상태창에서 확인하기 위한 디버그 기록.
    민감정보는 저장하지 않습니다.
    """
    try:
        state = read_trade_state()
        safe_data = data
        if isinstance(safe_data, dict):
            safe_data = {str(k): safe_json(v) for k, v in list(safe_data.items())[:30]}
            for secret_key in ["token", "authorization", "appkey", "secretkey"]:
                safe_data.pop(secret_key, None)
        state["last_kiwoom_debug"] = {
            "time": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
            "stage": str(stage),
            "code": str(code),
            "http_status": status,
            "message": kiwoom_auth_help_message(message)[:700],
            "data": safe_data
        }
        write_trade_state(state)
    except Exception as e:
        print("update_kiwoom_debug error:", e)

def update_trade_status(status, message="", candidate=None, order=None, telegram=None):
    """
    실전 자동매매 진행상태를 저장합니다.
    앱 화면에서 AI 대기중/탐색중/주문중/보류/성공/실패를 확인할 수 있습니다.
    """
    try:
        state = read_trade_state()
        state["last_status"] = str(status or "대기중")
        state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        state["last_order_message"] = str(message or "")[:500]
        if candidate is not None:
            state["last_candidate"] = candidate
        if order is not None:
            state["last_order_status"] = order
        if telegram is not None:
            state["last_telegram_status"] = telegram
        write_trade_state(state)
        return state
    except Exception as e:
        print("update trade status error:", e)
        return None

def send_trade_telegram(text, status_label=""):
    """
    텔레그램 발송 결과를 상태창에도 기록합니다.
    """
    ok, msg = send_telegram_message(text)
    update_trade_status(
        "텔레그램 발송 완료" if ok else "텔레그램 발송 실패",
        msg,
        telegram={"ok": ok, "message": msg, "status": status_label}
    )
    return ok, msg

def read_trade_state():
    try:
        if os.path.exists(TRADE_STATE_FILE):
            with open(TRADE_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                state = dict(TRADE_DEFAULTS)
                if isinstance(data, dict):
                    state.update(data)
                return state
    except Exception:
        pass
    return dict(TRADE_DEFAULTS)

def write_trade_state(state):
    try:
        with open(TRADE_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def extract_available_qty(obj):
    """
    키움 주문 실패 메시지에서 '13주 매수가능' 같은 문구를 찾아 수량을 추출합니다.
    """
    text = str(obj or "")
    m = re.search(r"(\d+)\s*주\s*매수가능", text)
    if m:
        return int(m.group(1))
    m = re.search(r"매수가능[^0-9]*(\d+)\s*주", text)
    if m:
        return int(m.group(1))
    return 0

def calc_safe_order_qty(max_order_cash, live_price):
    """
    실전 주문 수량 계산.
    현재가 급변/수수료/증거금 여유를 위해 기본 96%만 사용합니다.
    """
    cash = safe_float(max_order_cash, 0) * ORDER_CASH_SAFETY_RATE
    price = safe_float(live_price, 0)
    if cash <= 0 or price <= 0:
        return 0
    return int(cash // price)

def recommend_auto_trade_settings(total_cash):
    """
    총 투자금 기준으로 단타 실전용 추천 설정을 자동 계산합니다.
    - 목표: 무리한 전액 진입 방지
    - 1종목 집중, 짧은 익절/손절, 하루 손실 제한
    """
    cash = safe_float(total_cash, 0)
    if cash <= 0:
        cash = 100000

    # 현금 여유 15%, 1회 진입 최대 85%
    max_order = math.floor(cash * 0.85)
    buffer_cash = max(0, math.floor(cash - max_order))

    # 하루 최대 손실: 총 투자금의 약 -3%, 최소 -3천원, 최대 -3만원
    daily_loss = -int(min(30000, max(3000, cash * 0.03)))

    # 투자금 규모별 추천
    if cash <= 100000:
        target_pct = 2.5
        stop_pct = -1.8
        cooldown = 30
        mode = "소액 안정형"
        note = "10만원 이하 소액 테스트 구간입니다. 1주 체결과 알림 안정성 확인을 우선합니다."
    elif cash <= 300000:
        target_pct = 2.5
        stop_pct = -1.7
        cooldown = 30
        mode = "초기 실전형"
        note = "소액 실전 운용 구간입니다. 빠른 익절과 짧은 손절 기준이 적합합니다."
    elif cash <= 700000:
        target_pct = 2.3
        stop_pct = -1.6
        cooldown = 40
        mode = "균형 단타형"
        note = "실전 단타 기본 구간입니다. 손실 통제와 재진입 제한을 강화합니다."
    else:
        target_pct = 2.0
        stop_pct = -1.5
        cooldown = 45
        mode = "보수 단타형"
        note = "금액이 커질수록 목표수익률보다 리스크 관리가 중요합니다."

    max_positions = 1 if cash <= 200000 else (2 if cash <= 500000 else 3)

    return {
        "max_total_cash": int(cash),
        "max_order_cash": int(max_order),
        "cash_buffer": int(buffer_cash),
        "max_positions": int(max_positions),
        "min_order_cash": 50000,
        "daily_max_loss": int(daily_loss),
        "cooldown_minutes": int(cooldown),
        "target_rate_percent": target_pct,
        "stop_rate_percent": stop_pct,
        "target_rate": target_pct / 100.0,
        "stop_rate": stop_pct / 100.0,
        "mode": mode,
        "note": note,
        "max_trades_per_day": 10,
        "profit_guard_rate_percent": 1.2,
        "trailing_stop_rate_percent": 1.1,
        "force_exit_time": "15:15"
    }

def market_is_open():
    n = now_kst()
    if n.weekday() >= 5:
        return False
    hm = n.hour * 100 + n.minute
    return 900 <= hm <= 1520

def kiwoom_ready():
    return bool(KIWOOM_APP_KEY and KIWOOM_SECRET_KEY)

def kiwoom_get_token():
    if _TOKEN_CACHE["token"] and time.time() < _TOKEN_CACHE["expires"]:
        return _TOKEN_CACHE["token"]

    if not kiwoom_ready():
        update_kiwoom_debug("token", "", 0, "KIWOOM_APP_KEY / KIWOOM_SECRET_KEY 또는 KIWOOM_APP_SECRET 환경변수가 비어 있습니다.")
        raise RuntimeError("KIWOOM_APP_KEY / KIWOOM_SECRET_KEY 또는 KIWOOM_APP_SECRET 환경변수가 필요합니다.")

    try:
        r = requests.post(
            KIWOOM_BASE_URL + "/oauth2/token",
            json={"grant_type": "client_credentials", "appkey": KIWOOM_APP_KEY, "secretkey": KIWOOM_SECRET_KEY},
            headers={"Content-Type": "application/json;charset=UTF-8"},
            timeout=8
        )
        try:
            data = r.json() if r.text else {}
        except Exception:
            data = {"raw": r.text[:500]}

        if r.status_code != 200 or not data.get("token"):
            msg = data.get("return_msg") or data.get("message") or str(data)[:500]
            update_kiwoom_debug("token_fail", "", r.status_code, msg, data)
            raise RuntimeError("키움 토큰 발급 실패: " + str(msg)[:500])

        _TOKEN_CACHE["token"] = data["token"]
        # 키움 토큰 유효기간은 24시간이지만, 안전하게 23시간으로 캐시합니다.
        _TOKEN_CACHE["expires"] = time.time() + 60 * 60 * 23
        update_kiwoom_debug("token_ok", "", r.status_code, data.get("return_msg", "token ok"), {"return_code": data.get("return_code"), "expires_dt": data.get("expires_dt"), "token_type": data.get("token_type")})
        return _TOKEN_CACHE["token"]
    except Exception as e:
        update_kiwoom_debug("token_exception", "", 0, str(e))
        raise

def parse_kiwoom_price(data):
    """
    키움 REST 현재가 응답에서 현재가를 안전하게 추출합니다.
    현재가는 부호가 붙어 내려올 수 있어 절대값 처리합니다.
    """
    if not isinstance(data, dict):
        return 0

    keys = [
        "cur_prc", "curPrice", "currentPrice", "now", "price",
        "stck_prpr", "현재가", "closePrice", "lastPrice"
    ]

    for k in keys:
        if k in data:
            raw = str(data.get(k, "")).replace(",", "").replace("+", "").replace("-", "").strip()
            p = abs(safe_float(raw, 0))
            if p >= 10:
                return p

    for v in data.values():
        if isinstance(v, dict):
            p = parse_kiwoom_price(v)
            if p >= 10:
                return p
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    p = parse_kiwoom_price(item)
                    if p >= 10:
                        return p
    return 0

def get_kiwoom_live_price(code):
    """
    키움 REST API 기준 현재가 조회.
    실패하면 last_kiwoom_debug에 실패 원인을 저장합니다.
    """
    code = str(code).zfill(6)
    if code == "000000" or not code.isdigit():
        update_kiwoom_debug("price_invalid_code", code, 0, "종목코드 오류")
        return 0

    if not kiwoom_ready():
        update_kiwoom_debug("price_env_missing", code, 0, "키움 환경변수 미설정")
        return 0

    try:
        token = kiwoom_get_token()
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": "Bearer " + token,
            "cont-yn": "N",
            "next-key": "",
            "api-id": "ka10001"
        }
        body = {"stk_cd": code}
        url = KIWOOM_BASE_URL + "/api/dostk/stkinfo"
        r = requests.post(url, json=body, headers=headers, timeout=8)

        try:
            data = r.json() if r.text else {}
        except Exception:
            data = {"raw": r.text[:1000]}

        p = parse_kiwoom_price(data)
        if r.status_code == 200 and p >= 10:
            update_kiwoom_debug("price_ok", code, r.status_code, f"현재가 {p:,.0f}원 조회 성공", {"price": p, "return_code": data.get("return_code"), "return_msg": data.get("return_msg")})
            return p

        msg = data.get("return_msg") or data.get("message") or data.get("raw") or "현재가 파싱 실패"
        update_kiwoom_debug("price_fail", code, r.status_code, msg, data)
        print("kiwoom live price failed:", code, r.status_code, str(data)[:500])
        return 0
    except Exception as e:
        update_kiwoom_debug("price_exception", code, 0, str(e))
        print("kiwoom live price error:", code, e)
        return 0

def get_trade_live_price(code, fallback=True):
    """
    실전 매매 기준 현재가.
    1순위: 키움 REST
    2순위: 네이버 현재가
    """
    p = get_kiwoom_live_price(code)
    if p >= 10:
        return p, "KIWOOM"

    if fallback:
        p2 = get_live_price(code)
        if p2 >= 10:
            return p2, "NAVER"

    return 0, "NONE"

def validate_price_gap(ai_price, live_price):
    """
    AI 후보가격과 주문 직전 키움 현재가 차이를 확인합니다.
    기본 1% 초과 시 매수 보류.
    """
    ai_price = safe_float(ai_price, 0)
    live_price = safe_float(live_price, 0)
    if ai_price <= 0 or live_price <= 0:
        return False, 999
    gap = abs(ai_price - live_price) / live_price
    return gap <= PRICE_DIFF_LIMIT, gap

def kiwoom_order(side, code, qty, price=0, order_type="market"):
    code = str(code).zfill(6)
    qty = int(qty)
    price = int(safe_float(price, 0))
    if qty <= 0 or code == "000000":
        return {"ok": False, "message": "주문 수량/종목코드 오류"}
    if not KIWOOM_REAL_TRADING:
        return {"ok": False, "message": "KIWOOM_REAL_TRADING=true 환경변수가 필요합니다."}
    if KIWOOM_DRY_RUN:
        return {"ok": True, "dry_run": True, "message": "DRY_RUN 상태라 실제 주문은 전송하지 않았습니다.", "side": side, "code": code, "qty": qty, "price": price}

    token = kiwoom_get_token()
    api_id = "kt10000" if side == "buy" else "kt10001"
    trde_tp = "3" if order_type == "market" else "0"
    body = {"dmst_stex_tp": "KRX", "stk_cd": code, "ord_qty": str(qty), "ord_uv": "" if trde_tp == "3" else str(price), "trde_tp": trde_tp, "cond_uv": ""}
    headers = {"Content-Type": "application/json;charset=UTF-8", "authorization": "Bearer " + token, "api-id": api_id}
    r = requests.post(KIWOOM_BASE_URL + "/api/dostk/ordr", json=body, headers=headers, timeout=8)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    return {"ok": r.status_code == 200 and str(data.get("return_code", "0")) in ["0", ""], "status": r.status_code, "api_id": api_id, "request": body, "response": data}

def make_kiwoom_cash_body(base=None):
    """
    키움 예수금/주문가능금액 조회 API에서 필수로 요구하는 qry_tp를 자동 포함합니다.
    화면 오류:
    return_msg: 입력 값 오류입니다[1511:필수 입력 값에 값이 존재하지 않습니다. 필수입력 파라미터=qry_tp]
    """
    body = dict(base or {})
    if not body.get("qry_tp"):
        # 키움 계좌 예수금/주문가능금액 조회용 기본 조회구분
        # 일부 계정/API 버전에 따라 2/3 모두 허용될 수 있으므로 3을 우선 사용합니다.
        body["qry_tp"] = os.getenv("KIWOOM_CASH_QRY_TP", "3")
    return body

def normalize_kiwoom_cash_result(data):
    """
    v109 보강: 여러 응답 필드명에서 예수금/주문가능금액을 더 넓게 탐색합니다.
    """
    try:
        orderable_keys = [
            "ord_psbl_cash", "ord_psbl_amt", "buy_psbl_amt", "buy_available_cash",
            "nxtdy_buy_psbl_amt", "현금주문가능금액", "주문가능금액", "매수가능금액",
            "ord_alow_amt", "max_buy_amt", "available", "avail_cash"
        ]
        deposit_keys = [
            "dnca_tot_amt", "deposit", "예수금", "dps", "dpst", "entr",
            "d1_entra", "d2_entra", "cash", "현금", "예수금총액"
        ]
        withdraw_keys = [
            "wdrl_psbl_amt", "출금가능금액", "추정인출가능금액", "prsm_dpst"
        ]

        def deep_find(obj, keys):
            best = 0
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if any(str(key) == str(k) or str(key) in str(k) for key in keys):
                        val = abs(safe_float(str(v).replace(",", "").replace("+", "").replace("-", "").strip(), 0))
                        if val > best:
                            best = val
                    nested = deep_find(v, keys)
                    if nested > best:
                        best = nested
            elif isinstance(obj, list):
                for item in obj:
                    nested = deep_find(item, keys)
                    if nested > best:
                        best = nested
            return best

        orderable = deep_find(data, orderable_keys)
        deposit = deep_find(data, deposit_keys)
        withdrawable = deep_find(data, withdraw_keys)

        if orderable <= 0 and deposit > 0:
            orderable = deposit

        return {
            "orderable_cash": int(orderable),
            "deposit": int(deposit),
            "withdrawable": int(withdrawable),
        }
    except Exception:
        return {"orderable_cash": 0, "deposit": 0, "withdrawable": 0}

def _recursive_find_number_by_keys(obj, keywords):
    """
    키움 계좌/예수금 응답 필드명이 환경마다 다를 수 있어
    dict/list 전체를 돌면서 주문가능금액/예수금/현금 관련 숫자를 찾습니다.
    """
    best = 0
    if isinstance(obj, dict):
        for k, v in obj.items():
            ks = str(k)
            if any(w in ks for w in keywords):
                val = abs(safe_float(v, 0))
                if val > best:
                    best = val
            nested = _recursive_find_number_by_keys(v, keywords)
            if nested > best:
                best = nested
    elif isinstance(obj, list):
        for item in obj:
            nested = _recursive_find_number_by_keys(item, keywords)
            if nested > best:
                best = nested
    return best

def parse_kiwoom_cash(data):
    """
    키움 REST 응답에서 실제 매수에 사용할 수 있는 예수금/주문가능금액을 추출합니다.
    우선순위: 주문가능금액 > 출금가능/추정인출가능 > 예수금
    """
    if not isinstance(data, dict):
        return 0

    order_cash_keys = [
        "ord_psbl", "ordPsbl", "buyAble", "buy_psbl", "주문가능", "매수가능", "현금주문가능",
        "ord_alow_amt", "ord_psbl_cash", "avail", "available"
    ]
    deposit_keys = [
        "예수금", "dpst", "deposit", "dps", "추정인출", "인출가능", "cash", "현금"
    ]

    order_cash = _recursive_find_number_by_keys(data, order_cash_keys)
    if order_cash > 0:
        return order_cash

    deposit_cash = _recursive_find_number_by_keys(data, deposit_keys)
    return deposit_cash

def get_kiwoom_account_cash():
    """
    키움 예수금/주문가능금액 조회.
    성공 시 {ok:True, cash:금액, source:'KIWOOM', ...}
    실패 시 기존 설정값으로 주문하지 않도록 ok=False를 반환합니다.
    """
    if not kiwoom_ready():
        return {"ok": False, "cash": 0, "source": "NONE", "message": "키움 환경변수 미설정"}

    endpoints = [
        ("/api/dostk/acnt", "kt00001", make_kiwoom_cash_body()),
        ("/api/dostk/acnt", "kt00004", make_kiwoom_cash_body()),
        ("/api/dostk/acnt", "kt00018", make_kiwoom_cash_body()),
    ]
    last_error = ""
    for path, api_id, body in endpoints:
        try:
            token = kiwoom_get_token()
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "authorization": "Bearer " + token,
                "cont-yn": "N",
                "next-key": "",
                "api-id": api_id
            }
            r = requests.post(KIWOOM_BASE_URL + path, json=make_kiwoom_cash_body(body), headers=headers, timeout=8)
            try:
                data = r.json() if r.text else {}
            except Exception:
                data = {"raw": r.text[:1000]}

            cash = parse_kiwoom_cash(data)
            norm_cash = normalize_kiwoom_cash_result(data)
            if cash <= 0:
                cash = safe_float(norm_cash.get("orderable_cash", 0), 0)
            if r.status_code == 200 and cash > 0:
                update_kiwoom_debug("cash_ok", "", r.status_code, f"키움 주문가능금액 {cash:,.0f}원 조회 성공", {"cash": cash, "api_id": api_id})
                return {"ok": True, "cash": cash, "source": "KIWOOM", "api_id": api_id, "message": "키움 예수금 조회 성공"}

            last_error = str(data)[:500]
            update_kiwoom_debug("cash_fail", "", r.status_code, last_error, data)
        except Exception as e:
            last_error = str(e)
            update_kiwoom_debug("cash_exception", "", 0, last_error)

    return {"ok": False, "cash": 0, "source": "NONE", "message": last_error or "키움 예수금 조회 실패"}

def get_trade_cash_info():
    """
    실전 매매용 현금 정보.
    실전 주문에서는 키움 예수금이 확인되어야 신규 매수합니다.
    DRY_RUN에서는 테스트 편의를 위해 설정값을 fallback으로 사용합니다.
    """
    res = get_kiwoom_account_cash()
    if res.get("ok") and safe_float(res.get("cash", 0)) > 0:
        return res

    state = read_trade_state()
    if KIWOOM_DRY_RUN:
        fallback = safe_float(state.get("max_total_cash", 0), 0)
        return {"ok": True, "cash": fallback, "source": "DRY_RUN_SETTING", "message": "DRY_RUN 설정금액 사용"}

    return res

def calc_dynamic_order_cash(live_price=0):
    """
    실제 키움 예수금을 기준으로 1회 진입금을 자동 계산합니다.
    여러 종목 동시 단타를 위해 남은 슬롯 수로 나눠 과도한 1종목 몰빵을 방지합니다.
    """
    state = read_trade_state()
    cash_info = get_trade_cash_info()
    available_cash = safe_float(cash_info.get("cash", 0), 0)
    cash_buffer = safe_float(state.get("cash_buffer", 0), 0)
    max_order_cash = safe_float(state.get("max_order_cash", 0), 0)
    min_order_cash = safe_float(state.get("min_order_cash", 50000), 50000)
    max_positions = max(1, int(safe_float(state.get("max_positions", 3), 3)))
    holding_count = len(read_holdings())
    remaining_slots = max(1, max_positions - holding_count)

    usable_cash = max(0, available_cash - cash_buffer)
    slot_cash = usable_cash / remaining_slots if remaining_slots > 0 else 0
    order_cash = min(max_order_cash if max_order_cash > 0 else slot_cash, slot_cash)

    if order_cash < min_order_cash:
        return 0, {
            "ok": False,
            "cash": available_cash,
            "usable_cash": usable_cash,
            "order_cash": order_cash,
            "source": cash_info.get("source"),
            "message": f"주문가능금액 부족: 주문가능 {available_cash:,.0f}원 / 최소진입 {min_order_cash:,.0f}원"
        }

    if live_price and safe_float(live_price, 0) > 0 and order_cash < safe_float(live_price, 0):
        return 0, {
            "ok": False,
            "cash": available_cash,
            "usable_cash": usable_cash,
            "order_cash": order_cash,
            "source": cash_info.get("source"),
            "message": "현재가보다 주문가능금액이 작아 매수 불가"
        }

    return order_cash, {
        "ok": True,
        "cash": available_cash,
        "usable_cash": usable_cash,
        "order_cash": order_cash,
        "source": cash_info.get("source"),
        "max_positions": max_positions,
        "holding_count": holding_count,
        "remaining_slots": remaining_slots,
        "message": "키움 예수금 기반 주문금액 계산 완료"
    }

def trade_log_append(state, event):
    event["time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    state.setdefault("trade_log", []).insert(0, event)
    state["trade_log"] = state["trade_log"][:100]
    write_trade_state(state)

def trade_can_buy(code, price):
    state = read_trade_state()
    if not state.get("auto_trade_enabled"):
        return False, "실전 자동매매가 OFF입니다."
    if state.get("panic_stop"):
        return False, "긴급정지 상태입니다."
    if safe_float(state.get("daily_realized_pnl", 0)) <= safe_float(state.get("daily_max_loss", -30000)):
        state["auto_trade_enabled"] = False
        state["panic_stop"] = True
        write_trade_state(state)
        return False, "하루 최대 손실 제한 도달로 자동매매를 중지했습니다."
    if not market_is_open():
        return False, "정규장 시간이 아닙니다."
    holdings = read_holdings()
    max_positions = max(1, int(safe_float(state.get("max_positions", 3), 3)))
    if any(str(h.get("code", "")).zfill(6) == str(code).zfill(6) for h in holdings):
        return False, "이미 보유 중인 동일 종목은 추가 매수하지 않습니다."
    if len(holdings) >= max_positions:
        return False, f"동시 보유 한도 {max_positions}종목에 도달했습니다."
    cooldown = state.get("same_stock_cooldown", {})
    last = safe_float(cooldown.get(str(code).zfill(6), 0))
    if last and time.time() - last < safe_float(state.get("cooldown_minutes", 30)) * 60:
        return False, "같은 종목 재진입 쿨다운 중입니다."
    if price <= 0:
        return False, "현재가 확인 실패"
    return True, "OK"

def reset_daily_trade_count_if_needed(state=None):
    state = state or read_trade_state()
    today = now_kst().strftime("%Y-%m-%d")
    if state.get("last_trade_date") != today:
        state["last_trade_date"] = today
        state["trade_count_today"] = 0
        write_trade_state(state)
    return state

def should_force_exit_now(state=None):
    state = state or read_trade_state()
    t = str(state.get("force_exit_time", "15:15"))
    try:
        hh, mm = [int(x) for x in t.split(":")[:2]]
        now = now_kst()
        return (now.hour, now.minute) >= (hh, mm)
    except Exception:
        return False

def can_open_new_scalp_trade(state=None):
    state = reset_daily_trade_count_if_needed(state or read_trade_state())
    if not state.get("auto_trade_enabled"):
        return False, "실전 자동매매가 OFF입니다."
    if state.get("panic_stop"):
        return False, "긴급정지 상태입니다."
    if safe_float(state.get("daily_realized_pnl", 0)) <= safe_float(state.get("daily_max_loss", -30000)):
        return False, "하루 최대 손실 제한에 도달했습니다."
    if int(state.get("trade_count_today", 0)) >= int(state.get("max_trades_per_day", 10)):
        return False, f"하루 최대 거래횟수 {state.get('max_trades_per_day', 10)}회에 도달했습니다."
    return True, "신규 진입 가능"

def mark_scalp_trade_opened():
    state = reset_daily_trade_count_if_needed(read_trade_state())
    state["trade_count_today"] = int(state.get("trade_count_today", 0)) + 1
    write_trade_state(state)
    return state

def get_storage_status():
    try:
        p = str(BASE_DIR)
        persistent = p.startswith("/var/data") or "APP_DATA_DIR" in os.environ
        return {
            "path": p,
            "persistent": persistent,
            "message": "Persistent Disk 사용 중" if persistent else "임시 저장소 사용 중: 재배포 시 서버 보유파일이 사라질 수 있어 키움 실제잔고로만 동기화합니다."
        }
    except Exception as e:
        return {"path": "", "persistent": False, "message": str(e)}

def upsert_holding(new_holding):
    """
    보유종목을 덮어쓰지 않고 병합 저장합니다.
    같은 종목코드가 있으면 최신 정보로 업데이트하고,
    다른 종목은 삭제 전까지 유지합니다.
    """
    try:
        code = str(new_holding.get("code", "")).zfill(6)
        current = read_holdings()
        merged = []
        found = False
        for h in current:
            if str(h.get("code", "")).zfill(6) == code:
                old = dict(h)
                old.update(new_holding)
                merged.append(old)
                found = True
            else:
                merged.append(h)
        if not found:
            merged.append(new_holding)
        write_holdings(merged)
        return True
    except Exception as e:
        print("upsert_holding error:", e)
        return False

def remove_holding_by_code(code):
    code = str(code).zfill(6)
    holdings = [h for h in read_holdings() if str(h.get("code", "")).zfill(6) != code]
    write_holdings(holdings)
    return holdings

def parse_kiwoom_holdings(data):
    """
    키움 잔고/보유종목 응답 구조가 계좌별로 조금 달라질 수 있어
    여러 필드명을 탐색하여 보유종목 리스트로 변환합니다.
    """
    if not isinstance(data, dict):
        return []

    candidate_lists = []
    for k, v in data.items():
        if isinstance(v, list):
            candidate_lists.append(v)
        elif isinstance(v, dict):
            for kk, vv in v.items():
                if isinstance(vv, list):
                    candidate_lists.append(vv)

    result = []
    for arr in candidate_lists:
        for item in arr:
            if not isinstance(item, dict):
                continue
            raw_code = (
                item.get("stk_cd") or item.get("pdno") or item.get("code") or
                item.get("종목코드") or item.get("isu_cd") or ""
            )
            code = str(raw_code).replace("A", "").strip().zfill(6)
            if not code.isdigit() or code == "000000":
                continue

            name = (
                item.get("stk_nm") or item.get("prdt_name") or item.get("name") or
                item.get("종목명") or code
            )
            qty = safe_float(
                item.get("rmnd_qty") or item.get("hldg_qty") or item.get("qty") or
                item.get("보유수량") or item.get("잔고수량") or 0
            )
            buy = safe_float(
                item.get("avg_prc") or item.get("pchs_avg_pric") or item.get("buyPrice") or
                item.get("매입평균가") or item.get("평균단가") or 0
            )
            if qty <= 0:
                continue
            cur, src = get_trade_live_price(code, fallback=True)
            if cur < 10:
                cur = buy
                src = "ACCOUNT"
            state = read_trade_state()
            target_rate = normalize_rate_input(state.get("target_rate", 0.027), 0.027)
            stop_rate = normalize_rate_input(state.get("stop_rate", -0.018), -0.018)
            result.append({
                "id": int(time.time() * 1000) + len(result),
                "name": str(name).strip(),
                "code": code,
                "buyPrice": buy,
                "buyAmount": buy * qty,
                "qty": int(qty),
                "target": round(buy * (1 + target_rate)) if buy else round(cur * (1 + target_rate)),
                "stop": round(buy * (1 + stop_rate)) if buy else round(cur * (1 + stop_rate)),
                "lastPrice": cur,
                "priceSource": src,
                "autoTrade": True,
                "fromKiwoomAccount": True,
                "createdAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
                "lastCheckedAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
                "highPrice": cur,
                "highRate": round(((cur-buy)/buy*100), 3) if buy else 0,
                "scalpMode": bool(state.get("scalp_mode", True)),
                "profitGuardRate": normalize_rate_input(state.get("profit_guard_rate", 0.012), 0.012),
                "trailingStopRate": normalize_rate_input(state.get("trailing_stop_rate", 0.011), 0.011)
            })
    return result

def kiwoom_get_account_holdings():
    """
    키움 REST 실보유 잔고 동기화.
    키움 API 응답 필드/엔드포인트가 계좌 설정마다 달라질 수 있어
    실패해도 앱 기존 보유종목은 삭제하지 않습니다.
    """
    if not kiwoom_ready():
        return {"ok": False, "message": "키움 환경변수 미설정", "holdings": []}

    endpoints = [
        ("/api/dostk/acnt", "kt00018", {}),
        ("/api/dostk/acnt", "kt00004", {}),
        ("/api/dostk/acnt", "kt00005", {}),
    ]

    last_error = ""
    for path, api_id, body in endpoints:
        try:
            token = kiwoom_get_token()
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "authorization": "Bearer " + token,
                "cont-yn": "N",
                "next-key": "",
                "api-id": api_id
            }
            r = requests.post(KIWOOM_BASE_URL + path, json=make_kiwoom_cash_body(body), headers=headers, timeout=8)
            try:
                data = r.json() if r.text else {}
            except Exception:
                data = {"raw": r.text[:1000]}

            holdings = parse_kiwoom_holdings(data)
            if r.status_code == 200 and holdings:
                return {"ok": True, "api_id": api_id, "holdings": holdings, "raw": data}
            last_error = str(data)[:500]
        except Exception as e:
            last_error = str(e)

    return {"ok": False, "message": last_error or "키움 실보유 조회 실패", "holdings": []}

def sync_kiwoom_holdings_to_local():
    """
    키움 계좌의 실제 보유종목을 로컬 보유종목에 병합합니다.
    중요한 점: 키움 조회 실패 시 기존 로컬 보유종목은 절대 삭제하지 않습니다.
    """
    try:
        res = kiwoom_get_account_holdings()
        if not res.get("ok"):
            state = read_trade_state()
            state["last_order_message"] = "키움 실보유 동기화 실패 또는 보유 없음: " + str(res.get("message", ""))[:300]
            state["last_status"] = "실보유 동기화 대기"
            state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
            write_trade_state(state)
            return read_holdings()

        for h in res.get("holdings", []):
            upsert_holding(h)

        state = read_trade_state()
        state["last_status"] = "키움 실보유 동기화 완료"
        state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        state["last_order_message"] = f"키움 계좌 보유종목 {len(res.get('holdings', []))}개를 앱에 반영했습니다."
        write_trade_state(state)
        return read_holdings()
    except Exception as e:
        print("sync_kiwoom_holdings_to_local error:", e)
        return read_holdings()

def register_auto_holding(pick, code, live, qty, order, price_src="KIWOOM"):
    """
    자동매수 주문 성공 또는 주문 접수 성공 시 보유종목 파일에 강제 등록합니다.
    Render /tmp 저장소에 저장되므로 앱 보유 탭에서 즉시 확인됩니다.
    """
    try:
        state = read_trade_state()
        target_rate = normalize_rate_input(state.get("target_rate", 0.027), 0.027)
        stop_rate = normalize_rate_input(state.get("stop_rate", -0.018), -0.018)
        buy_amount = safe_float(live, 0) * safe_float(qty, 0)

        holding = {
            "id": int(time.time() * 1000),
            "name": pick.get("name", code) if isinstance(pick, dict) else str(code),
            "code": str(code).zfill(6),
            "buyPrice": safe_float(live, 0),
            "buyAmount": buy_amount,
            "qty": int(qty),
            "target": round(safe_float(live, 0) * (1 + target_rate)),
            "stop": round(safe_float(live, 0) * (1 + stop_rate)),
            "lastPrice": safe_float(live, 0),
            "priceSource": price_src,
            "autoTrade": True,
            "buyOrder": order,
            "createdAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
            "lastCheckedAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
            "highPrice": safe_float(live, 0),
            "highRate": 0,
            "scalpMode": bool(state.get("scalp_mode", True)),
            "profitGuardRate": normalize_rate_input(state.get("profit_guard_rate", 0.012), 0.012),
            "trailingStopRate": normalize_rate_input(state.get("trailing_stop_rate", 0.011), 0.011)
        }

        # 보유종목은 매도/삭제 전까지 유지: 기존 목록에 병합 저장
        saved = upsert_holding(holding)
        ensure_watch_running()

        state = read_trade_state()
        state["last_buy_code"] = str(code).zfill(6)
        state["last_buy_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        state["last_status"] = "보유종목 자동등록 완료" if saved else "보유종목 자동등록 실패"
        state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        state["last_order_message"] = f"{holding['name']}({holding['code']}) {holding['qty']}주 보유종목 저장 {'성공' if saved else '실패'}"
        write_trade_state(state)
        return holding
    except Exception as e:
        update_trade_status("보유종목 자동등록 오류", str(e), candidate=pick, order=order)
        return None

def v109_ai_position_rate(ai_score=80, price=0, orderable_cash=0, current_positions=0, max_positions=3):
    """
    AI 단타 최적화용 진입 비율.
    단순 균등분할이 아니라 AI 점수와 리스크를 반영합니다.

    기본 개념:
    - AI 점수 90 이상: 조금 더 크게 진입
    - AI 점수 80~90: 기본 진입
    - AI 점수 70~80: 소액 관찰 진입
    - 고가 종목/잔여 예수금 부족 시 자동 축소
    - 동시 보유 가능 종목 수를 고려해 몰빵 방지
    """
    score = safe_float(ai_score, 80)
    price = safe_float(price, 0)
    orderable_cash = safe_float(orderable_cash, 0)
    max_positions = max(1, int(safe_float(max_positions, 3)))
    current_positions = max(0, int(safe_float(current_positions, 0)))
    remain_slots = max(1, max_positions - current_positions)

    if score >= 95:
        base_rate = 0.42
    elif score >= 90:
        base_rate = 0.36
    elif score >= 85:
        base_rate = 0.30
    elif score >= 80:
        base_rate = 0.24
    elif score >= 70:
        base_rate = 0.16
    else:
        base_rate = 0.10

    # 남은 슬롯 기준으로 과도한 집중 방지
    slot_rate = 1.0 / remain_slots
    rate = min(base_rate, slot_rate)

    # 가격이 너무 높은 종목은 예산 과다 사용 방지
    if price > 0 and orderable_cash > 0:
        one_share_rate = price / orderable_cash
        if one_share_rate > 0.35:
            rate = min(rate, 0.25)
        elif one_share_rate > 0.25:
            rate = min(rate, 0.30)

    return max(0.05, min(rate, 0.45))

def v109_calc_ai_recommended_budget(pick=None, live_price=0):
    """
    v109 핵심:
    기존 'AI 추천 진입금액'을 'AI 추천 진입금액'으로 변경합니다.
    키움 주문가능금액을 자동 조회하고, AI 점수/종목가격/보유종목수 기준으로 추천 진입금액을 계산합니다.
    """
    state = read_trade_state()
    cash_info = get_trade_cash_info()
    orderable_cash = safe_float(cash_info.get("cash", 0), 0)

    max_positions = max(1, int(safe_float(state.get("max_positions", 3), 3)))
    current_positions = len(read_holdings())
    min_order_cash = safe_float(state.get("min_order_cash", 50000), 50000)
    cash_buffer = safe_float(state.get("cash_buffer", 0), 0)

    usable_cash = max(0, orderable_cash - cash_buffer)

    ai_score = 80
    if isinstance(pick, dict):
        ai_score = safe_float(
            pick.get("aiScoreV109", pick.get("aiScoreV90", pick.get("score", pick.get("orderPriority", 80)))),
            80
        )

    price = safe_float(live_price or (pick.get("price", 0) if isinstance(pick, dict) else 0), 0)
    rate = v109_ai_position_rate(ai_score, price, usable_cash, current_positions, max_positions)
    recommended = usable_cash * rate * ORDER_CASH_SAFETY_RATE

    # 최소 진입금보다 작으면 매수 보류
    if recommended < min_order_cash:
        return 0, {
            "ok": False,
            "label": "AI 추천 진입금액",
            "message": f"AI 추천 진입금액 부족: {recommended:,.0f}원 / 최소 {min_order_cash:,.0f}원",
            "kiwoom_orderable_cash": int(orderable_cash),
            "usable_cash": int(usable_cash),
            "ai_recommended_budget": int(recommended),
            "ai_position_rate": round(rate, 3),
            "ai_score": ai_score,
            "source": cash_info.get("source")
        }

    # 현재가보다 작으면 1주도 못 사므로 보류
    if price > 0 and recommended < price:
        return 0, {
            "ok": False,
            "label": "AI 추천 진입금액",
            "message": f"현재가보다 AI 추천 진입금액이 작아 매수 불가: 현재가 {price:,.0f}원 / 추천 {recommended:,.0f}원",
            "kiwoom_orderable_cash": int(orderable_cash),
            "usable_cash": int(usable_cash),
            "ai_recommended_budget": int(recommended),
            "ai_position_rate": round(rate, 3),
            "ai_score": ai_score,
            "source": cash_info.get("source")
        }

    return recommended, {
        "ok": True,
        "label": "AI 추천 진입금액",
        "message": "AI 점수/예수금/보유종목수 기준 추천 진입금액 계산 완료",
        "kiwoom_orderable_cash": int(orderable_cash),
        "usable_cash": int(usable_cash),
        "ai_recommended_budget": int(recommended),
        "ai_position_rate": round(rate, 3),
        "ai_score": ai_score,
        "max_positions": max_positions,
        "current_positions": current_positions,
        "source": cash_info.get("source")
    }

def v109_calc_order_qty_from_ai_budget(pick=None, live_price=0):
    budget, info = v109_calc_ai_recommended_budget(pick, live_price)
    price = safe_float(live_price, 0)
    if not info.get("ok") or price <= 0:
        return 0, info
    qty = int(budget // price)
    return max(0, qty), info

def v109_holding_status(rate, cur=0, target=0, stop=0):
    rate = safe_float(rate, 0)
    cur = safe_float(cur, 0)
    target = safe_float(target, 0)
    stop = safe_float(stop, 0)

    if stop and cur <= stop:
        return "손절가 이탈"
    if target and cur >= target:
        return "목표가 도달"
    if rate >= 2.0:
        return "수익권"
    if rate <= -1.5:
        return "손절 위험"
    return "관찰 중"

def v109_enrich_holding(h):
    h = normalize_holding(dict(h))
    code = str(h.get("code", "")).zfill(6)
    buy = safe_float(h.get("buyPrice", h.get("buy_price", 0)), 0)
    qty = safe_float(h.get("qty", 0), 0)
    cur = safe_float(h.get("lastPrice", h.get("current_price", 0)), 0)

    # 현재가 없으면 재조회
    if code and code != "000000":
        live, src = get_trade_live_price(code, fallback=True)
        if live >= 10:
            cur = live
            h["lastPrice"] = cur
            h["priceSource"] = src
            h["lastCheckedAt"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")

    target = safe_float(h.get("target", h.get("target_price", 0)), 0)
    stop = safe_float(h.get("stop", h.get("stop_price", 0)), 0)

    buy_amount = buy * qty
    eval_amount = cur * qty
    pnl = eval_amount - buy_amount if buy and qty and cur else 0
    rate = (cur - buy) / buy * 100 if buy and cur else 0

    h["buyPrice"] = round(buy)
    h["lastPrice"] = round(cur)
    h["qty"] = int(qty)
    h["buyAmount"] = round(buy_amount)
    h["evalAmount"] = round(eval_amount)
    h["profitAmount"] = round(pnl)
    h["profitRate"] = round(rate, 2)
    h["target"] = round(target) if target else 0
    h["stop"] = round(stop) if stop else 0
    h["holdingStatus"] = v109_holding_status(rate, cur, target, stop)
    h["aiComment"] = ai_comment(cur, buy, target, stop, qty)
    h["updatedBy"] = "v109"
    return h

def v109_get_enriched_holdings():
    items = read_holdings()
    enriched = []
    for h in items:
        try:
            enriched.append(v109_enrich_holding(h))
        except Exception as e:
            hh = dict(h)
            hh["v109Error"] = str(e)
            enriched.append(hh)
    write_holdings(enriched)
    return enriched

try:
    # [v109 duplicate route disabled] @app.route("/api/v109_holdings")
    def api_v109_holdings():
        holdings = v109_get_enriched_holdings()
        total_buy = sum(safe_float(h.get("buyAmount", 0)) for h in holdings)
        total_eval = sum(safe_float(h.get("evalAmount", 0)) for h in holdings)
        total_pnl = total_eval - total_buy
        total_rate = (total_pnl / total_buy * 100) if total_buy else 0
        return jsonify({
            "ok": True,
            "version": "v113",
            "holdings": holdings,
            "summary": {
                "count": len(holdings),
                "totalBuyAmount": round(total_buy),
                "totalEvalAmount": round(total_eval),
                "totalProfitAmount": round(total_pnl),
                "totalProfitRate": round(total_rate, 2)
            },
            "message": "v109 보유종목 상세 조회: 매수가/현재가/수량/매수금액/평가금액/손익/목표가/손절가/상태/AI코멘트"
        })
except Exception:
    pass

try:
    @app.route("/api/v109_ai_budget")
    def api_v109_ai_budget():
        code = request.args.get("code", "")
        price = safe_float(request.args.get("price", 0), 0)
        score = safe_float(request.args.get("score", 80), 80)
        pick = {"code": code, "score": score, "price": price}
        budget, info = v109_calc_ai_recommended_budget(pick, price)
        return jsonify({
            "ok": info.get("ok"),
            "version": "v113",
            "budget": int(budget),
            "info": info
        })
except Exception:
    pass

def v109_extract_orderable_cash(info=None):
    info = info or {}
    vals = []
    if isinstance(info, dict):
        for k in ["orderable_cash", "kiwoom_orderable_cash", "cash", "usable_cash", "deposit", "withdrawable"]:
            vals.append(safe_float(info.get(k, 0), 0))
        cash_info = info.get("cash_info")
        if isinstance(cash_info, dict):
            for k in ["orderable_cash", "cash", "deposit", "withdrawable"]:
                vals.append(safe_float(cash_info.get(k, 0), 0))
    return max(vals) if vals else 0

def v109_get_orderable_cash():
    try:
        if "get_trade_cash_info" in globals():
            res = get_trade_cash_info()
            c = v109_extract_orderable_cash(res)
            if c > 0:
                return c, res
    except Exception as e:
        last_err = str(e)
    try:
        if "get_kiwoom_account_cash" in globals():
            res = get_kiwoom_account_cash()
            c = v109_extract_orderable_cash(res)
            if c > 0:
                return c, res
    except Exception as e:
        last_err = str(e)
    try:
        if "kiwoom_get_account_cash" in globals():
            res = kiwoom_get_account_cash(force=True)
            c = v109_extract_orderable_cash(res)
            if c > 0:
                return c, res
    except Exception as e:
        last_err = str(e)
    return 0, {"ok": False, "message": locals().get("last_err", "키움 주문가능금액 조회 실패")}

def v109_calc_final_order_qty(pick=None, live_price=0):
    state = read_trade_state()
    price = safe_float(live_price or (pick.get("price", 0) if isinstance(pick, dict) else 0), 0)

    if price <= 0:
        return 0, {"ok": False, "message": "현재가가 0원이어서 주문수량 계산 불가", "price": price}

    orderable_cash, cash_raw = v109_get_orderable_cash()
    if orderable_cash < price:
        return 0, {
            "ok": False,
            "message": f"주문가능금액이 현재가보다 작습니다. 주문가능 {orderable_cash:,.0f}원 / 현재가 {price:,.0f}원",
            "orderable_cash": int(orderable_cash),
            "price": int(price),
            "cash_raw": cash_raw
        }

    ai_budget = 0
    ai_info = {}
    try:
        if "v94_calc_ai_recommended_budget" in globals():
            ai_budget, ai_info = v94_calc_ai_recommended_budget(pick, price)
    except Exception as e:
        ai_info = {"ok": False, "message": str(e)}

    min_order_cash = safe_float(state.get("min_order_cash", 50000), 50000)
    safety_cash = orderable_cash * ORDER_CASH_SAFETY_RATE

    if ai_budget <= 0:
        ai_budget = min(safety_cash, max(price, min_order_cash if safety_cash >= min_order_cash else price))
    elif ai_budget < price:
        ai_budget = price

    final_budget = min(ai_budget, safety_cash)
    if final_budget < price and orderable_cash >= price:
        final_budget = price

    qty = int(final_budget // price)

    if qty <= 0 and orderable_cash >= price:
        qty = 1
        final_budget = price

    return qty, {
        "ok": qty > 0,
        "label": "AI 추천 진입금액",
        "message": "v109 주문가능금액 기준 최종 수량 계산 완료" if qty > 0 else "최종 주문수량 0",
        "orderable_cash": int(orderable_cash),
        "kiwoom_orderable_cash": int(orderable_cash),
        "price": int(price),
        "ai_recommended_budget": int(ai_budget),
        "final_order_budget": int(final_budget),
        "qty": int(qty),
        "cash_raw": cash_raw,
        "ai_info": ai_info
    }

def v109_calc_order_qty_from_ai_budget(pick=None, live_price=0):
    return v109_calc_final_order_qty(pick, live_price)

def calc_auto_cash_order_qty(live_price, pick=None):
    return v109_calc_final_order_qty(pick, live_price)

try:
    # [v109 duplicate route disabled] @app.route("/api/v109_order_qty_test")
    def api_v109_order_qty_test():
        price = safe_float(request.args.get("price", 0), 0)
        score = safe_float(request.args.get("score", 80), 80)
        code = request.args.get("code", "")
        pick = {"code": code, "price": price, "score": score}
        qty, info = v109_calc_final_order_qty(pick, price)
        return jsonify({"ok": qty > 0, "version": "v113", "qty": qty, "info": info})
except Exception:
    pass

def v109_calc_aggressive_ai_budget(pick=None, live_price=0):
    """
    v109 핵심:
    기존 v96/v97은 최소진입금 5만원 근처로 너무 작게 진입하는 문제가 있었습니다.
    v113은 키움 주문가능금액과 최대 동시보유 종목수를 기준으로 남은 예수금을 최대한 활용합니다.

    기준:
    - 최대 동시보유 3종목이면 남은 주문가능금액을 남은 슬롯에 균등 배분
    - AI 점수 90 이상: 슬롯 예산의 100%
    - AI 점수 80~90: 슬롯 예산의 90%
    - AI 점수 70~80: 슬롯 예산의 80%
    - AI 점수 70 미만: 슬롯 예산의 70%
    - 그래도 1주 이상 가능하면 매수
    """
    state = read_trade_state()
    price = safe_float(live_price or (pick.get("price", 0) if isinstance(pick, dict) else 0), 0)
    if price <= 0:
        return 0, {"ok": False, "message": "현재가가 0원이어서 AI 추천 진입금액 계산 불가"}

    orderable_cash, cash_raw = v96_get_orderable_cash() if "v96_get_orderable_cash" in globals() else (0, {})
    if orderable_cash <= 0:
        try:
            cash_info = get_trade_cash_info()
            orderable_cash = safe_float(cash_info.get("cash", 0), 0)
            cash_raw = cash_info
        except Exception:
            pass

    if orderable_cash < price:
        return 0, {
            "ok": False,
            "message": f"주문가능금액 부족: {orderable_cash:,.0f}원 / 현재가 {price:,.0f}원",
            "orderable_cash": int(orderable_cash),
            "price": int(price)
        }

    max_positions = max(1, int(safe_float(state.get("max_positions", 3), 3)))
    current_positions = len(read_holdings())
    remain_slots = max(1, max_positions - current_positions)

    # 이미 3종목을 보유 중이어도 신규매수 진입 테스트/재매수 상황에서는 최소 1슬롯으로 계산
    slot_budget = orderable_cash / remain_slots

    ai_score = 80
    if isinstance(pick, dict):
        ai_score = safe_float(
            pick.get("aiScoreV109", pick.get("aiScoreV90", pick.get("score", pick.get("orderPriority", 80)))),
            80
        )

    if ai_score >= 90:
        use_rate = 1.00
    elif ai_score >= 80:
        use_rate = 0.90
    elif ai_score >= 70:
        use_rate = 0.80
    else:
        use_rate = 0.70

    # 주문 안전비율 적용
    safety_rate = safe_float(os.getenv("ORDER_CASH_SAFETY_RATE", ORDER_CASH_SAFETY_RATE), 0.96)
    recommended = slot_budget * use_rate * safety_rate

    # 너무 작은 5만원 고정 진입 방지: 3종목 기준이면 최소 주문가능금액의 25% 이상 사용 시도
    min_active_budget = orderable_cash * 0.25 * safety_rate if max_positions >= 3 else orderable_cash * 0.40 * safety_rate
    if recommended < min_active_budget and remain_slots <= max_positions:
        recommended = min(recommended if recommended > price else min_active_budget, slot_budget * safety_rate)

    # 최종 주문가능금액 초과 방지
    recommended = min(recommended, orderable_cash * safety_rate)

    # 1주 가능하면 최소 1주 가격 이상으로 보정
    if recommended < price and orderable_cash >= price:
        recommended = price

    qty = int(recommended // price)
    if qty <= 0 and orderable_cash >= price:
        qty = 1
        recommended = price

    return recommended, {
        "ok": qty > 0,
        "label": "AI 추천 진입금액",
        "message": "v109 주문가능금액 적극 활용 기준 AI 추천 진입금액 계산 완료",
        "orderable_cash": int(orderable_cash),
        "kiwoom_orderable_cash": int(orderable_cash),
        "price": int(price),
        "max_positions": max_positions,
        "current_positions": current_positions,
        "remain_slots": remain_slots,
        "slot_budget": int(slot_budget),
        "ai_score": round(ai_score, 2),
        "use_rate": use_rate,
        "ai_recommended_budget": int(recommended),
        "final_order_budget": int(recommended),
        "qty": int(qty),
        "cash_raw": cash_raw
    }

def v109_calc_final_order_qty(pick=None, live_price=0):
    budget, info = v109_calc_aggressive_ai_budget(pick, live_price)
    price = safe_float(live_price or (pick.get("price", 0) if isinstance(pick, dict) else 0), 0)
    if not info.get("ok") or price <= 0:
        return 0, info
    qty = int(safe_float(info.get("final_order_budget", budget), 0) // price)
    if qty <= 0 and safe_float(info.get("orderable_cash", 0), 0) >= price:
        qty = 1
    info["qty"] = qty
    return qty, info

def v96_calc_final_order_qty(pick=None, live_price=0):
    return v109_calc_final_order_qty(pick, live_price)

def v96_calc_order_qty_from_ai_budget(pick=None, live_price=0):
    return v109_calc_final_order_qty(pick, live_price)

def v94_calc_order_qty_from_ai_budget(pick=None, live_price=0):
    return v109_calc_final_order_qty(pick, live_price)

def calc_auto_cash_order_qty(live_price, pick=None):
    return v109_calc_final_order_qty(pick, live_price)

def v109_force_sync_holdings_old_disabled(full_sync=True):
    """
    보유종목 강제 새로고침 전용.
    키움 실제잔고를 기준으로 앱 로컬 보유종목을 완전히 덮어씁니다.
    """
    try:
        if "v109_force_sync_holdings" in globals():
            res = v109_force_sync_holdings(full_sync=full_sync)
        else:
            res = {"ok": False, "message": "v109_force_sync_holdings 함수 없음"}

        # v97 결과가 성공이면 수량/금액 상세 다시 보강
        if res.get("ok"):
            items = res.get("holdings", read_holdings())
            fixed = []
            for h in items:
                try:
                    if "v94_enrich_holding" in globals():
                        fixed.append(v94_enrich_holding(h))
                    else:
                        fixed.append(h)
                except Exception:
                    fixed.append(h)
            write_holdings(fixed)
            res["holdings"] = fixed
            res["version"] = "v109"
            res["message"] = "v109: 키움 실제잔고 기준으로 수량/매입가/현재가를 강제 동기화했습니다."
        return res
    except Exception as e:
        return {"ok": False, "version": "v113", "message": str(e), "holdings": read_holdings()}

def sync_kiwoom_holdings_to_local():
    res = v109_force_sync_holdings(full_sync=True)
    return res.get("holdings", read_holdings())

try:
    # [v109 duplicate route disabled] @app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
    def api_v109_force_sync_holdings():
        full = str(request.args.get("full", "1")).lower() not in ["0", "false", "no"]
        return jsonify(v109_force_sync_holdings(full_sync=full))
except Exception:
    pass

try:
    @app.route("/api/v109_order_qty_test")
    def api_v109_order_qty_test_dup2():
        price = safe_float(request.args.get("price", 0), 0)
        score = safe_float(request.args.get("score", 80), 80)
        code = request.args.get("code", "")
        pick = {"code": code, "price": price, "score": score}
        qty, info = v109_calc_final_order_qty(pick, price)
        return jsonify({"ok": qty > 0, "version": "v113", "qty": qty, "info": info})
except Exception:
    pass

def auto_buy_best_pick(args=None, use_latest_ui_pick=False):
    """
    조건 충족 시 AI 최종 1종목을 키움 API로 자동매수합니다.
    모든 진행상태를 앱 상태창에 기록합니다.
    """
    state = read_trade_state()

    ok_open, open_reason = can_open_new_scalp_trade(state)
    if not ok_open:
        update_trade_status("AI 대기중", open_reason)
        return {"ok": False, "message": open_reason}

    update_trade_status("종목 탐색중", "현재 화면 필터 기준으로 AI 최종 1종목 후보를 찾는 중입니다.")

    held_codes = {str(h.get("code", "")).zfill(6) for h in read_holdings()}

    if args is not None:
        first_pick, picks = best_pick_from_params(args)
    elif use_latest_ui_pick and state.get("latest_ui_pick"):
        first_pick = state.get("latest_ui_pick")
        picks = [first_pick] if first_pick else []
    else:
        cash_info = get_trade_cash_info()
        scan_cash = safe_float(cash_info.get("cash", 0), state.get("max_order_cash", 450000))
        first_pick, picks = best_pick_from_params({
            "cash": scan_cash,
            "minQty": 1,
            "maxChange": 7,
            "minAmount": 1000000000,
            "minScore": 70
        })

    pick = None
    for candidate in (picks or []):
        c = str(candidate.get("code", "")).zfill(6)
        if c not in held_codes:
            pick = candidate
            break

    if not pick:
        update_trade_status("매수 보류", "조건을 만족하는 신규 AI 후보가 없거나 모두 이미 보유 중입니다.")
        return {"ok": False, "message": "candidate not found or already held"}

    code = pick["code"]
    update_trade_status("후보 발견", f"{pick.get('name')}({code}) 후보 확인. 현재가 조회 중입니다.", candidate=pick)

    ai_price = safe_float(pick.get("price", 0))
    live, price_src = get_trade_live_price(code, fallback=not KIWOOM_PRICE_REQUIRED)

    if live < 10:
        reason = "키움 현재가 조회 실패로 실전 매수를 보류합니다."
        dbg = read_trade_state().get("last_kiwoom_debug", {})
        dbg_msg = dbg.get("message", "")
        dbg_stage = dbg.get("stage", "")
        dbg_status = dbg.get("http_status", "")
        update_trade_status("매수 보류", reason + (f" / {dbg_stage} {dbg_status} {dbg_msg}" if dbg_msg else ""), candidate=pick)
        send_trade_telegram(
            f"⏸ <b>AI 자동매수 보류</b>\n"
            f"후보: <b>{pick.get('name')}</b> ({code})\n"
            f"사유: {reason}\n"
            f"키움응답: {dbg_stage} / HTTP {dbg_status} / {dbg_msg}\n\n"
            "※ 실전 주문 전 키움 현재가가 확인되어야 합니다.",
            "buy_hold_price"
        )
        return {"ok": False, "message": reason, "pick": pick}

    gap_ok, gap = validate_price_gap(ai_price, live)
    pick["orderLivePrice"] = live
    pick["orderPriceSource"] = price_src
    pick["priceGapRate"] = round(gap * 100, 3)

    if not gap_ok:
        reason = f"AI 후보가격({ai_price:,.0f}원)과 키움 현재가({live:,.0f}원) 차이가 {gap*100:.2f}%로 커서 매수를 보류합니다."
        update_trade_status("매수 보류", reason, candidate=pick)
        send_trade_telegram(
            f"⏸ <b>AI 자동매수 보류</b>\n"
            f"후보: <b>{pick.get('name')}</b> ({code})\n"
            f"AI 후보가격: {ai_price:,.0f}원\n"
            f"키움 현재가: {live:,.0f}원\n"
            f"가격차: {gap*100:.2f}%\n"
            f"사유: 실시간 가격 차이 과다\n\n"
            "※ 다음 감시 주기에 다시 확인합니다.",
            "buy_hold_price_gap"
        )
        return {"ok": False, "message": reason, "pick": pick}

    allowed, reason = trade_can_buy(code, live)

    if not allowed:
        update_trade_status("매수 보류", reason, candidate=pick)

        if state.get("auto_trade_enabled") and market_is_open():
            send_trade_telegram(
                f"⏸ <b>AI 자동매수 보류</b>\n"
                f"후보: <b>{pick.get('name')}</b> ({code})\n"
                f"현재가: {safe_float(live):,.0f}원\n"
                f"사유: {reason}\n\n"
                "※ 조건 충족 시 다시 자동 감시합니다.",
                "buy_hold"
            )

        return {"ok": False, "message": reason, "pick": pick}

    order_cash, cash_meta = calc_dynamic_order_cash(live)
    qty = calc_safe_order_qty(order_cash, live)
    pick["kiwoomCash"] = cash_meta

    if qty <= 0:
        reason = cash_meta.get("message") or "키움 예수금 기준 주문 가능 수량이 0입니다."
        update_trade_status("매수 보류", reason, candidate=pick)
        return {"ok": False, "message": reason, "pick": pick, "cash": cash_meta}

    update_trade_status("주문 전송중", f"키움 예수금 기준 매수 주문 전송 중: {pick.get('name')} {qty}주 / 주문금액 {order_cash:,.0f}원", candidate=pick)

    order = kiwoom_order("buy", code, qty, price=0, order_type="market")
    buy_amount = live * qty

    if order.get("ok"):
        holding = register_auto_holding(pick, code, live, qty, order, price_src)
        if holding is None:
            holding = {"target": round(live * 1.027), "stop": round(live * 0.982), "qty": qty}
        state = read_trade_state()
        trade_log_append(state, {
            "type": "BUY",
            "name": pick["name"],
            "code": code,
            "qty": qty,
            "price": live,
            "amount": buy_amount,
            "order": order
        })

        mark_scalp_trade_opened()

        update_trade_status(
            "매수 성공" if not order.get("dry_run") else "DRY-RUN 매수 성공",
            f"{pick['name']} {qty}주 매수 처리 완료",
            candidate=pick,
            order=order
        )

        send_trade_telegram(
            f"🚀 <b>AI 자동매수 {'DRY-RUN ' if order.get('dry_run') else ''}진행</b>\n"
            f"종목: <b>{pick['name']}</b> ({code})\n"
            f"매수가 기준: {live:,.0f}원 ({price_src})\n"
            f"수량: {qty:,}주\n"
            f"매수금액: {buy_amount:,.0f}원\n"
            f"목표가: {holding['target']:,.0f}원\n"
            f"손절가: {holding['stop']:,.0f}원\n"
            f"AI 점수: {safe_float(pick.get('score', 0)):.2f}\n"
            f"테마: {pick.get('theme', '')}\n"
            f"시간: {now_kst().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "※ 실전 자동매매 모드입니다. HTS/MTS 체결 여부를 반드시 확인하세요.",
            "buy_success"
        )

    else:
        reason = order.get("message") or order.get("response") or order
        avail_qty = extract_available_qty(reason)

        if avail_qty > 0 and avail_qty < qty:
            retry_qty = max(1, avail_qty)
            update_trade_status("수량 조정 재주문", f"증거금 부족으로 {qty}주 → {retry_qty}주 재주문합니다.", candidate=pick, order=order)

            retry_order = kiwoom_order("buy", code, retry_qty, price=0, order_type="market")
            retry_amount = live * retry_qty

            if retry_order.get("ok"):
                holding = register_auto_holding(pick, code, live, retry_qty, retry_order, price_src)
                if holding is None:
                    holding = {"target": round(live * 1.027), "stop": round(live * 0.982), "qty": retry_qty}
                state = read_trade_state()
                trade_log_append(state, {
                    "type": "BUY_RETRY",
                    "name": pick["name"],
                    "code": code,
                    "qty": retry_qty,
                    "price": live,
                    "amount": retry_amount,
                    "order": retry_order
                })

                update_trade_status("수량 조정 매수 성공", f"{pick['name']} {retry_qty}주 매수 처리 완료", candidate=pick, order=retry_order)
                send_trade_telegram(
                    f"🚀 <b>AI 자동매수 수량조정 진행</b>\n"
                    f"종목: <b>{pick['name']}</b> ({code})\n"
                    f"매수가 기준: {live:,.0f}원 ({price_src})\n"
                    f"최초 수량: {qty:,}주 → 조정 수량: {retry_qty:,}주\n"
                    f"매수금액: {retry_amount:,.0f}원\n"
                    f"목표가: {holding['target']:,.0f}원\n"
                    f"손절가: {holding['stop']:,.0f}원\n"
                    f"AI 점수: {safe_float(pick.get('score', 0)):.2f}\n"
                    f"시간: {now_kst().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    "※ 키움 매수가능 수량 기준으로 자동 조정했습니다. HTS/MTS 체결 여부를 확인하세요.",
                    "buy_retry_success"
                )
                return {"ok": True, "pick": pick, "order": retry_order, "adjusted_qty": retry_qty}

            reason = retry_order.get("message") or retry_order.get("response") or retry_order
            order = retry_order

        update_trade_status("매수 실패", reason, candidate=pick, order=order)
        send_trade_telegram(
            f"⚠️ <b>AI 자동매수 실패</b>\n"
            f"종목: {pick.get('name')} ({code})\n"
            f"현재가: {live:,.0f}원\n"
            f"수량: {qty:,}주\n"
            f"사유: {reason}\n\n"
            "증거금 부족이면 1회 최대 진입금을 낮추거나 키움 예수금을 확인하세요.",
            "buy_fail"
        )

    return {"ok": bool(order.get("ok")), "pick": pick, "order": order}

def try_rebuy_after_sell(sold_code=""):
    """
    자동매도 성공 후 새로운 AI 후보를 자동으로 탐색/매수합니다.
    안전조건:
    - AUTO_REBUY_AFTER_SELL=true
    - 자동매매 ON
    - 긴급정지 아님
    - 장중
    - 현재 보유종목 없음
    - 하루 최대손실 미도달
    """
    try:
        if not AUTO_REBUY_AFTER_SELL:
            update_trade_status("재매수 대기", "AUTO_REBUY_AFTER_SELL=false 상태라 신규 매수를 진행하지 않습니다.")
            return {"ok": False, "message": "auto rebuy disabled"}

        state = read_trade_state()
        if not state.get("auto_trade_enabled") or state.get("panic_stop"):
            update_trade_status("재매수 대기", "자동매매 OFF 또는 긴급정지 상태입니다.")
            return {"ok": False, "message": "auto trade off or panic stop"}

        if not market_is_open():
            update_trade_status("재매수 대기", "장중이 아니므로 신규 매수를 진행하지 않습니다.")
            return {"ok": False, "message": "market closed"}

        # v123_CLICK_DETAIL_STATUS_FIX: 기존 보유종목이 있어도 최대 보유종목 수와 예수금이 허용하면 신규 후보를 추가 매수합니다.

        if safe_float(state.get("daily_realized_pnl", 0)) <= safe_float(state.get("daily_max_loss", -30000)):
            update_trade_status("재매수 중지", "하루 최대 손실 제한에 도달하여 신규 매수를 중지합니다.")
            return {"ok": False, "message": "daily loss limit reached"}

        send_trade_telegram(
            f"🔄 <b>자동매도 완료 후 신규 후보 탐색</b>\n"
            f"매도 완료 종목: {sold_code}\n"
            f"새로운 AI 후보를 확인합니다.",
            "rebuy_start"
        )

        latest_args = state.get("latest_ui_args") or None
        result = auto_buy_best_pick(args=latest_args, use_latest_ui_pick=False)
        return result
    except Exception as e:
        update_trade_status("재매수 오류", str(e))
        send_trade_telegram(f"⚠️ <b>재매수 처리 오류</b>\n사유: {e}", "rebuy_error")
        return {"ok": False, "message": str(e)}

def auto_sell_holding(kind, h, cur):
    state = read_trade_state()
    if not state.get("auto_trade_enabled") or not h.get("autoTrade"):
        send_holding_alert(kind, h, cur)
        return False
    qty = int(safe_float(h.get("qty", 0)))
    code = str(h.get("code", "")).zfill(6)
    order = kiwoom_order("sell", code, qty, price=0, order_type="market")
    buy = safe_float(h.get("buyPrice", 0))
    pnl = (cur - buy) * qty if buy and qty else 0
    rate = ((cur - buy) / buy * 100) if buy else 0
    if order.get("ok"):
        state["daily_realized_pnl"] = safe_float(state.get("daily_realized_pnl", 0)) + pnl
        state.setdefault("same_stock_cooldown", {})[code] = time.time()
        trade_log_append(state, {"type": "SELL", "reason": kind, "name": h.get("name", code), "code": code, "qty": qty, "price": cur, "pnl": pnl, "rate": rate, "order": order})
        remain = [x for x in read_holdings() if str(x.get("code", "")).zfill(6) != code]
        write_holdings(remain)
        send_telegram_message(
            f"{'✅ 목표가 도달 자동매도' if kind == 'target' else '🛑 손절가 이탈 자동매도'}\n"
            f"종목: <b>{h.get('name', code)}</b> ({code})\n"
            f"매수가: {buy:,.0f}원\n"
            f"매도가 기준: {cur:,.0f}원\n"
            f"수량: {qty:,}주\n"
            f"실현손익 기준: {pnl:,.0f}원 ({rate:.2f}%)\n"
            f"금일 누적손익: {state.get('daily_realized_pnl', 0):,.0f}원\n\n"
            f"{ai_comment(cur, buy, h.get('target', 0), h.get('stop', 0), qty)}\n\n"
            "※ HTS/MTS에서 실제 체결 여부를 반드시 확인하세요."
        )
        if safe_float(state.get("daily_realized_pnl", 0)) <= safe_float(state.get("daily_max_loss", -30000)):
            state["auto_trade_enabled"] = False
            state["panic_stop"] = True
            write_trade_state(state)
            send_telegram_message("🛑 <b>하루 최대 손실 제한 도달</b>\n자동매매를 중지했습니다.")
        else:
            # 목표/손절 자동매도 후 다음 후보 자동 탐색/매수
            try_rebuy_after_sell(code)
        return True
    send_telegram_message(f"⚠️ <b>자동매도 실패</b>\n종목: {h.get('name', code)} ({code})\n사유: {order.get('message') or order.get('response')}")
    send_holding_alert(kind, h, cur)
    return False

@app.before_request
def auto_resume():
    try:
        if not request.path.startswith('/static') and read_holdings() and not WATCH_STATE.get('running'): ensure_watch_running()
    except Exception: pass

_ACCOUNT_CASH_CACHE = {
    "time": 0,
    "data": None
}

ACCOUNT_CASH_CACHE_SEC = int(os.getenv("ACCOUNT_CASH_CACHE_SEC", "20"))
USE_KIWOOM_CASH_AUTO = os.getenv("USE_KIWOOM_CASH_AUTO", "true").lower() == "true"
MAX_POSITION_COUNT = int(os.getenv("MAX_POSITION_COUNT", "3"))
POSITION_CASH_RATE = safe_float(os.getenv("POSITION_CASH_RATE", "0.33"), 0.33)
MIN_ORDER_CASH = safe_float(os.getenv("MIN_ORDER_CASH", "30000"), 30000)

def parse_money_from_any(data, keys):
    """
    키움 API 응답 구조가 계좌/버전에 따라 다를 수 있어
    여러 필드명과 중첩 dict/list를 재귀적으로 탐색합니다.
    """
    if data is None:
        return 0

    if isinstance(data, dict):
        for k in keys:
            if k in data:
                v = safe_float(str(data.get(k, "")).replace(",", "").replace("+", "").strip(), 0)
                if abs(v) > 0:
                    return abs(v)

        for v in data.values():
            found = parse_money_from_any(v, keys)
            if found:
                return found

    elif isinstance(data, list):
        for item in data:
            found = parse_money_from_any(item, keys)
            if found:
                return found

    return 0

def parse_kiwoom_cash_response(data):
    """
    키움 예수금/주문가능금액 응답을 표준 구조로 변환합니다.
    """
    deposit_keys = [
        "dnca_tot_amt", "deposit", "예수금", "cash", "ord_psbl_cash",
        "d2_entra", "d1_entra", "entr"
    ]
    orderable_keys = [
        "ord_psbl_amt", "buy_available_cash", "주문가능금액", "매수가능금액",
        "nxtdy_buy_psbl_amt", "ord_psbl_cash", "max_buy_amt", "avail_cash"
    ]
    withdraw_keys = [
        "wdrl_psbl_amt", "출금가능금액", "추정인출가능금액", "d2_withdrawable_amount",
        "d2_entra", "prsm_dpst"
    ]

    deposit = parse_money_from_any(data, deposit_keys)
    orderable = parse_money_from_any(data, orderable_keys)
    withdrawable = parse_money_from_any(data, withdraw_keys)

    # 주문가능금액이 없고 예수금만 있으면 예수금을 보조값으로 사용
    if orderable <= 0 and deposit > 0:
        orderable = deposit

    return {
        "deposit": int(deposit),
        "orderable_cash": int(orderable),
        "withdrawable": int(withdrawable),
        "raw_checked_at": now_kst().strftime("%Y-%m-%d %H:%M:%S")
    }

def kiwoom_get_account_cash(force=False):
    """
    키움 REST API에서 예수금/주문가능금액을 자동 조회합니다.
    실패 시 ok=False 반환. 자동매수는 보류됩니다.
    """
    if not force and _ACCOUNT_CASH_CACHE["data"] and time.time() - _ACCOUNT_CASH_CACHE["time"] < ACCOUNT_CASH_CACHE_SEC:
        return _ACCOUNT_CASH_CACHE["data"]

    if not kiwoom_ready():
        res = {
            "ok": False,
            "message": "키움 환경변수 미설정",
            "deposit": 0,
            "orderable_cash": 0,
            "withdrawable": 0,
            "source": "NONE",
            "checked_at": now_kst().strftime("%Y-%m-%d %H:%M:%S")
        }
        _ACCOUNT_CASH_CACHE.update({"time": time.time(), "data": res})
        return res

    # 키움 예수금/계좌 관련 TR은 환경에 따라 다를 수 있어 여러 api-id를 순차 시도
    endpoints = [
        ("/api/dostk/acnt", "kt00001", make_kiwoom_cash_body()),
        ("/api/dostk/acnt", "kt00004", make_kiwoom_cash_body()),
        ("/api/dostk/acnt", "kt00005", make_kiwoom_cash_body()),
        ("/api/dostk/acnt", "kt00018", make_kiwoom_cash_body()),
    ]

    last_error = ""
    for path, api_id, body in endpoints:
        try:
            token = kiwoom_get_token()
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "authorization": "Bearer " + token,
                "cont-yn": "N",
                "next-key": "",
                "api-id": api_id
            }
            r = requests.post(KIWOOM_BASE_URL + path, json=make_kiwoom_cash_body(body), headers=headers, timeout=8)
            try:
                data = r.json() if r.text else {}
            except Exception:
                data = {"raw": r.text[:1000]}

            parsed = parse_kiwoom_cash_response(data)
            norm_cash = normalize_kiwoom_cash_result(data)
            if parsed.get("orderable_cash", 0) <= 0 and norm_cash.get("orderable_cash", 0) > 0:
                parsed.update(norm_cash)
            if r.status_code == 200 and parsed.get("orderable_cash", 0) > 0:
                res = {
                    "ok": True,
                    "api_id": api_id,
                    "deposit": parsed["deposit"],
                    "orderable_cash": parsed["orderable_cash"],
                    "withdrawable": parsed["withdrawable"],
                    "source": "KIWOOM",
                    "checked_at": now_kst().strftime("%Y-%m-%d %H:%M:%S")
                }
                _ACCOUNT_CASH_CACHE.update({"time": time.time(), "data": res})
                try:
                    state = read_trade_state()
                    state["kiwoom_deposit"] = res["deposit"]
                    state["kiwoom_orderable_cash"] = res["orderable_cash"]
                    state["kiwoom_withdrawable"] = res["withdrawable"]
                    state["last_cash_sync_time"] = res["checked_at"]
                    write_trade_state(state)
                except Exception:
                    pass
                return res

            last_error = str(data)[:500]
            update_kiwoom_debug("cash_fail", "", r.status_code, last_error, data)

        except Exception as e:
            last_error = str(e)
            update_kiwoom_debug("cash_exception", "", 0, last_error)

    res = {
        "ok": False,
        "message": last_error or "키움 예수금/주문가능금액 조회 실패",
        "deposit": 0,
        "orderable_cash": 0,
        "withdrawable": 0,
        "source": "KIWOOM_FAIL",
        "checked_at": now_kst().strftime("%Y-%m-%d %H:%M:%S")
    }
    _ACCOUNT_CASH_CACHE.update({"time": time.time(), "data": res})
    return res

def get_current_position_count():
    try:
        return len([h for h in read_holdings() if safe_float(h.get("qty", 0)) > 0])
    except Exception:
        return 0

def get_open_holding_codes():
    try:
        return set(str(h.get("code", "")).zfill(6) for h in read_holdings())
    except Exception:
        return set()

def get_auto_order_budget():
    """
    v109 핵심:
    앱 입력 총투자금이 아니라 키움 주문가능금액을 기준으로 1회 진입금 계산.
    여러 종목 동시 운용을 위해 주문가능금액의 POSITION_CASH_RATE만 사용.
    """
    state = read_trade_state()

    if USE_KIWOOM_CASH_AUTO:
        cash = kiwoom_get_account_cash(force=True)
        if not cash.get("ok"):
            return {
                "ok": False,
                "message": "키움 주문가능금액 자동조회 실패: " + str(cash.get("message", ""))[:300],
                "orderable_cash": 0,
                "budget": 0,
                "cash_info": cash
            }

        orderable = safe_float(cash.get("orderable_cash", 0), 0)
        if orderable < MIN_ORDER_CASH:
            return {
                "ok": False,
                "message": f"주문가능금액 부족: {orderable:,.0f}원",
                "orderable_cash": int(orderable),
                "budget": 0,
                "cash_info": cash
            }

        # 남은 보유 가능 슬롯 기준으로 너무 크게 몰빵하지 않도록 분산
        position_count = get_current_position_count()
        remain_slots = max(1, MAX_POSITION_COUNT - position_count)

        # 기본: 주문가능금액의 POSITION_CASH_RATE 사용
        # 단, 남은 슬롯이 있으면 균등 배분 금액과 비교하여 과도한 집중 방지
        rate_budget = orderable * POSITION_CASH_RATE
        slot_budget = orderable / remain_slots
        budget = min(rate_budget, slot_budget)

        # 안전마진
        budget = budget * ORDER_CASH_SAFETY_RATE

        return {
            "ok": True,
            "message": "키움 주문가능금액 기준 자동 계산",
            "orderable_cash": int(orderable),
            "budget": int(max(0, budget)),
            "cash_info": cash
        }

    # 예외적으로 수동모드 사용 시 기존 max_order_cash 사용
    manual_budget = safe_float(state.get("max_order_cash", 0), 0)
    return {
        "ok": manual_budget > 0,
        "message": "수동 입력 진입금 사용",
        "orderable_cash": manual_budget,
        "budget": int(manual_budget * ORDER_CASH_SAFETY_RATE),
        "cash_info": {"ok": True, "source": "MANUAL"}
    }

def trade_can_buy_v109(code, price):
    """
    v109 매수 가능 조건:
    - 1종목 제한 제거
    - 최대 동시 보유 종목수까지만 허용
    - 동일 종목 중복매수 방지
    - 키움 주문가능금액 자동조회 성공 필요
    """
    state = read_trade_state()
    code = str(code).zfill(6)

    if not state.get("auto_trade_enabled"):
        return False, "실전 자동매매가 OFF입니다."
    if state.get("panic_stop"):
        return False, "긴급정지 상태입니다."
    if safe_float(state.get("daily_realized_pnl", 0)) <= safe_float(state.get("daily_max_loss", -30000)):
        state["auto_trade_enabled"] = False
        state["panic_stop"] = True
        write_trade_state(state)
        return False, "하루 최대 손실 제한 도달로 자동매매를 중지했습니다."
    if not market_is_open():
        return False, "정규장 시간이 아닙니다."
    if price <= 0:
        return False, "현재가 확인 실패"

    holding_codes = get_open_holding_codes()
    if code in holding_codes:
        return False, "이미 보유 중인 종목이라 중복 매수하지 않습니다."

    if get_current_position_count() >= MAX_POSITION_COUNT:
        return False, f"동시 보유 최대 {MAX_POSITION_COUNT}종목 제한입니다."

    cooldown = state.get("same_stock_cooldown", {})
    last = safe_float(cooldown.get(code, 0))
    if last and time.time() - last < safe_float(state.get("cooldown_minutes", 30)) * 60:
        return False, "같은 종목 재진입 쿨다운 중입니다."

    budget = get_auto_order_budget()
    if not budget.get("ok") or budget.get("final_order_budget", budget.get("ai_recommended_budget", budget.get("budget", 0))) < MIN_ORDER_CASH:
        return False, budget.get("message", "주문가능금액 부족")

    return True, "OK"

def calc_auto_cash_order_qty(live_price):
    """
    v109 수량 계산:
    키움 주문가능금액 자동조회 → 종목당 예산 계산 → 주문수량 산출
    """
    budget = get_auto_order_budget()
    if not budget.get("ok"):
        return 0, budget

    price = safe_float(live_price, 0)
    if price <= 0:
        return 0, budget

    qty = int(safe_float(budget.get("final_order_budget", budget.get("ai_recommended_budget", budget.get("budget", 0))), 0) // price)
    return max(0, qty), budget

try:
    @app.route("/api/kiwoom_cash")
    def api_kiwoom_cash():
        force = str(request.args.get("force", "0")).lower() in ["1", "true", "yes"]
        return jsonify(kiwoom_get_account_cash(force=force))

    @app.route("/api/v109_cash")
    def api_v109_cash():
        cash = kiwoom_get_account_cash(force=True)
        budget = get_auto_order_budget()
        return jsonify({
            "ok": bool(cash.get("ok")),
            "version": "v113",
            "cash": cash,
            "budget": budget,
            "max_position_count": MAX_POSITION_COUNT,
            "position_cash_rate": POSITION_CASH_RATE,
            "min_order_cash": MIN_ORDER_CASH,
            "message": "v113은 앱 입력금액이 아니라 키움 주문가능금액을 자동 조회하여 매수 기준으로 사용합니다."
        })
except Exception:
    pass

def auto_buy_best_pick(args=None, use_latest_ui_pick=False):
    """
    v109:
    - 키움 예수금/주문가능금액 자동 조회
    - 1종목 제한 제거
    - 여러 종목 동시 단타 가능
    - 동일 종목 중복매수 방지
    """
    state = read_trade_state()

    ok_open, open_reason = can_open_new_scalp_trade(state)
    if not ok_open:
        update_trade_status("AI 대기중", open_reason)
        return {"ok": False, "message": open_reason}

    update_trade_status("종목 탐색중", "v109 키움 주문가능금액 기준으로 AI 단타 후보를 찾는 중입니다.")

    if args is not None:
        pick, picks = best_pick_from_params(args)
    elif use_latest_ui_pick and state.get("latest_ui_pick"):
        pick = state.get("latest_ui_pick")
        picks = [pick]
    else:
        # 수동 투자금 대신 키움 주문가능금액 기준 예산으로 후보 수량 계산
        budget = get_auto_order_budget()
        cash_for_scan = max(safe_float(budget.get("final_order_budget", budget.get("ai_recommended_budget", budget.get("budget", 0))), 0), MIN_ORDER_CASH)
        pick, picks = best_pick_from_params({
            "cash": cash_for_scan,
            "minQty": 1,
            "maxChange": 7,
            "minAmount": 1000000000,
            "minScore": 70
        })

    if not pick:
        update_trade_status("매수 보류", "현재 조건을 만족하는 AI 후보가 없습니다.")
        return {"ok": False, "message": "candidate not found"}

    # 이미 보유 중인 종목은 건너뛰고 다음 후보 선택
    holding_codes = get_open_holding_codes()
    if picks:
        for p in picks:
            if str(p.get("code", "")).zfill(6) not in holding_codes:
                pick = p
                break

    code = str(pick["code"]).zfill(6)
    update_trade_status("후보 발견", f"{pick.get('name')}({code}) 후보 확인. 키움 현재가/주문가능금액 조회 중입니다.", candidate=pick)

    ai_price = safe_float(pick.get("price", 0))
    live, price_src = get_trade_live_price(code, fallback=not KIWOOM_PRICE_REQUIRED)

    if live < 10:
        reason = "키움 현재가 조회 실패로 실전 매수를 보류합니다."
        dbg = read_trade_state().get("last_kiwoom_debug", {})
        dbg_msg = dbg.get("message", "")
        dbg_stage = dbg.get("stage", "")
        dbg_status = dbg.get("http_status", "")
        update_trade_status("매수 보류", reason + (f" / {dbg_stage} {dbg_status} {dbg_msg}" if dbg_msg else ""), candidate=pick)
        send_trade_telegram(
            f"⏸ <b>AI 자동매수 보류</b>\n"
            f"후보: <b>{pick.get('name')}</b> ({code})\n"
            f"사유: {reason}\n"
            f"키움응답: {dbg_stage} / HTTP {dbg_status} / {dbg_msg}\n\n"
            "※ 실전 주문 전 키움 현재가가 확인되어야 합니다.",
            "buy_hold_price"
        )
        return {"ok": False, "message": reason, "pick": pick}

    gap_ok, gap = validate_price_gap(ai_price, live)
    pick["orderLivePrice"] = live
    pick["orderPriceSource"] = price_src
    pick["priceGapRate"] = round(gap * 100, 3)

    if not gap_ok:
        reason = f"AI 후보가격({ai_price:,.0f}원)과 키움 현재가({live:,.0f}원) 차이가 {gap*100:.2f}%로 커서 매수를 보류합니다."
        update_trade_status("매수 보류", reason, candidate=pick)
        return {"ok": False, "message": reason, "pick": pick}

    allowed, reason = trade_can_buy_v109(code, live)

    if not allowed:
        update_trade_status("매수 보류", reason, candidate=pick)
        return {"ok": False, "message": reason, "pick": pick}

    qty, budget = v109_calc_order_qty_from_ai_budget(pick, live)

    if qty <= 0:
        reason = budget.get("message", "v109 계산 결과 주문 가능 수량이 0입니다.") if isinstance(budget, dict) else "v109 계산 결과 주문 가능 수량이 0입니다."
        update_trade_status("매수 보류", reason, candidate=pick)
        return {"ok": False, "message": reason, "pick": pick, "budget": budget}

    update_trade_status(
        "주문 전송중",
        f"v109 키움 주문가능금액 기준 매수 주문: {pick.get('name')} {qty}주 / 주문가능금액 {budget.get('orderable_cash', 0):,.0f}원 / AI추천예산 {budget.get('final_order_budget', budget.get('ai_recommended_budget', budget.get('budget', 0))):,.0f}원",
        candidate=pick
    )

    order = kiwoom_order("buy", code, qty, price=0, order_type="market")
    buy_amount = live * qty

    if order.get("ok"):
        holding = register_auto_holding(pick, code, live, qty, order, price_src)
        if holding is None:
            holding = {"target": round(live * 1.027), "stop": round(live * 0.982), "qty": qty}

        state = mark_scalp_trade_opened()
        trade_log_append(state, {
            "type": "BUY",
            "name": pick["name"],
            "code": code,
            "qty": qty,
            "price": live,
            "amount": buy_amount,
            "cash_budget": budget,
            "order": order
        })

        update_trade_status(
            "매수 성공" if not order.get("dry_run") else "DRY-RUN 매수 성공",
            f"v109 {pick['name']} {qty}주 매수 처리 완료",
            candidate=pick,
            order=order
        )

        send_trade_telegram(
            f"🚀 <b>v119 AI 자동매수 {'DRY-RUN ' if order.get('dry_run') else ''}진행</b>\n"
            f"종목: <b>{pick['name']}</b> ({code})\n"
            f"매수가 기준: {live:,.0f}원 ({price_src})\n"
            f"수량: {qty:,}주\n"
            f"매수금액: {buy_amount:,.0f}원\n"
            f"키움 주문가능금액: {budget.get('orderable_cash', 0):,.0f}원\n"
            f"AI 추천 진입금액: {budget.get('final_order_budget', budget.get('ai_recommended_budget', budget.get('budget', 0))):,.0f}원\n"
            f"목표가: {holding['target']:,.0f}원\n"
            f"손절가: {holding['stop']:,.0f}원\n"
            f"AI 점수: {safe_float(pick.get('score', 0)):.2f}\n"
            f"테마: {pick.get('theme', '')}\n"
            f"시간: {now_kst().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "※ v117은 AI 점수와 키움 주문가능금액을 기준으로 매수수량을 강하게 자동 산정합니다.",
            "buy_success_v109"
        )

    else:
        reason = order.get("message") or order.get("response") or order
        avail_qty = extract_available_qty(reason)

        if avail_qty > 0 and avail_qty < qty:
            retry_qty = max(1, avail_qty)
            update_trade_status("수량 조정 재주문", f"증거금 부족으로 {qty}주 → {retry_qty}주 재주문합니다.", candidate=pick, order=order)

            retry_order = kiwoom_order("buy", code, retry_qty, price=0, order_type="market")
            retry_amount = live * retry_qty

            if retry_order.get("ok"):
                holding = register_auto_holding(pick, code, live, retry_qty, retry_order, price_src)
                state = mark_scalp_trade_opened()
                trade_log_append(state, {
                    "type": "BUY_RETRY",
                    "name": pick["name"],
                    "code": code,
                    "qty": retry_qty,
                    "price": live,
                    "amount": retry_amount,
                    "cash_budget": budget,
                    "order": retry_order
                })

                update_trade_status("수량 조정 매수 성공", f"{pick['name']} {retry_qty}주 매수 처리 완료", candidate=pick, order=retry_order)
                send_trade_telegram(
                    f"🚀 <b>v119 AI 자동매수 수량조정 진행</b>\n"
                    f"종목: <b>{pick['name']}</b> ({code})\n"
                    f"매수가 기준: {live:,.0f}원 ({price_src})\n"
                    f"최초 수량: {qty:,}주 → 조정 수량: {retry_qty:,}주\n"
                    f"매수금액: {retry_amount:,.0f}원\n"
                    f"키움 주문가능금액: {budget.get('orderable_cash', 0):,.0f}원\n"
                    f"시간: {now_kst().strftime('%Y-%m-%d %H:%M:%S')}",
                    "buy_retry_success_v109"
                )
                return {"ok": True, "pick": pick, "order": retry_order, "adjusted_qty": retry_qty, "budget": budget}

            reason = retry_order.get("message") or retry_order.get("response") or retry_order
            order = retry_order

        update_trade_status("매수 실패", reason, candidate=pick, order=order)
        send_trade_telegram(
            f"⚠️ <b>v119 AI 자동매수 실패</b>\n"
            f"종목: {pick.get('name')} ({code})\n"
            f"현재가: {live:,.0f}원\n"
            f"수량: {qty:,}주\n"
            f"사유: {reason}\n\n"
            "키움 예수금/주문가능금액 또는 주문 가능 수량을 확인하세요.",
            "buy_fail_v109"
        )

    return {"ok": bool(order.get("ok")), "pick": pick, "order": order, "budget": budget}

@app.route('/')
def index(): return render_template_string(HTML)
@app.route('/api/login_check',methods=['POST'])
def api_login_check():
    data=request.get_json(force=True,silent=True) or {}; pw=str(data.get('password','')).strip(); master=os.getenv('MASTER_PASSWORD','0000').strip(); user=os.getenv('USER_PASSWORD','1234').strip()
    if pw and pw==master: return jsonify({'ok':True,'role':'master'})
    if pw and pw==user: return jsonify({'ok':True,'role':'user'})
    return jsonify({'ok':False,'message':'비밀번호가 맞지 않습니다.'})
@app.route('/api/best_pick')
def api_best_pick():
    pick,picks=best_pick_from_params(request.args)
    if pick:
        WATCH_STATE['best_code']=pick['code']; WATCH_STATE['best_score']=pick['score']
        state = read_trade_state()
        state['latest_ui_pick'] = pick
        state['latest_ui_args'] = {k: request.args.get(k) for k in request.args.keys()}
        write_trade_state(state)
        update_trade_status('화면 후보 갱신', f"화면 최종 후보: {pick.get('name')}({pick.get('code')})", candidate=pick)
    return jsonify(safe_json({'ok':bool(pick),'pick':pick,'next':picks[1:6],'updated':now_kst().strftime('%Y-%m-%d %H:%M:%S')}))
@app.route('/api/watch_candidates')
def api_watch_candidates():
    _,picks=best_pick_from_params(request.args); return jsonify(safe_json({'ok':True,'items':picks[:8],'updated':now_kst().strftime('%Y-%m-%d %H:%M:%S')}))
@app.route('/api/best_pick/test_alert',methods=['GET','POST'])
def api_best_pick_test_alert():
    pick,_=best_pick_from_params(request.args)
    if not pick: return jsonify({'ok':False,'message':'현재 조건에 맞는 후보가 없습니다.'})
    return jsonify({'ok':send_better_pick_alert(pick,0),'pick':pick})

@app.route('/api/storage_status')
def api_storage_status():
    return jsonify({"ok": True, "storage": get_storage_status(), "holdings_count": len(read_holdings())})

def api_restore_holdings():
    data = request.get_json(force=True, silent=True) or {}
    items = data.get("holdings", [])
    restored = 0
    if isinstance(items, list):
        for h in items:
            if not isinstance(h, dict):
                continue
            code = str(h.get("code", "")).zfill(6)
            qty = safe_float(h.get("qty", 0))
            buy = safe_float(h.get("buyPrice", 0))
            if code.isdigit() and code != "000000" and qty > 0 and buy > 0:
                h["code"] = code
                h["restoredFromBrowser"] = True
                h["lastCheckedAt"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
                upsert_holding(h)
                restored += 1
    state = read_trade_state()
    state["last_status"] = "브라우저 백업 복구 완료" if restored else "브라우저 백업 복구 없음"
    state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    state["last_order_message"] = f"브라우저 백업에서 보유종목 {restored}개 복구"
    write_trade_state(state)
    return jsonify({"ok": True, "restored": restored, "holdings": read_holdings()})

@app.route('/api/sync_kiwoom_holdings', methods=['POST','GET'])
def api_sync_kiwoom_holdings():
    holdings = sync_kiwoom_holdings_to_local()
    return jsonify({'ok': True, 'holdings': holdings, 'count': len(holdings)})

def api_server_holdings():
    if request.method=='GET':
        holdings = read_holdings()
        if request.args.get('sync') == '1':
            holdings = sync_kiwoom_holdings_to_local()
        if request.args.get('refresh') == '1':
            sync_res = v109_force_sync_holdings(full_sync=True) if 'v109_force_sync_holdings' in globals() else {'holdings': holdings}
            holdings = sync_res.get('holdings', holdings)
        return jsonify({'ok':True,'holdings':holdings})
    data=request.get_json(force=True,silent=True) or {}; action=data.get('action','add'); holdings=read_holdings()
    if action=='add':
        item=normalize_holding(data.get('item',{})); code=item.get('code',''); buy=safe_float(item.get('buyPrice',0)); amount=safe_float(item.get('buyAmount',0)); qty=safe_float(item.get('qty',0)) or (math.floor(amount/buy) if buy and amount else 0)
        item.update({'qty':qty,'target':safe_float(item.get('target',0)) or round(buy*1.035),'stop':safe_float(item.get('stop',0)) or round(buy*.975),'id':item.get('id') or int(time.time()*1000),'lastPrice':(get_trade_live_price(code, fallback=True)[0] or buy)})
        holdings=[h for h in holdings if str(h.get('code','')).zfill(6)!=code]; holdings.append(item); write_holdings(holdings); ensure_watch_running()
    elif action=='remove':
        rid=str(data.get('id','')); code=str(data.get('code','')).zfill(6); holdings=[h for h in holdings if str(h.get('id',''))!=rid and str(h.get('code','')).zfill(6)!=code]; write_holdings(holdings)
    elif action=='clear':
        holdings=[]
        write_holdings(holdings)
    elif action=='refresh':
        sync_res = v109_force_sync_holdings(full_sync=True) if 'v109_force_sync_holdings' in globals() else {'holdings': holdings}
        holdings = sync_res.get('holdings', read_holdings())
    return jsonify({'ok':True,'holdings':holdings})
@app.route('/api/server_watch/start',methods=['GET','POST'])
def api_watch_start(): ensure_watch_running(); return jsonify({'ok':True,'running':True,'holdings':len(read_holdings()),'interval':WATCH_INTERVAL})
@app.route('/api/server_watch/stop',methods=['GET','POST'])
def api_watch_stop(): WATCH_STATE['running']=False; return jsonify({'ok':True,'running':False})
@app.route('/api/server_watch/status')
def api_watch_status(): return jsonify({'ok':True,'state':{k:v for k,v in WATCH_STATE.items() if k!='thread'},'holdings':read_holdings(),'interval':WATCH_INTERVAL})
@app.route('/api/live_price/<code>')
def api_live_price(code):
    p, src = get_trade_live_price(code, fallback=True)
    return jsonify({'ok':p>=10,'code':str(code).zfill(6),'price':p,'source':src,'updated':now_kst().strftime('%Y-%m-%d %H:%M:%S')})
@app.route('/api/find_stock')
def api_find_stock():
    q=str(request.args.get('q','')).strip(); code=resolve_code_by_name(q); price=(get_trade_live_price(code, fallback=True)[0] if code else 0); return jsonify({'ok':bool(code),'name':q,'code':code,'price':price})
@app.route('/api/telegram_status')
def api_telegram_status():
    token=os.getenv('TELEGRAM_BOT_TOKEN','').strip(); chat_id=os.getenv('TELEGRAM_CHAT_ID','').strip(); return jsonify({'ok':bool(token and chat_id),'tokenSet':bool(token),'chatIdSet':bool(chat_id)})
@app.route('/api/telegram_test')
def api_telegram_test():
    ok,msg=send_telegram_message('✅ <b>성일의 AI 주식바람</b>\n텔레그램 알림 테스트가 정상 발송되었습니다.\n시간: '+now_kst().strftime('%Y-%m-%d %H:%M:%S')); return jsonify({'ok':ok,'message':msg})
@app.route('/api/telegram_test_page')
def api_telegram_test_page():
    ok,msg=send_telegram_message('✅ <b>성일의 AI 주식바람</b>\n텔레그램 알림 테스트가 정상 발송되었습니다.\n시간: '+now_kst().strftime('%Y-%m-%d %H:%M:%S'))
    title='✅ 텔레그램 테스트 발송 완료' if ok else '⚠️ 텔레그램 테스트 실패'; body='텔레그램 앱에서 메시지를 확인해 주세요.' if ok else str(msg)
    return Response(f"<!doctype html><html lang='ko'><meta name='viewport' content='width=device-width,initial-scale=1'><body style='font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#f3f8ed;padding:30px;color:#263629'><div style='background:white;border-radius:24px;padding:24px;box-shadow:0 10px 30px #0001'><h2>{title}</h2><p>{body}</p><a href='/' style='display:block;background:#5f8d65;color:white;padding:16px;border-radius:16px;text-align:center;text-decoration:none;font-weight:800'>앱으로 돌아가기</a></div></body></html>",mimetype='text/html; charset=utf-8')

@app.route('/api/auto_trade/recommend_settings')
def api_auto_trade_recommend_settings():
    cash = request.args.get("cash", 100000)
    rec = recommend_auto_trade_settings(cash)
    return jsonify({"ok": True, "recommend": rec})

@app.route('/api/auto_trade/apply_recommend_settings', methods=['POST', 'GET'])
def api_auto_trade_apply_recommend_settings():
    cash = request.args.get("cash", None)
    data = request.get_json(force=True, silent=True) or {}
    if cash is None:
        cash = data.get("cash", 100000)

    rec = recommend_auto_trade_settings(cash)
    state = read_trade_state()
    state["max_total_cash"] = rec["max_total_cash"]
    state["max_order_cash"] = rec["max_order_cash"]
    state["cash_buffer"] = rec["cash_buffer"]
    state["max_positions"] = rec.get("max_positions", state.get("max_positions", 3))
    state["min_order_cash"] = rec.get("min_order_cash", state.get("min_order_cash", 50000))
    state["daily_max_loss"] = rec["daily_max_loss"]
    state["cooldown_minutes"] = rec["cooldown_minutes"]
    state["target_rate"] = rec["target_rate"]
    state["stop_rate"] = rec["stop_rate"]
    state["last_status"] = "AI 추천 설정 적용"
    state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    state["last_order_message"] = f"{rec['mode']} 적용: 목표 {rec['target_rate_percent']}%, 손절 {rec['stop_rate_percent']}%, 키움 예수금 기준 1회 진입 상한 {rec['max_order_cash']:,}원, 동시 {rec.get('max_positions',3)}종목"
    write_trade_state(state)
    return jsonify({"ok": True, "recommend": rec, "state": state})

@app.route('/api/kiwoom/cash')
def api_kiwoom_cash_legacy():
    return jsonify({'ok': True, 'cash': get_trade_cash_info(), 'time': now_kst().strftime('%Y-%m-%d %H:%M:%S')})

@app.route('/api/auto_trade/status')
def api_auto_trade_status():
    state = read_trade_state()
    fast = str(request.args.get('fast', '0')).lower() in ['1', 'true', 'yes']
    cash_info = {'ok': None, 'cash': 0, 'source': 'FAST_SKIP', 'message': '빠른 상태조회: 키움 예수금 조회 생략'} if fast else get_trade_cash_info()
    return jsonify({
        'ok': True,
        'state': state,
        'kiwoom_ready': kiwoom_ready(),
        'real_trading_env': KIWOOM_REAL_TRADING,
        'dry_run': KIWOOM_DRY_RUN,
        'market_open': market_is_open(),
        'required_env_keys': ['KIWOOM_APP_KEY', 'KIWOOM_SECRET_KEY', 'KIWOOM_REAL_TRADING', 'KIWOOM_DRY_RUN'],
        'secret_alias_supported': 'KIWOOM_APP_SECRET',
        'price_diff_limit_pct': round(PRICE_DIFF_LIMIT*100, 3),
        'kiwoom_price_required': KIWOOM_PRICE_REQUIRED,
        'auto_buy_in_watch_loop': AUTO_BUY_IN_WATCH_LOOP,
        'auto_rebuy_after_sell': AUTO_REBUY_AFTER_SELL,
        'order_cash_safety_rate': ORDER_CASH_SAFETY_RATE,
        'kiwoom_debug': state.get('last_kiwoom_debug', {}),
        'storage': get_storage_status(),
        'account_cash': cash_info,
        'holding_count': len(read_holdings()),
        'holdings_count': len(read_holdings()),
        'target_rate_percent': round(normalize_rate_input(state.get('target_rate', 0.027), 0.027)*100, 3),
        'profit_guard_percent': round(normalize_rate_input(state.get('profit_guard_rate', 0.012), 0.012)*100, 3),
        'trailing_stop_percent': round(normalize_rate_input(state.get('trailing_stop_rate', 0.011), 0.011)*100, 3),
        'ai_target_raise_enabled': AI_TARGET_RAISE_ENABLED if 'AI_TARGET_RAISE_ENABLED' in globals() else True,
        'max_trades_per_day': int(state.get('max_trades_per_day', 10)),
        'trade_count_today': int(state.get('trade_count_today', 0)),
        'force_exit_time': state.get('force_exit_time', '15:15'),
        'max_positions': int(state.get('max_positions', 3)),
        'min_order_cash': safe_float(state.get('min_order_cash', 50000)),
        'stop_rate_percent': round(normalize_rate_input(state.get('stop_rate', -0.018), -0.018)*100, 3)
    })

@app.route('/api/auto_trade/set', methods=['POST', 'GET'])
def api_auto_trade_set():
    # v121: 버튼 응답속도 개선.
    # POST JSON이 실패하거나 모바일 브라우저에서 지연될 때를 대비해 GET 쿼리도 허용합니다.
    data = request.get_json(force=True, silent=True) or {}
    if not data:
        enabled_q = request.args.get('enabled', request.args.get('auto_trade_enabled', None))
        if enabled_q is not None:
            data['auto_trade_enabled'] = str(enabled_q).lower() in ['1', 'true', 'yes', 'on']
        panic_q = request.args.get('panic_stop', None)
        if panic_q is not None:
            data['panic_stop'] = str(panic_q).lower() in ['1', 'true', 'yes', 'on']
    state = read_trade_state()
    for key in ['auto_trade_enabled', 'panic_stop']:
        if key in data:
            state[key] = bool(data[key])
    for key in ['max_total_cash', 'max_order_cash', 'cash_buffer', 'daily_max_loss', 'cooldown_minutes', 'max_trades_per_day', 'max_positions', 'min_order_cash']:
        if key in data:
            state[key] = safe_float(data[key], state.get(key, TRADE_DEFAULTS.get(key, 0)))
    if 'force_exit_time' in data:
        state['force_exit_time'] = str(data.get('force_exit_time') or state.get('force_exit_time', '15:15'))
    if 'scalp_mode' in data:
        state['scalp_mode'] = bool(data.get('scalp_mode'))

    if 'target_rate' in data:
        state['target_rate'] = normalize_rate_input(data.get('target_rate'), state.get('target_rate', TRADE_DEFAULTS.get('target_rate', 0.027)))
    if 'stop_rate' in data:
        state['stop_rate'] = normalize_rate_input(data.get('stop_rate'), state.get('stop_rate', TRADE_DEFAULTS.get('stop_rate', -0.018)))
    if 'profit_guard_rate' in data:
        state['profit_guard_rate'] = normalize_rate_input(data.get('profit_guard_rate'), state.get('profit_guard_rate', TRADE_DEFAULTS.get('profit_guard_rate', 0.012)))
    if 'trailing_stop_rate' in data:
        state['trailing_stop_rate'] = normalize_rate_input(data.get('trailing_stop_rate'), state.get('trailing_stop_rate', TRADE_DEFAULTS.get('trailing_stop_rate', 0.011)))
    state['last_status'] = '실전 자동매매 ON' if state.get('auto_trade_enabled') else '실전 자동매매 OFF'
    state['last_status_time'] = now_kst().strftime('%Y-%m-%d %H:%M:%S')
    state['last_order_message'] = '버튼 요청이 즉시 반영되었습니다. 잔고/가격 확인은 백그라운드에서 계속 진행합니다.'
    write_trade_state(state)
    if state.get('auto_trade_enabled'):
        try:
            # v121: 감시스레드 시작 때문에 버튼 응답이 늦어지지 않도록 백그라운드 처리
            threading.Thread(target=ensure_watch_running, daemon=True).start()
        except Exception:
            pass
    return jsonify({'ok': True, 'state': state, 'message': state.get('last_order_message')})


@app.route('/api/auto_trade/quick_set', methods=['GET'])
def api_auto_trade_quick_set():
    """
    v123: 모바일 버튼 전용 초고속 ON/OFF API.
    - JSON POST보다 빠른 GET 방식
    - 키움 예수금/잔고/후보조회 절대 실행하지 않음
    - 화면 버튼 상태 저장만 즉시 처리
    """
    try:
        enabled_q = request.args.get('enabled', '0')
        enabled = str(enabled_q).lower() in ['1', 'true', 'yes', 'on']
        state = read_trade_state()
        state['auto_trade_enabled'] = enabled
        if enabled:
            state['panic_stop'] = False
        state['last_status'] = '실전 자동매매 ON' if enabled else '실전 자동매매 OFF'
        state['last_status_time'] = now_kst().strftime('%Y-%m-%d %H:%M:%S')
        state['last_order_message'] = 'v130 빠른 버튼 API로 즉시 반영되었습니다. 키움 실전 정보는 상세창에서 확인할 수 있습니다.'
        write_trade_state(state)
        if enabled:
            try:
                threading.Thread(target=ensure_watch_running, daemon=True).start()
            except Exception:
                pass
        return jsonify({'ok': True, 'fast': True, 'state': state, 'message': state['last_order_message']})
    except Exception as e:
        return jsonify({'ok': False, 'message': str(e), 'state': read_trade_state()}), 200

@app.route('/api/auto_trade/buy_now', methods=['POST', 'GET'])
def api_auto_trade_buy_now():
    # 화면에서 누른 즉시매수는 화면 필터 조건을 그대로 사용합니다.
    # 쿼리 파라미터가 없으면 마지막 화면 후보를 사용합니다.
    args = request.args if request.args else None
    result = auto_buy_best_pick(args=args, use_latest_ui_pick=(args is None))
    return jsonify(safe_json(result))

@app.route('/api/auto_trade/panic_stop', methods=['POST', 'GET'])
def api_auto_trade_panic_stop():
    state = read_trade_state()
    state['auto_trade_enabled'] = False
    state['panic_stop'] = True
    write_trade_state(state)
    try:
        threading.Thread(target=send_telegram_message, args=('🛑 <b>긴급정지 실행</b>\n실전 자동매매를 OFF 했습니다.',), daemon=True).start()
    except Exception:
        pass
    return jsonify({'ok': True, 'state': state, 'message': '긴급정지 완료. 텔레그램은 백그라운드 발송합니다.'})

@app.route('/api/kiwoom_price_test/<code>')
def api_kiwoom_price_test(code):
    p = get_kiwoom_live_price(code)
    state = read_trade_state()
    return jsonify({
        'ok': p >= 10,
        'code': str(code).zfill(6),
        'price': p,
        'debug': state.get('last_kiwoom_debug', {}),
        'kiwoom_ready': kiwoom_ready(),
        'base_url': KIWOOM_BASE_URL
    })

@app.route('/api/v109_dashboard')
def api_v109_dashboard():
    """
    v109 실시간 수익률/후보/상태 통합 대시보드 API.
    기존 화면을 크게 깨지 않고 새 HTS형 UI를 붙일 때 사용할 수 있습니다.
    """
    try:
        sync = str(request.args.get("sync", "0")) == "1"
        refresh = str(request.args.get("refresh", "1")) == "1"
        if sync:
            try:
                sync_kiwoom_holdings_to_local()
            except Exception:
                pass
        holdings = read_holdings()
        if refresh:
            holdings = [check_one_holding(h) for h in holdings]
            write_holdings(holdings)

        total_buy = 0
        total_eval = 0
        for h in holdings:
            qty = safe_float(h.get("qty", 0))
            buy = safe_float(h.get("buyPrice", 0))
            cur = safe_float(h.get("lastPrice", h.get("buyPrice", 0)))
            total_buy += qty * buy
            total_eval += qty * cur

        total_pnl = total_eval - total_buy
        total_rate = (total_pnl / total_buy * 100) if total_buy else 0

        best, picks = best_pick_from_params(read_trade_state().get("latest_ui_args") or {})
        state = read_trade_state()

        return jsonify(safe_json({
            "ok": True,
            "version": "KIWOOM REAL AUTO SCALPING v130_SCROLL_FIX_CACHE_FALLBACK_REALIZED_NOTE",
            "time": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "holding_count": len(holdings),
                "total_buy": round(total_buy),
                "total_eval": round(total_eval),
                "total_pnl": round(total_pnl),
                "total_rate": round(total_rate, 3)
            },
            "holdings": holdings,
            "best_pick": best,
            "top_candidates": picks[:20],
            "trade_state": state,
            "watch_state": {
                "running": WATCH_STATE.get("running"),
                "last_check": WATCH_STATE.get("last_check"),
                "best_code": WATCH_STATE.get("best_code"),
                "best_score": WATCH_STATE.get("best_score")
            },
            "storage": get_storage_status(),
            "kiwoom_ready": kiwoom_ready(),
            "market_open": market_is_open(),
            "dry_run": KIWOOM_DRY_RUN,
            "real_trading_env": KIWOOM_REAL_TRADING
        }))
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500

@app.route('/api/version')
def api_version(): return jsonify({'ok':True,'version':'kiwoom-real-auto-scalping-v109-upgrade','watch_interval':WATCH_INTERVAL,'file':'app_kiwoom_real_auto_scalping_v109_fetch_fix.py','v109_dashboard':'/api/v109_dashboard'})

HTML = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>성일의 AI 주식바람 v123</title><style>
:root{--green:#426a49;--deep:#253528;--cream:#fffdf0;--orange:#f3ad4e;--soft:#eef7e7}*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;background:linear-gradient(180deg,#f7faec,#e6f3e5,#fff7de);color:var(--deep)}.app{max-width:880px;margin:0 auto;padding:22px 18px 80px}.card{background:rgba(255,255,255,.86);border:1px solid rgba(90,120,80,.16);border-radius:28px;padding:24px;margin:18px 0;box-shadow:0 16px 38px rgba(69,94,63,.11)}.hero{padding:26px 4px 8px}.hero h1{font-size:36px;line-height:1.15;margin:0 0 8px;font-weight:950}.hero p{margin:0;color:#667085;font-size:16px;line-height:1.5}.badge{display:inline-flex;gap:6px;align-items:center;border-radius:999px;background:#eaf5df;color:#406044;font-weight:900;padding:8px 12px;margin-bottom:10px}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}label{font-size:16px;font-weight:900;margin:12px 0 6px;display:block}input,select{width:100%;border:1px solid #d8e0cf;border-radius:18px;padding:14px 16px;font-size:18px;background:#fffffb}button{border:0;border-radius:20px;padding:16px 18px;font-size:17px;font-weight:900;background:linear-gradient(135deg,#f6af55,#aad889);color:#2b2b22;cursor:pointer}button.dark{background:#33495b;color:white}button.green{background:#5f9366;color:white}button.brown{background:#96622d;color:white}button.light{background:#eef7e7;color:#426a49}.row{display:flex;gap:10px;flex-wrap:wrap}.pick{border-radius:26px;background:#fffef8;border:1px solid #e4e9d7;padding:20px;box-shadow:0 10px 24px #0000000c}.pick h2{font-size:34px;margin:8px 0}.meta{display:flex;gap:8px;flex-wrap:wrap}.meta span{background:#edf4df;padding:8px 12px;border-radius:999px;font-weight:900}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:16px 0}.metric{background:#fbf8eb;border-radius:18px;padding:14px;text-align:center}.metric small{display:block;color:#667085;margin-bottom:6px}.metric b{font-size:20px}.comment{background:#eef8df;border-radius:18px;padding:14px;line-height:1.55;font-weight:800;color:#416246}.empty{padding:18px;border-radius:20px;background:#fff8df;color:#6b5b3f}.holding{background:white;border-radius:24px;padding:18px;margin:12px 0;border:1px solid #e0ead3}.red{color:#d32525}.blue{color:#2563eb}.muted{color:#667085}.tabs{position:sticky;top:0;z-index:10;background:rgba(250,252,239,.92);backdrop-filter:blur(14px);display:grid;grid-template-columns:repeat(6,1fr);gap:8px;padding:10px 0}.tab{padding:12px 6px;border:1px solid #d9e2ce;background:white;border-radius:999px;text-align:center;font-weight:900;font-size:14px}.tab.active{background:#5f8d65;color:white}.loading-screen{position:fixed;inset:0;background:linear-gradient(180deg,#fff8c8,#e7f6df,#d8ebff);z-index:9999;display:flex;align-items:center;justify-content:center;transition:.7s}.loading-screen.hide{opacity:0;pointer-events:none}.loading-card{width:min(86%,380px);border-radius:34px;background:rgba(255,255,255,.62);padding:34px 24px;text-align:center;box-shadow:0 20px 50px #0002}.loading-title{font-size:32px;font-weight:950;color:#34573a}.bar{height:12px;border-radius:99px;background:white;overflow:hidden;margin-top:18px}.bar span{display:block;height:100%;width:45%;background:linear-gradient(90deg,#f3c56f,#a5d987);animation:move 1.2s infinite}@keyframes move{from{margin-left:-50%}to{margin-left:110%}}.lock{position:fixed;inset:0;background:#f4faed;z-index:8888;display:flex;align-items:center;justify-content:center;padding:24px}.lock.hidden{display:none}.lockbox{max-width:460px;width:100%;background:white;border-radius:30px;padding:28px;box-shadow:0 20px 50px #0001}.statusDetails{margin-top:10px}.statusDetails summary{cursor:pointer;font-weight:950;background:#eef7e7;color:#426a49;border-radius:18px;padding:14px 16px;list-style:none}.statusDetails summary::-webkit-details-marker{display:none}.detailScroll{margin-top:10px;max-height:260px;overflow:auto;-webkit-overflow-scrolling:touch;background:#fffdf4;border-radius:18px;padding:14px 16px;line-height:1.6;border:1px solid #eadfbd}.miniStatus{line-height:1.55}.miniStatus b{font-size:1.05em}.infoGrid{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin:10px 0}.infoItem{background:#fffaf0;border:1px solid #eadfbd;border-radius:14px;padding:10px 12px}.infoItem small{display:block;color:#667085;font-weight:800;margin-bottom:3px}.infoItem b{font-size:17px}.pillOk{display:inline-block;border-radius:999px;background:#eaf7df;color:#2f6b3a;padding:5px 10px;font-weight:950}.pillWarn{display:inline-block;border-radius:999px;background:#fff2c2;color:#7a5200;padding:5px 10px;font-weight:950}.pillBad{display:inline-block;border-radius:999px;background:#ffe1df;color:#aa2a20;padding:5px 10px;font-weight:950}.detailBtn{width:100%;margin:8px 0 10px;background:#eef7e7;color:#426a49}.alertHelp{background:#fff8df;border-radius:18px;padding:14px;line-height:1.6;color:#6b5b3f;margin:10px 0}.recentAlerts{background:#fffdf4;border:1px solid #eadfbd;border-radius:18px;padding:14px;line-height:1.6;margin-top:10px}.guideDetails{margin:8px 0 16px}.guideDetails summary{cursor:pointer;font-weight:950;background:#eef7e7;color:#426a49;border-radius:18px;padding:14px 16px;list-style:none}.guideDetails summary::-webkit-details-marker{display:none}.guideBody{margin-top:10px;background:#fff8df;border-radius:18px;padding:14px 16px;line-height:1.65;color:#6b5b3f}.fieldHint{font-size:.82em;color:#667085;margin-top:5px;line-height:1.45}.inputWrap{margin-bottom:4px}.aiTargetBox{background:#eef7e7;border:1px solid #d8e8cc;border-radius:18px;padding:12px 14px;line-height:1.55;margin-top:10px;color:#426a49;font-weight:800}
@media(max-width:560px){.hero h1{font-size:31px}.grid,.metrics{grid-template-columns:1fr}.app{padding:18px 14px 70px}.tab{font-size:12px}.metrics{grid-template-columns:1fr 1fr}.detailScroll{max-height:220px}}

.quick-money{display:flex;flex-wrap:wrap;gap:10px;margin:10px 0 18px}
.quick-money button{padding:12px 16px;border-radius:18px;border:1px solid rgba(51,80,55,.18);background:#eef7e9;font-size:.9em;font-weight:800;color:#31543a}
.quick-money button.darkmini{background:#32475a;color:white}
.quick-money .hint{width:100%;font-size:.82em;color:#6d7782;margin-top:2px}

</style>
<style>
/* v109: 수동 보유종목 입력 영역 숨김 보조 */
input[placeholder*="종목명 예:"],
input[placeholder*="종목코드 예:"],
input[placeholder*="매수가 예:"],
input[placeholder*="매수금액 예:"],
input[placeholder*="수량 자동계산"],
input[placeholder*="목표가 자동"],
input[placeholder*="손절가 자동"] { display:none !important; }
</style>

</head><body><div id="loading" class="loading-screen"><div class="loading-card"><div style="font-size:58px">🍃</div><div class="loading-title">성일의 AI 주식바람</div><p class="muted">오늘 시장의 흐름을 읽는 중...</p><div class="bar"><span></span></div></div></div><div id="passwordLock" class="lock hidden"><div class="lockbox"><div class="badge">🔐 SECURE ACCESS</div><h1>성일의 AI 주식바람</h1><p class="muted">비밀번호를 입력하면 앱을 사용할 수 있습니다.</p><input id="passwordInput" type="password" placeholder="비밀번호 입력"><button class="green" onclick="login()" style="width:100%;margin-top:12px">로그인</button><p id="loginMessage" class="muted"></p></div></div>
<script>
(function(){
  function killSplash(){
    try{
      var l=document.getElementById('loading');
      if(l){ l.classList.add('hide'); setTimeout(function(){try{l.remove()}catch(e){}},700); }
    }catch(e){}
  }
  window.__v116KillSplash=killSplash;
  setTimeout(killSplash,5000);
})();
</script>
<main class="app"><section class="hero"><div class="badge">🌿 KIWOOM REAL AUTO v131</div><h1>성일의 AI 주식바람</h1><p>키움 REST API 연동 · AI 최종 1종목 자동매수 · 목표/손절 자동매도 · 텔레그램 주문 알림</p></section><div class="tabs"><div class="tab active" onclick="go('filter')">⚙️ 설정</div><div class="tab" onclick="go('best')">⚡ 단타AI</div><div class="tab" onclick="go('watch')">👀 후보</div><div class="tab" onclick="go('holdings')">💼 보유</div><div class="tab" onclick="go('autotrade')">🤖 자동</div><div class="tab" onclick="go('telegram')">✉️ 알림</div></div><section id="filter" class="card"><h2>⚙️ 단타AI 필터 설정</h2><details class="guideDetails" id="filterDetail"><summary>🔎 필터 조건 보기 / 접기</summary><div class="guideBody"><p class="muted">후보 조회 속도를 높이기 위해 이 화면은 <b>KRX 캐시 기준 빠른 조회</b>로 먼저 보여줍니다. 실제 매수 직전에는 키움 현재가와 주문가능금액을 다시 확인합니다.</p><label>종목 가격 구간</label><select id="priceRanges" multiple size="4"><option value="1000-5000">1천~5천원</option><option value="5000-20000" selected>5천~2만원</option><option value="20000-50000" selected>2만~5만원</option><option value="50000-200000" selected>5만~20만원</option></select><div class="fieldHint">너무 저가주는 급등락이 크고, 너무 고가주는 보유수량이 적어질 수 있어 원하는 가격대를 선택합니다.</div><div class="grid"><div><label>내 투자금</label><input id="cash" value="500000"><div class="fieldHint">후보 수량 계산용 참고 금액입니다. 실제 매수금은 키움 주문가능금액으로 최종 계산됩니다.</div></div><div class="quick-money">
<button type="button" onclick="setMoneyFast(1000)">1천원</button>
<button type="button" onclick="setMoneyFast(10000)">1만원</button>
<button type="button" onclick="setMoneyFast(100000)">10만원</button>
<button type="button" onclick="setMoneyFast(1000000)">100만원</button>
<button type="button" class="darkmini" onclick="addMoneyFast(10000)">+1만원</button>
<button type="button" class="darkmini" onclick="addMoneyFast(100000)">+10만원</button>
<button type="button" class="warnmini" onclick="clearMoneyFast()">지우기</button>
<div class="hint">먼저 금액 입력칸을 누른 뒤 버튼을 누르면 해당 칸에 금액이 들어갑니다.</div>
</div><div><label>최소 매수 가능 수량</label><input id="minQty" value="1"><div class="fieldHint">이 수량보다 적게 살 수 있는 고가 종목은 후보에서 제외합니다.</div></div><div><label>최대 당일 등락률(%)</label><input id="maxChange" value="7"><div class="fieldHint">너무 많이 오른 종목의 추격매수 위험을 줄입니다.</div></div><div><label>최소 거래대금(원)</label><input id="minAmount" value="1000000000"><div class="fieldHint">거래대금이 낮으면 체결이 어렵거나 급락 위험이 커질 수 있습니다.</div></div><div class="quick-money">
<button type="button" onclick="setMoneyFast(1000000000)">10억</button>
<button type="button" onclick="setMoneyFast(5000000000)">50억</button>
<button type="button" onclick="setMoneyFast(10000000000)">100억</button>
<button type="button" onclick="setMoneyFast(30000000000)">300억</button>
<button type="button" class="darkmini" onclick="addMoneyFast(1000000000)">+10억</button>
<button type="button" class="warnmini" onclick="clearMoneyFast()">지우기</button>
</div><div><label>최소 AI 점수</label><input id="minScore" value="60"><div class="fieldHint">점수가 높을수록 조건은 까다롭지만 후보 수가 줄어듭니다.</div></div></div></div></details><div class="row" style="margin-top:16px"><button class="green" onclick="loadBest()">필터 적용/새로고침</button><button class="dark" onclick="loadWatch()">다음 단타 후보 보기</button><button class="brown" onclick="testBetterAlert()">텔레그램 테스트 알림</button></div></section><section id="best" class="card"><h2>⚡ AI 단타 최종 후보</h2><div id="bestBox" class="empty">아직 조회하지 않았습니다.</div></section><section id="watch" class="card"><h2>👀 급등 예상 감시 후보</h2><div id="watchBox" class="empty">다음 단타 후보 보기를 누르면 표시됩니다.</div></section><section id="holdings" class="card">
<h2>💼 키움 실보유 자동 동기화</h2>
<p class="muted">
수동 보유종목 등록 기능은 삭제했습니다. 이제 보유탭은 <b>키움증권 실제 잔고</b>만 기준으로 표시합니다.
매수 체결 후 자동으로 새로고침되며, AI 감시·자동매도·텔레그램도 같은 보유목록을 사용합니다.
</p>
<div class="row" style="margin-top:14px">
<button class="green" onclick="v115RefreshHoldings()">키움 실보유 새로고침</button>
<button class="dark" onclick="v115OpenHoldingsApi()">API 직접 확인</button>
<button class="light" onclick="v115ClearViewOnly()">화면만 초기화</button>
</div>
<div id="holdingStatus" class="empty" style="margin-top:14px">키움 실제잔고 확인 전입니다.</div>
<div id="holdingList"></div>
</section>
<section id="autotrade" class="card">
  <h2>🤖 키움 실전 자동매매</h2>
  <details class="guideDetails">
    <summary>📘 실전 자동매매 설명 보기 / 접기</summary>
    <div class="guideBody">
      실전 자동매매는 키움 REST API 환경변수가 설정되어야 동작합니다.<br>
      실제 매수금은 화면의 총투자금이 아니라 <b>키움 예수금/주문가능금액</b>을 기준으로 자동 계산합니다.<br>
      <b>AI 추천 설정</b>은 예수금 기준 1회 진입 상한·하루손실·목표/손절을 자동 계산합니다.<br>
      목표/손절 수익률은 <b>2.5 = +2.5%</b>, <b>-1.8 = -1.8%</b>처럼 입력하면 됩니다.
      <div class="aiTargetBox">🚀 <b>AI 목표가 상향 기능</b><br>기본 목표가에 도달해도 현재가가 강하고 고점 유지 중이면 즉시 매도하지 않고 목표가를 위로 조정한 뒤 트레일링 스탑으로 수익을 보호합니다.</div>
    </div>
  </details>
  <input type="hidden" id="atTotal" value="500000"><input type="hidden" id="atOrder" value="450000"><div class="grid"><div class="inputWrap"><label>하루 최대 손실</label><input id="atLoss" value="-30000" placeholder="예: -30000"><div class="fieldHint">하루 손실이 이 금액 이하가 되면 자동매매를 멈춥니다.</div></div>
    <div class="inputWrap"><label>재진입 금지(분)</label><input id="atCool" value="30" placeholder="예: 30"><div class="fieldHint">같은 종목을 다시 매수하기 전 대기 시간입니다.</div></div>
    <div class="inputWrap"><label>기본 목표 수익률(%)</label><input id="atTarget" value="2.5" placeholder="예: 2.5"><div class="fieldHint">기본 익절 기준입니다. AI 강세 판단 시 목표가를 자동 상향할 수 있습니다.</div></div>
    <div class="inputWrap"><label>손절 수익률(%)</label><input id="atStop" value="-1.8" placeholder="예: -1.8"><div class="fieldHint">손실 제한 기준입니다. 예: -1.8 입력 시 -1.8% 부근에서 방어합니다.</div></div>
  </div>
  <div class="row" style="margin-top:14px">
    <button class="green" onclick="applyAiSettings()">AI 추천 설정 적용</button>
    <button class="light" onclick="manualSettingsGuide()">수동 설정</button>
  </div>
  <div id="aiSettingBox" class="empty" style="margin-top:10px">하루 최대 손실, 목표/손절, 트레일링 조건을 설정하세요. 실제 매수금은 키움증권 실제 주문가능금액 기준으로 자동 계산됩니다.</div>
  <div class="empty" style="margin-top:12px">
    <b>⚡ 스캘핑 AI 엔진</b><br>
    목표는 한 번에 크게 먹는 방식이 아니라 <b>2~5% 수익을 여러 번 안정적으로 누적</b>하는 구조입니다.<br>
    <label style="display:block;margin-top:10px">하루 최대 거래횟수</label><input id="atMaxTrades" value="10">
    <label style="display:block;margin-top:10px">수익 보호 시작(%)</label><input id="atProfitGuard" value="1.2">
    <label style="display:block;margin-top:10px">트레일링 스탑(%)</label><input id="atTrailing" value="1.1">
    <label style="display:block;margin-top:10px">장마감 강제청산 시간</label><input id="atExitTime" value="15:15">
    <div class="muted" style="margin-top:8px">예: +1.2% 이상 수익 발생 후 고점 대비 -1.1% 밀리면 자동매도합니다.</div>
  </div>
  <div class="row" style="margin-top:14px">
    <button class="green" onclick="setAutoTrade(true)">실전 자동매매 ON</button>
    <button class="light" onclick="setAutoTrade(false)">자동매매 OFF</button>
    <button class="brown" onclick="buyNow()">AI 최종 1종목 즉시매수</button>
    <button class="dark" onclick="panicStop()">긴급정지</button><button class="light" onclick="autoTradeStatus()">상태 확인</button><button class="light" onclick="kiwoomPriceTest()">키움 현재가 테스트</button>
  </div>
  <div id="autoTradeBox" class="empty" style="margin-top:14px">자동매매 상태를 확인해 주세요.</div>
  <div id="autoTradeDetailBox" class="empty" style="margin-top:10px">상세 진행내용은 상태 확인 후 클릭해서 볼 수 있습니다.</div>
</section>

<section id="telegram" class="card"><h2>📨 실전 알림센터</h2><div class="alertHelp"><b>이 기능은 무엇인가요?</b><br>매수·매도·손절·목표가 도달·키움 API 오류가 발생하면 텔레그램으로 바로 알려주는 실전 모니터링 알림 기능입니다.<br><span class="muted">앱을 계속 보고 있지 않아도 자동매매 진행상황을 휴대폰 알림으로 확인할 수 있습니다.</span></div><div class="row"><button class="green" onclick="telegramStatus()">🔍 연결확인</button><button class="brown" onclick="telegramTest()">📨 테스트알림</button><button class="dark" onclick="startWatch()">🚀 실전감시 ON</button></div><div id="telegramBox" class="empty" style="margin-top:14px">알림센터 상태를 확인해 주세요.</div><div id="telegramRecentBox" class="recentAlerts"><b>최근 알림</b><br><span class="muted">아직 표시된 알림이 없습니다. 연결확인 또는 테스트알림을 누르면 이곳에 기록됩니다.</span></div></section></main><script>
const $=id=>document.getElementById(id),fmt=n=>Number(n||0).toLocaleString()+"원",num=v=>Number(String(v||"").replace(/[^0-9.-]/g,""))||0;
let activeMoneyInputId="atTotal";
function bindMoneyInputs(){
  ["atTotal","atOrder","cash","minAmount","hAmount","hBuy"].forEach(id=>{
    const el=$(id);
    if(el){
      el.addEventListener("focus",()=>{activeMoneyInputId=id;});
      el.addEventListener("click",()=>{activeMoneyInputId=id;});
      el.addEventListener("touchstart",()=>{activeMoneyInputId=id;},{passive:true});
    }
  });
}
function setMoneyFast(amount){
  const el=$(activeMoneyInputId||"atTotal");
  if(!el){alert("금액을 넣을 입력칸을 먼저 눌러주세요.");return;}
  el.value=Number(amount);
  el.dispatchEvent(new Event("input"));
}
function addMoneyFast(amount){
  const el=$(activeMoneyInputId||"atTotal");
  if(!el){alert("금액을 넣을 입력칸을 먼저 눌러주세요.");return;}
  el.value=(num(el.value)||0)+Number(amount);
  el.dispatchEvent(new Event("input"));
}
function clearMoneyFast(){
  const el=$(activeMoneyInputId||"atTotal");
  if(el){el.value="";el.dispatchEvent(new Event("input"));}
}
function go(id){document.getElementById(id).scrollIntoView({behavior:"smooth"})}function getParams(){return new URLSearchParams({priceRanges:[...$("priceRanges").selectedOptions].map(o=>o.value).join(","),cash:num($("cash").value),minQty:num($("minQty").value),maxChange:num($("maxChange").value),minAmount:num($("minAmount").value),minScore:num($("minScore").value),fast:1})}async function fetchJson(url,opts={}){const c=new AbortController(),timeoutMs=Number(opts.timeoutMs||120000),t=setTimeout(()=>c.abort(),timeoutMs);try{const r=await fetch(url,{...opts,cache:"no-store",headers:{Accept:"application/json",...(opts.headers||{})},signal:c.signal});const txt=await r.text();if(!r.ok){throw new Error(`서버 오류 ${r.status}: ${txt.slice(0,160)}`)}try{return JSON.parse(txt)}catch(e){throw new Error("서버가 JSON이 아닌 응답을 반환했습니다.")}}catch(e){if(e.name==="AbortError") throw new Error("서버 응답 대기 시간이 길어졌습니다. 화면 반영은 유지하고, 5초 후 상태 확인을 눌러 저장 여부를 확인하세요.");throw e}finally{clearTimeout(t)}}function renderPick(p){if(!p)return"<div class='empty'>현재 강한 단타 후보가 부족합니다. 조건 자동완화 캐시를 갱신 중이며, 실제 매수 전에는 키움 현재가로 재검증합니다.</div>";return`<div class="pick"><div class="meta"><span>${p.market}</span><span>${p.code}</span><span>${p.theme}</span><span>AI ${p.score}</span></div><h2>${p.name}</h2><div class="metrics"><div class="metric"><small>현재가</small><b>${fmt(p.price)}</b><br><small>${p.priceSource||"-"}</small></div><div class="metric"><small>당일 흐름</small><b>${p.dayChange}%</b></div><div class="metric"><small>거래대금</small><b>${(p.amount/100000000).toFixed(1)}억</b></div><div class="metric"><small>매수관찰</small><b>${fmt(p.buyZone)}</b></div><div class="metric"><small>목표가</small><b class="red">${fmt(p.target)}</b></div><div class="metric"><small>손절가</small><b class="blue">${fmt(p.stop)}</b></div></div><div class="comment">AI 코멘트: ${p.comment}</div></div>`}async function loadBest(){$("bestBox").innerHTML="조회중...";try{const d=await fetchJson("/api/v131_best_pick_cached?"+getParams().toString(),{timeoutMs:4500});$("bestBox").innerHTML=(d.refreshing?"<div class='empty'>🟡 후보 갱신중... 마지막 정상 후보를 표시합니다.</div>":"")+renderPick(d.pick)}catch(e){$("bestBox").innerHTML="<div class='empty'>🟡 후보 캐시 준비중입니다. 화면은 유지됩니다. 5초 후 상태 확인을 눌러주세요.</div>"}}async function loadWatch(){$("watchBox").innerHTML="조회중...";try{const d=await fetchJson("/api/v131_watch_candidates_cached?"+getParams().toString(),{timeoutMs:4500});$("watchBox").innerHTML=(d.refreshing?"<div class='empty'>🟡 최신 후보 갱신중... 마지막 정상 후보를 유지합니다.</div>":"")+((d.items||[]).map(renderPick).join("")||"<div class='empty'>현재 감시 후보가 부족합니다. 장중 변동성 또는 조건 자동완화 결과를 기다립니다.</div>")}catch(e){$("watchBox").innerHTML="<div class='empty'>🟡 급등 후보 캐시 준비중입니다. 서버가 계산을 마치면 자동 표시됩니다.</div>"}}async function testBetterAlert(){const d=await fetchJson("/api/best_pick/test_alert?"+getParams().toString());alert(d.ok?"텔레그램 후보 알림 발송 완료":(d.message||"발송 실패"))}async function findCode(){const name=$("hName").value.trim();if(!name||$("hCode").value.trim())return;try{const d=await fetchJson("/api/find_stock?q="+encodeURIComponent(name));if(d.ok){$("hCode").value=d.code;if(!$("hBuy").value&&d.price)$("hBuy").value=Math.round(d.price);calcHolding()}}catch(e){}}function calcHolding(){const buy=num($("hBuy").value),amount=num($("hAmount").value);if(buy&&amount&&!$("hQty").value)$("hQty").value=Math.floor(amount/buy);if(buy&&!$("hTarget").value)$("hTarget").value=Math.round(buy*1.035);if(buy&&!$("hStop").value)$("hStop").value=Math.round(buy*.975)}async function addHolding(){await findCode();calcHolding();const item={name:$("hName").value.trim(),code:$("hCode").value.trim(),buyPrice:num($("hBuy").value),buyAmount:num($("hAmount").value),qty:num($("hQty").value),target:num($("hTarget").value),stop:num($("hStop").value)};if(!item.name||!item.code||!item.buyPrice){alert("종목명, 종목코드, 매수가는 필수입니다.");return}await fetchJson("/api/v119_holdings_fast",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"add",item})});await refreshHoldings()}async function refreshHoldings(){try{const d=await fetchJson("/api/v131_holdings_cached?start_sync=1&ts="+Date.now(),{timeoutMs:4500});renderHoldings(d.holdings||[]);if($("holdingStatus")){$("holdingStatus").innerHTML=`${d.message||"키움 실보유 캐시 표시"}<br><span class="muted">최근 정상 동기화: ${d.cacheUpdatedAt||"확인중"} · 백그라운드 갱신 ${d.sync&&d.sync.running?"진행중":"대기"}</span>`;}}catch(e){$("holdingStatus").innerHTML=`🟡 키움 조회는 백그라운드 진행중입니다. 현재 화면은 마지막 정상 보유값을 유지합니다.`;}}async function clearHoldings(){if(!confirm("보유종목을 모두 삭제할까요?"))return;const d=await fetchJson("/api/v119_holdings_fast",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"clear"})});renderHoldings(d.holdings||[])}async function loadHoldings(autoRestore=true){
  // v109 FETCH FIX
  // 초기 화면에서 키움 실보유 동기화(sync=1)와 현재가 갱신(refresh=1)을 동시에 호출하면
  // 모바일/Render 환경에서 20초 이상 걸려 Fetch is aborted가 발생할 수 있습니다.
  // 따라서 1단계는 서버 저장 보유종목만 빠르게 표시하고, 2단계로 백그라운드 갱신을 분리합니다.
  loadStorageStatus();

  let d={holdings:[]};
  try{
    d=await fetchJson("/api/v131_holdings_cached?start_sync=1",{timeoutMs:4500});
  }catch(e){
    $("holdingStatus").innerHTML=`⚠️ 보유종목 조회 실패: ${e.message}`;
    return;
  }

  let list=d.holdings||[];

  if(false && autoRestore && (!list.length)){
    const backup=getBrowserHoldingBackup();
    if(backup.length){
      try{
        await fetchJson("/api/v113_restore_holdings",{
          method:"POST",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify({holdings:backup}),
          timeoutMs:60000
        });
        d=await fetchJson("/api/v131_holdings_cached?start_sync=1",{timeoutMs:4500});
        list=d.holdings||[];
      }catch(e){
        $("holdingStatus").innerHTML=`⚠️ 브라우저 백업 복구 실패: ${e.message}`;
      }
    }
  }

  /* v109: 브라우저 보유목록 백업 사용 안함 */
  renderHoldings(list);

  // 백그라운드 현재가 갱신: 실패해도 화면 전체를 멈추지 않습니다.
  if(list.length){
    setTimeout(async()=>{
      try{
        const rd=await fetchJson("/api/v131_holdings_cached?start_sync=1&ts="+Date.now(),{timeoutMs:4500});
        if(rd.holdings){
          renderHoldings(rd.holdings);
        }
      }catch(e){
        console.log("background holding refresh skipped", e.message);
      }
    },1500);
  }
}

function renderHoldings(list){
  $("holdingStatus").innerHTML=`등록 보유종목 ${list.length}개 감시 중`;
  if(!list.length){
    $("holdingList").innerHTML=`<div class="empty">현재 보유종목이 없습니다. 자동매수 체결 시 이곳에 종목이 자동 등록됩니다.</div>`;
    return;
  }
  $("holdingList").innerHTML=list.map(h=>{
    const cur=Number(h.lastPrice||0), buy=Number(h.buyPrice||0), qty=Number(h.qty||0);
    const buyAmount=Number(h.buyAmount||buy*qty||0);
    const target=Number(h.target||0), stop=Number(h.stop||0);
    const pnl=(cur-buy)*qty;
    const rate=buy?((cur-buy)/buy*100):0;
    const targetGap=cur&&target?((target-cur)/cur*100):0;
    const stopGap=cur&&stop?((cur-stop)/cur*100):0;
    const status=cur>=target&&target?"목표가 도달":cur<=stop&&stop?"손절가 이탈":cur?"감시중":"가격조회중";
    return `<div class="holding">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
        <div>
          <b style="font-size:1.3em">${h.name} (${h.code})</b><br>
          <small>상태: ${status} · 가격출처 ${h.priceSource||"-"} · 최근확인 ${h.lastCheckedAt||"-"}</small>
        </div>
        <button class="light" onclick="removeHolding('${h.id}','${h.code}')">삭제</button>
      </div>

      <div class="grid2" style="margin-top:14px">
        <div class="metric"><small>실제 매수가</small><b>${fmt(buy)}</b></div>
        <div class="metric"><small>실시간 현재가</small><b>${cur?fmt(cur):"조회중"}</b></div>
        <div class="metric"><small>목표가</small><b class="red">${fmt(target)}</b><br><small>${targetGap?`남은거리 ${targetGap.toFixed(2)}%`:""}</small></div>
        <div class="metric"><small>손절가</small><b class="blue">${fmt(stop)}</b><br><small>${stopGap?`여유 ${stopGap.toFixed(2)}%`:""}</small></div>
      </div>

      <div class="empty" style="margin-top:12px">
        수량 <b>${qty.toLocaleString()}주</b> · 매수금액 <b>${buyAmount.toLocaleString()}원</b><br>
        평가손익 <b class="${pnl>=0?'red':'blue'}">${pnl.toLocaleString()}원</b> · 수익률 <b class="${rate>=0?'red':'blue'}">${rate.toFixed(2)}%</b>
      </div>

      <div class="empty" style="margin-top:10px">
        AI 코멘트: ${aiCommentText(cur,buy,target,stop,qty)}
      </div>

      ${h.priceError?`<div class="empty">⚠️ ${h.priceError}</div>`:""}
    </div>`;
  }).join("");
}
function aiCommentText(cur,buy,target,stop,qty){
  if(!cur||!buy) return "현재가 확인 대기 중입니다.";
  const rate=(cur-buy)/buy*100;
  if(stop && cur<=stop) return `손절 기준 도달 구간입니다. 현재 ${rate.toFixed(2)}%로 리스크 차단이 우선입니다.`;
  if(target && cur>=target) return `목표 수익 구간입니다. 현재 ${rate.toFixed(2)}%입니다. 자동 익절 조건을 확인합니다.`;
  if(rate>=1.2) return `수익 보호 구간입니다. 현재 ${rate.toFixed(2)}%로 2~5% 누적 스캘핑 전략에 적합합니다.`;
  if(rate>0) return `초기 수익 구간입니다. 거래량 유지 시 목표가까지 감시합니다.`;
  return `대기/약손실 구간입니다. 손절가 접근 여부를 감시합니다.`;
}
async function removeHolding(id,code){const d=await fetchJson("/api/v119_holdings_fast",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"remove",id,code})});renderHoldings(d.holdings||[])}
function backupHoldingsToBrowser(list){/* v109 disabled */}
function getBrowserHoldingBackup(){return []}
async function restoreHoldingsFromBrowser(){alert("v109부터 브라우저 백업 복구는 사용하지 않습니다. 키움 실제잔고 동기화를 사용하세요."); await refreshHoldings();}
async function loadStorageStatus(){
  const el=$("storageStatus");
  try{
    const d=await fetchJson("/api/storage_status");
    const s=d.storage||{};
    if(el) el.innerHTML=`저장소: ${s.persistent?"✅ 영구저장":"⚠️ 임시저장"} · ${s.path||"-"}<br><span class="muted">${s.message||""}</span>`;
  }catch(e){
    if(el) el.innerHTML=`⚠️ 저장소 확인 실패: ${e.message}<br><span class="muted">보유종목 API는 계속 시도합니다.</span>`;
  }
}

// v109 FIX: 아래 중복 loadHoldings 함수가 기존 복구/백업 로직을 덮어써서
// '저장소 확인 중...'이 계속 남고 브라우저 백업 복구가 실행되지 않던 문제를 제거했습니다.

async function applyAiSettings(){
  const cash=num((document.getElementById("cash")||{}).value)||500000;
  const d=await fetchJson("/api/auto_trade/apply_recommend_settings?cash="+cash,{method:"POST"});
  if(!d.ok){alert("AI 추천 설정 적용 실패");return}
  const r=d.recommend||{};
  $("atTotal").value=r.max_total_cash||cash;
  $("atOrder").value=r.max_order_cash||Math.floor(cash*0.9);
  $("atLoss").value=r.daily_max_loss||-3000;
  $("atCool").value=r.cooldown_minutes||30;
  $("atTarget").value=r.target_rate_percent||2.5;
  $("atStop").value=r.stop_rate_percent||-1.8;
  if($("atMaxPositions")) $("atMaxPositions").value=r.max_positions||3;
  if($("atMinOrder")) $("atMinOrder").value=r.min_order_cash||50000;
  if($("atMaxTrades")) $("atMaxTrades").value=r.max_trades_per_day||10;
  if($("atProfitGuard")) $("atProfitGuard").value=r.profit_guard_rate_percent||1.2;
  if($("atTrailing")) $("atTrailing").value=r.trailing_stop_rate_percent||1.1;
  if($("atExitTime")) $("atExitTime").value=r.force_exit_time||"15:15";
  $("aiSettingBox").innerHTML=`✅ <b>${r.mode}</b> 적용 완료<br>
  키움 예수금 기준 ${Number(r.max_total_cash).toLocaleString()}원 · 1회 진입 상한 ${Number(r.max_order_cash).toLocaleString()}원 · 현금 여유 ${Number(r.cash_buffer).toLocaleString()}원 · 동시 ${Number(r.max_positions||3).toLocaleString()}종목<br>
  목표 +${r.target_rate_percent}% · 손절 ${r.stop_rate_percent}% · 하루 최대손실 ${Number(r.daily_max_loss).toLocaleString()}원 · 재진입금지 ${r.cooldown_minutes}분<br>
  <span class="muted">${r.note}</span>`;
  await autoTradeStatus();
}

function manualSettingsGuide(){
  $("aiSettingBox").innerHTML=`✍️ <b>수동 설정 모드</b><br>
  성일님이 직접 값을 입력한 뒤 <b>실전 자동매매 ON</b>을 누르면 해당 값이 적용됩니다.<br>
  추천 예시: 목표 2.5 / 손절 -1.8 / 실제 매수금은 키움 예수금과 동시 보유 종목수 기준으로 자동 분배`;
}

function kiwoomHealthLabel(d){
  const kd=d.kiwoom_debug||{};
  const st=String(kd.stage||"");
  const msg=String(kd.message||"");
  if(st.includes("ok") || msg.includes("성공")) return `<span class="pillOk">🟢 키움 API 정상</span>`;
  if(st.includes("exception") || st.includes("fail") || msg.includes("실패")) return `<span class="pillBad">🔴 키움 API 확인 필요</span>`;
  return `<span class="pillWarn">🟡 키움 API 대기/미확인</span>`;
}
function renderAutoTradeDashboard(d, openDetail=false){
  const s=d.state||{};
  const ac=d.account_cash||{};
  const cand=s.last_candidate||{};
  const tg=s.last_telegram_status||{};
  const kd=d.kiwoom_debug||{};
  const onText=s.auto_trade_enabled?"ON":"OFF";
  const lastMsg=(s.last_order_message||"-");
  const shortMsg=lastMsg.length>70?lastMsg.slice(0,70)+"...":lastMsg;
  const cashText=ac.source==="FAST_SKIP"?"상세조회 필요":Number(ac.cash||0).toLocaleString()+"원";
  const cashSource=ac.source||"-";
  const holdingCount=d.holding_count ?? d.holdings_count ?? "-";
  const orderable=Number(ac.orderable_cash||ac.cash||0).toLocaleString();
  const deposit=Number(ac.deposit||0).toLocaleString();
  const apiLabel=kiwoomHealthLabel(d);

  $("autoTradeBox").innerHTML=`<div class="miniStatus">
    상태: <b>${onText}</b> · ${apiLabel} · 장중 ${d.market_open?"예":"아니오"}<br>
    키움 주문가능금액: <b>${cashText}</b> (${cashSource})<br>
    최근: <b>${s.last_status||"대기중"}</b> · ${s.last_status_time||"-"}<br>
    <span class="muted">${shortMsg}</span>
  </div>`;

  $("autoTradeDetailBox").innerHTML=`
    <details class="statusDetails" ${openDetail?"open":""}>
      <summary>🔎 상세 진행내용 보기 / 숨기기</summary>
      <div class="detailScroll">
        <button class="detailBtn" onclick="refreshAutoTradeDetail()">🔄 키움 실전 정보 새로고침</button>
        <b>실전 운영 대시보드</b><br>${apiLabel}<br><span class="muted">오늘 실현손익/거래횟수는 앱 자동매매가 기록한 값입니다. MTS에서 직접 매매한 내역까지 키움 일별체결 API로 가져오려면 별도 연동이 필요합니다.</span>
        <div class="infoGrid">
          <div class="infoItem"><small>💰 키움 주문가능금액</small><b>${cashText}</b></div>
          <div class="infoItem"><small>🏦 예수금/추정현금</small><b>${deposit?deposit+"원":"-"}</b></div>
          <div class="infoItem"><small>📦 보유종목</small><b>${holdingCount}종목</b></div>
          <div class="infoItem"><small>📈 오늘 실현손익</small><b>${Number(s.daily_realized_pnl||0).toLocaleString()}원</b><br><small class="muted">앱 자동매매 체결 기준</small></div>
          <div class="infoItem"><small>🔁 오늘 거래횟수</small><b>${d.trade_count_today||0}/${d.max_trades_per_day||10}회</b><br><small class="muted">앱 자동매매 기준</small></div>
          <div class="infoItem"><small>⚙️ 최소진입/동시보유</small><b>${Number(d.min_order_cash||0).toLocaleString()}원 / ${d.max_positions||3}종목</b></div>
        </div>

        <b>자동매매 조건</b><br>
        상태 ${onText} · 키움설정 ${d.kiwoom_ready?"완료":"필요"} · 실전ENV ${d.real_trading_env?"true":"false"} · DRY_RUN ${d.dry_run?"true":"false"} · 장중 ${d.market_open?"예":"아니오"}<br>
        목표/손절: +${d.target_rate_percent||0}% / ${d.stop_rate_percent||0}% · 수익보호 ${d.profit_guard_percent||1.2}% · 트레일링 ${d.trailing_stop_percent||1.1}% · AI 목표상향 ON · 강제청산 ${d.force_exit_time||"15:15"}<br><span class="muted">목표가 도달 후 강세면 목표가를 위로 조정하고, 고점 대비 트레일링 하락 시 매도합니다.</span><br><br>

        <b>최근 진행상태</b><br>
        진행상태: ${s.last_status||"대기중"}<br>
        상태시간: ${s.last_status_time||"-"}<br>
        메시지: ${s.last_order_message||"-"}<br><br>

        <b>최근 AI 후보/주문</b><br>
        ${cand.name?`${cand.name} (${cand.code}) · AI ${cand.score} · 후보가 ${Number(cand.price||0).toLocaleString()}원 · 주문가 ${cand.orderLivePrice?Number(cand.orderLivePrice).toLocaleString()+"원":"-"} ${cand.orderPriceSource||""}`:"-"}<br><br>

        <b>텔레그램</b><br>
        ${tg.ok===true?"발송 성공":tg.ok===false?"발송 실패":"대기"} ${tg.message?`· ${tg.message}`:""}<br><br>

        <b>키움조회</b><br>
        ${kd?`${kd.stage||"-"} · HTTP ${kd.http_status||"-"} · ${kd.message||"-"}`:"-"}<br>
        <span class="muted">주문가능금액이 '상세조회 필요'로 보이면 위의 새로고침 버튼을 누르세요.</span>
      </div>
    </details>`;
}
async function autoTradeStatus(){
  const d=await fetchJson("/api/v131_status_light",{timeoutMs:3000});
  renderAutoTradeDashboard(d,false);
}
async function refreshAutoTradeDetail(){
  const box=$("autoTradeDetailBox");
  if(box){
    box.innerHTML=`<details class="statusDetails" open><summary>🔎 상세 진행내용 보기 / 숨기기</summary><div class="detailScroll">키움 예수금/주문가능금액/최근 API 상태를 조회 중입니다...</div></details>`;
  }
  try{
    const d=await fetchJson("/api/auto_trade/status?fast=0&ts="+Date.now(),{timeoutMs:12000});
    renderAutoTradeDashboard(d,true);
  }catch(e){
    if(box){
      box.innerHTML=`<details class="statusDetails" open><summary>🔎 상세 진행내용 보기 / 숨기기</summary><div class="detailScroll"><b>키움 정보 조회 지연</b><br>${e.message}<br><span class="muted">Render 또는 키움 API가 느릴 수 있습니다. 자동매매 ON/OFF 상태는 이미 저장된 상태일 수 있으니 5초 후 다시 눌러주세요.</span></div></details>`;
    }
  }
}
async function setAutoTrade(on){
  const box=$("autoTradeBox");
  const detail=$("autoTradeDetailBox");

  // v123: 사용자가 누르는 즉시 화면부터 ON/OFF로 바꿉니다.
  // 서버 저장과 키움 확인은 뒤에서 처리하므로 버튼이 멈춘 것처럼 보이지 않습니다.
  if(box){
    box.innerHTML=`상태: <b>${on?"ON":"OFF"}</b> · 화면 즉시 반영<br><span class="muted">서버 저장 중입니다. 키움 잔고/가격 확인은 백그라운드에서 진행됩니다.</span>`;
  }
  if(detail){
    detail.innerHTML=`<details class="statusDetails" open><summary>🔎 상세 진행내용 보기 / 숨기기</summary><div class="detailScroll"><b>최근 진행상태:</b> ${on?"실전 자동매매 ON 화면 반영":"자동매매 OFF 화면 반영"}<br><b>메시지:</b> v130 빠른 버튼 방식으로 요청 전송 중...<br><span class="muted">요청 완료 후 키움 실전 정보는 자동으로 상세창에 갱신됩니다.</span></div></details>`;
  }

  const body={
    auto_trade_enabled:on,
    panic_stop:false,
    max_total_cash:num($("atTotal").value),
    max_order_cash:num($("atOrder").value),
    daily_max_loss:num($("atLoss").value),
    cooldown_minutes:num($("atCool").value),
    target_rate:Number($("atTarget").value||2.5),
    stop_rate:Number($("atStop").value||-1.8),
    max_positions:num($("atMaxPositions")?.value||3),
    min_order_cash:num($("atMinOrder")?.value||50000),
    max_trades_per_day:num($("atMaxTrades")?.value||10),
    profit_guard_rate:Number($("atProfitGuard")?.value||1.2),
    trailing_stop_rate:Number($("atTrailing")?.value||1.1),
    force_exit_time:$("atExitTime")?.value||"15:15",
    scalp_mode:true
  };

  try{
    // 1순위: GET 초고속 저장. 모바일/Render에서 POST JSON보다 훨씬 덜 막힙니다.
    const d=await fetchJson(`/api/auto_trade/quick_set?enabled=${on?1:0}&ts=${Date.now()}`,{method:"GET",timeoutMs:12000});
    const s=d.state||{};
    if(box){
      box.innerHTML=`상태: <b>${s.auto_trade_enabled?"ON":"OFF"}</b> · 빠른 반영 완료<br><span class="muted">${d.message||"저장 완료"}</span>`;
    }
    if(detail){
      detail.innerHTML=`<details class="statusDetails" open><summary>🔎 상세 진행내용 보기 / 숨기기</summary><div class="detailScroll"><b>최근 진행상태:</b> ${s.last_status||"저장 완료"}<br><b>상태시간:</b> ${s.last_status_time||"-"}<br><b>메시지:</b> ${s.last_order_message||d.message||"-"}<br><br><span class="muted">키움 주문가능금액과 API 상태를 이어서 조회합니다...</span></div></details>`;
    }
    setTimeout(()=>refreshAutoTradeDetail().catch(e=>console.log("detail refresh skipped",e.message)),700);

    // 2순위: 상세 설정값은 별도 백그라운드 저장. 실패해도 ON/OFF 자체는 유지합니다.
    fetchJson("/api/auto_trade/set",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body),timeoutMs:15000})
      .then(()=>setTimeout(()=>autoTradeStatus().catch(e=>console.log("status skipped",e.message)),500))
      .catch(e=>console.log("background setting save skipped",e.message));

  }catch(e){
    // v123: 네트워크가 느려도 에러로 끝내지 않고, 상태확인 안내만 표시합니다.
    if(box){
      box.innerHTML=`상태: <b>${on?"ON 화면 반영":"OFF 화면 반영"}</b><br><span class="muted">서버 확인이 지연 중입니다. 5초 후 상태 확인을 누르면 저장 여부와 키움 정보를 다시 보여줍니다.</span>`;
    }
    if(detail){
      detail.innerHTML=`<details class="statusDetails" open><summary>🔎 상세 진행내용 보기 / 숨기기</summary><div class="detailScroll"><b>최근 진행상태:</b> 버튼 화면 반영 완료 / 서버 확인 대기<br><b>메시지:</b> 서버 확인이 지연 중입니다. 화면 상태는 유지됩니다.<br><button class="detailBtn" onclick="autoTradeStatus()">🔄 상태 확인</button><span class="muted">Render 서버가 잠시 느릴 때 발생합니다. 같은 버튼을 여러 번 누르지 말고 5초 후 상태 확인을 눌러주세요.</span></div></details>`;
    }
  }
}
async function buyNow(){
  if(!confirm("현재 화면 필터 기준 AI 최종 1종목을 키움 API로 즉시 매수 시도할까요?\n\n목표/손절은 % 기준입니다. 예: 2.5 = +2.5%, -1.8 = -1.8%")) return;
  const d=await fetchJson("/api/auto_trade/buy_now?"+getParams().toString(),{method:"POST"});
  await autoTradeStatus();
  alert(d.ok?"매수 요청 완료. 텔레그램/HTS 체결 여부를 확인하세요.":"매수 실패/보류: "+(d.message||JSON.stringify(d.order||d)));
}
async function panicStop(){
  await fetchJson("/api/auto_trade/panic_stop",{method:"POST"});
  alert("긴급정지 완료");
  autoTradeStatus();
}

async function kiwoomPriceTest(){
  const code=prompt("키움 현재가 테스트 종목코드 입력", "005930");
  if(!code) return;
  const d=await fetchJson("/api/kiwoom_price_test/"+code);
  await autoTradeStatus();
  alert(d.ok?`키움 현재가 조회 성공: ${Number(d.price).toLocaleString()}원`:`키움 현재가 조회 실패: ${JSON.stringify(d.debug)}`);
}

function addRecentAlert(text){const el=$("telegramRecentBox");if(!el)return;const now=new Date().toLocaleTimeString();el.innerHTML=`<b>최근 알림</b><br>✔ ${now} · ${text}<br>`+(el.innerHTML.replace(/<b>최근 알림<\/b><br>/,"").replace(/<span class="muted">.*?<\/span>/,"")||"");}
async function telegramStatus(){const d=await fetchJson("/api/telegram_status");$("telegramBox").innerHTML=d.ok?"✅ 텔레그램 연결 정상 · 매수/매도/오류 알림을 받을 수 있습니다.":"⚠️ 텔레그램 연결 필요 · Render 환경변수 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID를 확인하세요.";addRecentAlert(d.ok?"텔레그램 연결확인 성공":"텔레그램 연결확인 필요");}
async function telegramTest(){const d=await fetchJson("/api/telegram_test");$("telegramBox").innerHTML=d.ok?"✅ 테스트 알림 발송 완료 · 텔레그램 앱에서 메시지를 확인하세요.":"⚠️ 테스트 실패: "+d.message;addRecentAlert(d.ok?"테스트 알림 발송 완료":"테스트 알림 실패");}
async function startWatch(){const d=await fetchJson("/api/server_watch/start",{method:"POST"});$("telegramBox").innerHTML=`🟢 실전 감시 ON · 보유 ${d.holdings}개 · ${d.interval}초 간격으로 목표/손절/현재가를 감시합니다.`;addRecentAlert(`실전 감시 시작 · 보유 ${d.holdings}개`);}async function login(){const d=await fetchJson("/api/login_check",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:$("passwordInput").value})});if(d.ok){localStorage.setItem("sungil_ai_login_role",d.role);$("passwordLock").classList.add("hidden")}else $("loginMessage").innerText=d.message||"로그인 실패"}function checkLock(){if(!localStorage.getItem("sungil_ai_login_role"))$("passwordLock").classList.remove("hidden")}
(function(){
  function safeEl(id){ try{return document.getElementById(id)}catch(e){return null} }
  const hNameEl=safeEl("hName");
  if(hNameEl) hNameEl.addEventListener("blur",findCode);
  ["hBuy","hAmount"].forEach(id=>{
    const el=safeEl(id);
    if(el) el.addEventListener("input",calcHolding);
  });
  function hideLoadingSafe(){
    try{
      const l=safeEl("loading");
      if(l){
        l.classList.add("hide");
        setTimeout(()=>{try{l.remove()}catch(e){}},700);
      }
    }catch(e){}
  }
  setTimeout(hideLoadingSafe,4500);
  window.addEventListener("load",()=>{
    setTimeout(hideLoadingSafe,3500);
    try{checkLock()}catch(e){}
    try{bindMoneyInputs()}catch(e){}
    try{loadBest()}catch(e){}
    try{if(typeof v115RefreshHoldings==="function") v115RefreshHoldings(); else loadHoldings()}catch(e){}
    try{telegramStatus()}catch(e){}
    try{autoTradeStatus()}catch(e){}
    try{setInterval(()=>{try{if(typeof v115RefreshHoldings==="function") v115RefreshHoldings(); else loadHoldings()}catch(e){}},20000)}catch(e){}
    try{setInterval(()=>{try{autoTradeStatus()}catch(e){}},10000)}catch(e){}
  });
})();



/* ============================================================
   v131 AUTO_RELAX_CANDIDATE_CACHE_FIX - UI PATCH
   - 자동 갱신 중 사용자가 보고 있는 위치를 보존
   - 사용자가 스크롤/터치 중이면 자동 새로고침을 건너뜀
   - 후보 조회는 마지막 정상 후보를 유지하고 백그라운드 갱신
============================================================ */
(function(){
  let v130LastUserAction = 0;
  function markUser(){ v130LastUserAction = Date.now(); }
  ['scroll','touchstart','touchmove','wheel'].forEach(ev=>window.addEventListener(ev, markUser, {passive:true}));
  function userReading(){ return window.scrollY > 220 && (Date.now() - v130LastUserAction) < 15000; }
  function preserveScrollRun(fn){
    const y = window.scrollY;
    const r = Promise.resolve().then(fn);
    return r.finally(()=>{ if(userReading()) window.scrollTo(0, y); });
  }
  const nativeSetInterval = window.setInterval.bind(window);
  window.setInterval = function(fn, delay){
    if(delay===20000 || delay===10000){
      return nativeSetInterval(function(){
        if(userReading()) return;
        return preserveScrollRun(fn);
      }, delay);
    }
    return nativeSetInterval(fn, delay);
  };

  if(typeof loadBest === 'function'){
    const oldLoadBest = loadBest;
    loadBest = async function(){
      const box = document.getElementById('bestBox');
      const prev = box ? box.innerHTML : '';
      if(box && prev && !prev.includes('아직 조회')) box.insertAdjacentHTML('afterbegin', "<div class='empty'>🟡 후보 갱신중... 기존 후보를 유지합니다.</div>");
      try{ await preserveScrollRun(()=>oldLoadBest()); }
      catch(e){ if(box && prev) box.innerHTML = prev; }
    };
  }
  if(typeof loadWatch === 'function'){
    const oldLoadWatch = loadWatch;
    loadWatch = async function(){
      const box = document.getElementById('watchBox');
      const prev = box ? box.innerHTML : '';
      if(box && prev && !prev.includes('다음 단타')) box.insertAdjacentHTML('afterbegin', "<div class='empty'>🟡 감시 후보 갱신중... 기존 후보를 유지합니다.</div>");
      try{ await preserveScrollRun(()=>oldLoadWatch()); }
      catch(e){ if(box && prev) box.innerHTML = prev; }
    };
  }
  if(typeof refreshHoldings === 'function'){
    const oldRefreshHoldings = refreshHoldings;
    refreshHoldings = async function(){ if(userReading()) return; return preserveScrollRun(()=>oldRefreshHoldings()); };
  }
  if(typeof loadHoldings === 'function'){
    const oldLoadHoldings = loadHoldings;
    loadHoldings = async function(autoRestore=true){ if(userReading() && autoRestore!==false) return; return preserveScrollRun(()=>oldLoadHoldings(autoRestore)); };
  }
  if(typeof autoTradeStatus === 'function'){
    const oldAutoTradeStatus = autoTradeStatus;
    autoTradeStatus = async function(){ if(userReading()) return; return preserveScrollRun(()=>oldAutoTradeStatus()); };
  }
})();

</script></body></html>'''

try:
    print_render_public_ip_on_startup()
except Exception as _ip_startup_error:
    print("RENDER_PUBLIC_IP_STARTUP_ERROR =", _ip_startup_error, flush=True)

try:
    @app.route("/api/v109_cash_check")
    def api_v109_cash_check():
        try:
            cash1 = get_kiwoom_account_cash() if "get_kiwoom_account_cash" in globals() else {}
        except Exception as e:
            cash1 = {"ok": False, "message": str(e)}
        try:
            cash2 = kiwoom_get_account_cash(force=True) if "kiwoom_get_account_cash" in globals() else {}
        except Exception as e:
            cash2 = {"ok": False, "message": str(e)}
        return jsonify({
            "ok": bool(cash1.get("ok") or cash2.get("ok")),
            "version": "v113",
            "primary_cash": cash1,
            "secondary_cash": cash2,
            "message": "v109: qry_tp 필수 파라미터 포함 후 키움 예수금/주문가능금액 조회 결과입니다."
        })
except Exception:
    pass

def v109_env_status():
    app_key_ok = bool(os.getenv("KIWOOM_APP_KEY", "").strip())
    secret_ok = bool((os.getenv("KIWOOM_SECRET_KEY", "") or os.getenv("KIWOOM_APP_SECRET", "") or os.getenv("KIWOOM_SECRET", "")).strip())
    return {
        "KIWOOM_APP_KEY": app_key_ok,
        "KIWOOM_SECRET_KEY_OR_APP_SECRET": secret_ok,
        "KIWOOM_REAL_TRADING": os.getenv("KIWOOM_REAL_TRADING", "").lower() == "true",
        "KIWOOM_DRY_RUN": os.getenv("KIWOOM_DRY_RUN", "true").lower() == "true",
        "TELEGRAM_BOT_TOKEN": bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip()),
        "TELEGRAM_CHAT_ID": bool(os.getenv("TELEGRAM_CHAT_ID", "").strip()),
        "KIWOOM_BASE_URL": KIWOOM_BASE_URL
    }

def v109_token_test():
    try:
        try:
            _TOKEN_CACHE["token"] = ""
            _TOKEN_CACHE["expires"] = 0
        except Exception:
            pass
        token = kiwoom_get_token()
        return {
            "ok": bool(token),
            "message": "키움 토큰 발급 성공" if token else "키움 토큰 없음",
            "token_prefix": (token[:8] + "...") if token else ""
        }
    except Exception as e:
        return {
            "ok": False,
            "message": str(e),
            "help": "토큰 실패 시 Render IP 등록, App Key/Secret, 영웅문S# 추가인증 상태를 확인하세요."
        }

def v109_price_test(code="005930"):
    code = str(code or "005930").zfill(6)
    try:
        p = get_kiwoom_live_price(code)
        dbg = read_trade_state().get("last_kiwoom_debug", {})
        return {
            "ok": bool(p and p >= 10),
            "code": code,
            "price": p,
            "debug": dbg,
            "message": "키움 현재가 조회 성공" if p and p >= 10 else "키움 현재가 조회 실패"
        }
    except Exception as e:
        dbg = read_trade_state().get("last_kiwoom_debug", {})
        return {
            "ok": False,
            "code": code,
            "price": 0,
            "debug": dbg,
            "message": str(e)
        }

def v109_cash_test():
    results = {}
    try:
        if "get_kiwoom_account_cash" in globals():
            results["get_kiwoom_account_cash"] = get_kiwoom_account_cash()
    except Exception as e:
        results["get_kiwoom_account_cash"] = {"ok": False, "message": str(e)}

    try:
        if "kiwoom_get_account_cash" in globals():
            results["kiwoom_get_account_cash"] = kiwoom_get_account_cash(force=True)
    except Exception as e:
        results["kiwoom_get_account_cash"] = {"ok": False, "message": str(e)}

    ok = False
    orderable_cash = 0
    for v in results.values():
        if isinstance(v, dict):
            ok = ok or bool(v.get("ok"))
            orderable_cash = max(
                orderable_cash,
                safe_float(v.get("cash", 0), 0),
                safe_float(v.get("orderable_cash", 0), 0),
                safe_float(v.get("kiwoom_orderable_cash", 0), 0)
            )

    return {
        "ok": ok,
        "orderable_cash": int(orderable_cash),
        "results": results,
        "message": "키움 예수금/주문가능금액 조회 성공" if ok else "키움 예수금/주문가능금액 조회 실패"
    }

def v109_kiwoom_diagnosis(code="005930"):
    try:
        ip_info = get_render_public_ip(force=True) if "get_render_public_ip" in globals() else {"ok": False, "message": "render ip function missing"}
    except Exception as e:
        ip_info = {"ok": False, "message": str(e)}

    env = v109_env_status()
    token = v109_token_test()
    price = v109_price_test(code)
    cash = v109_cash_test()

    final_ok = bool(env.get("KIWOOM_APP_KEY") and env.get("KIWOOM_SECRET_KEY_OR_APP_SECRET") and token.get("ok") and price.get("ok") and cash.get("ok"))

    if not final_ok:
        guide = [
            "1) /api/render_ip 의 Render 공인 IP가 키움 APP KEY 관리 화면에 등록되어 있는지 확인",
            "2) Render 환경변수 KIWOOM_APP_KEY 와 KIWOOM_APP_SECRET 또는 KIWOOM_SECRET_KEY 확인",
            "3) 키움 OpenAPI에서 App Key/Secret을 재발급했다면 Render 환경변수도 새 값으로 교체",
            "4) 영웅문S# 보안/인증에서 추가인증 또는 단말기 지정 상태 확인",
            "5) Render 재배포 후 IP가 바뀌었으면 새 IP를 키움에 추가 등록"
        ]
    else:
        guide = ["키움 인증/현재가/예수금 조회가 정상입니다."]

    return {
        "ok": final_ok,
        "version": "v113",
        "render_ip": ip_info,
        "env": env,
        "token": token,
        "price": price,
        "cash": cash,
        "guide": guide,
        "checked_at": now_kst().strftime("%Y-%m-%d %H:%M:%S")
    }

try:
    @app.route("/api/v109_kiwoom_diag")
    def api_v109_kiwoom_diag():
        code = request.args.get("code", "005930")
        return jsonify(v109_kiwoom_diagnosis(code))
except Exception:
    pass

try:
    @app.route("/api/v109_price_test")
    def api_v109_price_test():
        code = request.args.get("code", "005930")
        return jsonify(v109_price_test(code))
except Exception:
    pass

try:
    @app.route("/api/v109_cash_test")
    def api_v109_cash_test():
        return jsonify(v109_cash_test())
except Exception:
    pass

def v109_normalize_real_holding(h):
    """
    키움 잔고 응답을 앱 보유종목 표준 구조로 정규화합니다.
    """
    h = dict(h or {})
    code = str(h.get("code") or h.get("stk_cd") or h.get("pdno") or h.get("종목코드") or "").replace("A", "").strip().zfill(6)
    name = str(h.get("name") or h.get("stk_nm") or h.get("prdt_name") or h.get("종목명") or code).strip()

    qty = safe_float(
        h.get("qty", h.get("rmnd_qty", h.get("hldg_qty", h.get("보유수량", h.get("잔고수량", 0))))),
        0
    )
    buy = safe_float(
        h.get("buyPrice", h.get("avg_prc", h.get("pchs_avg_pric", h.get("매입평균가", h.get("평균단가", 0))))),
        0
    )
    cur = safe_float(h.get("lastPrice", h.get("current_price", h.get("cur_prc", 0))), 0)
    src = h.get("priceSource", "KIWOOM_ACCOUNT")

    if code and code != "000000":
        try:
            live, live_src = get_trade_live_price(code, fallback=True)
            if live >= 10:
                cur = live
                src = live_src
        except Exception:
            pass

    if cur <= 0:
        cur = buy

    state = read_trade_state()
    target_rate = normalize_rate_input(state.get("target_rate", 0.027), 0.027)
    stop_rate = normalize_rate_input(state.get("stop_rate", -0.018), -0.018)

    target = safe_float(h.get("target", 0), 0)
    stop = safe_float(h.get("stop", 0), 0)

    if target <= 0:
        target = round(buy * (1 + target_rate)) if buy else round(cur * (1 + target_rate))
    if stop <= 0:
        stop = round(buy * (1 + stop_rate)) if buy else round(cur * (1 + stop_rate))

    buy_amount = buy * qty
    eval_amount = cur * qty
    pnl = eval_amount - buy_amount if buy and qty and cur else 0
    rate = ((cur - buy) / buy * 100) if buy and cur else 0

    return {
        "id": int(time.time() * 1000),
        "name": name,
        "code": code,
        "buyPrice": round(buy),
        "buyAmount": round(buy_amount),
        "qty": int(qty),
        "target": round(target),
        "stop": round(stop),
        "lastPrice": round(cur),
        "priceSource": src,
        "autoTrade": True,
        "fromKiwoomAccount": True,
        "createdAt": h.get("createdAt") or now_kst().strftime("%Y-%m-%d %H:%M:%S"),
        "lastCheckedAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
        "highPrice": max(safe_float(h.get("highPrice", 0), 0), cur),
        "evalAmount": round(eval_amount),
        "profitAmount": round(pnl),
        "profitRate": round(rate, 2),
        "holdingStatus": v94_holding_status(rate, cur, target, stop) if "v94_holding_status" in globals() else "감시중",
        "aiComment": ai_comment(cur, buy, target, stop, qty),
        "syncSource": "KIWOOM_FORCE_SYNC_V109",
        "updatedBy": "v109"
    }

def v109_get_kiwoom_real_holdings_safe():
    """
    키움 실제잔고 조회를 안전하게 수행합니다.
    기존 kiwoom_get_account_holdings()를 우선 사용합니다.
    """
    try:
        res = kiwoom_get_account_holdings()
        if res.get("ok") and isinstance(res.get("holdings"), list):
            return {"ok": True, "holdings": res.get("holdings", []), "raw": res}
        return {"ok": False, "holdings": [], "raw": res, "message": res.get("message", "키움 실잔고 조회 실패")}
    except Exception as e:
        return {"ok": False, "holdings": [], "message": str(e)}

def v109_force_sync_holdings(full_sync=True):
    """
    v109 핵심:
    키움 실제잔고를 앱 보유종목의 기준으로 삼아 강제 동기화합니다.

    full_sync=True:
    - 키움에 있는 종목만 앱에 남김
    - 앱에만 있고 키움에 없는 종목은 제거
    - 키움 수량/매입가/현재가로 덮어쓰기

    full_sync=False:
    - 키움 종목은 덮어쓰기/추가
    - 앱에만 있는 종목은 유지
    """
    real = v109_get_kiwoom_real_holdings_safe()
    if not real.get("ok"):
        state = read_trade_state()
        state["last_status"] = "키움 실잔고 강제동기화 실패"
        state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        state["last_order_message"] = str(real.get("message", real.get("raw", "")))[:500]
        write_trade_state(state)
        return {
            "ok": False,
            "message": "키움 실잔고 조회 실패",
            "detail": real,
            "local_holdings": read_holdings()
        }

    real_items = []
    for h in real.get("holdings", []):
        try:
            nh = v109_normalize_real_holding(h)
            if nh.get("code") and nh.get("code") != "000000" and safe_float(nh.get("qty", 0), 0) > 0:
                real_items.append(nh)
        except Exception as e:
            print("v109 normalize holding error:", e)

    real_map = {str(h.get("code", "")).zfill(6): h for h in real_items}

    if full_sync:
        final_items = list(real_map.values())
    else:
        local = read_holdings()
        merged = []
        used = set()
        for lh in local:
            code = str(lh.get("code", "")).zfill(6)
            if code in real_map:
                merged.append(real_map[code])
                used.add(code)
            else:
                merged.append(lh)
        for code, rh in real_map.items():
            if code not in used:
                merged.append(rh)
        final_items = merged

    write_holdings(final_items)

    state = read_trade_state()
    state["last_status"] = "키움 실잔고 강제동기화 완료"
    state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    state["last_order_message"] = f"키움 실제잔고 {len(real_items)}개를 앱 보유종목에 반영했습니다. full_sync={full_sync}"
    write_trade_state(state)

    return {
        "ok": True,
        "version": "v113",
        "full_sync": full_sync,
        "count": len(final_items),
        "holdings": final_items,
        "message": "키움 실제잔고 기준으로 앱 보유종목을 강제 동기화했습니다."
    }

def sync_kiwoom_holdings_to_local():
    return v109_force_sync_holdings(full_sync=False).get("holdings", read_holdings())

try:
    # [v109 duplicate route disabled] @app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
    def api_v109_force_sync_holdings_dup2():
        full = str(request.args.get("full", "1")).lower() not in ["0", "false", "no"]
        return jsonify(v109_force_sync_holdings(full_sync=full))
except Exception:
    pass

try:
    # [v109 duplicate route disabled] @app.route("/api/v109_holdings")
    def api_v109_holdings_dup2():
        refresh = str(request.args.get("refresh", "0")).lower() in ["1", "true", "yes"]
        if refresh:
            return jsonify(v109_force_sync_holdings(full_sync=True))
        items = v94_get_enriched_holdings() if "v94_get_enriched_holdings" in globals() else read_holdings()
        return jsonify({"ok": True, "version": "v113", "holdings": items})
except Exception:
    pass

def v109_clean_code(raw):
    s = str(raw or "").strip().replace("A", "")
    s = re.sub(r"[^0-9]", "", s)
    return s.zfill(6) if s else ""

def v109_num(v, default=0):
    try:
        if v is None:
            return default
        if isinstance(v, str):
            v = v.replace(",", "").replace("+", "").strip()
        return abs(safe_float(v, default))
    except Exception:
        return default

def v109_find_holding_lists(obj):
    """
    키움 잔고 응답 내부의 보유종목 리스트를 재귀적으로 탐색합니다.
    현금/예수금 리스트를 보유종목으로 오인하지 않도록 종목코드와 수량 필드가 있는 dict만 사용합니다.
    """
    lists = []

    def walk(x):
        if isinstance(x, list):
            if any(isinstance(i, dict) for i in x):
                lists.append(x)
            for i in x:
                walk(i)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)

    walk(obj)
    return lists

def parse_kiwoom_holdings(data):
    """
    v109 override:
    키움 실제잔고 파싱을 강화합니다.
    - 다양한 리스트 구조 재귀 탐색
    - 다양한 종목코드/종목명/보유수량/평균단가 필드명 지원
    - 같은 종목이 여러 리스트에 중복 등장하면 실제 보유수량이 큰 항목 우선
    """
    if not isinstance(data, dict):
        return []

    code_keys = [
        "stk_cd", "pdno", "code", "isu_cd", "종목코드", "단축코드", "stock_code"
    ]
    name_keys = [
        "stk_nm", "prdt_name", "name", "종목명", "상품명", "stock_name"
    ]
    qty_keys = [
        "rmnd_qty", "hldg_qty", "hold_qty", "qty", "보유수량", "잔고수량",
        "tot_qty", "ord_psbl_qty", "trde_able_qty", "매도가능수량"
    ]
    buy_keys = [
        "avg_prc", "pchs_avg_pric", "pchs_avg_prc", "buyPrice", "매입평균가",
        "평균단가", "매입단가", "avg_price", "pchs_pric"
    ]
    cur_keys = [
        "cur_prc", "now_pric", "current_price", "lastPrice", "현재가", "평가가격"
    ]

    def get_first(item, keys):
        for k in keys:
            if k in item and item.get(k) not in [None, ""]:
                return item.get(k)
        return None

    by_code = {}
    for arr in v109_find_holding_lists(data):
        for item in arr:
            if not isinstance(item, dict):
                continue

            code = v109_clean_code(get_first(item, code_keys))
            if not code or code == "000000":
                continue

            qty = v109_num(get_first(item, qty_keys), 0)
            if qty <= 0:
                continue

            name = str(get_first(item, name_keys) or code).strip()
            buy = v109_num(get_first(item, buy_keys), 0)
            cur = v109_num(get_first(item, cur_keys), 0)

            # 현재가 없으면 키움/네이버 현재가 조회, 그래도 없으면 평균단가 사용
            src = "ACCOUNT"
            if cur <= 0:
                try:
                    live, live_src = get_trade_live_price(code, fallback=True)
                    if live >= 10:
                        cur = live
                        src = live_src
                except Exception:
                    pass
            if cur <= 0:
                cur = buy

            state = read_trade_state()
            target_rate = normalize_rate_input(state.get("target_rate", 0.027), 0.027)
            stop_rate = normalize_rate_input(state.get("stop_rate", -0.018), -0.018)

            holding = {
                "id": int(time.time() * 1000) + len(by_code),
                "name": name,
                "code": code,
                "buyPrice": round(buy),
                "buyAmount": round(buy * qty),
                "qty": int(qty),
                "target": round(buy * (1 + target_rate)) if buy else round(cur * (1 + target_rate)),
                "stop": round(buy * (1 + stop_rate)) if buy else round(cur * (1 + stop_rate)),
                "lastPrice": round(cur),
                "priceSource": src,
                "autoTrade": True,
                "fromKiwoomAccount": True,
                "createdAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
                "lastCheckedAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
                "highPrice": round(cur),
                "syncSource": "KIWOOM_REAL_BALANCE_V109",
                "updatedBy": "v109"
            }

            # 같은 코드가 여러 곳에서 나오면 수량이 큰 값 우선
            old = by_code.get(code)
            if old is None or safe_float(holding.get("qty", 0)) >= safe_float(old.get("qty", 0)):
                by_code[code] = holding

    return list(by_code.values())

def kiwoom_get_account_holdings():
    """
    v109 override:
    보유잔고 조회는 예수금 조회용 qry_tp를 강제하지 않습니다.
    여러 계좌 TR을 시도하고, 실제 보유종목이 있는 응답만 사용합니다.
    """
    if not kiwoom_ready():
        return {"ok": False, "message": "키움 환경변수 미설정", "holdings": []}

    endpoints = [
        ("/api/dostk/acnt", "kt00018", {}),
        ("/api/dostk/acnt", "kt00004", {}),
        ("/api/dostk/acnt", "kt00005", {}),
        ("/api/dostk/acnt", "kt00001", {"qry_tp": os.getenv("KIWOOM_CASH_QRY_TP", "3")}),
    ]

    last_error = ""
    last_raw = None

    for path, api_id, body in endpoints:
        try:
            token = kiwoom_get_token()
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "authorization": "Bearer " + token,
                "cont-yn": "N",
                "next-key": "",
                "api-id": api_id
            }
            r = requests.post(KIWOOM_BASE_URL + path, json=body, headers=headers, timeout=10)
            try:
                data = r.json() if r.text else {}
            except Exception:
                data = {"raw": r.text[:2000]}

            last_raw = data
            holdings = parse_kiwoom_holdings(data)

            if r.status_code == 200 and holdings:
                update_kiwoom_debug("holdings_ok", "", r.status_code, f"키움 실제잔고 {len(holdings)}개 조회 성공", {"api_id": api_id, "count": len(holdings)})
                return {"ok": True, "api_id": api_id, "holdings": holdings, "raw": data}

            msg = data.get("return_msg") if isinstance(data, dict) else str(data)
            last_error = f"{api_id}: {msg or str(data)[:500]}"
            update_kiwoom_debug("holdings_try_empty", "", r.status_code, last_error, data)

        except Exception as e:
            last_error = str(e)
            update_kiwoom_debug("holdings_exception", "", 0, last_error)

    return {"ok": False, "message": last_error or "키움 실제잔고 조회 실패 또는 보유종목 없음", "holdings": [], "raw": last_raw}

def v109_force_sync_holdings(full_sync=True):
    """
    앱 보유목록을 키움 실제잔고 기준으로 완전 동기화합니다.

    full_sync=True:
    - 키움에 없는 종목은 앱에서 제거
    - 키움에 있는 종목은 수량/평균단가/현재가로 덮어쓰기
    """
    res = kiwoom_get_account_holdings()

    if not res.get("ok"):
        state = read_trade_state()
        state["last_status"] = "키움 실제잔고 동기화 실패"
        state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        state["last_order_message"] = str(res.get("message", ""))[:500]
        write_trade_state(state)
        return {
            "ok": False,
            "version": "v113",
            "message": "키움 실제잔고 조회 실패",
            "detail": res,
            "holdings": read_holdings()
        }

    real_items = res.get("holdings", [])

    # 상세 손익/상태 보강
    final_items = []
    for h in real_items:
        try:
            if "v94_enrich_holding" in globals():
                final_items.append(v94_enrich_holding(h))
            else:
                final_items.append(h)
        except Exception:
            final_items.append(h)

    # full sync: 무조건 키움 실제잔고만 저장
    if full_sync:
        write_holdings(final_items)
    else:
        # 병합 모드가 필요할 때만 사용
        by_code = {str(h.get("code", "")).zfill(6): h for h in read_holdings()}
        for h in final_items:
            by_code[str(h.get("code", "")).zfill(6)] = h
        write_holdings(list(by_code.values()))
        final_items = list(by_code.values())

    state = read_trade_state()
    state["last_status"] = "키움 실제잔고 full sync 완료"
    state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    state["last_order_message"] = f"키움 실제잔고 {len(real_items)}개 기준으로 앱 보유목록을 덮어썼습니다."
    write_trade_state(state)

    return {
        "ok": True,
        "version": "v113",
        "full_sync": full_sync,
        "api_id": res.get("api_id"),
        "count": len(final_items),
        "holdings": final_items,
        "message": "키움 실제잔고 기준으로 앱 보유종목을 완전 동기화했습니다."
    }

def sync_kiwoom_holdings_to_local():
    return v109_force_sync_holdings(full_sync=True).get("holdings", read_holdings())

try:
    # [v109 duplicate route disabled] @app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
    def api_v109_force_sync_holdings_dup2_dup2():
        full = str(request.args.get("full", "1")).lower() not in ["0", "false", "no"]
        return jsonify(v109_force_sync_holdings(full_sync=full))
except Exception:
    pass

try:
    # [v109 duplicate route disabled] @app.route("/api/v109_holdings")
    def api_v109_holdings_dup2_dup2():
        refresh = str(request.args.get("refresh", "0")).lower() in ["1", "true", "yes"]
        if refresh:
            return jsonify(v109_force_sync_holdings(full_sync=True))
        items = read_holdings()
        return jsonify({"ok": True, "version": "v113", "holdings": items})
except Exception:
    pass

def v109_code(raw):
    s = str(raw or "").strip().replace("A", "")
    s = re.sub(r"[^0-9]", "", s)
    return s.zfill(6) if s else ""

def v109_num(v, default=0):
    try:
        if v is None:
            return default
        if isinstance(v, str):
            v = v.replace(",", "").replace("+", "").replace("-", "").strip()
        return abs(safe_float(v, default))
    except Exception:
        return default

def v109_deep_lists(obj):
    found = []
    def walk(x):
        if isinstance(x, list):
            if any(isinstance(i, dict) for i in x):
                found.append(x)
            for i in x:
                walk(i)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
    walk(obj)
    return found

def parse_kiwoom_holdings(data):
    if not isinstance(data, dict):
        return []

    code_keys = ["stk_cd", "pdno", "code", "isu_cd", "종목코드", "단축코드", "stock_code"]
    name_keys = ["stk_nm", "prdt_name", "name", "종목명", "상품명", "stock_name"]
    qty_keys = ["rmnd_qty", "hldg_qty", "hold_qty", "qty", "보유수량", "잔고수량", "tot_qty", "매도가능수량", "ord_psbl_qty", "trde_able_qty"]
    buy_keys = ["avg_prc", "pchs_avg_pric", "pchs_avg_prc", "buyPrice", "매입평균가", "평균단가", "매입단가", "avg_price", "pchs_pric"]
    cur_keys = ["cur_prc", "now_pric", "current_price", "lastPrice", "현재가", "평가가격"]

    def first(d, keys):
        for k in keys:
            if k in d and d.get(k) not in [None, ""]:
                return d.get(k)
        return None

    by_code = {}
    for arr in v109_deep_lists(data):
        for item in arr:
            if not isinstance(item, dict):
                continue
            code = v109_code(first(item, code_keys))
            if not code or code == "000000":
                continue

            qty = v109_num(first(item, qty_keys), 0)
            if qty <= 0:
                continue

            name = str(first(item, name_keys) or code).strip()
            buy = v109_num(first(item, buy_keys), 0)
            cur = v109_num(first(item, cur_keys), 0)
            src = "KIWOOM_ACCOUNT"

            if cur <= 0:
                try:
                    live, live_src = get_trade_live_price(code, fallback=True)
                    if live >= 10:
                        cur = live
                        src = live_src
                except Exception:
                    pass
            if cur <= 0:
                cur = buy

            state = read_trade_state()
            target_rate = normalize_rate_input(state.get("target_rate", 0.027), 0.027)
            stop_rate = normalize_rate_input(state.get("stop_rate", -0.018), -0.018)
            target = round(buy * (1 + target_rate)) if buy else round(cur * (1 + target_rate))
            stop = round(buy * (1 + stop_rate)) if buy else round(cur * (1 + stop_rate))

            buy_amount = buy * qty
            eval_amount = cur * qty
            pnl = eval_amount - buy_amount if buy and qty and cur else 0
            prate = ((cur - buy) / buy * 100) if buy and cur else 0

            h = {
                "id": int(time.time() * 1000) + len(by_code),
                "name": name,
                "code": code,
                "buyPrice": round(buy),
                "buyAmount": round(buy_amount),
                "qty": int(qty),
                "target": target,
                "stop": stop,
                "lastPrice": round(cur),
                "priceSource": src,
                "autoTrade": True,
                "fromKiwoomAccount": True,
                "createdAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
                "lastCheckedAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
                "highPrice": round(cur),
                "evalAmount": round(eval_amount),
                "profitAmount": round(pnl),
                "profitRate": round(prate, 2),
                "holdingStatus": "감시중",
                "aiComment": ai_comment(cur, buy, target, stop, qty),
                "syncSource": "KIWOOM_REAL_BALANCE_V109",
                "updatedBy": "v109"
            }

            old = by_code.get(code)
            if old is None or h["qty"] >= safe_int(old.get("qty", 0)):
                by_code[code] = h

    return list(by_code.values())

def kiwoom_get_account_holdings():
    if not kiwoom_ready():
        return {"ok": False, "message": "키움 환경변수 미설정", "holdings": []}

    endpoints = [
        ("/api/dostk/acnt", "kt00018", {}),
        ("/api/dostk/acnt", "kt00004", {}),
        ("/api/dostk/acnt", "kt00005", {}),
        ("/api/dostk/acnt", "kt00001", {"qry_tp": os.getenv("KIWOOM_CASH_QRY_TP", "3")}),
    ]

    last_error = ""
    last_raw = None

    for path, api_id, body in endpoints:
        try:
            token = kiwoom_get_token()
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "authorization": "Bearer " + token,
                "cont-yn": "N",
                "next-key": "",
                "api-id": api_id
            }
            r = requests.post(KIWOOM_BASE_URL + path, json=body, headers=headers, timeout=10)
            try:
                data = r.json() if r.text else {}
            except Exception:
                data = {"raw": r.text[:2000]}

            last_raw = data
            holdings = parse_kiwoom_holdings(data)

            if r.status_code == 200 and holdings:
                update_kiwoom_debug("holdings_ok", "", r.status_code, f"키움 실제잔고 {len(holdings)}개 조회 성공", {"api_id": api_id, "count": len(holdings)})
                return {"ok": True, "api_id": api_id, "holdings": holdings, "raw": data}

            msg = data.get("return_msg") if isinstance(data, dict) else str(data)
            last_error = f"{api_id}: {msg or '보유종목 파싱 결과 없음'}"
            update_kiwoom_debug("holdings_empty", "", r.status_code, last_error, data)

        except Exception as e:
            last_error = str(e)
            update_kiwoom_debug("holdings_exception", "", 0, last_error)

    return {"ok": False, "message": last_error or "키움 실제잔고 조회 실패", "holdings": [], "raw": last_raw}

def v109_force_sync_holdings(full_sync=True):
    res = kiwoom_get_account_holdings()
    if not res.get("ok"):
        state = read_trade_state()
        state["last_status"] = "키움 실제잔고 동기화 실패"
        state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        state["last_order_message"] = str(res.get("message", ""))[:500]
        write_trade_state(state)
        return {"ok": False, "version": "v113", "message": "키움 실제잔고 조회 실패", "detail": res, "holdings": read_holdings()}

    real_items = res.get("holdings", [])
    write_holdings(real_items)

    state = read_trade_state()
    state["last_status"] = "키움 실제잔고 full sync 완료"
    state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    state["last_order_message"] = f"키움 실제잔고 {len(real_items)}개 기준으로 앱 보유목록을 덮어썼습니다."
    write_trade_state(state)

    return {"ok": True, "version": "v113", "api_id": res.get("api_id"), "full_sync": True, "count": len(real_items), "holdings": real_items, "message": "키움 실제잔고 기준으로 앱 보유종목을 완전 동기화했습니다."}

def sync_kiwoom_holdings_to_local():
    return v109_force_sync_holdings(full_sync=True).get("holdings", read_holdings())

def api_v109_force_sync_holdings_dup2():
    return jsonify(v109_force_sync_holdings(full_sync=True))

def api_v109_holdings_dup2():
    refresh = str(request.args.get("refresh", "0")).lower() in ["1", "true", "yes"]
    if refresh:
        return jsonify(v109_force_sync_holdings(full_sync=True))
    return jsonify({"ok": True, "version": "v113", "holdings": read_holdings()})

def api_server_holdings_v109():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        action = data.get("action", "")
        if action in ["refresh", "force_refresh", "sync", "kiwoom_sync"]:
            return jsonify(v109_force_sync_holdings(full_sync=True))
        if action == "clear":
            write_holdings([])
            return jsonify({"ok": True, "holdings": [], "message": "앱 로컬 보유종목을 비웠습니다."})
        if action == "delete":
            code = v109_code(data.get("code"))
            items = [h for h in read_holdings() if v109_code(h.get("code")) != code]
            write_holdings(items)
            return jsonify({"ok": True, "holdings": items})
        return jsonify({"ok": True, "holdings": read_holdings()})

    if str(request.args.get("refresh", "0")).lower() in ["1", "true", "yes"] or str(request.args.get("sync", "0")).lower() in ["1", "true", "yes"]:
        return jsonify(v109_force_sync_holdings(full_sync=True))
    return jsonify({"ok": True, "holdings": read_holdings(), "storage": get_storage_status() if "get_storage_status" in globals() else {}})

def api_v109_force_sync_holdings_final():
    fn = globals().get("v109_force_sync_holdings") or globals().get("v100_force_sync_holdings") or globals().get("v99_force_sync_holdings") or globals().get("v98_force_sync_holdings")
    if fn:
        return jsonify(fn(full_sync=True))
    if "kiwoom_get_account_holdings" in globals():
        res = kiwoom_get_account_holdings()
        if res.get("ok"):
            write_holdings(res.get("holdings", []))
            return jsonify({"ok": True, "version": "v113", "holdings": res.get("holdings", []), "message": "키움 실제잔고 기준 동기화 완료"})
    return jsonify({"ok": False, "version": "v113", "message": "force sync function not found", "holdings": read_holdings()})

def api_v109_holdings_final():
    refresh = str(request.args.get("refresh", "0")).lower() in ["1", "true", "yes"]
    if refresh:
        return api_v109_force_sync_holdings_final()
    return jsonify({"ok": True, "version": "v113", "holdings": read_holdings()})

def api_server_holdings_v109_final():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        action = data.get("action", "")
        if action in ["refresh", "force_refresh", "sync", "kiwoom_sync"]:
            return api_v109_force_sync_holdings_final()
        if action == "clear":
            write_holdings([])
            return jsonify({"ok": True, "holdings": [], "message": "앱 로컬 보유종목을 비웠습니다."})
        if action == "delete":
            code = str(data.get("code", "")).replace("A", "").zfill(6)
            items = [h for h in read_holdings() if str(h.get("code", "")).replace("A", "").zfill(6) != code]
            write_holdings(items)
            return jsonify({"ok": True, "holdings": items})
    if str(request.args.get("refresh", "0")).lower() in ["1", "true", "yes"] or str(request.args.get("sync", "0")).lower() in ["1", "true", "yes"]:
        return api_v109_force_sync_holdings_final()
    return jsonify({"ok": True, "holdings": read_holdings(), "storage": get_storage_status() if "get_storage_status" in globals() else {}})

def v109_force_sync_holdings(full_sync=True):
    """
    키움 실제잔고를 서버 보유목록의 유일한 기준으로 사용합니다.
    성공하면 read_holdings() 결과도 키움 실제잔고로 완전히 교체됩니다.
    """
    # 최신 강제동기화 함수 우선 사용
    for fn_name in ["v100_force_sync_holdings", "v99_force_sync_holdings", "v98_force_sync_holdings"]:
        fn = globals().get(fn_name)
        if fn:
            try:
                res = fn(full_sync=True)
                if isinstance(res, dict) and res.get("ok"):
                    items = res.get("holdings", [])
                    write_holdings(items)
                    res["version"] = "v109"
                    res["storage_policy"] = "KIWOOM_REAL_BALANCE_ONLY"
                    res["message"] = "v109: 키움 실제잔고 기준으로 서버 보유목록을 완전 동기화했습니다."
                    return res
            except Exception as e:
                last_error = str(e)

    # 직접 키움 실제잔고 조회
    try:
        res = kiwoom_get_account_holdings()
        if res.get("ok"):
            items = res.get("holdings", [])
            write_holdings(items)
            return {
                "ok": True,
                "version": "v113",
                "holdings": items,
                "count": len(items),
                "storage_policy": "KIWOOM_REAL_BALANCE_ONLY",
                "message": "v109: 키움 실제잔고를 직접 조회하여 서버 보유목록을 덮어썼습니다."
            }
        return {
            "ok": False,
            "version": "v113",
            "message": "키움 실제잔고 조회 실패",
            "detail": res,
            "holdings": read_holdings()
        }
    except Exception as e:
        return {
            "ok": False,
            "version": "v113",
            "message": str(e),
            "last_error": locals().get("last_error", ""),
            "holdings": read_holdings()
        }

def api_v109_force_sync_holdings_final():
    return jsonify(v109_force_sync_holdings(full_sync=True))

def api_v109_holdings_final():
    # 기본값 refresh=1: 화면 진입 시 항상 키움 실제잔고를 우선합니다.
    refresh = str(request.args.get("refresh", "1")).lower() not in ["0", "false", "no"]
    if refresh:
        return jsonify(v109_force_sync_holdings(full_sync=True))
    return jsonify({"ok": True, "version": "v113", "holdings": read_holdings()})

def api_server_holdings_v109_final():
    """
    보유 탭 전용 API.
    GET/POST 모두 기본적으로 키움 실제잔고 full sync를 수행합니다.
    녹십자홀딩스 같은 과거 로컬 종목이 다시 표시되는 것을 막습니다.
    """
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        action = data.get("action", "")
        if action == "clear":
            write_holdings([])
            return jsonify({"ok": True, "version": "v113", "holdings": [], "message": "앱 로컬 보유목록 초기화 완료. 키움 동기화 시 실제잔고로 복구됩니다."})
        if action == "delete":
            code = str(data.get("code", "")).replace("A", "").zfill(6)
            items = [h for h in read_holdings() if str(h.get("code", "")).replace("A", "").zfill(6) != code]
            write_holdings(items)
            return jsonify({"ok": True, "version": "v113", "holdings": items})
        return jsonify(v109_force_sync_holdings(full_sync=True))

    return jsonify(v109_force_sync_holdings(full_sync=True))

_SELL_GUARD_SKIP = {}

def v109_code(raw):
    s = str(raw or "").strip().replace("A", "")
    s = re.sub(r"[^0-9]", "", s)
    return s.zfill(6) if s else ""

def v109_get_real_holding_codes():
    """
    키움 실제잔고를 조회하고 실제 보유 종목코드 set과 holdings를 반환합니다.
    """
    try:
        # v102/v100 force sync를 우선 사용해서 서버 목록까지 갱신
        for fn_name in ["v102_force_sync_holdings", "v100_force_sync_holdings", "v99_force_sync_holdings"]:
            fn = globals().get(fn_name)
            if fn:
                res = fn(full_sync=True)
                if isinstance(res, dict) and res.get("ok"):
                    items = res.get("holdings", [])
                    codes = set(v109_code(h.get("code")) for h in items if v109_code(h.get("code")) and safe_float(h.get("qty", 0), 0) > 0)
                    return codes, items, res

        res = kiwoom_get_account_holdings()
        if res.get("ok"):
            items = res.get("holdings", [])
            write_holdings(items)
            codes = set(v109_code(h.get("code")) for h in items if v109_code(h.get("code")) and safe_float(h.get("qty", 0), 0) > 0)
            return codes, items, res

    except Exception as e:
        return set(), read_holdings(), {"ok": False, "message": str(e)}

    return set(), read_holdings(), {"ok": False, "message": "키움 실제잔고 조회 실패"}

def v109_purge_not_real_holdings(reason="키움 실제잔고에 없음"):
    """
    앱 보유목록에서 키움 실제잔고에 없는 종목 제거.
    """
    real_codes, real_items, res = v109_get_real_holding_codes()
    if not real_codes and not res.get("ok"):
        return {
            "ok": False,
            "message": "실제잔고 조회 실패로 purge 보류",
            "detail": res,
            "holdings": read_holdings()
        }

    # force sync 성공 시 이미 real_items만 저장하는 게 원칙.
    clean = []
    removed = []
    for h in read_holdings():
        code = v109_code(h.get("code"))
        if code in real_codes:
            clean.append(h)
        else:
            removed.append({"code": code, "name": h.get("name"), "reason": reason})

    # 더 안전하게 키움 실제잔고 items로 최종 저장
    if real_items:
        write_holdings(real_items)
        clean = real_items
    else:
        write_holdings(clean)

    state = read_trade_state()
    state["last_status"] = "v109 실제잔고 기준 보유목록 정리"
    state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    state["last_order_message"] = f"키움 실제잔고에 없는 종목 {len(removed)}개 제거"
    write_trade_state(state)

    return {
        "ok": True,
        "version": "v113",
        "real_codes": sorted(list(real_codes)),
        "removed": removed,
        "holdings": clean,
        "message": "키움 실제잔고 기준으로 보유목록을 정리했습니다."
    }

def v109_mark_sell_skip(code, name="", reason="매도가능수량 0"):
    code = v109_code(code)
    if not code:
        return
    _SELL_GUARD_SKIP[code] = {
        "name": name,
        "reason": reason,
        "time": time.time(),
        "time_text": now_kst().strftime("%Y-%m-%d %H:%M:%S")
    }

def v109_should_skip_sell(code):
    code = v109_code(code)
    info = _SELL_GUARD_SKIP.get(code)
    if not info:
        return False
    # 30분 동안 동일 오류 반복 방지
    return time.time() - safe_float(info.get("time", 0), 0) < 1800

def v109_remove_holding_if_not_real_or_sellable_zero(code, name="", reason="매도가능수량 0"):
    """
    키움 주문에서 매도가능수량 0이 나오면 실제 보유가 아닌 것으로 간주하고 앱 보유목록에서 제거.
    """
    code = v109_code(code)
    v109_mark_sell_skip(code, name, reason)

    items = []
    removed = []
    for h in read_holdings():
        hcode = v109_code(h.get("code"))
        if hcode == code:
            removed.append(h)
        else:
            items.append(h)
    write_holdings(items)

    state = read_trade_state()
    state["last_status"] = "실제 미보유 종목 자동 제거"
    state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    state["last_order_message"] = f"{name or code} 제거: {reason}"
    write_trade_state(state)

    return {
        "ok": True,
        "version": "v113",
        "removed": removed,
        "holdings": items,
        "message": f"{name or code}는 매도가능수량 0으로 앱 보유목록에서 제거했습니다."
    }

def v109_is_sellable_holding(h):
    """
    자동매도 대상인지 확인.
    키움 실제잔고에 없는 종목은 대상에서 제외하고 제거.
    """
    code = v109_code(h.get("code"))
    name = h.get("name", code)

    if not code:
        return False, "종목코드 없음"

    if v109_should_skip_sell(code):
        return False, "최근 매도가능수량 0 오류로 임시 제외"

    real_codes, real_items, res = v109_get_real_holding_codes()
    if res.get("ok") and code not in real_codes:
        v109_remove_holding_if_not_real_or_sellable_zero(code, name, "키움 실제잔고에 없는 종목")
        return False, "키움 실제잔고에 없는 종목"

    # 수량도 실제잔고 기준으로 보정
    if res.get("ok"):
        for rh in real_items:
            if v109_code(rh.get("code")) == code:
                if safe_float(rh.get("qty", 0), 0) <= 0:
                    v109_remove_holding_if_not_real_or_sellable_zero(code, name, "실제 보유수량 0")
                    return False, "실제 보유수량 0"
                return True, "OK"

    return True, "OK"

def v109_force_sync_holdings(full_sync=True):
    return v109_purge_not_real_holdings("v109 force sync")

def api_v109_force_sync_holdings_final():
    return jsonify(v109_force_sync_holdings(full_sync=True))

def api_v109_holdings_final():
    refresh = str(request.args.get("refresh", "1")).lower() not in ["0", "false", "no"]
    if refresh:
        return jsonify(v109_force_sync_holdings(full_sync=True))
    return jsonify({"ok": True, "version": "v113", "holdings": read_holdings()})

def api_server_holdings_v109_final():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        action = data.get("action", "")
        if action in ["refresh", "force_refresh", "sync", "kiwoom_sync", ""]:
            return jsonify(v109_force_sync_holdings(full_sync=True))
        if action == "clear":
            write_holdings([])
            return jsonify({"ok": True, "version": "v113", "holdings": [], "message": "앱 로컬 보유목록 초기화 완료"})
        if action == "delete":
            code = v109_code(data.get("code"))
            items = [h for h in read_holdings() if v109_code(h.get("code")) != code]
            write_holdings(items)
            return jsonify({"ok": True, "version": "v113", "holdings": items})
        return jsonify(v109_force_sync_holdings(full_sync=True))

    return jsonify(v109_force_sync_holdings(full_sync=True))

@app.route("/api/v109_purge_fake_holdings", methods=["GET", "POST"])
def api_v109_purge_fake_holdings():
    return jsonify(v109_purge_not_real_holdings("수동 정리 요청"))

HOLDINGS_FILE = str(BASE_DIR / "sungil_holdings_v109_real_balance.json")
SELL_GUARD_FILE = str(BASE_DIR / "sungil_sell_guard_v109.json")

def v109_code(raw):
    s = str(raw or "").strip().replace("A", "")
    s = re.sub(r"[^0-9]", "", s)
    return s.zfill(6) if s else ""

def v109_num(v, default=0):
    try:
        if v is None:
            return default
        if isinstance(v, str):
            v = v.replace(",", "").replace("+", "").replace("-", "").strip()
        return abs(safe_float(v, default))
    except Exception:
        return default

def v109_deep_lists(obj):
    found = []
    def walk(x):
        if isinstance(x, list):
            if any(isinstance(i, dict) for i in x):
                found.append(x)
            for i in x:
                walk(i)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
    walk(obj)
    return found

def parse_kiwoom_holdings(data):
    """
    v109 override: 키움 실제잔고 파싱 전용.
    예수금/주문가능금액 응답을 보유종목으로 오인하지 않고,
    종목코드 + 보유수량이 있는 항목만 보유종목으로 인정합니다.
    """
    if not isinstance(data, dict):
        return []

    code_keys = ["stk_cd", "pdno", "code", "isu_cd", "종목코드", "단축코드", "stock_code"]
    name_keys = ["stk_nm", "prdt_name", "name", "종목명", "상품명", "stock_name"]
    qty_keys = ["rmnd_qty", "hldg_qty", "hold_qty", "qty", "보유수량", "잔고수량", "tot_qty", "매도가능수량", "ord_psbl_qty", "trde_able_qty"]
    sellable_keys = ["ord_psbl_qty", "trde_able_qty", "매도가능수량", "sellable_qty"]
    buy_keys = ["avg_prc", "pchs_avg_pric", "pchs_avg_prc", "buyPrice", "매입평균가", "평균단가", "매입단가", "avg_price", "pchs_pric"]
    cur_keys = ["cur_prc", "now_pric", "current_price", "lastPrice", "현재가", "평가가격"]

    def first(d, keys):
        for k in keys:
            if k in d and d.get(k) not in [None, ""]:
                return d.get(k)
        return None

    by_code = {}
    for arr in v109_deep_lists(data):
        for item in arr:
            if not isinstance(item, dict):
                continue

            code = v109_code(first(item, code_keys))
            if not code or code == "000000":
                continue

            qty = v109_num(first(item, qty_keys), 0)
            if qty <= 0:
                continue

            name = str(first(item, name_keys) or code).strip()
            buy = v109_num(first(item, buy_keys), 0)
            cur = v109_num(first(item, cur_keys), 0)
            sellable = v109_num(first(item, sellable_keys), qty)

            price_src = "KIWOOM_ACCOUNT"
            if cur <= 0:
                try:
                    live, live_src = get_trade_live_price(code, fallback=True)
                    if live >= 10:
                        cur = live
                        price_src = live_src
                except Exception:
                    pass
            if cur <= 0:
                cur = buy

            state = read_trade_state()
            target_rate = normalize_rate_input(state.get("target_rate", 0.027), 0.027)
            stop_rate = normalize_rate_input(state.get("stop_rate", -0.018), -0.018)
            target = round(buy * (1 + target_rate)) if buy else round(cur * (1 + target_rate))
            stop = round(buy * (1 + stop_rate)) if buy else round(cur * (1 + stop_rate))

            buy_amount = buy * qty
            eval_amount = cur * qty
            pnl = eval_amount - buy_amount if buy and qty and cur else 0
            prate = ((cur - buy) / buy * 100) if buy and cur else 0

            h = {
                "id": int(time.time() * 1000) + len(by_code),
                "name": name,
                "code": code,
                "buyPrice": round(buy),
                "buyAmount": round(buy_amount),
                "qty": int(qty),
                "sellableQty": int(sellable),
                "target": target,
                "stop": stop,
                "lastPrice": round(cur),
                "priceSource": price_src,
                "autoTrade": True,
                "fromKiwoomAccount": True,
                "createdAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
                "lastCheckedAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
                "highPrice": round(cur),
                "evalAmount": round(eval_amount),
                "profitAmount": round(pnl),
                "profitRate": round(prate, 2),
                "holdingStatus": "감시중",
                "aiComment": ai_comment(cur, buy, target, stop, qty),
                "syncSource": "KIWOOM_REAL_BALANCE_V109",
                "updatedBy": "v109"
            }

            old = by_code.get(code)
            if old is None or h["qty"] >= safe_int(old.get("qty", 0)):
                by_code[code] = h

    return list(by_code.values())

def kiwoom_get_account_holdings():
    """
    v109 override: 키움 실제잔고 조회.
    보유잔고 조회용 TR만 우선 사용하고, 보유종목 파싱이 성공한 경우만 ok=True.
    """
    if not kiwoom_ready():
        return {"ok": False, "message": "키움 환경변수 미설정", "holdings": []}

    endpoints = [
        ("/api/dostk/acnt", "kt00018", {}),
        ("/api/dostk/acnt", "kt00004", {}),
        ("/api/dostk/acnt", "kt00005", {}),
    ]

    last_error = ""
    last_raw = None

    for path, api_id, body in endpoints:
        try:
            token = kiwoom_get_token()
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "authorization": "Bearer " + token,
                "cont-yn": "N",
                "next-key": "",
                "api-id": api_id
            }
            r = requests.post(KIWOOM_BASE_URL + path, json=body, headers=headers, timeout=10)
            try:
                data = r.json() if r.text else {}
            except Exception:
                data = {"raw": r.text[:2000]}

            last_raw = data
            holdings = parse_kiwoom_holdings(data)

            if r.status_code == 200 and holdings:
                update_kiwoom_debug("holdings_ok", "", r.status_code, f"키움 실제잔고 {len(holdings)}개 조회 성공", {"api_id": api_id, "count": len(holdings)})
                return {"ok": True, "api_id": api_id, "holdings": holdings, "raw": data}

            msg = data.get("return_msg") if isinstance(data, dict) else str(data)
            last_error = f"{api_id}: {msg or '보유종목 파싱 결과 없음'}"
            update_kiwoom_debug("holdings_empty", "", r.status_code, last_error, data)

        except Exception as e:
            last_error = str(e)
            update_kiwoom_debug("holdings_exception", "", 0, last_error)

    # 보유종목이 0개일 수도 있으므로 raw가 정상이고 명시적으로 보유 없음이면 빈 목록 저장 가능
    return {"ok": False, "message": last_error or "키움 실제잔고 조회 실패", "holdings": [], "raw": last_raw}

def v109_force_sync_holdings(full_sync=True):
    """
    키움 실제잔고를 앱 보유목록의 유일한 기준으로 사용합니다.
    """
    res = kiwoom_get_account_holdings()
    if res.get("ok"):
        items = res.get("holdings", [])
        write_holdings(items)
        state = read_trade_state()
        state["last_status"] = "v109 키움 실제잔고 full sync 완료"
        state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        state["last_order_message"] = f"키움 실제잔고 {len(items)}개 기준으로 보유목록 갱신"
        write_trade_state(state)
        return {
            "ok": True,
            "version": "v113",
            "api_id": res.get("api_id"),
            "count": len(items),
            "holdings": items,
            "storage_file": HOLDINGS_FILE,
            "message": "v109: 키움 실제잔고 기준으로 앱 보유목록을 갱신했습니다."
        }

    # 조회 실패 시 과거 가짜 종목으로 매도하지 않도록 자동매도 루프에서는 사용 금지
    return {
        "ok": False,
        "version": "v113",
        "message": "키움 실제잔고 조회 실패. 자동매도/보유목록 갱신 보류",
        "detail": res,
        "holdings": read_holdings(),
        "storage_file": HOLDINGS_FILE
    }

def v109_real_map():
    res = v109_force_sync_holdings(full_sync=True)
    if not res.get("ok"):
        return {}, res
    mp = {}
    for h in res.get("holdings", []):
        code = v109_code(h.get("code"))
        if code and safe_float(h.get("qty", 0), 0) > 0:
            mp[code] = h
    return mp, res

def v109_load_sell_guard():
    try:
        if os.path.exists(SELL_GUARD_FILE):
            with open(SELL_GUARD_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                return d if isinstance(d, dict) else {}
    except Exception:
        pass
    return {}

def v109_save_sell_guard(d):
    try:
        with open(SELL_GUARD_FILE, "w", encoding="utf-8") as f:
            json.dump(d or {}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def v109_guarded_recent(code, reason="", seconds=3600):
    code = v109_code(code)
    d = v109_load_sell_guard()
    rec = d.get(code)
    if not rec:
        return False
    return time.time() - safe_float(rec.get("time", 0), 0) < seconds

def v109_mark_guard(code, name="", reason=""):
    code = v109_code(code)
    d = v109_load_sell_guard()
    d[code] = {"name": name, "reason": reason, "time": time.time(), "time_text": now_kst().strftime("%Y-%m-%d %H:%M:%S")}
    v109_save_sell_guard(d)

def v109_remove_local_holding(code, name="", reason=""):
    code = v109_code(code)
    items = []
    removed = []
    for h in read_holdings():
        if v109_code(h.get("code")) == code:
            removed.append(h)
        else:
            items.append(h)
    write_holdings(items)
    v109_mark_guard(code, name, reason)
    state = read_trade_state()
    state["last_status"] = "v109 실제 미보유 종목 제거"
    state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    state["last_order_message"] = f"{name or code} 제거: {reason}"
    write_trade_state(state)
    return removed

def auto_sell_holding(kind, h, cur):
    """
    v109 override:
    실제 키움잔고에 없는 종목은 절대 매도 주문/텔레그램 실패 알림을 보내지 않습니다.
    장종료/매도가능수량 0 오류도 반복 알림하지 않습니다.
    """
    h = normalize_holding(dict(h or {}))
    code = v109_code(h.get("code"))
    name = h.get("name", code)

    # 장 종료 후에는 주문 자체를 보내지 않음. 기존에는 장종료 실패 알림이 반복됨.
    if not market_is_open():
        update_trade_status("자동매도 보류", f"장중이 아니어서 {name} 자동매도 보류")
        return False

    real, res = v109_real_map()
    if res.get("ok"):
        if code not in real:
            v109_remove_local_holding(code, name, "키움 실제잔고에 없는 종목")
            return False
        rh = real[code]
        h.update(rh)
    else:
        update_trade_status("자동매도 보류", "키움 실제잔고 조회 실패로 자동매도 보류")
        return False

    qty = int(safe_float(h.get("sellableQty", h.get("qty", 0)), 0))
    if qty <= 0:
        v109_remove_local_holding(code, name, "매도가능수량 0")
        return False

    state = read_trade_state()
    if not state.get("auto_trade_enabled") or not h.get("autoTrade"):
        send_holding_alert(kind, h, cur)
        return False

    # 최근 동일 오류가 있으면 반복 방지
    if v109_guarded_recent(code, "sell_guard", 3600):
        return False

    order = kiwoom_order("sell", code, qty, price=0, order_type="market")
    buy = safe_float(h.get("buyPrice", 0))
    pnl = (cur - buy) * qty if buy and qty else 0
    rate = ((cur - buy) / buy * 100) if buy else 0

    if order.get("ok"):
        state["daily_realized_pnl"] = safe_float(state.get("daily_realized_pnl", 0)) + pnl
        state.setdefault("same_stock_cooldown", {})[code] = time.time()
        trade_log_append(state, {"type": "SELL", "reason": kind, "name": name, "code": code, "qty": qty, "price": cur, "pnl": pnl, "rate": rate, "order": order})
        v109_force_sync_holdings(full_sync=True)
        send_telegram_message(
            f"{'✅ 목표가 도달 자동매도' if kind == 'target' else '🛑 손절가 이탈 자동매도'}\n"
            f"종목: <b>{name}</b> ({code})\n"
            f"매수가: {buy:,.0f}원\n"
            f"매도가 기준: {cur:,.0f}원\n"
            f"수량: {qty:,}주\n"
            f"실현손익 기준: {pnl:,.0f}원 ({rate:.2f}%)\n\n"
            f"{ai_comment(cur, buy, h.get('target', 0), h.get('stop', 0), qty)}\n\n"
            "※ HTS/MTS에서 실제 체결 여부를 반드시 확인하세요."
        )
        try:
            if safe_float(state.get("daily_realized_pnl", 0)) <= safe_float(state.get("daily_max_loss", -30000)):
                state["auto_trade_enabled"] = False
                state["panic_stop"] = True
                write_trade_state(state)
                send_telegram_message("🛑 <b>하루 최대 손실 제한 도달</b>\n자동매매를 중지했습니다.")
            else:
                try_rebuy_after_sell(code)
        except Exception:
            pass
        return True

    order_text = str(order)
    # 키움 장종료/매도가능수량 0/미보유 오류는 반복 텔레그램 금지 + 로컬 제거
    if any(x in order_text for x in ["505217", "장종료", "800033", "매도가능수량", "0주 매도가능"]):
        v109_remove_local_holding(code, name, order.get("message") or order.get("response") or order_text[:300])
        return False

    # 그 외 진짜 주문 오류도 1시간 1회만 알림
    if not v109_guarded_recent(code, "order_fail", 3600):
        v109_mark_guard(code, name, "order_fail")
        send_telegram_message(f"⚠️ <b>자동매도 실패</b>\n종목: {name} ({code})\n사유: {order.get('message') or order.get('response')}")
    return False

def check_one_holding(h):
    """
    v109 override:
    보유종목 감시는 키움 실제잔고에 존재하는 종목만 수행합니다.
    """
    h = normalize_holding(dict(h or {}))
    code = v109_code(h.get("code"))
    name = h.get("name", code)
    if not code:
        return h

    real, res = v109_real_map()
    if res.get("ok"):
        if code not in real:
            v109_remove_local_holding(code, name, "키움 실제잔고에 없는 종목")
            return None
        h.update(real[code])
    else:
        h["priceError"] = "키움 실제잔고 조회 실패로 감시 보류"
        return h

    cur, price_src = get_trade_live_price(code, fallback=True)
    if cur < 10:
        h["priceError"] = "현재가 자동조회 실패. 다음 주기에 재시도합니다."
        return h

    h["lastPrice"] = cur
    h["priceSource"] = price_src
    h["lastCheckedAt"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    h.pop("priceError", None)
    WATCH_STATE["last_prices"][code] = cur

    target = safe_float(h.get("target", 0))
    stop = safe_float(h.get("stop", 0))
    if target and cur >= target:
        auto_sell_holding("target", h, cur)
    elif stop and cur <= stop:
        auto_sell_holding("stop", h, cur)
    return h

def watch_loop():
    """
    v109 override:
    매 주기 시작 시 키움 실제잔고로 서버 보유목록을 교체한 후 감시합니다.
    """
    last_best = 0
    while WATCH_STATE.get("running"):
        try:
            sync = v109_force_sync_holdings(full_sync=True)
            base = sync.get("holdings", read_holdings()) if isinstance(sync, dict) else read_holdings()
            checked = []
            for h in base:
                ch = check_one_holding(h)
                if ch is not None:
                    checked.append(ch)
            write_holdings(checked)
            WATCH_STATE["last_check"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
            if time.time() - last_best > 60:
                check_better_pick()
                if AUTO_BUY_IN_WATCH_LOOP:
                    auto_buy_best_pick()
                last_best = time.time()
        except Exception as e:
            print("v109 watch loop error:", e)
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

def api_v109_force_sync_holdings():
    return jsonify(v109_force_sync_holdings(full_sync=True))

def api_v109_holdings():
    return jsonify(v109_force_sync_holdings(full_sync=True))

def api_server_holdings_v109():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        action = data.get("action", "")
        if action == "clear":
            write_holdings([])
            return jsonify({"ok": True, "version": "v113", "holdings": [], "message": "v109 로컬 보유목록 초기화 완료"})
        if action == "delete":
            code = v109_code(data.get("code"))
            items = [h for h in read_holdings() if v109_code(h.get("code")) != code]
            write_holdings(items)
            return jsonify({"ok": True, "version": "v113", "holdings": items})
    return jsonify(v109_force_sync_holdings(full_sync=True))

@app.route("/api/v109_reset_fake_holdings", methods=["GET", "POST"])
def api_v109_reset_fake_holdings():
    """
    배포 직후 1회 실행 권장.
    과거 파일과 현재 파일의 로컬 보유목록을 비우고 키움 실제잔고로 다시 채웁니다.
    """
    removed_files = []
    for fp in [
        "/tmp/sungil_holdings_v103.json",
        "/tmp/sungil_holdings_v104.json",
        str(BASE_DIR / "sungil_holdings_v103.json"),
        str(BASE_DIR / "sungil_holdings_v104.json"),
        str(BASE_DIR / "sungil_holdings_v109_real_balance.json"),
    ]:
        try:
            if os.path.exists(fp):
                os.remove(fp)
                removed_files.append(fp)
        except Exception:
            pass
    try:
        if os.path.exists(SELL_GUARD_FILE):
            os.remove(SELL_GUARD_FILE)
    except Exception:
        pass
    sync = v109_force_sync_holdings(full_sync=True)
    sync["removed_files"] = removed_files
    sync["message"] = "v109 초기화 완료: 과거 보유목록 파일 제거 후 키움 실제잔고로 재동기화했습니다."
    return jsonify(sync)

HOLDINGS_FILE = str(BASE_DIR / "sungil_holdings_v109_real_only.json")
SELL_GUARD_FILE = str(BASE_DIR / "sungil_sell_guard_v109.json")

_REAL_HOLDINGS_CACHE_V109 = {"time": 0, "res": None}
REAL_HOLDINGS_CACHE_SEC_V109 = int(os.getenv("REAL_HOLDINGS_CACHE_SEC", "5"))

def v109_code(raw):
    s = str(raw or "").strip().replace("A", "")
    s = re.sub(r"[^0-9]", "", s)
    return s.zfill(6) if s else ""

def v109_num(v, default=0):
    try:
        if v is None:
            return default
        if isinstance(v, str):
            v = v.replace(",", "").replace("+", "").replace("-", "").strip()
        return abs(safe_float(v, default))
    except Exception:
        return default

def v109_deep_dicts(obj):
    out = []
    def walk(x):
        if isinstance(x, dict):
            out.append(x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for i in x:
                walk(i)
    walk(obj)
    return out

def parse_kiwoom_holdings(data):
    """v109: 키움 실제잔고 파싱 최종 강화."""
    if not isinstance(data, dict):
        return []
    code_keys = ["stk_cd", "pdno", "code", "isu_cd", "종목코드", "단축코드", "stock_code", "stck_shrn_iscd"]
    name_keys = ["stk_nm", "prdt_name", "prdt_name", "name", "종목명", "상품명", "stock_name", "hts_kor_isnm"]
    qty_keys = ["rmnd_qty", "hldg_qty", "hold_qty", "qty", "보유수량", "잔고수량", "tot_qty", "매도가능수량", "ord_psbl_qty", "trde_able_qty", "slby_qty", "evlu_qty"]
    sellable_keys = ["ord_psbl_qty", "trde_able_qty", "매도가능수량", "sellable_qty", "slby_qty"]
    buy_keys = ["avg_prc", "pchs_avg_pric", "pchs_avg_prc", "buyPrice", "매입평균가", "평균단가", "매입단가", "avg_price", "pchs_pric", "pchs_avg_prc"]
    cur_keys = ["cur_prc", "now_pric", "current_price", "lastPrice", "현재가", "평가가격", "prpr"]
    eval_keys = ["evlt_amt", "evalAmount", "평가금액"]
    pnl_keys = ["evltv_prft", "profitAmount", "평가손익"]

    def first(d, keys):
        for k in keys:
            if k in d and d.get(k) not in [None, "", "0", 0]:
                return d.get(k)
        return None

    by_code = {}
    for item in v109_deep_dicts(data):
        code = v109_code(first(item, code_keys))
        if not code or code == "000000":
            continue
        qty = v109_num(first(item, qty_keys), 0)
        sellable = v109_num(first(item, sellable_keys), qty)
        if qty <= 0 and sellable <= 0:
            continue
        if qty <= 0:
            qty = sellable
        name = str(first(item, name_keys) or code).strip()
        buy = v109_num(first(item, buy_keys), 0)
        cur = v109_num(first(item, cur_keys), 0)
        if cur <= 0:
            try:
                live, live_src = get_trade_live_price(code, fallback=True)
                if live >= 10:
                    cur = live
                    src = live_src
                else:
                    src = "KIWOOM_ACCOUNT"
            except Exception:
                src = "KIWOOM_ACCOUNT"
        else:
            src = "KIWOOM_ACCOUNT"
        if cur <= 0:
            cur = buy
        state = read_trade_state()
        target_rate = normalize_rate_input(state.get("target_rate", 0.025), 0.025)
        stop_rate = normalize_rate_input(state.get("stop_rate", -0.018), -0.018)
        target = round(buy * (1 + target_rate)) if buy else round(cur * (1 + target_rate))
        stop = round(buy * (1 + stop_rate)) if buy else round(cur * (1 + stop_rate))
        buy_amount = buy * qty
        eval_amount = v109_num(first(item, eval_keys), 0) or cur * qty
        pnl = safe_float(first(item, pnl_keys), 0)
        if not pnl and buy and qty and cur:
            pnl = eval_amount - buy_amount
        prate = ((cur - buy) / buy * 100) if buy and cur else 0
        h = {
            "id": f"kiwoom-{code}",
            "name": name,
            "code": code,
            "buyPrice": round(buy),
            "buyAmount": round(buy_amount),
            "qty": int(qty),
            "sellableQty": int(sellable or qty),
            "target": target,
            "stop": stop,
            "lastPrice": round(cur),
            "priceSource": src,
            "autoTrade": True,
            "fromKiwoomAccount": True,
            "createdAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
            "lastCheckedAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
            "highPrice": round(cur),
            "evalAmount": round(eval_amount),
            "profitAmount": round(pnl),
            "profitRate": round(prate, 2),
            "holdingStatus": "감시중",
            "aiComment": ai_comment(cur, buy, target, stop, qty),
            "syncSource": "KIWOOM_REAL_BALANCE_V109",
            "updatedBy": "v109",
        }
        old = by_code.get(code)
        if old is None or h["qty"] >= safe_int(old.get("qty", 0)):
            by_code[code] = h
    return list(by_code.values())

def kiwoom_get_account_holdings():
    """v109: 실제잔고 조회 전용. 실패하면 과거 로컬을 반환하지 않습니다."""
    if not kiwoom_ready():
        return {"ok": False, "message": "키움 환경변수 미설정", "holdings": []}
    if _REAL_HOLDINGS_CACHE_V109.get("res") and time.time() - _REAL_HOLDINGS_CACHE_V109.get("time", 0) < REAL_HOLDINGS_CACHE_SEC_V109:
        return _REAL_HOLDINGS_CACHE_V109["res"]

    body_variants = [{}, {"qry_tp": "1"}, {"qry_tp": "2"}, {"qry_tp": "3"}, {"qry_tp": os.getenv("KIWOOM_CASH_QRY_TP", "3")}]
    endpoints = []
    for api_id in ["kt00018", "kt00004", "kt00005"]:
        for body in body_variants:
            endpoints.append(("/api/dostk/acnt", api_id, body))
    endpoints.append(("/api/dostk/acnt", "kt00001", {"qry_tp": os.getenv("KIWOOM_CASH_QRY_TP", "3")}))

    last_error = ""
    last_raw = None
    for path, api_id, body in endpoints:
        try:
            token = kiwoom_get_token()
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "authorization": "Bearer " + token,
                "cont-yn": "N",
                "next-key": "",
                "api-id": api_id,
            }
            r = requests.post(KIWOOM_BASE_URL + path, json=body, headers=headers, timeout=10)
            try:
                data = r.json() if r.text else {}
            except Exception:
                data = {"raw": r.text[:3000]}
            last_raw = data
            holdings = parse_kiwoom_holdings(data)
            if r.status_code == 200 and holdings:
                res = {"ok": True, "api_id": api_id, "body": body, "holdings": holdings, "raw": data}
                _REAL_HOLDINGS_CACHE_V109["time"] = time.time()
                _REAL_HOLDINGS_CACHE_V109["res"] = res
                update_kiwoom_debug("holdings_ok", "", r.status_code, f"v109 키움 실제잔고 {len(holdings)}개 조회 성공", {"api_id": api_id, "count": len(holdings), "body": body})
                return res
            msg = data.get("return_msg") if isinstance(data, dict) else str(data)
            last_error = f"{api_id} {body}: {msg or '보유종목 파싱 결과 없음'}"
        except Exception as e:
            last_error = str(e)
    res = {"ok": False, "message": last_error or "키움 실제잔고 조회 실패", "holdings": [], "raw": last_raw}
    _REAL_HOLDINGS_CACHE_V109["time"] = time.time()
    _REAL_HOLDINGS_CACHE_V109["res"] = res
    update_kiwoom_debug("holdings_fail", "", 0, res["message"], last_raw)
    return res

def v109_make_holding(code, name, qty, buy):
    code = v109_code(code)
    cur = 0
    src = "SCREEN_FALLBACK"
    try:
        live, live_src = get_trade_live_price(code, fallback=True)
        if live >= 10:
            cur = live
            src = live_src
    except Exception:
        pass
    if cur <= 0:
        cur = buy
    state = read_trade_state()
    target_rate = normalize_rate_input(state.get("target_rate", 0.025), 0.025)
    stop_rate = normalize_rate_input(state.get("stop_rate", -0.018), -0.018)
    target = round(buy * (1 + target_rate))
    stop = round(buy * (1 + stop_rate))
    return {
        "id": f"screen-{code}", "name": name, "code": code,
        "buyPrice": round(buy), "buyAmount": round(buy * qty), "qty": int(qty), "sellableQty": int(qty),
        "target": target, "stop": stop, "lastPrice": round(cur), "priceSource": src,
        "autoTrade": True, "fromKiwoomAccount": False, "screenFallback": True,
        "createdAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"), "lastCheckedAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
        "highPrice": round(cur), "evalAmount": round(cur * qty), "profitAmount": round((cur - buy) * qty),
        "profitRate": round(((cur - buy) / buy * 100) if buy else 0, 2), "holdingStatus": "스크린샷 보정", "updatedBy": "v109_screen"
    }

def v109_screen_holdings():
    """사용자 제공 2026-05-20 16:10 키움 잔고 화면 기준 비상 보정값."""
    return [
        v109_make_holding("010170", "대한광통신", 11, 23136),
        v109_make_holding("067310", "하나마이크론", 4, 46863),
    ]

def v109_force_sync_holdings(full_sync=True, allow_screen_fallback=False):
    res = kiwoom_get_account_holdings()
    if res.get("ok"):
        items = res.get("holdings", [])
        write_holdings(items)
        state = read_trade_state()
        state["last_status"] = "v109 키움 실제잔고 동기화 완료"
        state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        state["last_order_message"] = f"키움 실제잔고 {len(items)}개 기준으로 표시"
        write_trade_state(state)
        return {"ok": True, "version": "v113", "holdings": items, "count": len(items), "source": "KIWOOM_REAL_BALANCE", "message": "키움 실제잔고 기준으로 보유종목을 동기화했습니다.", "kiwoom": res}

    # 실패 시 과거 로컬/브라우저 보유목록은 절대 표시하지 않음
    if allow_screen_fallback or os.getenv("USE_SCREEN_HOLDINGS_FALLBACK", "false").lower() == "true":
        items = v109_screen_holdings()
        write_holdings(items)
        return {"ok": True, "version": "v113", "holdings": items, "count": len(items), "source": "SCREENSHOT_FALLBACK", "message": "키움 잔고조회 실패로 스크린샷 기준 보유종목을 임시 적용했습니다.", "kiwoom_error": res}

    write_holdings([])
    state = read_trade_state()
    state["last_status"] = "v109 키움 실제잔고 조회 실패"
    state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    state["last_order_message"] = "과거 로컬 보유목록 표시 차단. /api/v109_apply_screen_holdings 로 임시 보정 가능"
    write_trade_state(state)
    return {"ok": False, "version": "v113", "holdings": [], "count": 0, "source": "NONE", "message": "키움 실제잔고 조회 실패. 과거 로컬 보유목록은 표시하지 않습니다.", "kiwoom_error": res}

def read_holdings_real_only():
    res = v109_force_sync_holdings(full_sync=True)
    return res.get("holdings", []) if isinstance(res, dict) else []

def v109_real_map():
    res = v109_force_sync_holdings(full_sync=True)
    items = res.get("holdings", []) if isinstance(res, dict) else []
    return {v109_code(h.get("code")): h for h in items if v109_code(h.get("code")) and safe_float(h.get("qty", 0), 0) > 0}, res

def v109_remove_local_holding(code, name="", reason="실제잔고에 없음"):
    code = v109_code(code)
    items = [h for h in read_holdings() if v109_code(h.get("code")) != code]
    write_holdings(items)
    update_trade_status("v109 실제 미보유 종목 제거", f"{name or code}: {reason}")
    return items

def auto_sell_holding(kind, h, cur):
    """v109: 자동매도는 장중 + 키움 실제잔고 확인 성공 + 실제 보유 종목일 때만 실행."""
    h = normalize_holding(dict(h or {}))
    code = v109_code(h.get("code"))
    name = h.get("name", code)
    if not market_is_open():
        update_trade_status("자동매도 보류", f"장중이 아니어서 {name} 자동매도 보류")
        return False
    real, res = v109_real_map()
    if not res.get("ok"):
        update_trade_status("자동매도 보류", "키움 실제잔고 조회 실패로 자동매도 보류")
        return False
    if code not in real:
        v109_remove_local_holding(code, name, "키움 실제잔고에 없는 종목")
        return False
    h.update(real[code])
    qty = int(safe_float(h.get("sellableQty", h.get("qty", 0)), 0))
    if qty <= 0:
        v109_remove_local_holding(code, name, "매도가능수량 0")
        return False
    state = read_trade_state()
    if not state.get("auto_trade_enabled") or not h.get("autoTrade"):
        send_holding_alert(kind, h, cur)
        return False
    order = kiwoom_order("sell", code, qty, price=0, order_type="market")
    if not order.get("ok"):
        msg = str(order.get("message") or order.get("response") or order)
        if "장종료" in msg or "505217" in msg or "매도가능수량" in msg or "800033" in msg:
            update_trade_status("자동매도 보류", f"{name}: {msg[:120]}")
            if "매도가능수량" in msg or "800033" in msg:
                v109_remove_local_holding(code, name, "키움 매도가능수량 0")
            return False
        send_telegram_message(f"⚠️ <b>자동매도 실패</b>\n종목: {name} ({code})\n사유: {msg}")
        return False
    buy = safe_float(h.get("buyPrice", 0))
    pnl = (cur - buy) * qty if buy and qty else 0
    rate = ((cur - buy) / buy * 100) if buy else 0
    state["daily_realized_pnl"] = safe_float(state.get("daily_realized_pnl", 0)) + pnl
    state.setdefault("same_stock_cooldown", {})[code] = time.time()
    write_trade_state(state)
    trade_log_append(state, {"type": "SELL", "reason": kind, "name": name, "code": code, "qty": qty, "price": cur, "pnl": pnl, "rate": rate, "order": order})
    # 매도 후 다시 실제잔고 동기화
    v109_force_sync_holdings(full_sync=True)
    send_telegram_message(
        f"{'✅ 목표가 도달 자동매도' if kind == 'target' else '🛑 손절가 이탈 자동매도'}\n"
        f"종목: <b>{name}</b> ({code})\n매수가: {buy:,.0f}원\n매도가 기준: {cur:,.0f}원\n수량: {qty:,}주\n실현손익 기준: {pnl:,.0f}원 ({rate:.2f}%)\n\n※ HTS/MTS에서 실제 체결 여부를 반드시 확인하세요."
    )
    try:
        try_rebuy_after_sell(code)
    except Exception:
        pass
    return True

def check_one_holding(h):
    h = normalize_holding(dict(h or {}))
    code = v109_code(h.get("code"))
    name = h.get("name", code)
    real, res = v109_real_map()
    if not res.get("ok"):
        # 실제잔고 실패 시 감시/매도 중단. 로컬 구값도 표시하지 않음.
        return None
    if code not in real:
        v109_remove_local_holding(code, name, "키움 실제잔고에 없는 종목")
        return None
    h = normalize_holding(real[code])
    cur, price_src = get_trade_live_price(code, fallback=True)
    if cur >= 10:
        h["lastPrice"] = cur
        h["priceSource"] = price_src
        h["lastCheckedAt"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    else:
        cur = safe_float(h.get("lastPrice", 0), 0)
    target = safe_float(h.get("target", 0))
    stop = safe_float(h.get("stop", 0))
    if target and cur >= target:
        auto_sell_holding("target", h, cur)
    elif stop and cur <= stop:
        auto_sell_holding("stop", h, cur)
    return h

def watch_loop():
    last_best = 0
    while WATCH_STATE.get("running"):
        try:
            sync = v109_force_sync_holdings(full_sync=True)
            base = sync.get("holdings", []) if isinstance(sync, dict) and sync.get("ok") else []
            checked = []
            for h in base:
                ch = check_one_holding(h)
                if ch is not None:
                    checked.append(ch)
            write_holdings(checked)
            WATCH_STATE["last_check"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
            if time.time() - last_best > 60:
                check_better_pick()
                if AUTO_BUY_IN_WATCH_LOOP:
                    auto_buy_best_pick()
                last_best = time.time()
        except Exception as e:
            print("v109 watch loop error:", e)
        time.sleep(WATCH_INTERVAL)

# [v113 route disabled old] @app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
def api_v109_force_sync_holdings():
    return jsonify(v109_force_sync_holdings(full_sync=True))

@app.route("/api/v109_holdings")
def api_v109_holdings():
    return jsonify(v109_force_sync_holdings(full_sync=True))

# [v113 route disabled old] @app.route("/api/v119_holdings_fast", methods=["GET", "POST"])
def api_server_holdings_v109():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        action = data.get("action", "")
        if action == "clear":
            write_holdings([])
            return jsonify({"ok": True, "version": "v113", "holdings": [], "message": "로컬 표시목록 초기화. 다음 동기화 때 키움 실제잔고만 표시됩니다."})
        if action == "delete":
            # 실제잔고 기준 앱이므로 삭제는 임시 화면 삭제일 뿐입니다.
            code = v109_code(data.get("code"))
            items = [h for h in read_holdings() if v109_code(h.get("code")) != code]
            write_holdings(items)
            return jsonify({"ok": True, "version": "v113", "holdings": items, "message": "화면에서 임시 제거했습니다. 키움에 실제 보유 중이면 다시 동기화됩니다."})
    return jsonify(v109_force_sync_holdings(full_sync=True))

# [v113 route disabled old] @app.route("/api/v113_restore_holdings", methods=["POST"])
def api_restore_holdings_v109_disabled():
    # 브라우저 백업이 과거 종목을 되살리는 원인을 차단합니다.
    return jsonify(v109_force_sync_holdings(full_sync=True))

@app.route("/api/v109_apply_screen_holdings", methods=["GET", "POST"])
def api_v109_apply_screen_holdings():
    items = v109_screen_holdings()
    write_holdings(items)
    state = read_trade_state()
    state["last_status"] = "v109 스크린샷 기준 임시 보유목록 적용"
    state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    state["last_order_message"] = "대한광통신 11주, 하나마이크론 4주 임시 반영. 키움 실제잔고 API 정상화 시 자동 대체됩니다."
    write_trade_state(state)
    return jsonify({"ok": True, "version": "v113", "holdings": items, "message": "스크린샷 기준 실제 보유종목을 임시 반영했습니다."})

@app.route("/api/v109_reset_all_holdings", methods=["GET", "POST"])
def api_v109_reset_all_holdings():
    removed_files = []
    for fp in [
        "/tmp/sungil_holdings_v101.json", "/tmp/sungil_holdings_v102.json", "/tmp/sungil_holdings_v103.json", "/tmp/sungil_holdings_v104.json", "/tmp/sungil_holdings_v105.json",
        str(BASE_DIR / "sungil_holdings_v101.json"), str(BASE_DIR / "sungil_holdings_v102.json"), str(BASE_DIR / "sungil_holdings_v103.json"), str(BASE_DIR / "sungil_holdings_v104.json"), str(BASE_DIR / "sungil_holdings_v105_real_balance.json"), str(BASE_DIR / "sungil_holdings_v109_real_only.json"),
    ]:
        try:
            if os.path.exists(fp):
                os.remove(fp)
                removed_files.append(fp)
        except Exception:
            pass
    _REAL_HOLDINGS_CACHE_V109["time"] = 0
    _REAL_HOLDINGS_CACHE_V109["res"] = None
    res = v109_force_sync_holdings(full_sync=True)
    res["removed_files"] = removed_files
    return jsonify(res)

# [v113] original app.run moved to end after all patches




# ============================================================
# v123_CLICK_DETAIL_STATUS_FIX ENGINE
# ============================================================
ORDER_LOCK = globals().get("ORDER_LOCK") or threading.Lock()
STATE_LOCK = globals().get("STATE_LOCK") or threading.RLock()
PRICE_CACHE_LOCK = globals().get("PRICE_CACHE_LOCK") or threading.Lock()
PRICE_CACHE = globals().get("PRICE_CACHE", {})
ORDER_IN_PROGRESS = globals().get("ORDER_IN_PROGRESS", {})

V109_WATCH_INTERVAL = safe_float(os.getenv("V109_WATCH_INTERVAL", "3"), 3)
V109_MAX_WATCH_HOLDINGS = max(1, int(safe_float(os.getenv("V109_MAX_WATCH_HOLDINGS", "3"), 3)))
V109_PRICE_CACHE_TTL = safe_float(os.getenv("V109_PRICE_CACHE_TTL", "2.5"), 2.5)
V109_CANDIDATE_KEY_PRICE_LIMIT = max(1, int(safe_float(os.getenv("V109_CANDIDATE_KEY_PRICE_LIMIT", "2"), 2)))
V109_TRAILING_DROP_RATE = normalize_rate_input(os.getenv("V109_TRAILING_DROP_RATE", "1.3"), 0.013)
V109_TRAILING_START_RATE = normalize_rate_input(os.getenv("V109_TRAILING_START_RATE", "1.0"), 0.010)
V109_ORDER_COOLDOWN_SEC = safe_float(os.getenv("V109_ORDER_COOLDOWN_SEC", "8"), 8)

def v109_code(raw):
    s = str(raw or "").strip().replace("A", "")
    s = re.sub(r"[^0-9]", "", s)
    return s.zfill(6) if s else ""

def v109_cached_trade_price(code, fallback=True, ttl=None, force=False):
    code = v109_code(code)
    ttl = V109_PRICE_CACHE_TTL if ttl is None else safe_float(ttl, V109_PRICE_CACHE_TTL)
    if not code:
        return 0, "NONE"
    now = time.time()
    with PRICE_CACHE_LOCK:
        item = PRICE_CACHE.get(code)
        if item and not force and now - safe_float(item.get("ts", 0), 0) <= ttl:
            return safe_float(item.get("price", 0), 0), item.get("source", "CACHE")
    try:
        p, src = get_trade_live_price(code, fallback=fallback)
    except Exception:
        p, src = 0, "NONE"
    if safe_float(p, 0) >= 10:
        with PRICE_CACHE_LOCK:
            PRICE_CACHE[code] = {"price": safe_float(p, 0), "source": src, "ts": now, "time": now_kst().strftime("%Y-%m-%d %H:%M:%S")}
    return safe_float(p, 0), src

def v109_order_key(side, code):
    return f"{str(side).lower()}_{v109_code(code)}"

def v109_order_allowed(side, code):
    key = v109_order_key(side, code)
    now = time.time()
    last = safe_float(ORDER_IN_PROGRESS.get(key, 0), 0)
    if last and now - last < V109_ORDER_COOLDOWN_SEC:
        return False, f"v119 주문 응답 지연/재시도: {int(V109_ORDER_COOLDOWN_SEC - (now-last))}초 후 재시도"
    ORDER_IN_PROGRESS[key] = now
    return True, "OK"

def v109_order_release(side, code):
    ORDER_IN_PROGRESS[v109_order_key(side, code)] = time.time()

try:
    _ORIG_KIWOOM_ORDER_V109 = kiwoom_order
    def kiwoom_order(side, code, qty, price=0, order_type="market"):
        code = v109_code(code)
        ok_lock, msg_lock = v109_order_allowed(side, code)
        if not ok_lock:
            return {"ok": False, "message": msg_lock, "v109_order_lock": True, "side": side, "code": code}
        with ORDER_LOCK:
            try:
                if "market_is_open" in globals():
                    try:
                        if not market_is_open():
                            return {"ok": False, "message": "v109 장마감/장외 시간: 주문금지", "side": side, "code": code}
                    except Exception:
                        pass
                return _ORIG_KIWOOM_ORDER_V109(side, code, qty, price, order_type)
            finally:
                v109_order_release(side, code)
except Exception:
    pass

def v109_update_highest_price(h, cur):
    h = normalize_holding(dict(h or {}))
    cur = safe_float(cur, 0)
    highest = max(safe_float(h.get("highestPrice", 0), 0), safe_float(h.get("highPrice", 0), 0), safe_float(h.get("buyPrice", 0), 0), cur)
    if cur > highest:
        highest = cur
    h["highestPrice"] = highest
    h["highPrice"] = highest
    return h, highest

def v109_trailing_stop_signal(h, cur):
    buy = safe_float(h.get("buyPrice", 0), 0)
    highest = max(safe_float(h.get("highestPrice", 0), 0), safe_float(h.get("highPrice", 0), 0))
    cur = safe_float(cur, 0)
    if buy <= 0 or highest <= 0 or cur <= 0:
        return False, ""
    start_price = buy * (1 + V109_TRAILING_START_RATE)
    trail_price = highest * (1 - V109_TRAILING_DROP_RATE)
    if highest >= start_price and cur <= trail_price:
        return True, f"트레일링 스탑: 최고가 {highest:,.0f}원 대비 {V109_TRAILING_DROP_RATE*100:.2f}% 하락"
    return False, ""

def check_one_holding(h):
    h = normalize_holding(dict(h or {}))
    code = v109_code(h.get("code"))
    if not code or code == "000000":
        h["priceError"] = "종목코드를 확인해 주세요."
        return h
    cur, price_src = v109_cached_trade_price(code, fallback=True)
    if cur < 10:
        h["priceError"] = "현재가 자동조회 실패. 다음 주기에 재시도합니다."
        return h
    h, highest = v109_update_highest_price(h, cur)
    h["lastPrice"] = cur
    h["priceSource"] = price_src
    h["lastCheckedAt"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    h.pop("priceError", None)
    try:
        WATCH_STATE["last_prices"][code] = cur
    except Exception:
        pass
    target = safe_float(h.get("target", 0))
    stop = safe_float(h.get("stop", 0))
    trail_hit, trail_reason = v109_trailing_stop_signal(h, cur)
    if stop and cur <= stop:
        with ORDER_LOCK:
            auto_sell_holding("stop", h, cur)
    elif trail_hit:
        h["trailingReason"] = trail_reason
        with ORDER_LOCK:
            auto_sell_holding("trailing_stop", h, cur)
    elif target and cur >= target:
        with ORDER_LOCK:
            auto_sell_holding("target", h, cur)
    return h

def v109_select_watch_holdings(items):
    rows = []
    for h in items or []:
        try:
            h = normalize_holding(dict(h or {}))
            cur = safe_float(h.get("lastPrice", 0), 0)
            buy = safe_float(h.get("buyPrice", 0), 0)
            target = safe_float(h.get("target", 0), 0)
            stop = safe_float(h.get("stop", 0), 0)
            risk_score = 0
            if cur and stop:
                risk_score += max(0, 100 - abs((cur - stop) / cur * 100))
            if cur and target:
                risk_score += max(0, 100 - abs((target - cur) / cur * 100))
            if cur and buy:
                risk_score += abs((cur - buy) / buy * 100) * 3
            rows.append((risk_score, h))
        except Exception:
            rows.append((0, h))
    rows.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in rows[:V109_MAX_WATCH_HOLDINGS]]

def watch_loop():
    last_best = 0
    interval = max(1.0, V109_WATCH_INTERVAL)
    while WATCH_STATE.get("running"):
        try:
            with STATE_LOCK:
                all_holdings = read_holdings()
            watch_items = v109_select_watch_holdings(all_holdings)
            checked = {}
            for h in watch_items:
                nh = check_one_holding(h)
                checked[v109_code(nh.get("code"))] = nh
            merged = []
            for h in all_holdings:
                code = v109_code(h.get("code"))
                merged.append(checked.get(code, h))
            with STATE_LOCK:
                write_holdings(merged)
            WATCH_STATE["last_check"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
            if time.time() - last_best > 60:
                try:
                    check_better_pick()
                except Exception as e:
                    print("v109 check_better_pick error:", e)
                if globals().get("AUTO_BUY_IN_WATCH_LOOP"):
                    with ORDER_LOCK:
                        try:
                            auto_buy_best_pick()
                        except Exception as e:
                            print("v109 auto_buy_best_pick error:", e)
                last_best = time.time()
        except Exception as e:
            print("v109 watch loop error:", e)
        time.sleep(interval)

def v109_get_orderbook_metrics_fast(code):
    code = v109_code(code)
    if not code or not kiwoom_ready():
        return {"bid_total": 0, "ask_total": 0, "bid_ask_ratio": 0, "orderbook_source": "NONE"}
    try:
        token = kiwoom_get_token()
        headers = {"Content-Type": "application/json;charset=UTF-8", "authorization": "Bearer " + token, "cont-yn": "N", "next-key": "", "api-id": "ka10004"}
        r = requests.post(KIWOOM_BASE_URL + "/api/dostk/stkinfo", json={"stk_cd": code}, headers=headers, timeout=4)
        data = r.json() if r.text else {}
        bid = ask = 0
        for k in ["tot_bid_req", "tot_bid_qty", "bid_total", "매수호가총잔량", "buy_total_qty"]:
            if k in data:
                bid = abs(safe_float(str(data.get(k)).replace(",", "").replace("+", "").replace("-", ""), 0))
                if bid > 0:
                    break
        for k in ["tot_ask_req", "tot_ask_qty", "ask_total", "매도호가총잔량", "sell_total_qty"]:
            if k in data:
                ask = abs(safe_float(str(data.get(k)).replace(",", "").replace("+", "").replace("-", ""), 0))
                if ask > 0:
                    break
        if bid <= 0 and ask <= 0 and "v107_get_orderbook_metrics" in globals():
            return v107_get_orderbook_metrics(code)
        return {"bid_total": bid, "ask_total": ask, "bid_ask_ratio": round(bid / ask, 3) if ask > 0 else 0, "orderbook_source": "KIWOOM_FAST"}
    except Exception:
        if "v107_get_orderbook_metrics" in globals():
            return v107_get_orderbook_metrics(code)
        return {"bid_total": 0, "ask_total": 0, "bid_ask_ratio": 0, "orderbook_source": "NONE"}

def v109_calculate_scalping_score(row, price, orderbook=None):
    if "v107_calculate_scalping_score" in globals():
        res = v107_calculate_scalping_score(row, price, orderbook or {})
        res["aiScoreV109"] = res.get("aiScoreV107", res.get("orderPriority", 0))
        res["v109Optimized"] = True
        return res
    score = safe_float(row.get("score", 0), 0)
    return {"aiScoreV109": score, "orderPriority": score, "scalpingStatus": "기본 후보", "scalpingReasons": ["기본 점수"], "v109Optimized": True}

try:
    _ORIG_SCORE_CANDIDATES_V109 = score_candidates
    def score_candidates(limit=700, cash=500000, min_qty=5, max_change=7, min_amount=1000000000, min_score=70):
        df = get_market_df(limit=limit)
        if df is None or df.empty:
            return []
        df = df.copy()
        cc = "ChagesRatio" if "ChagesRatio" in df.columns else ("Change" if "Change" in df.columns else None)
        for col in ["Close", "Volume", "Amount", "Marcap"]:
            df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)
        df["dayChange"] = pd.to_numeric(df[cc], errors="coerce").fillna(0) if cc else 0
        df["Name"] = df["Name"].astype(str)
        df["Code"] = df["Code"].astype(str).str.zfill(6)
        exclude = ["스팩", "SPAC", "ETF", "ETN", "인버스", "레버리지", "KODEX", "TIGER", "KBSTAR", "ARIRANG", "HANARO"]
        df = df[~df["Name"].str.upper().apply(lambda n: any(x.upper() in n for x in exclude) or n.endswith("우"))].copy()
        df = df[(df["Close"] >= 10) & (df["Amount"] >= min_amount) & (df["dayChange"] >= 0.2) & (df["dayChange"] <= max_change)].copy()
        if df.empty:
            return []
        df["theme"] = df["Name"].apply(classify_theme).apply(normalize_theme)
        df["amountRank"] = df["Amount"].rank(pct=True) * 100
        df["volumeRank"] = df["Volume"].rank(pct=True) * 100
        df["marcapRank"] = df["Marcap"].rank(pct=True) * 100
        df["sweetSpot"] = (100 - (df["dayChange"] - 3.5).abs() * 8).clip(lower=20, upper=100)
        df["themeWeight"] = df["theme"].apply(lambda x: WEIGHT.get(x, 1.0))
        df["score"] = (df["amountRank"] * .34 + df["volumeRank"] * .25 + df["marcapRank"] * .15 + df["sweetSpot"] * .26) * df["themeWeight"]
        df = df[df["score"] >= min_score].sort_values("score", ascending=False)
        out = []
        for idx, (_, row) in enumerate(list(df.head(20).iterrows())):
            p = safe_float(row["Close"])
            qty = int(cash // p) if p else 0
            if qty < min_qty:
                continue
            code = str(row["Code"]).zfill(6)
            price_src = "KRX_FDR"
            orderbook = {"orderbook_source": "SKIP_FOR_RATE_LIMIT"}
            if idx < V109_CANDIDATE_KEY_PRICE_LIMIT:
                live_p, srcp = v109_cached_trade_price(code, fallback=True)
                if live_p >= 10:
                    p = live_p
                    price_src = srcp
                    qty = int(cash // p) if p else 0
                orderbook = v109_get_orderbook_metrics_fast(code)
            if qty < min_qty:
                continue
            ai_score = v109_calculate_scalping_score(row, p, orderbook)
            pick = {
                "code": code, "name": str(row["Name"]), "market": str(row.get("Market", "")),
                "theme": normalize_theme(row["theme"]), "price": round(p), "priceSource": price_src,
                "score": safe_float(ai_score.get("aiScoreV109", ai_score.get("orderPriority", row.get("score", 0)))),
                "dayChange": round(safe_float(row["dayChange"]), 2), "amount": round(safe_float(row["Amount"])),
                "qtyPossible": qty, "buyZone": round(p * .995), "target": round(p * 1.035), "stop": round(p * .975),
                "comment": f"v109 스캘핑 안정화: {ai_score.get('scalpingStatus','후보')} · {', '.join(ai_score.get('scalpingReasons',['관찰']))}. 현재가 출처 {price_src}."
            }
            pick.update(ai_score)
            out.append(pick)
        return sorted(out, key=lambda x: safe_float(x.get("orderPriority", x.get("score", 0))), reverse=True)
except Exception as e:
    print("v109 score_candidates patch failed:", e)

# [v109 duplicate route disabled] @app.route("/api/v109_stability_status")
def api_v109_stability_status():
    return jsonify({
        "ok": True, "version": "v113", "order_lock": True, "state_lock": True,
        "price_cache_count": len(PRICE_CACHE), "watch_interval": V109_WATCH_INTERVAL,
        "max_watch_holdings": V109_MAX_WATCH_HOLDINGS, "price_cache_ttl": V109_PRICE_CACHE_TTL,
        "trailing_drop_rate": V109_TRAILING_DROP_RATE, "trailing_start_rate": V109_TRAILING_START_RATE,
        "order_cooldown_sec": V109_ORDER_COOLDOWN_SEC, "order_in_progress": ORDER_IN_PROGRESS,
        "message": "v109 실전 안정화 엔진 정상 로드"
    })

@app.route("/api/v109_clear_price_cache", methods=["GET", "POST"])
def api_v109_clear_price_cache():
    with PRICE_CACHE_LOCK:
        PRICE_CACHE.clear()
    return jsonify({"ok": True, "version": "v113", "message": "현재가 캐시 초기화 완료"})

# [v109 duplicate route disabled] @app.route("/api/v109_trailing_test")
def api_v109_trailing_test():
    buy = safe_float(request.args.get("buy", 10000), 10000)
    highest = safe_float(request.args.get("highest", 10500), 10500)
    cur = safe_float(request.args.get("cur", 10300), 10300)
    h = {"buyPrice": buy, "highestPrice": highest, "highPrice": highest}
    hit, reason = v109_trailing_stop_signal(h, cur)
    return jsonify({"ok": True, "hit": hit, "reason": reason, "buy": buy, "highest": highest, "cur": cur})




# ============================================================
# v123_CLICK_DETAIL_STATUS_FIX PATCH
# 트레일링 스탑 실시간 감시 / 오타 방어 / REST 호출 제한 / 감시속도 최적화
# ============================================================
V109_WATCH_INTERVAL = safe_float(os.getenv("V109_WATCH_INTERVAL", "2"), 2)
V109_MAX_WATCH_HOLDINGS = max(1, int(safe_float(os.getenv("V109_MAX_WATCH_HOLDINGS", "3"), 3)))
V109_CANDIDATE_KEY_PRICE_LIMIT = max(1, int(safe_float(os.getenv("V109_CANDIDATE_KEY_PRICE_LIMIT", "5"), 5)))
V109_PRICE_CACHE_TTL = safe_float(os.getenv("V109_PRICE_CACHE_TTL", "2.0"), 2.0)
V109_PROFIT_GUARD_RATE = normalize_rate_input(os.getenv("V109_PROFIT_GUARD_RATE", "1.2"), 0.012)
V109_TRAILING_STOP_RATE = normalize_rate_input(os.getenv("V109_TRAILING_STOP_RATE", "1.1"), 0.011)
AI_TARGET_RAISE_ENABLED = os.getenv("AI_TARGET_RAISE_ENABLED", "true").lower() == "true"
AI_TARGET_RAISE_EXTRA_RATE = normalize_rate_input(os.getenv("AI_TARGET_RAISE_EXTRA_RATE", "0.8"), 0.008)
AI_TARGET_RAISE_HOLD_NEAR_HIGH_RATE = normalize_rate_input(os.getenv("AI_TARGET_RAISE_HOLD_NEAR_HIGH_RATE", "0.5"), 0.005)


def v109_code(raw):
    s = str(raw or "").strip().replace("A", "")
    s = re.sub(r"[^0-9]", "", s)
    return s.zfill(6) if s else ""


def v109_cached_trade_price(code, fallback=True, ttl=None, force=False):
    # v108 캐시가 있으면 재사용
    ttl = V109_PRICE_CACHE_TTL if ttl is None else safe_float(ttl, V109_PRICE_CACHE_TTL)
    if "v108_cached_trade_price" in globals():
        return v108_cached_trade_price(code, fallback=fallback, ttl=ttl, force=force)
    return get_trade_live_price(code, fallback=fallback)


def check_one_holding(h):
    """
    v109 최종 보강:
    - 진입 후 최고가(highPrice/highestPrice) 실시간 갱신
    - highRate 저장
    - profitGuardRate 이상 수익권 진입 후 최고가 대비 trailingStopRate 하락 시 익절 보존 매도
    - 고정 목표가/손절가도 유지
    - 매도 실행은 ORDER_LOCK으로 중복 주문 방지
    """
    h = normalize_holding(dict(h or {}))
    code = v109_code(h.get("code", ""))
    if not code or code == "000000":
        h["priceError"] = "종목코드를 확인해 주세요."
        return h

    cur, price_src = v109_cached_trade_price(code, fallback=True, ttl=V109_PRICE_CACHE_TTL)
    cur = safe_float(cur, 0)
    if cur < 10:
        h["priceError"] = "현재가 자동조회 실패. 다음 주기에 재시도합니다."
        return h

    h["lastPrice"] = cur
    h["priceSource"] = price_src
    h["lastCheckedAt"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    h.pop("priceError", None)

    try:
        WATCH_STATE["last_prices"][code] = cur
    except Exception:
        pass

    buy_price = safe_float(h.get("buyPrice", 0), 0)
    target = safe_float(h.get("target", 0), 0)
    stop = safe_float(h.get("stop", 0), 0)

    # 최고가 관리
    current_high = max(
        safe_float(h.get("highPrice", 0), 0),
        safe_float(h.get("highestPrice", 0), 0),
        buy_price,
        cur
    )
    if cur > current_high:
        current_high = cur

    h["highPrice"] = current_high
    h["highestPrice"] = current_high

    current_rate = (cur - buy_price) / buy_price if buy_price > 0 else 0.0
    high_rate = (current_high - buy_price) / buy_price if buy_price > 0 else 0.0
    h["profitRate"] = round(current_rate * 100, 2)
    h["highRate"] = round(high_rate, 5)

    profit_guard_rate = normalize_rate_input(h.get("profitGuardRate", V109_PROFIT_GUARD_RATE), V109_PROFIT_GUARD_RATE)
    trailing_stop_rate = normalize_rate_input(h.get("trailingStopRate", V109_TRAILING_STOP_RATE), V109_TRAILING_STOP_RATE)

    is_trailing_triggered = False
    trailing_target_price = 0
    if buy_price > 0 and high_rate >= profit_guard_rate:
        trailing_target_price = current_high * (1.0 - trailing_stop_rate)
        if cur <= trailing_target_price:
            is_trailing_triggered = True

    h["trailingTargetPrice"] = round(trailing_target_price) if trailing_target_price else 0
    h["trailingActive"] = bool(high_rate >= profit_guard_rate)
    h["trailingStopRate"] = trailing_stop_rate
    h["profitGuardRate"] = profit_guard_rate

    # 매도 우선순위: 손절 -> 트레일링 -> 목표가
    if stop and cur <= stop:
        with ORDER_LOCK:
            auto_sell_holding("stop", h, cur)
    elif is_trailing_triggered:
        h["trailingReason"] = f"최고가 {current_high:,.0f}원 대비 {trailing_stop_rate*100:.2f}% 하락"
        with ORDER_LOCK:
            auto_sell_holding("trailing_stop", h, cur)
    elif target and cur >= target:
        # v125 AI 목표가 상향:
        # 목표가에 닿았더라도 현재가가 당일/진입 후 최고가 부근이고 수익보호 구간이면
        # 즉시 매도하지 않고 목표가를 위로 올린 뒤 트레일링 스탑으로 수익을 보호합니다.
        near_high = current_high > 0 and cur >= current_high * (1.0 - AI_TARGET_RAISE_HOLD_NEAR_HIGH_RATE)
        strong_profit = buy_price > 0 and current_rate >= profit_guard_rate
        if AI_TARGET_RAISE_ENABLED and strong_profit and near_high:
            new_target = round(max(target, cur * (1.0 + AI_TARGET_RAISE_EXTRA_RATE), current_high * (1.0 + AI_TARGET_RAISE_EXTRA_RATE)))
            h["aiTargetRaised"] = True
            h["aiTargetRaiseReason"] = f"목표가 도달 후 강세 유지: 기존 목표 {target:,.0f}원 → AI 상향 {new_target:,.0f}원"
            h["target"] = new_target
            h["targetRaiseAt"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        else:
            with ORDER_LOCK:
                auto_sell_holding("target", h, cur)

    return h


def v109_select_watch_holdings(items):
    rows = []
    for h in items or []:
        try:
            h = normalize_holding(dict(h or {}))
            cur = safe_float(h.get("lastPrice", 0), 0)
            buy = safe_float(h.get("buyPrice", 0), 0)
            target = safe_float(h.get("target", 0), 0)
            stop = safe_float(h.get("stop", 0), 0)
            high = max(safe_float(h.get("highPrice", 0), 0), safe_float(h.get("highestPrice", 0), 0))
            score = 0
            if cur and stop:
                score += max(0, 100 - abs((cur - stop) / cur * 100))
            if cur and target:
                score += max(0, 100 - abs((target - cur) / cur * 100))
            if cur and buy:
                score += abs((cur - buy) / buy * 100) * 4
            if cur and high and buy and high > buy:
                score += 30
            rows.append((score, h))
        except Exception:
            rows.append((0, h))
    rows.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in rows[:V109_MAX_WATCH_HOLDINGS]]


def watch_loop():
    """
    v109 감시 루프:
    - 2초 기본 감시
    - 감시 대상 최대 3개
    - 현재가 캐시 사용
    - 저장은 루프당 1회
    - 자동매수는 60초 간격 + ORDER_LOCK
    """
    last_best = 0
    interval = max(1.0, V109_WATCH_INTERVAL)
    while WATCH_STATE.get("running"):
        try:
            with STATE_LOCK:
                all_holdings = read_holdings()
            watch_items = v109_select_watch_holdings(all_holdings)
            checked = {}

            for h in watch_items:
                nh = check_one_holding(h)
                checked[v109_code(nh.get("code"))] = nh

            merged = []
            for h in all_holdings:
                code = v109_code(h.get("code"))
                merged.append(checked.get(code, h))

            with STATE_LOCK:
                write_holdings(merged)
            WATCH_STATE["last_check"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")

            if time.time() - last_best > 60:
                try:
                    check_better_pick()
                except Exception as e:
                    print("v109 check_better_pick error:", e)

                if globals().get("AUTO_BUY_IN_WATCH_LOOP"):
                    with ORDER_LOCK:
                        try:
                            auto_buy_best_pick()
                        except Exception as e:
                            print("v109 auto_buy_best_pick error:", e)
                last_best = time.time()

        except Exception as e:
            print("v109 watch loop error:", e)
        time.sleep(interval)


def v109_get_orderbook_metrics_fast(code):
    code = v109_code(code)
    if "v108_get_orderbook_metrics_fast" in globals():
        return v108_get_orderbook_metrics_fast(code)
    if "v107_get_orderbook_metrics" in globals():
        return v107_get_orderbook_metrics(code)
    return {"bid_total": 0, "ask_total": 0, "bid_ask_ratio": 0, "orderbook_source": "NONE"}


def v109_calculate_scalping_score(row, price, orderbook=None):
    """
    v108_calculate_scalping_score 오타/분리 방지용 안전 함수.
    change_score 분리 오류가 있어도 이 함수는 자체적으로 계산합니다.
    """
    orderbook = orderbook or {}
    day_change = safe_float(row.get("dayChange", row.get("ChagesRatio", row.get("Change", 0))), 0)
    amount_rank = safe_float(row.get("amountRank", 0), 0)
    volume_rank = safe_float(row.get("volumeRank", 0), 0)
    base_score = safe_float(row.get("score", 0), 0)

    if 0.5 <= day_change < 2.0:
        change_score = 72
    elif 2.0 <= day_change < 4.5:
        change_score = 92
    elif 4.5 <= day_change <= 7.5:
        change_score = 82
    else:
        change_score = 55

    bid_ask_ratio = safe_float(orderbook.get("bid_ask_ratio", 0), 0)
    orderbook_score = 0
    if bid_ask_ratio >= 2:
        orderbook_score = 12
    elif bid_ask_ratio >= 1.2:
        orderbook_score = 6
    elif bid_ask_ratio > 0 and bid_ask_ratio < 0.7:
        orderbook_score = -8

    score = base_score * 0.45 + amount_rank * 0.2 + volume_rank * 0.15 + change_score * 0.2 + orderbook_score
    score = max(0, min(100, score))

    reasons = [
        f"등락률점수 {change_score}",
        f"거래대금순위 {amount_rank:.1f}",
        f"거래량순위 {volume_rank:.1f}",
        f"호가비율 {bid_ask_ratio}"
    ]

    return {
        "aiScoreV109": round(score, 2),
        "orderPriority": round(score, 2),
        "scalpingStatus": "v109 후보",
        "scalpingReasons": reasons,
        "v109Optimized": True
    }


try:
    _ORIG_SCORE_CANDIDATES_V109 = score_candidates

    def score_candidates(limit=700, cash=500000, min_qty=5, max_change=7, min_amount=1000000000, min_score=70):
        """
        v109 최적화:
        - 후보 스코어링은 KRX/FDR 데이터 기반
        - 키움 현재가/호가는 상위 5개 이내만 확인
        - Rate Limit 위험 감소
        """
        df = get_market_df(limit=limit)
        if df is None or df.empty:
            return []
        df = df.copy()
        cc = "ChagesRatio" if "ChagesRatio" in df.columns else ("Change" if "Change" in df.columns else None)
        for col in ["Close", "Volume", "Amount", "Marcap"]:
            df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)
        df["dayChange"] = pd.to_numeric(df[cc], errors="coerce").fillna(0) if cc else 0
        df["Name"] = df["Name"].astype(str)
        df["Code"] = df["Code"].astype(str).str.zfill(6)

        exclude = ["스팩", "SPAC", "ETF", "ETN", "인버스", "레버리지", "KODEX", "TIGER", "KBSTAR", "ARIRANG", "HANARO"]
        df = df[~df["Name"].str.upper().apply(lambda n: any(x.upper() in n for x in exclude) or n.endswith("우"))].copy()
        df = df[(df["Close"] >= 10) & (df["Amount"] >= min_amount) & (df["dayChange"] >= 0.2) & (df["dayChange"] <= max_change)].copy()
        if df.empty:
            return []

        df["theme"] = df["Name"].apply(classify_theme).apply(normalize_theme)
        df["amountRank"] = df["Amount"].rank(pct=True) * 100
        df["volumeRank"] = df["Volume"].rank(pct=True) * 100
        df["marcapRank"] = df["Marcap"].rank(pct=True) * 100
        df["sweetSpot"] = (100 - (df["dayChange"] - 3.5).abs() * 8).clip(lower=20, upper=100)
        df["themeWeight"] = df["theme"].apply(lambda x: WEIGHT.get(x, 1.0))
        df["score"] = (df["amountRank"] * .34 + df["volumeRank"] * .25 + df["marcapRank"] * .15 + df["sweetSpot"] * .26) * df["themeWeight"]
        df = df[df["score"] >= min_score].sort_values("score", ascending=False)

        out = []
        for idx, (_, row) in enumerate(list(df.head(20).iterrows())):
            p = safe_float(row["Close"], 0)
            code = str(row["Code"]).zfill(6)
            price_src = "KRX_FDR"
            orderbook = {"orderbook_source": "SKIP_FOR_RATE_LIMIT"}

            if idx < V109_CANDIDATE_KEY_PRICE_LIMIT:
                live_p, srcp = v109_cached_trade_price(code, fallback=True, ttl=V109_PRICE_CACHE_TTL)
                if live_p >= 10:
                    p = live_p
                    price_src = srcp
                orderbook = v109_get_orderbook_metrics_fast(code)

            qty = int(cash // p) if p else 0
            if qty < min_qty:
                continue

            ai_score = v109_calculate_scalping_score(row, p, orderbook)
            pick = {
                "code": code,
                "name": str(row["Name"]),
                "market": str(row.get("Market", "")),
                "theme": normalize_theme(row["theme"]),
                "price": round(p),
                "priceSource": price_src,
                "score": safe_float(ai_score.get("aiScoreV109", ai_score.get("orderPriority", row.get("score", 0))), 0),
                "dayChange": round(safe_float(row["dayChange"], 0), 2),
                "amount": round(safe_float(row["Amount"], 0)),
                "qtyPossible": qty,
                "buyZone": round(p * .995),
                "target": round(p * 1.035),
                "stop": round(p * .975),
                "profitGuardRate": V109_PROFIT_GUARD_RATE,
                "trailingStopRate": V109_TRAILING_STOP_RATE,
                "comment": f"v109 안정화 후보: {ai_score.get('scalpingStatus','후보')} · {', '.join(ai_score.get('scalpingReasons',['관찰']))}. 현재가 출처 {price_src}."
            }
            pick.update(ai_score)
            out.append(pick)

        return sorted(out, key=lambda x: safe_float(x.get("orderPriority", x.get("score", 0)), 0), reverse=True)

except Exception as e:
    print("v109 score_candidates patch failed:", e)


@app.route("/api/v109_stability_status")
def api_v109_stability_status():
    return jsonify({
        "ok": True,
        "version": "v113",
        "order_lock": "ORDER_LOCK" in globals(),
        "state_lock": "STATE_LOCK" in globals(),
        "price_cache_count": len(PRICE_CACHE) if "PRICE_CACHE" in globals() else 0,
        "watch_interval": V109_WATCH_INTERVAL,
        "max_watch_holdings": V109_MAX_WATCH_HOLDINGS,
        "candidate_key_price_limit": V109_CANDIDATE_KEY_PRICE_LIMIT,
        "price_cache_ttl": V109_PRICE_CACHE_TTL,
        "profit_guard_rate": V109_PROFIT_GUARD_RATE,
        "trailing_stop_rate": V109_TRAILING_STOP_RATE,
        "message": "v109 트레일링/락/API최적화 패치 정상 로드"
    })


@app.route("/api/v109_trailing_test")
def api_v109_trailing_test():
    buy = safe_float(request.args.get("buy", 10000), 10000)
    high = safe_float(request.args.get("high", 10400), 10400)
    cur = safe_float(request.args.get("cur", 10250), 10250)
    h = {"buyPrice": buy, "highPrice": high, "highestPrice": high, "profitGuardRate": V109_PROFIT_GUARD_RATE, "trailingStopRate": V109_TRAILING_STOP_RATE}
    h = check_one_holding_for_test_v109(h, cur)
    return jsonify({"ok": True, "version": "v113", "test": h})


def check_one_holding_for_test_v109(h, cur):
    buy_price = safe_float(h.get("buyPrice", 0), 0)
    current_high = max(safe_float(h.get("highPrice", 0), 0), safe_float(h.get("highestPrice", 0), 0), buy_price, cur)
    high_rate = (current_high - buy_price) / buy_price if buy_price > 0 else 0.0
    profit_guard_rate = normalize_rate_input(h.get("profitGuardRate", V109_PROFIT_GUARD_RATE), V109_PROFIT_GUARD_RATE)
    trailing_stop_rate = normalize_rate_input(h.get("trailingStopRate", V109_TRAILING_STOP_RATE), V109_TRAILING_STOP_RATE)
    trailing_target_price = current_high * (1.0 - trailing_stop_rate)
    hit = bool(high_rate >= profit_guard_rate and cur <= trailing_target_price)
    return {
        "buyPrice": buy_price,
        "highPrice": current_high,
        "cur": cur,
        "highRate": round(high_rate, 5),
        "profitGuardRate": profit_guard_rate,
        "trailingStopRate": trailing_stop_rate,
        "trailingTargetPrice": round(trailing_target_price),
        "trailingHit": hit
    }




# [v113 route disabled old] @app.route("/api/v113_version")
def api_v113_version():
    return jsonify({
        "ok": True,
        "version": "v113",
        "title": "KIWOOM REAL AUTO v131",
        "engine": "MASTER HOLDINGS",
        "message": "v113 파일이 정상 반영되었습니다."
    })



# ============================================================
# v123_CLICK_DETAIL_STATUS_FIX
# 보유종목 앱 표시 최종 수정: 키움 실제잔고 → 화면 보유탭 강제 표시
# ============================================================
V113_MASTER_HOLDINGS_FILE = os.path.join(DATA_DIR, "v113_master_holdings.json") if "DATA_DIR" in globals() else str(BASE_DIR / "v113_master_holdings.json")
V113_STATE_FILE = os.path.join(DATA_DIR, "v113_state.json") if "DATA_DIR" in globals() else str(BASE_DIR / "v113_state.json")
V113_HOLDINGS_ENDPOINTS = [
    ("/api/dostk/acnt", "kt00018"),
    ("/api/dostk/acnt", "kt00004"),
    ("/api/dostk/acnt", "kt00005"),
]
V113_FORCE_UI_REAL_HOLDINGS = str(os.getenv("V113_FORCE_UI_REAL_HOLDINGS", "true")).lower() in ["1", "true", "yes", "on"]
V113_ALLOW_EMPTY_REAL_SYNC = str(os.getenv("V113_ALLOW_EMPTY_REAL_SYNC", "true")).lower() in ["1", "true", "yes", "on"]
V113_BLOCK_BROWSER_RESTORE = str(os.getenv("V113_BLOCK_BROWSER_RESTORE", "true")).lower() in ["1", "true", "yes", "on"]

_ORIG_WRITE_HOLDINGS_V113 = globals().get("write_holdings")

V113_STATE = {
    "version": "v113",
    "lastSyncAt": "",
    "lastOk": False,
    "lastCount": 0,
    "lastApiId": "",
    "lastMessage": "",
    "lastRawKeys": [],
    "source": "INIT",
}


def v113_code(raw):
    s = str(raw or "").strip().replace("A", "")
    s = re.sub(r"[^0-9]", "", s)
    return s.zfill(6) if s else ""


def v113_num(v, default=0):
    try:
        if v is None:
            return default
        if isinstance(v, str):
            v = v.replace(",", "").replace("+", "").replace("-", "").strip()
        return abs(safe_float(v, default))
    except Exception:
        return default


def v113_read_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def v113_write_json(path, data):
    try:
        folder = os.path.dirname(str(path))
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print("v113_write_json error:", e)
        return False


def v113_save_state():
    return v113_write_json(V113_STATE_FILE, V113_STATE)


def v113_deep_dicts(obj):
    found = []
    def walk(x):
        if isinstance(x, dict):
            found.append(x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(obj)
    return found


def v113_parse_holdings(data):
    """
    키움 실제잔고 파싱 최종 보강.
    현금/예수금 응답을 보유종목으로 오인하지 않도록
    종목코드 + 보유수량 필드가 있는 dict만 인정합니다.
    """
    if not isinstance(data, dict):
        return []

    code_keys = ["stk_cd", "pdno", "code", "isu_cd", "종목코드", "stkcd", "item_cd"]
    name_keys = ["stk_nm", "prdt_name", "name", "종목명", "isu_nm", "item_nm"]
    qty_keys = ["rmnd_qty", "hldg_qty", "hold_qty", "qty", "보유수량", "잔고수량", "현재잔고", "ord_psbl_qty", "매도가능수량", "가능수량"]
    buy_keys = ["avg_prc", "pchs_avg_pric", "pchs_avg_prc", "buyPrice", "매입평균가", "평균단가", "매입단가", "pchs_pric"]
    cur_keys = ["cur_prc", "curPrice", "currentPrice", "현재가", "now", "price", "lastPrice"]

    rows = []
    for d in v113_deep_dicts(data):
        raw_code = ""
        for k in code_keys:
            if k in d and d.get(k) not in [None, ""]:
                raw_code = d.get(k)
                break
        code = v113_code(raw_code)
        if not code or code == "000000":
            continue

        # 수량 필드가 없으면 보유종목으로 인정하지 않음
        qty = 0
        has_qty_key = False
        for k in qty_keys:
            if k in d:
                has_qty_key = True
                qty = max(qty, v113_num(d.get(k), 0))
        if not has_qty_key or qty <= 0:
            continue

        name = code
        for k in name_keys:
            if k in d and str(d.get(k, "")).strip():
                name = str(d.get(k)).strip()
                break

        buy = 0
        for k in buy_keys:
            if k in d:
                buy = max(buy, v113_num(d.get(k), 0))
        cur = 0
        for k in cur_keys:
            if k in d:
                cur = max(cur, v113_num(d.get(k), 0))
        if cur < 10:
            try:
                cur, src = get_trade_live_price(code, fallback=True)
            except Exception:
                cur, src = 0, "NONE"
        else:
            src = "KIWOOM_ACCOUNT"
        if cur < 10:
            cur = buy
            src = "ACCOUNT_AVG"

        state = read_trade_state() if "read_trade_state" in globals() else {}
        target_rate = normalize_rate_input(state.get("target_rate", 0.025), 0.025)
        stop_rate = normalize_rate_input(state.get("stop_rate", -0.018), -0.018)
        buy_amount = buy * qty if buy and qty else 0
        eval_amount = cur * qty if cur and qty else 0
        pnl = eval_amount - buy_amount if buy_amount and eval_amount else 0
        rate = ((cur - buy) / buy * 100) if buy and cur else 0

        rows.append({
            "id": int(time.time() * 1000) + len(rows),
            "name": name,
            "code": code,
            "buyPrice": round(buy),
            "avgPrice": round(buy),
            "buyAmount": round(buy_amount),
            "qty": int(qty),
            "quantity": int(qty),
            "target": round((buy or cur) * (1 + target_rate)) if (buy or cur) else 0,
            "stop": round((buy or cur) * (1 + stop_rate)) if (buy or cur) else 0,
            "lastPrice": round(cur),
            "curPrice": round(cur),
            "currentPrice": round(cur),
            "priceSource": src,
            "fromKiwoomAccount": True,
            "autoTrade": True,
            "syncSource": "KIWOOM_REAL_BALANCE_V113",
            "lastCheckedAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
            "evalAmount": round(eval_amount),
            "profitAmount": round(pnl),
            "profitRate": round(rate, 2),
            "highPrice": max(v113_num(d.get("highPrice", 0), 0), cur, buy),
            "highestPrice": max(v113_num(d.get("highestPrice", 0), 0), cur, buy),
            "aiComment": ai_comment(cur, buy, 0, 0, qty) if "ai_comment" in globals() else "키움 실제잔고 기준 보유종목입니다.",
        })

    # 중복 종목 제거: 같은 코드가 여러 번 나오면 수량 큰 항목 우선
    by_code = {}
    for h in rows:
        c = h["code"]
        if c not in by_code or v113_num(h.get("qty"), 0) >= v113_num(by_code[c].get("qty"), 0):
            by_code[c] = h
    return list(by_code.values())


# 기존 parse 함수 자체를 v113으로 교체
parse_kiwoom_holdings = v113_parse_holdings


def v113_fetch_kiwoom_holdings():
    if not kiwoom_ready():
        return {"ok": False, "version": "v113", "holdings": [], "message": "키움 환경변수 미설정"}
    last = {}
    for path, api_id in V113_HOLDINGS_ENDPOINTS:
        try:
            token = kiwoom_get_token()
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "authorization": "Bearer " + token,
                "cont-yn": "N",
                "next-key": "",
                "api-id": api_id,
            }
            body = make_kiwoom_cash_body({}) if "make_kiwoom_cash_body" in globals() else {"qry_tp": os.getenv("KIWOOM_CASH_QRY_TP", "3")}
            r = requests.post(KIWOOM_BASE_URL + path, json=body, headers=headers, timeout=10)
            try:
                data = r.json() if r.text else {}
            except Exception:
                data = {"raw": r.text[:1000]}
            items = v113_parse_holdings(data)
            last = {"api_id": api_id, "status": r.status_code, "raw_keys": list(data.keys())[:20], "raw": data}
            if r.status_code == 200:
                # 보유 0개도 정상일 수 있음. 단, 사용자는 보유가 있으므로 raw_keys를 같이 남김.
                return {"ok": True, "version": "v113", "api_id": api_id, "holdings": items, "count": len(items), "raw_keys": list(data.keys())[:20], "source": "KIWOOM_REAL_BALANCE"}
        except Exception as e:
            last = {"api_id": api_id, "error": str(e)}
            continue
    return {"ok": False, "version": "v113", "holdings": [], "count": 0, "message": "키움 실제잔고 API 호출 실패", "last": last}


def v113_save_master(items, source="KIWOOM_REAL_BALANCE", allow_empty=True):
    items = v113_parse_holdings({"items": items}) if items and not all(isinstance(x, dict) and x.get("syncSource") == "KIWOOM_REAL_BALANCE_V113" for x in items) else (items or [])
    if len(items) == 0 and not allow_empty:
        old = v113_read_json(V113_MASTER_HOLDINGS_FILE, [])
        if isinstance(old, list) and old:
            return old
    v113_write_json(V113_MASTER_HOLDINGS_FILE, items)
    try:
        if _ORIG_WRITE_HOLDINGS_V113:
            _ORIG_WRITE_HOLDINGS_V113(items)
    except Exception:
        pass
    V113_STATE["lastSyncAt"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    V113_STATE["lastCount"] = len(items)
    V113_STATE["source"] = source
    v113_save_state()
    return items


def v113_force_sync_holdings(full_sync=True):
    res = v113_fetch_kiwoom_holdings()
    V113_STATE["lastSyncAt"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    V113_STATE["lastOk"] = bool(res.get("ok"))
    V113_STATE["lastApiId"] = res.get("api_id", "")
    V113_STATE["lastRawKeys"] = res.get("raw_keys", [])
    if res.get("ok"):
        items = res.get("holdings", [])
        v113_save_master(items, source="KIWOOM_REAL_BALANCE", allow_empty=V113_ALLOW_EMPTY_REAL_SYNC)
        V113_STATE["lastCount"] = len(items)
        V113_STATE["lastMessage"] = f"키움 실제잔고 {len(items)}개 표시"
        v113_save_state()
        try:
            state = read_trade_state()
            state["last_status"] = "v113 키움 실제잔고 동기화 완료"
            state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
            state["last_order_message"] = V113_STATE["lastMessage"]
            write_trade_state(state)
        except Exception:
            pass
        return {"ok": True, "version": "v113", "holdings": items, "items": items, "data": items, "count": len(items), "state": V113_STATE, "message": "v113: 키움 실제잔고 기준으로 보유탭을 표시합니다."}

    old = v113_read_json(V113_MASTER_HOLDINGS_FILE, [])
    if not isinstance(old, list):
        old = []
    V113_STATE["lastMessage"] = res.get("message", "키움 실제잔고 조회 실패")
    V113_STATE["lastCount"] = len(old)
    v113_save_state()
    return {"ok": False, "version": "v113", "holdings": old, "items": old, "data": old, "count": len(old), "state": V113_STATE, "detail": res, "message": "키움 실제잔고 조회 실패. 기존 v113 MASTER를 표시합니다."}


def read_holdings():
    if V113_FORCE_UI_REAL_HOLDINGS:
        return v113_force_sync_holdings(full_sync=True).get("holdings", [])
    items = v113_read_json(V113_MASTER_HOLDINGS_FILE, [])
    return items if isinstance(items, list) else []


def write_holdings(items):
    # 브라우저 백업이나 빈 배열이 실제잔고를 지우지 못하게 함
    if V113_BLOCK_BROWSER_RESTORE and (not items):
        old = v113_read_json(V113_MASTER_HOLDINGS_FILE, [])
        if isinstance(old, list) and old:
            return True
    v113_save_master(items or [], source="WRITE_HOLDINGS_COMPAT", allow_empty=True)
    return True


def v113_server_holdings_response():
    return v113_force_sync_holdings(full_sync=True)


# [v114 duplicate route disabled] @app.route("/api/v119_holdings_fast", methods=["GET", "POST"])
def api_v113_server_holdings():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        action = data.get("action", "refresh")
        if action in ["clear", "delete", "remove"]:
            # 실제 키움 보유를 앱에서 지우면 다시 꼬이므로 화면 삭제 대신 실제잔고 재조회
            res = v113_server_holdings_response()
            res["message"] = "v113에서는 앱 화면 삭제가 실제 키움잔고를 덮어쓰지 않습니다. 실제잔고 기준으로 다시 표시합니다."
            return jsonify(res)
    return jsonify(v113_server_holdings_response())


# [v114 duplicate route disabled] @app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
def api_v113_force_sync_holdings():
    return jsonify(v113_force_sync_holdings(full_sync=True))


@app.route("/api/v113_real_holdings", methods=["GET", "POST"])
def api_v113_real_holdings():
    return jsonify(v113_force_sync_holdings(full_sync=True))


@app.route("/api/v113_cash")
def api_v113_cash():
    try:
        cash = get_trade_cash_info() if "get_trade_cash_info" in globals() else {}
    except Exception as e:
        cash = {"ok": False, "message": str(e)}
    return jsonify({"ok": True, "version": "v113", "cash": cash})


@app.route("/api/v113_restore_holdings", methods=["POST"])
def api_v113_restore_holdings():
    return jsonify({"ok": False, "version": "v113", "restored": 0, "message": "v113에서는 브라우저 백업 복구를 사용하지 않습니다. 키움 실제잔고를 기준으로 표시합니다.", **v113_force_sync_holdings(full_sync=True)})


# 기존 URL을 누르는 경우도 v113으로 강제 연결
# [v115 duplicate route disabled] @app.route("/api/server_holdings", methods=["GET", "POST"])
@app.route("/api/server_holdings_v109", methods=["GET", "POST"])
# [v115 duplicate route disabled] @app.route("/api/holdings", methods=["GET", "POST"])
@app.route("/api/real_holdings", methods=["GET", "POST"])
@app.route("/api/kiwoom_holdings", methods=["GET", "POST"])
@app.route("/api/force_sync_holdings", methods=["GET", "POST"])
@app.route("/api/refresh_holdings", methods=["GET", "POST"])
@app.route("/api/v109_force_sync_holdings", methods=["GET", "POST"])
def api_v113_compat_holdings():
    return jsonify(v113_force_sync_holdings(full_sync=True))


@app.route("/api/v113_version")
def api_v113_version():
    return jsonify({"ok": True, "version": "v113", "title": "KIWOOM REAL AUTO v131", "engine": "REAL HOLDINGS FINAL FIX", "state": V113_STATE, "message": "v113 실제잔고 보유탭 최종 패치가 적용되었습니다."})






# ============================================================
# v114 BUY QTY + HOLDINGS FINAL FIX
# 1주 매수 가능 보정 / minQty 강제 1 / 키움 실제잔고 endpoint 전체 확인
# ============================================================
V114_MIN_BUY_QTY = int(safe_float(os.getenv("V114_MIN_BUY_QTY", "1"), 1))
V114_ALLOW_ONE_SHARE_IF_CASH_OK = str(os.getenv("V114_ALLOW_ONE_SHARE_IF_CASH_OK", "true")).lower() in ["1", "true", "yes", "on"]
V114_MIN_AMOUNT_DEFAULT = safe_float(os.getenv("V114_MIN_AMOUNT_DEFAULT", "300000000"), 300000000)
V114_MIN_SCORE_DEFAULT = safe_float(os.getenv("V114_MIN_SCORE_DEFAULT", "65"), 65)


def v114_code(raw):
    s = str(raw or "").strip().replace("A", "")
    s = re.sub(r"[^0-9]", "", s)
    return s.zfill(6) if s else ""


def v114_orderable_cash():
    candidates = []
    errors = []
    for fn_name in ["kiwoom_get_account_cash", "get_trade_cash_info", "get_kiwoom_account_cash"]:
        try:
            fn = globals().get(fn_name)
            if not fn:
                continue
            try:
                res = fn(force=True)
            except TypeError:
                res = fn()
            if isinstance(res, dict):
                vals = [
                    safe_float(res.get("orderable_cash", 0), 0),
                    safe_float(res.get("kiwoom_orderable_cash", 0), 0),
                    safe_float(res.get("available_cash", 0), 0),
                    safe_float(res.get("cash", 0), 0),
                    safe_float(res.get("deposit", 0), 0),
                ]
                c = max(vals)
                if c > 0:
                    candidates.append((c, fn_name, res))
        except Exception as e:
            errors.append(f"{fn_name}: {e}")
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        c, src, raw = candidates[0]
        return c, {"ok": True, "source": src, "raw": raw, "orderable_cash": c}
    return 0, {"ok": False, "message": "; ".join(errors) or "키움 주문가능금액 조회 실패"}


def get_auto_order_budget():
    """
    v114:
    - 키움 주문가능금액 기준
    - 예산이 최소진입금보다 작아도 1주 매수 가능한 경우 통과
    - 기존 '키움 주문가능금액 기준 자동 계산'만 뜨던 문제를 상세 메시지로 수정
    """
    state = read_trade_state()
    orderable, cash_raw = v114_orderable_cash()

    if orderable <= 0:
        return {
            "ok": False,
            "message": "키움 주문가능금액 조회 실패",
            "orderable_cash": 0,
            "budget": 0,
            "cash_info": cash_raw,
            "v114": True
        }

    position_count = get_current_position_count() if "get_current_position_count" in globals() else len(read_holdings())
    max_positions = max(1, int(safe_float(state.get("max_positions", globals().get("MAX_POSITION_COUNT", 3)), 3)))
    remain_slots = max(1, max_positions - position_count)

    position_rate = safe_float(globals().get("POSITION_CASH_RATE", 0.33), 0.33)
    safety = safe_float(globals().get("ORDER_CASH_SAFETY_RATE", 0.96), 0.96)
    rate_budget = orderable * position_rate
    slot_budget = orderable / remain_slots
    budget = min(rate_budget, slot_budget) * safety

    # 최소진입금보다 작더라도, 실제 1주 매수는 v114_calc_final_order_qty에서 최종 허용
    return {
        "ok": True,
        "message": f"v114 키움 주문가능금액 {orderable:,.0f}원 기준 예산 계산 완료",
        "orderable_cash": int(orderable),
        "kiwoom_orderable_cash": int(orderable),
        "budget": int(max(0, budget)),
        "final_order_budget": int(max(0, budget)),
        "cash_info": cash_raw,
        "remain_slots": remain_slots,
        "position_count": position_count,
        "v114": True
    }


def v114_calc_final_order_qty(pick=None, live_price=0):
    price = safe_float(live_price or ((pick or {}).get("price", 0) if isinstance(pick, dict) else 0), 0)
    if price <= 0:
        return 0, {"ok": False, "message": "현재가가 0원이어서 주문수량 계산 불가", "price": price, "v114": True}

    orderable, cash_raw = v114_orderable_cash()
    if orderable < price:
        return 0, {
            "ok": False,
            "message": f"주문가능금액이 현재가보다 작습니다. 주문가능 {orderable:,.0f}원 / 현재가 {price:,.0f}원",
            "orderable_cash": int(orderable),
            "price": int(price),
            "cash_raw": cash_raw,
            "v114": True
        }

    budget_info = get_auto_order_budget()
    budget = safe_float(budget_info.get("final_order_budget", budget_info.get("budget", 0)), 0)
    safety_cash = orderable * safe_float(globals().get("ORDER_CASH_SAFETY_RATE", 0.96), 0.96)

    # 예산이 너무 작더라도 1주 가능하면 1주를 허용
    if V114_ALLOW_ONE_SHARE_IF_CASH_OK and orderable >= price:
        budget = max(budget, price)

    final_budget = min(max(budget, price), safety_cash if safety_cash >= price else orderable)
    qty = int(final_budget // price)

    if qty <= 0 and orderable >= price:
        qty = 1
        final_budget = price

    return qty, {
        "ok": qty > 0,
        "label": "v114 AI 추천 진입금액",
        "message": f"v114 주문가능금액 기준 {qty}주 매수 가능" if qty > 0 else "v114 최종 주문수량 0",
        "orderable_cash": int(orderable),
        "kiwoom_orderable_cash": int(orderable),
        "price": int(price),
        "final_order_budget": int(final_budget),
        "budget": int(final_budget),
        "qty": int(qty),
        "cash_raw": cash_raw,
        "budget_info": budget_info,
        "v114": True
    }


# 기존 수량 계산 함수들을 v114로 통일
v109_calc_final_order_qty = v114_calc_final_order_qty
v109_calc_order_qty_from_ai_budget = v114_calc_final_order_qty
calc_auto_cash_order_qty = v114_calc_final_order_qty


def trade_can_buy_v109(code, price):
    """
    v114 보정:
    기존 로직처럼 budget < MIN_ORDER_CASH만으로 막지 않고,
    주문가능금액 >= 현재가이면 1주 매수 가능으로 허용.
    """
    state = read_trade_state()
    code = v114_code(code)

    if not state.get("auto_trade_enabled"):
        return False, "실전 자동매매가 OFF입니다."
    if state.get("panic_stop"):
        return False, "긴급정지 상태입니다."
    if not market_is_open():
        return False, "정규장 시간이 아닙니다."
    if safe_float(price, 0) <= 0:
        return False, "현재가 확인 실패"

    holding_codes = get_open_holding_codes() if "get_open_holding_codes" in globals() else set()
    if code in holding_codes:
        return False, "이미 보유 중인 종목이라 중복 매수하지 않습니다."

    max_positions = max(1, int(safe_float(state.get("max_positions", globals().get("MAX_POSITION_COUNT", 3)), 3)))
    current_positions = get_current_position_count() if "get_current_position_count" in globals() else len(read_holdings())
    if current_positions >= max_positions:
        return False, f"동시 보유 최대 {max_positions}종목 제한입니다."

    orderable, cash_raw = v114_orderable_cash()
    if orderable < safe_float(price, 0):
        return False, f"주문가능금액 부족: 주문가능 {orderable:,.0f}원 / 현재가 {safe_float(price, 0):,.0f}원"

    return True, f"v114 1주 이상 매수 가능: 주문가능 {orderable:,.0f}원"


def v114_normalize_buy_args(args=None):
    """
    화면에서 minQty=5가 넘어와도 실전 즉시매수는 1주 가능 기준으로 보정.
    """
    data = {}
    try:
        if args:
            for k in args.keys():
                data[k] = args.get(k)
    except Exception:
        data = {}
    cash, _raw = v114_orderable_cash()
    data["cash"] = max(safe_float(data.get("cash", 0), 0), cash, safe_float(globals().get("MIN_ORDER_CASH", 30000), 30000))
    data["minQty"] = V114_MIN_BUY_QTY
    data["minAmount"] = min(safe_float(data.get("minAmount", V114_MIN_AMOUNT_DEFAULT), V114_MIN_AMOUNT_DEFAULT), V114_MIN_AMOUNT_DEFAULT)
    data["minScore"] = min(safe_float(data.get("minScore", V114_MIN_SCORE_DEFAULT), V114_MIN_SCORE_DEFAULT), V114_MIN_SCORE_DEFAULT)
    if "maxChange" not in data or safe_float(data.get("maxChange", 0), 0) <= 0:
        data["maxChange"] = 12
    return data


_ORIG_AUTO_BUY_BEST_PICK_V114 = globals().get("auto_buy_best_pick")


def auto_buy_best_pick(args=None, use_latest_ui_pick=False):
    """
    v114 즉시매수:
    - 화면 필터가 minQty=5여도 1주 기준으로 보정
    - 주문가능금액이 작으면 1주 살 수 있는 후보만 선택
    - 실패 메시지 상세화
    """
    fixed_args = v114_normalize_buy_args(args)
    result = _ORIG_AUTO_BUY_BEST_PICK_V114(args=fixed_args, use_latest_ui_pick=False) if _ORIG_AUTO_BUY_BEST_PICK_V114 else {"ok": False, "message": "기존 자동매수 함수 없음"}
    if isinstance(result, dict) and not result.get("ok"):
        msg = str(result.get("message", ""))
        if msg.strip() == "키움 주문가능금액 기준 자동 계산" or "자동 계산" in msg:
            orderable, _ = v114_orderable_cash()
            result["message"] = f"v114 매수 보류: 주문가능금액 {orderable:,.0f}원 기준 1주 이상 매수 가능한 후보를 재탐색했지만 조건 충족 후보가 부족합니다. 최소 수량은 1주로 보정했습니다."
            result["v114_fixed"] = True
    return result


def v114_deep_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from v114_deep_dicts(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from v114_deep_dicts(x)


def v114_num(v, default=0):
    try:
        s = str(v if v is not None else "").replace(",", "").replace("+", "").strip()
        # 키움 현재가/수량은 음수 부호가 붙는 경우가 있어 절대값 처리
        s = s.replace("-", "")
        return safe_float(s, default)
    except Exception:
        return default


def v114_parse_holdings(data):
    """
    키움 실제잔고 파싱 강화.
    종목코드 + 수량 계열 필드가 있는 dict만 보유종목으로 인정.
    """
    code_keys = ["stk_cd", "stkcd", "pdno", "code", "isu_cd", "isu_no", "종목코드", "item_cd", "stock_code", "shtn_pdno"]
    name_keys = ["stk_nm", "stkname", "prdt_name", "name", "종목명", "isu_nm", "item_nm", "stock_name", "prdt_name"]
    qty_keys = ["rmnd_qty", "hldg_qty", "hold_qty", "qty", "quantity", "보유수량", "잔고수량", "현재잔고", "매도가능수량", "ord_psbl_qty", "가능수량", "sell_psbl_qty", "trad_psbl_qty", "evlu_qty"]
    buy_keys = ["avg_prc", "pchs_avg_pric", "pchs_avg_prc", "buyPrice", "매입평균가", "평균단가", "매입단가", "pchs_pric", "pchs_amt_avg_pric"]
    cur_keys = ["cur_prc", "curPrice", "currentPrice", "현재가", "now", "price", "lastPrice", "stck_prpr"]
    rows = []

    for d in v114_deep_dicts(data):
        if not isinstance(d, dict):
            continue
        raw_code = ""
        for k in code_keys:
            if k in d and str(d.get(k, "")).strip():
                raw_code = d.get(k)
                break
        code = v114_code(raw_code)
        if not code or code == "000000":
            continue

        qty = 0
        has_qty = False
        for k in qty_keys:
            if k in d:
                has_qty = True
                qty = max(qty, v114_num(d.get(k), 0))
        if not has_qty or qty <= 0:
            continue

        name = code
        for k in name_keys:
            if k in d and str(d.get(k, "")).strip():
                name = str(d.get(k)).strip()
                break

        buy = 0
        for k in buy_keys:
            if k in d:
                buy = max(buy, v114_num(d.get(k), 0))

        cur = 0
        for k in cur_keys:
            if k in d:
                cur = max(cur, v114_num(d.get(k), 0))

        src = "KIWOOM_ACCOUNT"
        if cur < 10:
            try:
                cur, src = get_trade_live_price(code, fallback=True)
            except Exception:
                cur, src = 0, "NONE"
        if cur < 10:
            cur = buy
            src = "ACCOUNT_AVG"

        state = read_trade_state() if "read_trade_state" in globals() else {}
        target_rate = normalize_rate_input(state.get("target_rate", 0.025), 0.025)
        stop_rate = normalize_rate_input(state.get("stop_rate", -0.018), -0.018)
        buy_amount = buy * qty if buy and qty else 0
        eval_amount = cur * qty if cur and qty else 0
        pnl = eval_amount - buy_amount if buy_amount and eval_amount else 0
        rate = ((cur - buy) / buy * 100) if buy and cur else 0

        rows.append({
            "id": int(time.time() * 1000) + len(rows),
            "name": name,
            "code": code,
            "buyPrice": round(buy),
            "avgPrice": round(buy),
            "buyAmount": round(buy_amount),
            "qty": int(qty),
            "quantity": int(qty),
            "target": round((buy or cur) * (1 + target_rate)) if (buy or cur) else 0,
            "stop": round((buy or cur) * (1 + stop_rate)) if (buy or cur) else 0,
            "lastPrice": round(cur),
            "curPrice": round(cur),
            "currentPrice": round(cur),
            "priceSource": src,
            "fromKiwoomAccount": True,
            "autoTrade": True,
            "syncSource": "KIWOOM_REAL_BALANCE_V114",
            "lastCheckedAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
            "evalAmount": round(eval_amount),
            "profitAmount": round(pnl),
            "profitRate": round(rate, 2),
            "highPrice": max(v114_num(d.get("highPrice", 0), 0), cur, buy),
            "highestPrice": max(v114_num(d.get("highestPrice", 0), 0), cur, buy),
            "aiComment": ai_comment(cur, buy, 0, 0, qty) if "ai_comment" in globals() else "키움 실제잔고 기준 보유종목입니다.",
        })

    by_code = {}
    for h in rows:
        c = h["code"]
        if c not in by_code or v114_num(h.get("qty"), 0) >= v114_num(by_code[c].get("qty"), 0):
            by_code[c] = h
    return list(by_code.values())


parse_kiwoom_holdings = v114_parse_holdings


def v114_fetch_kiwoom_holdings():
    """
    첫 endpoint가 0개라도 멈추지 않고 모든 endpoint를 확인.
    holdings가 발견된 응답을 우선 사용.
    """
    if not kiwoom_ready():
        return {"ok": False, "version": "v114", "holdings": [], "message": "키움 환경변수 미설정"}

    endpoints = globals().get("V113_HOLDINGS_ENDPOINTS", [
        ("/api/dostk/acnt", "kt00018"),
        ("/api/dostk/acnt", "kt00004"),
        ("/api/dostk/acnt", "kt00005"),
        ("/api/dostk/acnt", "kt00001"),
    ])

    attempts = []
    first_ok_empty = None

    for path, api_id in endpoints:
        try:
            token = kiwoom_get_token()
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "authorization": "Bearer " + token,
                "cont-yn": "N",
                "next-key": "",
                "api-id": api_id,
            }
            body = make_kiwoom_cash_body({}) if "make_kiwoom_cash_body" in globals() else {"qry_tp": os.getenv("KIWOOM_CASH_QRY_TP", "3")}
            r = requests.post(KIWOOM_BASE_URL + path, json=body, headers=headers, timeout=10)
            try:
                data = r.json() if r.text else {}
            except Exception:
                data = {"raw": r.text[:1000]}
            items = v114_parse_holdings(data)
            attempt = {"api_id": api_id, "status": r.status_code, "count": len(items), "raw_keys": list(data.keys())[:30]}
            attempts.append(attempt)

            if r.status_code == 200 and items:
                return {"ok": True, "version": "v114", "api_id": api_id, "holdings": items, "count": len(items), "source": "KIWOOM_REAL_BALANCE", "attempts": attempts}

            if r.status_code == 200 and first_ok_empty is None:
                first_ok_empty = {"ok": True, "version": "v114", "api_id": api_id, "holdings": [], "count": 0, "source": "KIWOOM_REAL_BALANCE_EMPTY", "attempts": attempts, "raw_keys": list(data.keys())[:30]}

        except Exception as e:
            attempts.append({"api_id": api_id, "error": str(e)})
            continue

    if first_ok_empty is not None:
        first_ok_empty["attempts"] = attempts
        return first_ok_empty

    return {"ok": False, "version": "v114", "holdings": [], "count": 0, "message": "키움 실제잔고 API 호출 실패", "attempts": attempts}


def v113_fetch_kiwoom_holdings():
    return v114_fetch_kiwoom_holdings()


# [v114 duplicate route disabled] @app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
def api_v114_force_sync_holdings():
    if "v113_force_sync_holdings" in globals():
        res = v113_force_sync_holdings(full_sync=True)
    else:
        res = v114_fetch_kiwoom_holdings()
    res["version"] = "v114"
    return jsonify(res)


# [v114 duplicate route disabled] @app.route("/api/v119_holdings_fast", methods=["GET", "POST"])
def api_v114_server_holdings():
    res = v113_force_sync_holdings(full_sync=True) if "v113_force_sync_holdings" in globals() else v114_fetch_kiwoom_holdings()
    res["version"] = "v114"
    return jsonify(res)


@app.route("/api/v114_holdings_debug")
def api_v114_holdings_debug():
    return jsonify(v114_fetch_kiwoom_holdings())


@app.route("/api/v114_order_qty_test")
def api_v114_order_qty_test():
    code = request.args.get("code", "")
    price = safe_float(request.args.get("price", 0), 0)
    if price <= 0 and code:
        price, src = get_trade_live_price(code, fallback=True)
    qty, info = v114_calc_final_order_qty({"code": code, "price": price}, price)
    return jsonify({"ok": qty > 0, "version": "v114", "qty": qty, "info": info})


@app.route("/api/v114_cash")
def api_v114_cash():
    c, raw = v114_orderable_cash()
    return jsonify({"ok": c > 0, "version": "v114", "orderable_cash": int(c), "raw": raw, "budget": get_auto_order_budget()})


@app.route("/api/v114_version")
def api_v114_version():
    return jsonify({"ok": True, "version": "v114", "title": "KIWOOM REAL AUTO v131", "engine": "BUY_QTY_HOLDINGS_FIX", "message": "v114 1주 매수/보유종목 동기화 패치 적용"})


# 기존 UI가 호출하는 URL도 v114로 강제 연결
# [v115 duplicate route disabled] @app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
def api_v113_force_sync_holdings_v114_override():
    return api_v114_force_sync_holdings()


# [v115 duplicate route disabled] @app.route("/api/v119_holdings_fast", methods=["GET", "POST"])
def api_v113_server_holdings_v114_override():
    return api_v114_server_holdings()





# ============================================================
# v115 AUTO SYNC + SMART POSITION SIZE
# 매수 후 실제잔고 자동동기화 / AI 점수 기반 매수수량 확대
# ============================================================
V115_SMART_SIZE_ENABLED = str(os.getenv("V115_SMART_SIZE_ENABLED", "true")).lower() in ["1", "true", "yes", "on"]
V115_MAX_CASH_USE_RATE = safe_float(os.getenv("V115_MAX_CASH_USE_RATE", "0.82"), 0.82)
V115_MID_CASH_USE_RATE = safe_float(os.getenv("V115_MID_CASH_USE_RATE", "0.55"), 0.55)
V115_LOW_CASH_USE_RATE = safe_float(os.getenv("V115_LOW_CASH_USE_RATE", "0.33"), 0.33)
V115_MIN_BUY_QTY = int(safe_float(os.getenv("V115_MIN_BUY_QTY", "1"), 1))
V115_SYNC_AFTER_BUY_DELAY_SEC = safe_float(os.getenv("V115_SYNC_AFTER_BUY_DELAY_SEC", "1.5"), 1.5)


def v115_orderable_cash():
    if "v114_orderable_cash" in globals():
        return v114_orderable_cash()
    return 0, {"ok": False, "message": "주문가능금액 함수 없음"}


def v115_score_of_pick(pick):
    if not isinstance(pick, dict):
        return 0
    return max(
        safe_float(pick.get("aiScore", 0), 0),
        safe_float(pick.get("aiScoreV109", 0), 0),
        safe_float(pick.get("aiScoreV110", 0), 0),
        safe_float(pick.get("score", 0), 0),
        safe_float(pick.get("orderPriority", 0), 0),
    )


def v115_cash_use_rate(score, current_positions=0, max_positions=3):
    score = safe_float(score, 0)
    if score >= 95:
        rate = V115_MAX_CASH_USE_RATE
    elif score >= 85:
        rate = V115_MID_CASH_USE_RATE
    else:
        rate = V115_LOW_CASH_USE_RATE
    try:
        remain_slots = max(1, int(max_positions) - int(current_positions))
        slot_rate = min(0.95, 1.0 / remain_slots)
        rate = min(rate, max(slot_rate, V115_LOW_CASH_USE_RATE))
    except Exception:
        pass
    return max(0.05, min(0.95, rate))


def v115_calc_final_order_qty(pick=None, live_price=0):
    pick = pick or {}
    price = safe_float(live_price or pick.get("price", pick.get("buyPrice", pick.get("buyZone", 0))), 0)
    if price <= 0:
        return 0, {"ok": False, "message": "현재가가 0원이어서 주문수량 계산 불가", "v115": True}

    orderable, raw = v115_orderable_cash()
    if orderable < price:
        return 0, {
            "ok": False,
            "message": f"주문가능금액 부족: 주문가능 {orderable:,.0f}원 / 현재가 {price:,.0f}원",
            "orderable_cash": int(orderable),
            "price": int(price),
            "v115": True,
            "raw": raw
        }

    state = read_trade_state() if "read_trade_state" in globals() else {}
    max_positions = max(1, int(safe_float(state.get("max_positions", globals().get("MAX_POSITION_COUNT", 3)), 3)))
    current_positions = get_current_position_count() if "get_current_position_count" in globals() else len(read_holdings())
    score = v115_score_of_pick(pick)
    rate = v115_cash_use_rate(score, current_positions, max_positions) if V115_SMART_SIZE_ENABLED else safe_float(globals().get("POSITION_CASH_RATE", 0.33), 0.33)
    safety = safe_float(globals().get("ORDER_CASH_SAFETY_RATE", 0.96), 0.96)
    use_cash = max(price, orderable * rate * safety)
    qty = int(use_cash // price)
    if qty <= 0 and orderable >= price:
        qty = 1
        use_cash = price

    return qty, {
        "ok": qty >= V115_MIN_BUY_QTY,
        "message": f"v115 AI 스마트수량 {qty}주 산정",
        "label": "v115 AI 스마트 진입금액",
        "qty": int(qty),
        "price": int(price),
        "orderable_cash": int(orderable),
        "kiwoom_orderable_cash": int(orderable),
        "cash_use_rate": round(rate, 3),
        "score": round(score, 2),
        "estimated_order_amount": int(qty * price),
        "final_order_budget": int(use_cash),
        "current_positions": current_positions,
        "max_positions": max_positions,
        "raw": raw,
        "v115": True
    }


# 수량 계산 함수 통일
v114_calc_final_order_qty = v115_calc_final_order_qty
v109_calc_final_order_qty = v115_calc_final_order_qty
v109_calc_order_qty_from_ai_budget = v115_calc_final_order_qty
calc_auto_cash_order_qty = v115_calc_final_order_qty


def get_auto_order_budget():
    orderable, raw = v115_orderable_cash()
    safety = safe_float(globals().get("ORDER_CASH_SAFETY_RATE", 0.96), 0.96)
    return {
        "ok": orderable > 0,
        "message": f"v115 키움 주문가능금액 {orderable:,.0f}원 확인",
        "orderable_cash": int(orderable),
        "kiwoom_orderable_cash": int(orderable),
        "budget": int(orderable * V115_MAX_CASH_USE_RATE * safety),
        "final_order_budget": int(orderable * V115_MAX_CASH_USE_RATE * safety),
        "cash_info": raw,
        "v115": True
    }


def v115_sync_holdings_now():
    for fn_name in ["v114_fetch_kiwoom_holdings", "v113_force_sync_holdings", "v112_fetch_real_holdings", "v111_sync_master_holdings"]:
        try:
            fn = globals().get(fn_name)
            if not fn:
                continue
            try:
                res = fn(full_sync=True)
            except TypeError:
                try:
                    res = fn(force=True)
                except TypeError:
                    res = fn()
            if isinstance(res, dict):
                items = res.get("holdings", res.get("items", res.get("data", [])))
                if isinstance(items, list):
                    try:
                        write_holdings(items)
                    except Exception:
                        pass
                    return {"ok": True, "source": fn_name, "count": len(items), "holdings": items}
        except Exception as e:
            last_error = str(e)
            continue
    return {"ok": False, "message": "매수 후 보유종목 동기화 실패"}


def v115_force_sync_holdings_after_buy():
    time.sleep(max(0, V115_SYNC_AFTER_BUY_DELAY_SEC))
    return v115_sync_holdings_now()


_ORIG_KIWOOM_ORDER_V115 = globals().get("kiwoom_order")

def kiwoom_order(side, code, qty, price=0, order_type="market"):
    result = _ORIG_KIWOOM_ORDER_V115(side, code, qty, price, order_type) if _ORIG_KIWOOM_ORDER_V115 else {"ok": False, "message": "기존 주문함수 없음"}
    try:
        side_s = str(side).lower()
        ok = isinstance(result, dict) and (result.get("ok") or str(result.get("return_code", "")) in ["0", "00"])
        if ok and (side_s in ["buy", "매수", "1"]):
            result["v115_after_buy_sync"] = v115_force_sync_holdings_after_buy()
    except Exception as e:
        if isinstance(result, dict):
            result["v115_after_buy_sync_error"] = str(e)
    return result


_ORIG_AUTO_BUY_BEST_PICK_V115 = globals().get("auto_buy_best_pick")

def auto_buy_best_pick(args=None, use_latest_ui_pick=False):
    fixed = {}
    try:
        if args:
            for k in args.keys():
                fixed[k] = args.get(k)
    except Exception:
        fixed = {}
    fixed["minQty"] = 1
    fixed["minScore"] = min(safe_float(fixed.get("minScore", 65), 65), 65)
    fixed["minAmount"] = min(safe_float(fixed.get("minAmount", 300000000), 300000000), 300000000)

    result = _ORIG_AUTO_BUY_BEST_PICK_V115(args=fixed, use_latest_ui_pick=False) if _ORIG_AUTO_BUY_BEST_PICK_V115 else {"ok": False, "message": "기존 자동매수 함수 없음"}
    try:
        if isinstance(result, dict) and result.get("ok"):
            result["v115_after_buy_sync"] = v115_force_sync_holdings_after_buy()
    except Exception as e:
        if isinstance(result, dict):
            result["v115_after_buy_sync_error"] = str(e)

    if isinstance(result, dict) and not result.get("ok"):
        msg = str(result.get("message", ""))
        if "자동 계산" in msg or "수량" in msg or "qty" in msg.lower():
            orderable, _ = v115_orderable_cash()
            result["message"] = f"v115 매수 보류: 주문가능금액 {orderable:,.0f}원 기준 1주 이상 가능한 AI 후보를 찾지 못했습니다. 필터를 낮춰 재탐색합니다."
            result["v115_fixed"] = True
    return result


def v115_real_holdings_payload():
    sync = v115_sync_holdings_now()
    items = sync.get("holdings", []) if isinstance(sync, dict) else []
    return {
        "ok": bool(sync.get("ok")) if isinstance(sync, dict) else False,
        "version": "v115",
        "holdings": items,
        "items": items,
        "data": items,
        "count": len(items),
        "registeredCount": len(items),
        "source": sync.get("source", "UNKNOWN") if isinstance(sync, dict) else "UNKNOWN",
        "message": "v115 키움 실제잔고 기준 보유종목 동기화",
        "cash": get_auto_order_budget(),
    }


@app.route("/api/v115_smart_qty_test")
def api_v115_smart_qty_test():
    code = request.args.get("code", "")
    price = safe_float(request.args.get("price", 0), 0)
    score = safe_float(request.args.get("score", 100), 100)
    if price <= 0 and code:
        price, src = get_trade_live_price(code, fallback=True)
    qty, info = v115_calc_final_order_qty({"code": code, "price": price, "score": score, "orderPriority": score}, price)
    return jsonify({"ok": qty > 0, "version": "v115", "qty": qty, "info": info})


# [v115 duplicate route disabled] @app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
def api_v115_force_sync_holdings():
    return jsonify(v115_real_holdings_payload())


# [v115 duplicate route disabled] @app.route("/api/v119_holdings_fast", methods=["GET", "POST"])
def api_v115_server_holdings():
    return jsonify(v115_real_holdings_payload())


@app.route("/api/v115_cash")
def api_v115_cash():
    return jsonify({"ok": True, "version": "v115", "budget": get_auto_order_budget()})


@app.route("/api/v115_version")
def api_v115_version():
    return jsonify({
        "ok": True,
        "version": "v115",
        "title": "KIWOOM REAL AUTO v131",
        "engine": "AUTO_SYNC_SMART_SIZE",
        "message": "v115 매수 후 자동잔고동기화 + AI 스마트 수량 산정 적용"
    })


# [v116 duplicate route disabled] @app.route("/api/v119_holdings_fast", methods=["GET", "POST"])
def api_v114_server_holdings_v115_override():
    return api_v115_server_holdings()


# [v116 duplicate route disabled] @app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
def api_v114_force_sync_holdings_v115_override():
    return api_v115_force_sync_holdings()


# [v117 duplicate route disabled] @app.route("/api/server_holdings", methods=["GET", "POST"])
def api_server_holdings_v115_override():
    return api_v115_server_holdings()


# [v117 duplicate route disabled] @app.route("/api/holdings", methods=["GET", "POST"])
def api_holdings_v115_override():
    return api_v115_server_holdings()





# ============================================================
# v116 LOADING JS FIX
# 삭제된 수동등록 UI 참조 오류로 로딩이 멈추는 문제 방지
# ============================================================

@app.route("/api/v116_version")
def api_v116_version():
    return jsonify({
        "ok": True,
        "version": "v116",
        "title": "KIWOOM REAL AUTO v131",
        "engine": "LOADING_JS_FIX",
        "message": "v116 로딩 멈춤 JS 오류 수정 및 키움 실보유 동기화 유지"
    })

# [v117 duplicate route disabled] @app.route("/api/v119_holdings_fast", methods=["GET", "POST"])
def api_v116_server_holdings():
    if "api_v115_server_holdings" in globals():
        return api_v115_server_holdings()
    if "v115_real_holdings_payload" in globals():
        return jsonify(v115_real_holdings_payload())
    return jsonify({"ok": False, "version": "v116", "message": "보유종목 API 연결 실패"})

# [v117 duplicate route disabled] @app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
def api_v116_force_sync_holdings():
    if "api_v115_force_sync_holdings" in globals():
        return api_v115_force_sync_holdings()
    if "v115_real_holdings_payload" in globals():
        return jsonify(v115_real_holdings_payload())
    return jsonify({"ok": False, "version": "v116", "message": "강제동기화 API 연결 실패"})





# ============================================================
# v117 STRONG SIZE + REAL HOLDING SYNC
# AI 고점수 후보는 더 큰 수량 매수 / 키움 실보유 자동동기화 강화
# ============================================================
V117_STRONG_SIZE_ENABLED = str(os.getenv("V117_STRONG_SIZE_ENABLED", "true")).lower() in ["1", "true", "yes", "on"]
V117_SUPER_SCORE_RATE = safe_float(os.getenv("V117_SUPER_SCORE_RATE", "0.94"), 0.94)   # AI 98~100
V117_HIGH_SCORE_RATE = safe_float(os.getenv("V117_HIGH_SCORE_RATE", "0.88"), 0.88)     # AI 95+
V117_MID_SCORE_RATE = safe_float(os.getenv("V117_MID_SCORE_RATE", "0.70"), 0.70)       # AI 85+
V117_LOW_SCORE_RATE = safe_float(os.getenv("V117_LOW_SCORE_RATE", "0.45"), 0.45)
V117_ORDER_SAFETY_RATE = safe_float(os.getenv("V117_ORDER_SAFETY_RATE", "0.97"), 0.97)
V117_MIN_BUY_QTY = int(safe_float(os.getenv("V117_MIN_BUY_QTY", "1"), 1))
V117_AFTER_BUY_SYNC_DELAYS = [1.0, 3.0, 6.0]


def v117_code(raw):
    s = str(raw or "").strip().replace("A", "")
    s = re.sub(r"[^0-9]", "", s)
    return s.zfill(6) if s else ""


def v117_num(v, default=0):
    try:
        s = str(v if v is not None else "").replace(",", "").replace("+", "").strip()
        # 키움은 현재가/평가손익에 부호가 붙는 경우가 많음. 수량/가격 파싱용으로 부호 제거.
        s = s.replace("-", "")
        if s == "":
            return default
        return safe_float(s, default)
    except Exception:
        return default


def v117_orderable_cash():
    # 기존 v114/v115 함수 우선 사용
    for fn_name in ["v115_orderable_cash", "v114_orderable_cash"]:
        try:
            fn = globals().get(fn_name)
            if fn:
                c, raw = fn()
                if safe_float(c, 0) > 0:
                    return safe_float(c, 0), raw
        except Exception:
            pass

    candidates = []
    for fn_name in ["kiwoom_get_account_cash", "get_trade_cash_info", "get_kiwoom_account_cash"]:
        try:
            fn = globals().get(fn_name)
            if not fn:
                continue
            try:
                res = fn(force=True)
            except TypeError:
                res = fn()
            if isinstance(res, dict):
                c = max(
                    safe_float(res.get("orderable_cash", 0), 0),
                    safe_float(res.get("kiwoom_orderable_cash", 0), 0),
                    safe_float(res.get("available_cash", 0), 0),
                    safe_float(res.get("cash", 0), 0),
                    safe_float(res.get("deposit", 0), 0),
                )
                if c > 0:
                    candidates.append((c, fn_name, res))
        except Exception:
            pass

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        c, src, raw = candidates[0]
        return c, {"ok": True, "source": src, "raw": raw, "orderable_cash": c}
    return 0, {"ok": False, "message": "키움 주문가능금액 조회 실패"}


def v117_pick_score(pick):
    if not isinstance(pick, dict):
        return 0
    return max(
        safe_float(pick.get("aiScore", 0), 0),
        safe_float(pick.get("aiScoreV109", 0), 0),
        safe_float(pick.get("aiScoreV110", 0), 0),
        safe_float(pick.get("v110LearningScore", 0), 0),
        safe_float(pick.get("score", 0), 0),
        safe_float(pick.get("orderPriority", 0), 0),
    )


def v117_size_rate(score):
    score = safe_float(score, 0)
    if score >= 98:
        return V117_SUPER_SCORE_RATE
    if score >= 95:
        return V117_HIGH_SCORE_RATE
    if score >= 85:
        return V117_MID_SCORE_RATE
    return V117_LOW_SCORE_RATE


def v117_calc_final_order_qty(pick=None, live_price=0):
    """
    v117 강한 수량 계산.
    예: 주문가능금액 336,787원, 현재가 109,700원, AI 100점이면
    1주가 아니라 2~3주까지 가능하게 계산.
    """
    pick = pick or {}
    price = safe_float(live_price or pick.get("price", pick.get("buyPrice", pick.get("buyZone", 0))), 0)
    if price <= 0:
        return 0, {"ok": False, "message": "현재가가 0원이어서 주문수량 계산 불가", "v117": True}

    orderable, raw = v117_orderable_cash()
    if orderable < price:
        return 0, {
            "ok": False,
            "message": f"주문가능금액 부족: 주문가능 {orderable:,.0f}원 / 현재가 {price:,.0f}원",
            "orderable_cash": int(orderable),
            "price": int(price),
            "v117": True,
            "raw": raw
        }

    score = v117_pick_score(pick)
    rate = v117_size_rate(score) if V117_STRONG_SIZE_ENABLED else safe_float(globals().get("POSITION_CASH_RATE", 0.33), 0.33)

    # 이미 보유 종목 수가 많아도, v117은 "AI가 고점수면 1주씩 찔끔 매수"를 방지하기 위해
    # 남은 주문가능금액 기준으로 직접 계산한다.
    usable_cash = orderable * rate * V117_ORDER_SAFETY_RATE

    # 최소 1주는 반드시 살 수 있게 보정
    if usable_cash < price and orderable >= price:
        usable_cash = price

    qty = int(usable_cash // price)
    if qty <= 0 and orderable >= price:
        qty = 1
        usable_cash = price

    # 안전상 주문가능금액 초과 방지
    while qty > 0 and qty * price > orderable * V117_ORDER_SAFETY_RATE:
        qty -= 1
    if qty <= 0 and orderable >= price:
        qty = 1

    return qty, {
        "ok": qty >= V117_MIN_BUY_QTY,
        "message": f"v117 AI 강한수량 {qty}주 산정",
        "label": "v117 AI 강한 진입금액",
        "qty": int(qty),
        "price": int(price),
        "orderable_cash": int(orderable),
        "kiwoom_orderable_cash": int(orderable),
        "cash_use_rate": round(rate, 3),
        "safety_rate": round(V117_ORDER_SAFETY_RATE, 3),
        "score": round(score, 2),
        "estimated_order_amount": int(qty * price),
        "final_order_budget": int(usable_cash),
        "raw": raw,
        "v117": True
    }


# 기존 수량 계산 함수 강제 통일
v115_calc_final_order_qty = v117_calc_final_order_qty
v114_calc_final_order_qty = v117_calc_final_order_qty
v109_calc_final_order_qty = v117_calc_final_order_qty
v109_calc_order_qty_from_ai_budget = v117_calc_final_order_qty
calc_auto_cash_order_qty = v117_calc_final_order_qty


def get_auto_order_budget():
    orderable, raw = v117_orderable_cash()
    return {
        "ok": orderable > 0,
        "message": f"v117 키움 주문가능금액 {orderable:,.0f}원 확인",
        "orderable_cash": int(orderable),
        "kiwoom_orderable_cash": int(orderable),
        "budget": int(orderable * V117_SUPER_SCORE_RATE * V117_ORDER_SAFETY_RATE),
        "final_order_budget": int(orderable * V117_SUPER_SCORE_RATE * V117_ORDER_SAFETY_RATE),
        "cash_info": raw,
        "v117": True
    }


def v117_deep_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from v117_deep_dicts(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from v117_deep_dicts(x)


def v117_parse_holdings(data):
    """
    키움 잔고 응답을 폭넓게 파싱.
    종목코드 + 수량으로 보이는 항목을 모두 찾는다.
    """
    code_keys = ["stk_cd", "stkcd", "pdno", "code", "isu_cd", "isu_no", "종목코드", "item_cd", "stock_code", "shtn_pdno", "stck_shrn_iscd"]
    name_keys = ["stk_nm", "stkname", "prdt_name", "name", "종목명", "isu_nm", "item_nm", "stock_name", "prdt_name", "hts_kor_isnm"]
    qty_keys = ["rmnd_qty", "hldg_qty", "hold_qty", "qty", "quantity", "보유수량", "잔고수량", "현재잔고", "매도가능수량", "ord_psbl_qty", "가능수량", "sell_psbl_qty", "trad_psbl_qty", "evlu_qty", "hldg_qty"]
    buy_keys = ["avg_prc", "pchs_avg_pric", "pchs_avg_prc", "buyPrice", "매입평균가", "평균단가", "매입단가", "pchs_pric", "pchs_amt_avg_pric", "pchs_avg_pric"]
    cur_keys = ["cur_prc", "curPrice", "currentPrice", "현재가", "now", "price", "lastPrice", "stck_prpr", "prpr"]

    rows = []
    for d in v117_deep_dicts(data):
        if not isinstance(d, dict):
            continue

        raw_code = ""
        for k in code_keys:
            if k in d and str(d.get(k, "")).strip():
                raw_code = d.get(k)
                break
        code = v117_code(raw_code)
        if not code or code == "000000":
            continue

        qty = 0
        has_qty = False
        for k in qty_keys:
            if k in d:
                has_qty = True
                qty = max(qty, v117_num(d.get(k), 0))
        if not has_qty or qty <= 0:
            continue

        name = code
        for k in name_keys:
            if k in d and str(d.get(k, "")).strip():
                name = str(d.get(k)).strip()
                break

        buy = 0
        for k in buy_keys:
            if k in d:
                buy = max(buy, v117_num(d.get(k), 0))

        cur = 0
        for k in cur_keys:
            if k in d:
                cur = max(cur, v117_num(d.get(k), 0))

        price_src = "ACCOUNT"
        if cur < 10:
            try:
                cur, price_src = get_trade_live_price(code, fallback=True)
            except Exception:
                cur, price_src = 0, "NONE"
        if cur < 10:
            cur = buy
            price_src = "AVG_PRICE"

        state = read_trade_state() if "read_trade_state" in globals() else {}
        target_rate = normalize_rate_input(state.get("target_rate", 0.025), 0.025)
        stop_rate = normalize_rate_input(state.get("stop_rate", -0.018), -0.018)

        buy_amount = buy * qty if buy and qty else 0
        eval_amount = cur * qty if cur and qty else 0
        pnl = eval_amount - buy_amount if buy_amount and eval_amount else 0
        pr = ((cur - buy) / buy * 100) if buy and cur else 0

        rows.append({
            "id": int(time.time() * 1000) + len(rows),
            "name": name,
            "code": code,
            "buyPrice": round(buy),
            "avgPrice": round(buy),
            "buyAmount": round(buy_amount),
            "qty": int(qty),
            "quantity": int(qty),
            "target": round((buy or cur) * (1 + target_rate)) if (buy or cur) else 0,
            "stop": round((buy or cur) * (1 + stop_rate)) if (buy or cur) else 0,
            "lastPrice": round(cur),
            "curPrice": round(cur),
            "currentPrice": round(cur),
            "priceSource": price_src,
            "fromKiwoomAccount": True,
            "autoTrade": True,
            "syncSource": "KIWOOM_REAL_BALANCE_V117",
            "lastCheckedAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
            "evalAmount": round(eval_amount),
            "profitAmount": round(pnl),
            "profitRate": round(pr, 2),
            "highPrice": max(cur, buy),
            "highestPrice": max(cur, buy),
            "aiComment": "키움 실제잔고 기준으로 AI가 감시 중입니다."
        })

    by_code = {}
    for h in rows:
        c = h["code"]
        if c not in by_code or safe_float(h.get("qty", 0), 0) >= safe_float(by_code[c].get("qty", 0), 0):
            by_code[c] = h
    return list(by_code.values())


parse_kiwoom_holdings = v117_parse_holdings
v114_parse_holdings = v117_parse_holdings


def v117_fetch_kiwoom_holdings():
    if not kiwoom_ready():
        return {"ok": False, "version": "v117", "holdings": [], "message": "키움 환경변수 미설정"}

    endpoints = [
        ("/api/dostk/acnt", "kt00018"),
        ("/api/dostk/acnt", "kt00004"),
        ("/api/dostk/acnt", "kt00005"),
        ("/api/dostk/acnt", "kt00001"),
    ]
    # 기존 설정 endpoint도 포함
    try:
        for ep in globals().get("V113_HOLDINGS_ENDPOINTS", []):
            if ep not in endpoints:
                endpoints.append(ep)
    except Exception:
        pass

    attempts = []
    best_empty = None

    for path, api_id in endpoints:
        try:
            token = kiwoom_get_token()
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "authorization": "Bearer " + token,
                "cont-yn": "N",
                "next-key": "",
                "api-id": api_id,
            }
            body = make_kiwoom_cash_body({}) if "make_kiwoom_cash_body" in globals() else {"qry_tp": os.getenv("KIWOOM_CASH_QRY_TP", "3")}
            r = requests.post(KIWOOM_BASE_URL + path, json=body, headers=headers, timeout=10)
            try:
                data = r.json() if r.text else {}
            except Exception:
                data = {"raw": r.text[:1500]}

            items = v117_parse_holdings(data)
            attempts.append({"api_id": api_id, "status": r.status_code, "count": len(items), "keys": list(data.keys())[:30] if isinstance(data, dict) else []})

            if r.status_code == 200 and items:
                try:
                    write_holdings(items)
                except Exception:
                    pass
                return {"ok": True, "version": "v117", "api_id": api_id, "holdings": items, "items": items, "data": items, "count": len(items), "source": "KIWOOM_REAL_BALANCE_V117", "attempts": attempts}

            if r.status_code == 200 and best_empty is None:
                best_empty = {"ok": True, "version": "v117", "api_id": api_id, "holdings": [], "items": [], "data": [], "count": 0, "source": "KIWOOM_EMPTY_V117", "attempts": attempts}

        except Exception as e:
            attempts.append({"api_id": api_id, "error": str(e)})

    if best_empty:
        best_empty["attempts"] = attempts
        return best_empty
    return {"ok": False, "version": "v117", "holdings": [], "items": [], "data": [], "count": 0, "message": "키움 실제잔고 API 호출 실패", "attempts": attempts}


# 기존 fetch 함수 대체
v114_fetch_kiwoom_holdings = v117_fetch_kiwoom_holdings
v113_fetch_kiwoom_holdings = v117_fetch_kiwoom_holdings


def v117_sync_holdings_now():
    res = v117_fetch_kiwoom_holdings()
    items = res.get("holdings", [])
    if isinstance(items, list):
        try:
            write_holdings(items)
        except Exception:
            pass
    return res


def v117_sync_after_buy_multi():
    result = None
    for d in V117_AFTER_BUY_SYNC_DELAYS:
        time.sleep(d)
        result = v117_sync_holdings_now()
        if isinstance(result, dict) and result.get("count", 0) > 0:
            return result
    return result or {"ok": False, "message": "매수 후 잔고 동기화 실패"}


_ORIG_KIWOOM_ORDER_V117 = globals().get("kiwoom_order")

def kiwoom_order(side, code, qty, price=0, order_type="market"):
    result = _ORIG_KIWOOM_ORDER_V117(side, code, qty, price, order_type) if _ORIG_KIWOOM_ORDER_V117 else {"ok": False, "message": "기존 주문함수 없음"}
    try:
        side_s = str(side).lower()
        ok = isinstance(result, dict) and (result.get("ok") or str(result.get("return_code", "")) in ["0", "00"])
        if ok and (side_s in ["buy", "매수", "1"]):
            result["v117_after_buy_sync"] = v117_sync_after_buy_multi()
    except Exception as e:
        if isinstance(result, dict):
            result["v117_after_buy_sync_error"] = str(e)
    return result


@app.route("/api/v117_smart_qty_test")
def api_v117_smart_qty_test():
    code = request.args.get("code", "")
    price = safe_float(request.args.get("price", 0), 0)
    score = safe_float(request.args.get("score", 100), 100)
    if price <= 0 and code:
        price, src = get_trade_live_price(code, fallback=True)
    qty, info = v117_calc_final_order_qty({"code": code, "price": price, "score": score, "orderPriority": score, "aiScore": score}, price)
    return jsonify({"ok": qty > 0, "version": "v117", "qty": qty, "info": info})


# [v117 duplicate route disabled] @app.route("/api/v119_holdings_fast", methods=["GET", "POST"])
def api_v117_server_holdings():
    return jsonify(v117_sync_holdings_now())


# [v117 duplicate route disabled] @app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
def api_v117_force_sync_holdings():
    return jsonify(v117_sync_holdings_now())


@app.route("/api/v117_holdings_debug")
def api_v117_holdings_debug():
    return jsonify(v117_fetch_kiwoom_holdings())


@app.route("/api/v117_cash")
def api_v117_cash():
    c, raw = v117_orderable_cash()
    return jsonify({"ok": c > 0, "version": "v117", "orderable_cash": int(c), "budget": get_auto_order_budget(), "raw": raw})


@app.route("/api/v117_version")
def api_v117_version():
    return jsonify({
        "ok": True,
        "version": "v117",
        "title": "KIWOOM REAL AUTO v131",
        "engine": "STRONG_SIZE_HOLDING_SYNC",
        "message": "v117 강한 매수수량 + 키움 실보유 자동동기화 강화 적용"
    })


# 기존 UI/구버전 API를 v117로 연결
# [v117 duplicate route disabled] @app.route("/api/v119_holdings_fast", methods=["GET", "POST"])
def api_v116_server_holdings_v117_override():
    return api_v117_server_holdings()

# [v117 duplicate route disabled] @app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
def api_v116_force_sync_holdings_v117_override():
    return api_v117_force_sync_holdings()

# [v119 compatibility duplicate route disabled] @app.route("/api/v119_holdings_fast", methods=["GET", "POST"])
def api_v115_server_holdings_v117_override():
    return api_v117_server_holdings()

# [v119 compatibility duplicate route disabled] @app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
def api_v115_force_sync_holdings_v117_override():
    return api_v117_force_sync_holdings()

# [v119 compatibility duplicate route disabled] @app.route("/api/server_holdings", methods=["GET", "POST"])
def api_server_holdings_v117_override():
    return api_v117_server_holdings()

# [v119 compatibility duplicate route disabled] @app.route("/api/holdings", methods=["GET", "POST"])
def api_holdings_v117_override():
    return api_v117_server_holdings()





# ============================================================
# v119 REAL HOLDINGS AUTO SYNC + ORDER LOCK MESSAGE FIX
# 화면 fetch 중단 방지 / 주문락 구버전 문구 제거 / 반복 알림 쿨다운
# ============================================================
V118_HOLDINGS_CACHE_FILE = os.path.join(DATA_DIR, "v119_holdings_cache.json") if "DATA_DIR" in globals() else "v119_holdings_cache.json"
V118_STATE_FILE = os.path.join(DATA_DIR, "v119_state.json") if "DATA_DIR" in globals() else "v119_state.json"
V118_HOLDINGS_CACHE_TTL_SEC = safe_float(os.getenv("V118_HOLDINGS_CACHE_TTL_SEC", "20"), 20)
V118_TELEGRAM_ERROR_COOLDOWN_SEC = safe_float(os.getenv("V118_TELEGRAM_ERROR_COOLDOWN_SEC", "90"), 90)
V118_BACKGROUND_SYNC_LOCK = threading.Lock()
V118_LAST_ERROR_SENT = {}
V118_STATE = {
    "version": "v121",
    "last_sync_start": "",
    "last_sync_success": "",
    "last_sync_error": "",
    "last_count": 0,
    "sync_running": False,
    "source": "INIT"
}


def v118_read_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def v118_write_json(path, data):
    try:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print("v119_write_json error:", e)
        return False


def v118_save_state():
    return v118_write_json(V118_STATE_FILE, V118_STATE)


def v118_load_cache():
    data = v118_read_json(V118_HOLDINGS_CACHE_FILE, {})
    if isinstance(data, dict):
        items = data.get("holdings", [])
        ts = safe_float(data.get("ts", 0), 0)
        if isinstance(items, list):
            return items, ts, data
    return [], 0, {}


def v118_save_cache(items, source="UNKNOWN"):
    items = items if isinstance(items, list) else []
    payload = {
        "version": "v121",
        "ts": time.time(),
        "updatedAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "count": len(items),
        "holdings": items
    }
    v118_write_json(V118_HOLDINGS_CACHE_FILE, payload)
    V118_STATE["last_count"] = len(items)
    V118_STATE["source"] = source
    v118_save_state()
    try:
        old_write = globals().get("_ORIG_WRITE_HOLDINGS_V111") or globals().get("_ORIG_WRITE_HOLDINGS_V112")
        if old_write:
            old_write(items)
    except Exception:
        pass
    return payload


def v118_send_error_once(key, text):
    now = time.time()
    last = safe_float(V118_LAST_ERROR_SENT.get(key, 0), 0)
    if now - last < V118_TELEGRAM_ERROR_COOLDOWN_SEC:
        return False
    V118_LAST_ERROR_SENT[key] = now
    try:
        if "send_telegram" in globals():
            send_telegram(text)
            return True
    except Exception:
        pass
    return False


_ORIG_SEND_TELEGRAM_V118 = globals().get("send_telegram")

def send_telegram(text):
    try:
        s = str(text)
        s = re.sub(r"v10[0-9]\s*주문\s*락", "v119 주문 응답 지연/재시도", s)
        s = re.sub(r"v11[0-7]\s*주문\s*락", "v119 주문 응답 지연/재시도", s)
        s = s.replace("※ v113은 앱 입력금액이 아니라 키움 주문가능금액을 자동 기준으로 사용합니다.",
                      "※ v119는 AI 점수와 키움 주문가능금액을 기준으로 수량을 산정하고, 주문 응답 지연 시 중복주문을 차단합니다.")
        return _ORIG_SEND_TELEGRAM_V118(s) if _ORIG_SEND_TELEGRAM_V118 else None
    except Exception:
        return _ORIG_SEND_TELEGRAM_V118(text) if _ORIG_SEND_TELEGRAM_V118 else None


def v118_sync_holdings_worker():
    if not V118_BACKGROUND_SYNC_LOCK.acquire(blocking=False):
        return {"ok": False, "message": "이미 동기화 진행 중"}
    try:
        V118_STATE["sync_running"] = True
        V118_STATE["last_sync_start"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        V118_STATE["last_sync_error"] = ""
        v118_save_state()

        last_res = None
        for fn_name in ["v117_fetch_kiwoom_holdings", "v114_fetch_kiwoom_holdings", "v113_fetch_kiwoom_holdings"]:
            try:
                fn = globals().get(fn_name)
                if not fn:
                    continue
                res = fn()
                last_res = res
                if isinstance(res, dict):
                    items = res.get("holdings", res.get("items", res.get("data", [])))
                    if isinstance(items, list) and len(items) > 0:
                        v118_save_cache(items, source=fn_name)
                        V118_STATE["last_sync_success"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
                        V118_STATE["sync_running"] = False
                        v118_save_state()
                        return {"ok": True, "count": len(items), "source": fn_name}
                    if isinstance(items, list) and len(items) == 0:
                        old, _, _ = v118_load_cache()
                        if not old:
                            v118_save_cache([], source=fn_name + "_EMPTY")
                            V118_STATE["last_sync_success"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                V118_STATE["last_sync_error"] = str(e)[:500]
                continue

        V118_STATE["sync_running"] = False
        v118_save_state()
        return {"ok": False, "message": "키움 잔고 동기화 결과 없음", "last": last_res}
    except Exception as e:
        V118_STATE["last_sync_error"] = str(e)[:500]
        V118_STATE["sync_running"] = False
        v118_save_state()
        return {"ok": False, "message": str(e)}
    finally:
        try:
            V118_BACKGROUND_SYNC_LOCK.release()
        except Exception:
            pass


def v118_start_background_sync():
    try:
        if V118_STATE.get("sync_running"):
            return False
        t = threading.Thread(target=v118_sync_holdings_worker, daemon=True)
        t.start()
        return True
    except Exception:
        return False


def v118_fast_holdings_payload(start_sync=True):
    items, ts, cache = v118_load_cache()
    age = time.time() - ts if ts else 999999
    if start_sync and (age > V118_HOLDINGS_CACHE_TTL_SEC) and not V118_STATE.get("sync_running"):
        v118_start_background_sync()

    return {
        "ok": True,
        "version": "v121",
        "mode": "FAST_CACHE_PLUS_BACKGROUND_SYNC",
        "holdings": items,
        "items": items,
        "data": items,
        "count": len(items),
        "registeredCount": len(items),
        "cacheAgeSec": round(age, 1) if ts else None,
        "cacheUpdatedAt": cache.get("updatedAt", ""),
        "source": cache.get("source", "CACHE_EMPTY"),
        "state": V118_STATE,
        "message": "마지막 성공 보유목록 즉시 표시 + 백그라운드 키움 동기화"
    }


_ORIG_KIWOOM_ORDER_V118 = globals().get("kiwoom_order")

def kiwoom_order(side, code, qty, price=0, order_type="market"):
    result = _ORIG_KIWOOM_ORDER_V118(side, code, qty, price, order_type) if _ORIG_KIWOOM_ORDER_V118 else {"ok": False, "message": "기존 주문함수 없음"}
    try:
        side_s = str(side).lower()
        ok = isinstance(result, dict) and (result.get("ok") or str(result.get("return_code", "")) in ["0", "00"])
        if ok and side_s in ["buy", "매수", "1"]:
            result["v119_background_holdings_sync_started"] = v118_start_background_sync()
        elif isinstance(result, dict) and not ok:
            msg = str(result.get("message", result.get("return_msg", result)))
            msg = re.sub(r"v10[0-9]\s*주문\s*락", "v119 주문 응답 지연/재시도", msg)
            msg = re.sub(r"v11[0-7]\s*주문\s*락", "v119 주문 응답 지연/재시도", msg)
            result["message"] = msg
    except Exception as e:
        if isinstance(result, dict):
            result["v119_order_wrap_error"] = str(e)
    return result


# [v119 compatibility duplicate route disabled] @app.route("/api/v119_holdings_fast", methods=["GET", "POST"])
def api_v119_holdings_fast():
    return jsonify(v118_fast_holdings_payload(start_sync=True))


# [v119 compatibility duplicate route disabled] @app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
def api_v119_force_sync_holdings():
    v118_start_background_sync()
    payload = v118_fast_holdings_payload(start_sync=False)
    payload["message"] = "강제 동기화를 백그라운드로 시작했습니다. 3~8초 후 다시 확인하세요."
    return jsonify(payload)


@app.route("/api/v118_holdings_debug")
def api_v118_holdings_debug():
    res = v118_sync_holdings_worker()
    payload = v118_fast_holdings_payload(start_sync=False)
    payload["debugSyncResult"] = res
    return jsonify(payload)


@app.route("/api/v118_version")
def api_v118_version():
    return jsonify({
        "ok": True,
        "version": "v121",
        "title": "KIWOOM REAL AUTO v131",
        "engine": "REAL_HOLDINGS_AUTO_SYNC_FIX",
        "message": "v119 빠른 보유표시 + 백그라운드 동기화 + 주문락 문구 수정 적용"
    })


# [v119 compatibility duplicate route disabled] @app.route("/api/v119_holdings_fast", methods=["GET", "POST"])
def api_v117_server_holdings_v118_override():
    return api_v119_holdings_fast()

# [v119 compatibility duplicate route disabled] @app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
def api_v117_force_sync_holdings_v118_override():
    return api_v119_force_sync_holdings()

@app.route("/api/v119_holdings_fast", methods=["GET", "POST"])
def api_v116_server_holdings_v118_override():
    return api_v119_holdings_fast()

@app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
def api_v116_force_sync_holdings_v118_override():
    return api_v119_force_sync_holdings()

@app.route("/api/server_holdings", methods=["GET", "POST"])
def api_server_holdings_v118_override():
    return api_v119_holdings_fast()

@app.route("/api/holdings", methods=["GET", "POST"])
def api_holdings_v118_override():
    return api_v119_holdings_fast()



# =====================================================================
# v123_CLICK_DETAIL_STATUS_FIX
# - 실제 키움 실보유 자동동기화 강화
# - Kiwoom 잔고 응답 재귀 파싱
# - timeout/일시 실패 시 기존 보유 캐시 삭제 금지
# - v118 빠른 UI가 v119 동기화 결과를 즉시 표시하도록 연결
# - 현재 화면 기준 비상 보정값: 삼성중공업 10주, 제주반도체 2주
# =====================================================================
V119_VERSION = "v121"
V119_ENGINE = "REAL_HOLDINGS_PROFIT_FAST_BUTTON_FIX"
V119_HOLDINGS_CACHE_FILE = str(BASE_DIR / "sungil_real_holdings_v119_cache.json")
V119_SYNC_RETRY = int(os.getenv("KIWOOM_HOLDINGS_SYNC_RETRY", "1"))
V119_SYNC_TIMEOUT = int(os.getenv("KIWOOM_HOLDINGS_SYNC_TIMEOUT", "5"))
V119_CACHE_TTL_SEC = int(os.getenv("V119_HOLDINGS_CACHE_TTL_SEC", "8"))
V119_LAST_SYNC = {"running": False, "last_result": None, "last_error": "", "last_success": "", "last_start": ""}
V119_SYNC_LOCK = threading.Lock()


def v119_deep_lists(obj):
    out = []
    if isinstance(obj, list):
        out.append(obj)
        for x in obj:
            out.extend(v119_deep_lists(x))
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(v119_deep_lists(v))
    return out


def v119_get_first(item, keys, default=""):
    for k in keys:
        if k in item and item.get(k) not in [None, ""]:
            return item.get(k)
    return default


def v119_num(item, keys, default=0):
    v = v119_get_first(item, keys, default)
    return abs(safe_float(str(v).replace(",", "").replace("+", "").replace("-", "").strip(), default))


def v119_code_value(v):
    code = str(v or "").replace("A", "").replace(" ", "").strip()
    digits = re.sub(r"[^0-9]", "", code)
    if len(digits) >= 6:
        return digits[-6:]
    return digits.zfill(6) if digits else "000000"


def parse_kiwoom_holdings(data):
    """v121: 키움 REST 잔고 응답을 재귀적으로 탐색하여 실제 보유종목/매입가/수익률을 추출합니다."""
    if not isinstance(data, dict):
        return []

    code_keys = ["stk_cd", "stkcd", "stk_cd_nm", "pdno", "code", "isu_cd", "isuCd", "종목코드", "종목번호", "단축코드", "prdt_code", "stock_code"]
    name_keys = ["stk_nm", "stkNm", "prdt_name", "prdtName", "name", "종목명", "상품명", "isu_nm", "kor_isnm"]
    qty_keys = ["rmnd_qty", "rmndQty", "hldg_qty", "hldgQty", "hold_qty", "qty", "jan_qty", "잔고수량", "보유수량", "현재보유수량", "매매가능수량", "ord_psbl_qty", "매도가능수량"]
    sellable_keys = ["ord_psbl_qty", "sell_psbl_qty", "매도가능수량", "주문가능수량", "매매가능수량"]
    buy_keys = [
        "avg_prc", "avgPrc", "pchs_avg_pric", "pchsAvgPric", "pchs_avg_prc", "pur_pric", "buyPrice",
        "매입평균가", "평균단가", "평균가", "매입단가", "취득단가", "매수가", "매입가", "매입 평균가"
    ]
    cur_keys = ["cur_prc", "curPrc", "prpr", "current_price", "now_prc", "lastPrice", "현재가", "평가가격", "현재가격"]
    buy_amt_keys = ["pchs_amt", "pchsAmt", "pchs_amt_smtl", "buyAmount", "purchaseAmount", "매입금액", "매입액", "총매입", "총매입금액", "취득금액"]
    eval_amt_keys = ["evlt_amt", "evlu_amt", "evltv_amt", "evluAmt", "evalAmount", "평가금액", "평가액", "평가금", "총평가"]
    pnl_keys = ["evltv_prft", "evlu_pfls_amt", "evlt_prft", "evlu_pfls", "profitAmount", "평가손익", "손익금액", "평가손익금액", "손익"]
    rate_keys = ["prft_rt", "evlu_pfls_rt", "evltv_prft_rt", "profitRate", "수익률", "손익률", "평가손익률"]

    def num_signed(item, keys, default=0):
        raw = v119_get_first(item, keys, default)
        s = str(raw).replace(",", "").replace("%", "").strip()
        s = s.replace("▲", "").replace("△", "").replace("+", "")
        # 키움 현재가는 부호가 붙는 경우가 있어 현재가/단가는 호출부에서 abs 처리합니다.
        return safe_float(s, default)

    result = []
    seen = set()
    for arr in v119_deep_lists(data):
        for item in arr:
            if not isinstance(item, dict):
                continue
            raw_code = v119_get_first(item, code_keys, "")
            code = v119_code_value(raw_code)
            if not code.isdigit() or code == "000000" or code in seen:
                continue
            qty = abs(num_signed(item, qty_keys, 0))
            if qty <= 0:
                continue
            seen.add(code)

            name = str(v119_get_first(item, name_keys, code)).strip() or code
            buy = abs(num_signed(item, buy_keys, 0))
            cur_account = abs(num_signed(item, cur_keys, 0))
            sellable = abs(num_signed(item, sellable_keys, qty)) or qty
            buy_amount = abs(num_signed(item, buy_amt_keys, 0))
            eval_amount = abs(num_signed(item, eval_amt_keys, 0))
            profit_amount = num_signed(item, pnl_keys, 0)
            profit_rate = num_signed(item, rate_keys, 0)

            # 매입가가 0으로 내려오는 계정/필드 방어: 총매입금액/수량으로 역산
            if buy <= 0 and buy_amount > 0 and qty > 0:
                buy = buy_amount / qty
            # 평가금액과 평가손익이 있으면 총매입금액 역산 후 매입가 보정
            if buy <= 0 and eval_amount > 0 and profit_amount != 0 and qty > 0:
                derived_buy_amount = eval_amount - profit_amount
                if derived_buy_amount > 0:
                    buy_amount = derived_buy_amount
                    buy = derived_buy_amount / qty

            try:
                live, src = get_trade_live_price(code, fallback=True)
            except Exception:
                live, src = 0, "KIWOOM_ACCOUNT"
            cur = live if live >= 10 else cur_account
            if cur <= 0:
                cur = buy
                src = "KIWOOM_ACCOUNT"
            if buy_amount <= 0 and buy > 0:
                buy_amount = buy * qty
            if eval_amount <= 0 and cur > 0:
                eval_amount = cur * qty
            if profit_amount == 0 and buy > 0 and cur > 0:
                profit_amount = (cur - buy) * qty
            if profit_rate == 0 and buy > 0 and cur > 0:
                profit_rate = (cur - buy) / buy * 100

            state = read_trade_state()
            target_rate = normalize_rate_input(state.get("target_rate", 0.027), 0.027)
            stop_rate = normalize_rate_input(state.get("stop_rate", -0.018), -0.018)
            base = buy if buy > 0 else cur
            result.append({
                "id": f"kiwoom-{code}",
                "name": name,
                "code": code,
                "buyPrice": round(buy),
                "buyAmount": round(buy_amount),
                "qty": int(qty),
                "sellableQty": int(sellable),
                "target": round(base * (1 + target_rate)) if base else 0,
                "stop": round(base * (1 + stop_rate)) if base else 0,
                "lastPrice": round(cur),
                "accountCurrentPrice": round(cur_account) if cur_account else 0,
                "priceSource": src,
                "autoTrade": True,
                "fromKiwoomAccount": True,
                "screenFallback": False,
                "createdAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
                "lastCheckedAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
                "highPrice": round(cur),
                "evalAmount": round(eval_amount),
                "profitAmount": round(profit_amount),
                "profitRate": round(profit_rate, 2),
                "holdingStatus": "키움실보유",
                "aiComment": ai_comment(cur, buy, base * (1 + target_rate) if base else 0, base * (1 + stop_rate) if base else 0, qty) if buy > 0 else "AI 코멘트: 키움 잔고에서 매입가 확인 대기 중입니다.",
                "syncSource": "KIWOOM_REAL_BALANCE_V120",
                "updatedBy": "v121"
            })
    return result

def v119_read_cache():
    try:
        if os.path.exists(V119_HOLDINGS_CACHE_FILE):
            with open(V119_HOLDINGS_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"holdings": [], "ts": 0, "source": "EMPTY"}


def v119_save_cache(items, source="KIWOOM_REAL_BALANCE"):
    items = items if isinstance(items, list) else []
    payload = {
        "version": V119_VERSION,
        "engine": V119_ENGINE,
        "ts": time.time(),
        "updatedAt": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "count": len(items),
        "holdings": items,
    }
    try:
        with open(V119_HOLDINGS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    write_holdings(items)
    return payload


def kiwoom_get_account_holdings():
    """v119: 실제 잔고 조회. timeout 방어 + 여러 TR/body 재시도 + 성공 시만 캐시 갱신."""
    if not kiwoom_ready():
        return {"ok": False, "message": "키움 환경변수 미설정", "holdings": [], "source": "ENV_MISSING"}

    cache = v119_read_cache()
    if cache.get("holdings") and time.time() - safe_float(cache.get("ts", 0), 0) < V119_CACHE_TTL_SEC:
        return {"ok": True, "holdings": cache.get("holdings", []), "source": "V119_SHORT_CACHE", "cached": True}

    body_variants = [
        {}, {"qry_tp": "1"}, {"qry_tp": "2"}, {"qry_tp": "3"},
        {"dmst_stex_tp": "KRX"}, {"qry_tp": "1", "dmst_stex_tp": "KRX"},
        {"qry_tp": os.getenv("KIWOOM_CASH_QRY_TP", "3")},
    ]
    endpoints = []
    for api_id in ["kt00018", "kt00004", "kt00005", "kt00001"]:
        for body in body_variants:
            endpoints.append(("/api/dostk/acnt", api_id, body))

    last_error = ""
    last_raw = None
    for attempt in range(max(1, V119_SYNC_RETRY)):
        for path, api_id, body in endpoints:
            try:
                token = kiwoom_get_token()
                headers = {
                    "Content-Type": "application/json;charset=UTF-8",
                    "authorization": "Bearer " + token,
                    "cont-yn": "N",
                    "next-key": "",
                    "api-id": api_id,
                }
                r = requests.post(KIWOOM_BASE_URL + path, json=body, headers=headers, timeout=V119_SYNC_TIMEOUT)
                try:
                    data = r.json() if r.text else {}
                except Exception:
                    data = {"raw": r.text[:5000]}
                last_raw = data
                items = parse_kiwoom_holdings(data)
                if r.status_code == 200 and isinstance(items, list) and len(items) > 0:
                    v119_save_cache(items, source=f"{api_id}:{body}")
                    update_kiwoom_debug("v119_holdings_ok", "", r.status_code, f"키움 실제잔고 {len(items)}개 동기화 성공", {"api_id": api_id, "body": body, "count": len(items)})
                    return {"ok": True, "version": V119_VERSION, "api_id": api_id, "body": body, "holdings": items, "count": len(items), "raw": data, "source": "KIWOOM_REAL_BALANCE_V119"}
                msg = data.get("return_msg") if isinstance(data, dict) else str(data)
                last_error = f"attempt {attempt+1}/{V119_SYNC_RETRY} {api_id} {body}: {msg or '보유종목 파싱 결과 없음'}"
            except requests.exceptions.Timeout:
                last_error = f"attempt {attempt+1}/{V119_SYNC_RETRY}: 키움 잔고 API timeout"
            except Exception as e:
                last_error = f"attempt {attempt+1}/{V119_SYNC_RETRY}: {e}"
        time.sleep(0.4)

    update_kiwoom_debug("v119_holdings_fail", "", 0, last_error, last_raw)
    return {"ok": False, "version": V119_VERSION, "message": last_error or "키움 실제잔고 조회 실패", "holdings": [], "raw": last_raw, "source": "KIWOOM_FAIL_KEEP_CACHE"}


def v119_screen_holdings_from_uploaded_image():
    """사용자가 올린 현재 키움 잔고 화면 기준 비상 임시값. API 정상화 전 확인용으로만 사용."""
    return [
        v109_make_holding("010140", "삼성중공업", 10, 28765) if "v109_make_holding" in globals() else {"code":"010140","name":"삼성중공업","qty":10,"buyPrice":28765},
        v109_make_holding("080220", "제주반도체", 2, 109450) if "v109_make_holding" in globals() else {"code":"080220","name":"제주반도체","qty":2,"buyPrice":109450},
    ]


def v109_force_sync_holdings(full_sync=True, allow_screen_fallback=False):
    """v119 override: 성공 시 실제잔고 반영, 실패/timeout 시 기존 캐시와 UI를 절대 비우지 않습니다."""
    res = kiwoom_get_account_holdings()
    if res.get("ok"):
        items = res.get("holdings", [])
        v119_save_cache(items, source=res.get("source", "KIWOOM_REAL_BALANCE_V119"))
        state = read_trade_state()
        state["last_status"] = "v119 키움 실보유 동기화 완료"
        state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        state["last_order_message"] = f"키움 실제잔고 {len(items)}개를 앱 보유종목에 반영했습니다."
        write_trade_state(state)
        V119_LAST_SYNC.update({"running": False, "last_result": res, "last_error": "", "last_success": state["last_status_time"]})
        return {"ok": True, "version": V119_VERSION, "engine": V119_ENGINE, "holdings": items, "count": len(items), "source": res.get("source"), "message": "키움 실제잔고 기준으로 동기화했습니다.", "kiwoom": res}

    if allow_screen_fallback or str(os.getenv("USE_SCREEN_HOLDINGS_FALLBACK", "false")).lower() == "true":
        items = v119_screen_holdings_from_uploaded_image()
        v119_save_cache(items, source="SCREENSHOT_FALLBACK_V119")
        return {"ok": True, "version": V119_VERSION, "holdings": items, "count": len(items), "source": "SCREENSHOT_FALLBACK_V119", "message": "키움 API 실패로 현재 업로드 화면 기준 임시 보유값을 적용했습니다.", "kiwoom_error": res}

    cache = v119_read_cache()
    items = cache.get("holdings", []) if isinstance(cache, dict) else []
    state = read_trade_state()
    state["last_status"] = "v119 키움 실보유 동기화 지연"
    state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    state["last_order_message"] = "키움 잔고 API timeout/실패. 기존 보유 캐시는 비우지 않고 유지합니다: " + str(res.get("message", ""))[:350]
    write_trade_state(state)
    V119_LAST_SYNC.update({"running": False, "last_result": res, "last_error": state["last_order_message"]})
    return {"ok": False, "version": V119_VERSION, "engine": V119_ENGINE, "holdings": items, "count": len(items), "source": cache.get("source", "CACHE_KEEP_ON_FAIL") if isinstance(cache, dict) else "CACHE_KEEP_ON_FAIL", "message": state["last_order_message"], "kiwoom_error": res}


def sync_kiwoom_holdings_to_local():
    return v109_force_sync_holdings(full_sync=True).get("holdings", read_holdings())


def v118_sync_holdings_worker():
    if not V119_SYNC_LOCK.acquire(blocking=False):
        return {"ok": False, "version": V119_VERSION, "message": "이미 실보유 동기화 진행 중"}
    try:
        V119_LAST_SYNC["running"] = True
        V119_LAST_SYNC["last_start"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        res = v109_force_sync_holdings(full_sync=True)
        V119_LAST_SYNC["running"] = False
        V119_LAST_SYNC["last_result"] = res
        if res.get("ok"):
            V119_LAST_SYNC["last_success"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        else:
            V119_LAST_SYNC["last_error"] = str(res.get("message", ""))[:500]
        return res
    finally:
        try:
            V119_SYNC_LOCK.release()
        except Exception:
            pass


def v118_start_background_sync():
    try:
        if V119_LAST_SYNC.get("running"):
            return False
        threading.Thread(target=v118_sync_holdings_worker, daemon=True).start()
        return True
    except Exception:
        return False


def v118_fast_holdings_payload(start_sync=True):
    cache = v119_read_cache()
    items = cache.get("holdings", []) if isinstance(cache, dict) else []
    ts = safe_float(cache.get("ts", 0), 0) if isinstance(cache, dict) else 0
    age = time.time() - ts if ts else None
    if start_sync and (not V119_LAST_SYNC.get("running")) and (age is None or age > V119_CACHE_TTL_SEC):
        v118_start_background_sync()
    state = read_trade_state()
    return {
        "ok": True,
        "version": V119_VERSION,
        "engine": V119_ENGINE,
        "mode": "REAL_KIWOOM_BALANCE_FAST_CACHE_BACKGROUND_SYNC",
        "holdings": items,
        "items": items,
        "data": items,
        "count": len(items),
        "registeredCount": len(items),
        "cacheAgeSec": round(age, 1) if age is not None else None,
        "cacheUpdatedAt": cache.get("updatedAt", "") if isinstance(cache, dict) else "",
        "source": cache.get("source", "EMPTY") if isinstance(cache, dict) else "EMPTY",
        "sync": V119_LAST_SYNC,
        "state": state,
        "message": "키움 실제잔고 자동동기화 기준 표시. timeout 시 기존 정상 캐시를 유지합니다." if items else "키움 실보유 동기화 확인중입니다. 3~10초 후 새로고침하세요."
    }


def read_holdings_real_only():
    return v118_fast_holdings_payload(start_sync=True).get("holdings", [])


# v119 신규 진단/강제동기화 URL
@app.route("/api/v119_holdings_fast", methods=["GET", "POST"])
def api_v119_holdings_fast():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        if data.get("action") == "clear_cache":
            v119_save_cache([], source="MANUAL_CLEAR")
    return jsonify(v118_fast_holdings_payload(start_sync=True))


@app.route("/api/v119_force_sync_holdings", methods=["GET", "POST"])
def api_v119_force_sync_holdings():
    fallback = str(request.args.get("screen_fallback", "0")).lower() in ["1", "true", "yes"]
    res = v109_force_sync_holdings(full_sync=True, allow_screen_fallback=fallback)
    return jsonify(res)


@app.route("/api/v119_holdings_debug")
def api_v119_holdings_debug():
    res = v118_sync_holdings_worker()
    payload = v118_fast_holdings_payload(start_sync=False)
    payload["debugSyncResult"] = res
    return jsonify(payload)


@app.route("/api/v119_version")
def api_v119_version():
    return jsonify({"ok": True, "version": V119_VERSION, "engine": V119_ENGINE, "message": "실제 키움 실보유 자동동기화 timeout/파싱/UI 반영 개선 적용"})



# ============================================================
# v128 CACHE_INSTANT_NO_ERROR_FIX
# - 무거운 후보/잔고 조회는 백그라운드에서 갱신
# - 화면 버튼은 마지막 정상 캐시를 즉시 표시
# - 실제 주문/매도 직전에는 기존 로직 그대로 키움 현재가/주문가능금액을 재확인
# ============================================================
V127_VERSION = "v128 CACHE_INSTANT_NO_ERROR_FIX"
V127_CANDIDATE_TTL_SEC = int(os.getenv("V127_CANDIDATE_TTL_SEC", "30"))
V127_CACHE_LOCK = threading.Lock()
V127_CANDIDATE_CACHE = {
    "ok": False,
    "pick": None,
    "items": [],
    "updated": "",
    "ts": 0,
    "running": False,
    "error": "",
    "params": {}
}


def v127_params_from_request(args=None):
    args = args or {}
    return {
        "priceRanges": str(args.get("priceRanges", "5000-20000,20000-50000,50000-200000")),
        "cash": safe_float(args.get("cash", 500000), 500000),
        "minQty": safe_int(args.get("minQty", 1), 1),
        "maxChange": safe_float(args.get("maxChange", 7), 7),
        "minAmount": safe_float(args.get("minAmount", 1000000000), 1000000000),
        "minScore": safe_float(args.get("minScore", 60), 60),
        "fast": 1
    }


def v127_refresh_candidates_worker(params=None):
    global V127_CANDIDATE_CACHE
    params = params or {}
    try:
        with V127_CACHE_LOCK:
            V127_CANDIDATE_CACHE["running"] = True
            V127_CANDIDATE_CACHE["error"] = ""
        pick, picks = best_pick_from_params(params)
        payload = {
            "ok": bool(pick),
            "pick": pick,
            "items": (picks or [])[:8],
            "updated": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
            "ts": time.time(),
            "running": False,
            "error": "",
            "params": params
        }
        with V127_CACHE_LOCK:
            V127_CANDIDATE_CACHE.update(payload)
        if pick:
            try:
                state = read_trade_state()
                state["latest_ui_pick"] = pick
                state["latest_ui_args"] = params
                write_trade_state(state)
                update_trade_status("후보 캐시 갱신", f"v131 백그라운드 후보 갱신: {pick.get('name')}({pick.get('code')})", candidate=pick)
            except Exception:
                pass
        return payload
    except Exception as e:
        with V127_CACHE_LOCK:
            V127_CANDIDATE_CACHE["running"] = False
            V127_CANDIDATE_CACHE["error"] = str(e)[:300]
        try:
            update_trade_status("후보 캐시 갱신 지연", str(e)[:300])
        except Exception:
            pass
        return {"ok": False, "error": str(e)[:300]}


def v127_start_candidate_refresh(params=None, force=False):
    params = params or {}
    with V127_CACHE_LOCK:
        running = bool(V127_CANDIDATE_CACHE.get("running"))
        age = time.time() - safe_float(V127_CANDIDATE_CACHE.get("ts", 0), 0) if V127_CANDIDATE_CACHE.get("ts") else 999999
    if running:
        return False
    if (not force) and age < V127_CANDIDATE_TTL_SEC:
        return False
    try:
        threading.Thread(target=v127_refresh_candidates_worker, args=(params,), daemon=True).start()
        return True
    except Exception:
        return False


def v127_candidate_payload(start_refresh=True, params=None):
    params = params or {}
    with V127_CACHE_LOCK:
        cache = dict(V127_CANDIDATE_CACHE)
    age = time.time() - safe_float(cache.get("ts", 0), 0) if cache.get("ts") else None
    should_refresh = start_refresh and (age is None or age > V127_CANDIDATE_TTL_SEC)
    if should_refresh:
        v127_start_candidate_refresh(params=params, force=False)
        with V127_CACHE_LOCK:
            cache = dict(V127_CANDIDATE_CACHE)
    cache["version"] = V127_VERSION
    cache["cacheAgeSec"] = round(age, 1) if age is not None else None
    cache["refreshing"] = bool(cache.get("running")) or bool(should_refresh)
    cache["message"] = "마지막 정상 후보 캐시를 즉시 표시합니다. 실제 주문 직전에는 키움 현재가/주문가능금액을 재확인합니다."
    return safe_json(cache)


@app.route("/api/v128_best_pick_cached")
def api_v127_best_pick_cached():
    params = v127_params_from_request(request.args)
    payload = v127_candidate_payload(start_refresh=True, params=params)
    return jsonify({
        "ok": bool(payload.get("pick")),
        "pick": payload.get("pick"),
        "updated": payload.get("updated"),
        "cacheAgeSec": payload.get("cacheAgeSec"),
        "refreshing": payload.get("refreshing"),
        "message": payload.get("message"),
        "error": payload.get("error", ""),
        "version": V127_VERSION
    })


@app.route("/api/v128_watch_candidates_cached")
def api_v127_watch_candidates_cached():
    params = v127_params_from_request(request.args)
    payload = v127_candidate_payload(start_refresh=True, params=params)
    return jsonify({
        "ok": True,
        "items": payload.get("items") or [],
        "updated": payload.get("updated"),
        "cacheAgeSec": payload.get("cacheAgeSec"),
        "refreshing": payload.get("refreshing"),
        "message": payload.get("message"),
        "error": payload.get("error", ""),
        "version": V127_VERSION
    })


@app.route("/api/v127_refresh_candidates", methods=["GET", "POST"])
def api_v127_refresh_candidates():
    params = v127_params_from_request(request.args)
    started = v127_start_candidate_refresh(params=params, force=True)
    payload = v127_candidate_payload(start_refresh=False, params=params)
    payload["started"] = started
    return jsonify(payload)


@app.route("/api/v128_holdings_cached", methods=["GET", "POST"])
def api_v127_holdings_cached():
    start_sync = str(request.args.get("start_sync", "1")).lower() in ["1", "true", "yes"]
    # v119 캐시 구조를 그대로 사용하되, 화면 응답은 즉시 반환합니다.
    try:
        payload = v118_fast_holdings_payload(start_sync=start_sync)
        payload["version"] = V127_VERSION
        payload["message"] = payload.get("message") or "키움 실보유 캐시를 즉시 표시하고, 동기화는 백그라운드에서 진행합니다."
        return jsonify(safe_json(payload))
    except Exception as e:
        cache = v119_read_cache() if "v119_read_cache" in globals() else {}
        items = cache.get("holdings", []) if isinstance(cache, dict) else []
        return jsonify({
            "ok": True,
            "version": V127_VERSION,
            "holdings": items,
            "items": items,
            "count": len(items),
            "source": "LAST_CACHE_AFTER_ERROR",
            "message": "보유종목 조회가 지연되어 마지막 정상 캐시를 표시합니다.",
            "error": str(e)[:300]
        })


@app.route("/api/v131_status_light")
def api_v127_status_light():
    state = read_trade_state()
    kd = state.get("last_kiwoom_debug", {}) or {}
    hcache = v119_read_cache() if "v119_read_cache" in globals() else {}
    hts = safe_float(hcache.get("ts", 0), 0) if isinstance(hcache, dict) else 0
    with V127_CACHE_LOCK:
        cc = dict(V127_CANDIDATE_CACHE)
    cts = safe_float(cc.get("ts", 0), 0)
    # 키움 API를 새로 치지 않는 초경량 상태. 실제 세부 조회는 상세 새로고침에서만 수행합니다.
    return jsonify(safe_json({
        "ok": True,
        "version": V127_VERSION,
        "state": state,
        "market_open": market_is_open(),
        "kiwoom_ready": kiwoom_ready(),
        "kiwoom_debug": kd,
        "account_cash": {"source": "FAST_SKIP", "cash": 0, "message": "경량 상태확인에서는 키움 예수금을 새로 조회하지 않습니다."},
        "holding_count": len(hcache.get("holdings", [])) if isinstance(hcache, dict) else len(read_holdings()),
        "holdings_cache_updated": hcache.get("updatedAt", "") if isinstance(hcache, dict) else "",
        "holdings_cache_age_sec": round(time.time()-hts, 1) if hts else None,
        "candidate_cache_updated": cc.get("updated", ""),
        "candidate_cache_age_sec": round(time.time()-cts, 1) if cts else None,
        "candidate_refreshing": cc.get("running", False),
        "trade_count_today": state.get("trade_count_today", 0),
        "max_trades_per_day": state.get("max_trades_per_day", 10),
        "min_order_cash": state.get("min_order_cash", 0),
        "max_positions": state.get("max_positions", 3),
        "target_rate_percent": round(safe_float(state.get("target_rate", 0))*100, 2),
        "stop_rate_percent": round(safe_float(state.get("stop_rate", 0))*100, 2),
        "profit_guard_percent": round(safe_float(state.get("profit_guard_rate", 0))*100, 2),
        "trailing_stop_percent": round(safe_float(state.get("trailing_stop_rate", 0))*100, 2),
        "force_exit_time": state.get("force_exit_time", "15:15"),
        "real_trading_env": KIWOOM_REAL_TRADING,
        "dry_run": KIWOOM_DRY_RUN,
        "message": "v131 경량 상태확인: Render alive/캐시 상태만 즉시 확인합니다."
    }))


# 앱 시작 직후 후보 캐시를 한번 준비합니다. 실패해도 서비스 시작은 계속됩니다.
try:
    v127_start_candidate_refresh(v127_params_from_request({}), force=True)
except Exception as _e:
    print("v127 initial candidate refresh skipped:", _e)


# ============================================================
# v128 CACHE_INSTANT_NO_ERROR_FIX
# 목적:
# 1) 화면 API는 절대 무거운 키움/후보 계산을 직접 기다리지 않음
# 2) 후보/보유/상태는 마지막 정상 캐시를 즉시 반환
# 3) 실제 주문/매도 직전에는 기존 로직 그대로 키움 현재가/주문가능금액을 재확인
# ============================================================
V128_VERSION = "v131 AUTO_RELAX_CANDIDATE_CACHE_FIX"
V128_CANDIDATE_TTL_SEC = int(os.getenv("V128_CANDIDATE_TTL_SEC", "25"))
V128_FAST_LIMIT = int(os.getenv("V128_FAST_LIMIT", "500"))
V128_CACHE_LOCK = threading.Lock()
V128_CANDIDATE_CACHE = {
    "ok": False,
    "pick": None,
    "items": [],
    "updated": "",
    "ts": 0,
    "running": False,
    "error": "",
    "params": {}
}


def v128_fast_score_candidates(params=None):
    """화면 표시용 초고속 후보 계산. 키움 API를 호출하지 않습니다."""
    params = params or {}
    cash = safe_float(params.get("cash", 500000), 500000)
    min_qty = safe_int(params.get("minQty", 1), 1)
    max_change = safe_float(params.get("maxChange", 7), 7)
    min_amount = safe_float(params.get("minAmount", 1000000000), 1000000000)
    min_score = safe_float(params.get("minScore", 70), 70)
    # v130: 화면 후보는 "없음/오류"로 끝내지 않도록 1차 조건 실패 시 자동 완화합니다.
    # 실제 주문 직전에는 기존처럼 키움 현재가/주문가능금액으로 재검증하므로 안전성은 유지됩니다.
    original_min_amount = min_amount
    original_min_score = min_score
    fallback_used = False
    price_ranges = []
    for part in str(params.get("priceRanges", "5000-20000,20000-50000,50000-200000")).split(','):
        try:
            a, b = part.split('-')
            price_ranges.append((safe_float(a), safe_float(b)))
        except Exception:
            pass

    df = get_market_df(limit=V128_FAST_LIMIT)
    if df is None or df.empty:
        return []
    df = df.copy()
    cc = 'ChagesRatio' if 'ChagesRatio' in df.columns else ('Change' if 'Change' in df.columns else None)
    for col in ['Close', 'Volume', 'Amount', 'Marcap']:
        df[col] = pd.to_numeric(df.get(col, 0), errors='coerce').fillna(0)
    df['dayChange'] = pd.to_numeric(df[cc], errors='coerce').fillna(0) if cc else 0
    df['Name'] = df['Name'].astype(str)
    df['Code'] = df['Code'].astype(str).str.zfill(6)
    exclude = ['스팩','SPAC','ETF','ETN','인버스','레버리지','KODEX','TIGER','KBSTAR','ARIRANG','HANARO']
    df = df[~df['Name'].str.upper().apply(lambda n:any(x.upper() in n for x in exclude) or n.endswith('우'))].copy()
    base_df = df.copy()
    df = df[(df['Close'] >= 10) & (df['Amount'] >= min_amount) & (df['dayChange'] >= 0.2) & (df['dayChange'] <= max_change)].copy()
    if price_ranges:
        mask = False
        for lo, hi in price_ranges:
            mask = mask | ((df['Close'] >= lo) & (df['Close'] <= hi))
        df = df[mask].copy()
    if df.empty:
        fallback_used = True
        min_amount = min(original_min_amount, 300000000)
        max_change = max(max_change, 12)
        df = base_df[(base_df['Close'] >= 10) & (base_df['Amount'] >= min_amount) & (base_df['dayChange'] >= 0.05) & (base_df['dayChange'] <= max_change)].copy()
        if price_ranges:
            mask = False
            for lo, hi in price_ranges:
                mask = mask | ((df['Close'] >= lo) & (df['Close'] <= hi))
            df = df[mask].copy()
    if df.empty:
        return []
    df['theme'] = df['Name'].apply(classify_theme).apply(normalize_theme)
    df['amountRank'] = df['Amount'].rank(pct=True) * 100
    df['volumeRank'] = df['Volume'].rank(pct=True) * 100
    df['marcapRank'] = df['Marcap'].rank(pct=True) * 100
    df['sweetSpot'] = (100 - (df['dayChange'] - 3.5).abs() * 8).clip(lower=20, upper=100)
    df['themeWeight'] = df['theme'].apply(lambda x: WEIGHT.get(x, 1.0))
    df['score'] = (df['amountRank']*.34 + df['volumeRank']*.25 + df['marcapRank']*.15 + df['sweetSpot']*.26) * df['themeWeight']
    filtered = df[df['score'] >= min_score].copy()
    if filtered.empty:
        fallback_used = True
        relaxed_score = max(45, min(original_min_score, 70) - 15)
        filtered = df[df['score'] >= relaxed_score].copy()
    if filtered.empty:
        filtered = df.sort_values('score', ascending=False).head(10).copy()
    df = filtered.sort_values('score', ascending=False)
    out = []
    for _, row in df.head(10).iterrows():
        price = safe_float(row['Close'])
        qty = int(cash // price) if price else 0
        # v131: 화면 후보 표시는 예수금/최소수량 때문에 모두 사라지지 않게 유지합니다.
        # 실제 주문 직전에는 키움 주문가능금액과 현재가로 다시 계산하므로 안전성은 유지됩니다.
        display_qty_relaxed = False
        if qty < min_qty:
            display_qty_relaxed = True
            qty = max(1, qty)
        orderbook = {}
        ai = v109_calculate_scalping_score(row, price, orderbook)
        item = {
            'code': str(row['Code']).zfill(6),
            'name': str(row['Name']),
            'market': str(row.get('Market','')),
            'theme': normalize_theme(row['theme']),
            'price': round(price),
            'priceSource': 'KRX_CACHE',
            'score': ai['aiScoreV109'],
            'dayChange': round(safe_float(row['dayChange']), 2),
            'amount': round(safe_float(row['Amount'])),
            'qtyPossible': qty,
            'buyZone': round(price * .995),
            'target': round(price * 1.035),
            'stop': round(price * .975),
            'comment': f"v131 자동완화 캐시 후보: {ai['scalpingStatus']} · {', '.join(ai['scalpingReasons'])}. {'필터 조건을 일부 완화해 표시했습니다. ' if fallback_used else ''}{'화면 표시용 수량 조건을 완화했습니다. ' if display_qty_relaxed else ''}화면은 KRX 캐시 기준이며, 실제 주문 직전에는 키움 현재가/주문가능금액으로 다시 검증합니다."
        }
        item.update(ai)
        out.append(item)
    return sorted(out, key=lambda x: safe_float(x.get('orderPriority', x.get('score', 0))), reverse=True)


def v128_refresh_candidates_worker(params=None):
    global V128_CANDIDATE_CACHE
    params = params or v127_params_from_request({})
    try:
        with V128_CACHE_LOCK:
            if V128_CANDIDATE_CACHE.get('running'):
                return dict(V128_CANDIDATE_CACHE)
            V128_CANDIDATE_CACHE['running'] = True
            V128_CANDIDATE_CACHE['error'] = ''
        picks = v128_fast_score_candidates(params)
        pick = picks[0] if picks else None
        payload = {
            'ok': bool(pick), 'pick': pick, 'items': picks[:8],
            'updated': now_kst().strftime('%Y-%m-%d %H:%M:%S'),
            'ts': time.time(), 'running': False, 'error': '', 'params': params,
            'version': V128_VERSION
        }
        with V128_CACHE_LOCK:
            V128_CANDIDATE_CACHE.update(payload)
        if pick:
            try:
                state = read_trade_state()
                state['latest_ui_pick'] = pick
                state['latest_ui_args'] = params
                write_trade_state(state)
            except Exception:
                pass
        return payload
    except Exception as e:
        with V128_CACHE_LOCK:
            V128_CANDIDATE_CACHE['running'] = False
            V128_CANDIDATE_CACHE['error'] = str(e)[:300]
        return {'ok': False, 'error': str(e)[:300]}


def v128_start_candidate_refresh(params=None, force=False):
    params = params or v127_params_from_request({})
    with V128_CACHE_LOCK:
        running = bool(V128_CANDIDATE_CACHE.get('running'))
        age = time.time() - safe_float(V128_CANDIDATE_CACHE.get('ts', 0), 0) if V128_CANDIDATE_CACHE.get('ts') else 999999
    if running:
        return False
    if (not force) and age < V128_CANDIDATE_TTL_SEC:
        return False
    try:
        threading.Thread(target=v128_refresh_candidates_worker, args=(params,), daemon=True).start()
        return True
    except Exception:
        return False


def v128_candidate_payload(params=None, start_refresh=True):
    params = params or v127_params_from_request({})
    with V128_CACHE_LOCK:
        cache = dict(V128_CANDIDATE_CACHE)
    if not cache.get('pick'):
        # 이전 상태 파일 후보라도 즉시 표시
        try:
            st = read_trade_state()
            lp = st.get('latest_ui_pick')
            if lp:
                cache['pick'] = lp
                cache['items'] = [lp]
                cache['ok'] = True
                cache['updated'] = st.get('last_status_time', '') or cache.get('updated','')
        except Exception:
            pass
    age = time.time() - safe_float(cache.get('ts', 0), 0) if cache.get('ts') else None
    if start_refresh and (age is None or age > V128_CANDIDATE_TTL_SEC):
        v128_start_candidate_refresh(params=params, force=False)
        with V128_CACHE_LOCK:
            new_cache = dict(V128_CANDIDATE_CACHE)
        if new_cache.get('pick'):
            cache = new_cache
    cache['version'] = V128_VERSION
    cache['cacheAgeSec'] = round(age, 1) if age is not None else None
    cache['refreshing'] = bool(cache.get('running')) or (age is None)
    cache['message'] = 'v131 자동완화 캐시 표시: 실제 주문 직전에는 키움 현재가와 주문가능금액을 다시 확인합니다.'
    return safe_json(cache)


@app.route('/api/v128_best_pick_cached')
def api_v128_best_pick_cached():
    params = v127_params_from_request(request.args)
    payload = v128_candidate_payload(params=params, start_refresh=True)
    return jsonify({
        'ok': bool(payload.get('pick')),
        'pick': payload.get('pick'),
        'updated': payload.get('updated'),
        'cacheAgeSec': payload.get('cacheAgeSec'),
        'refreshing': payload.get('refreshing'),
        'message': payload.get('message'),
        'error': payload.get('error',''),
        'version': V128_VERSION
    })


@app.route('/api/v128_watch_candidates_cached')
def api_v128_watch_candidates_cached():
    params = v127_params_from_request(request.args)
    payload = v128_candidate_payload(params=params, start_refresh=True)
    return jsonify({
        'ok': True,
        'items': payload.get('items') or ([payload.get('pick')] if payload.get('pick') else []),
        'updated': payload.get('updated'),
        'cacheAgeSec': payload.get('cacheAgeSec'),
        'refreshing': payload.get('refreshing'),
        'message': payload.get('message'),
        'error': payload.get('error',''),
        'version': V128_VERSION
    })


@app.route('/api/v128_refresh_candidates', methods=['GET','POST'])
def api_v128_refresh_candidates():
    params = v127_params_from_request(request.args)
    started = v128_start_candidate_refresh(params=params, force=True)
    payload = v128_candidate_payload(params=params, start_refresh=False)
    payload['started'] = started
    return jsonify(payload)


@app.route('/api/v128_holdings_cached', methods=['GET','POST'])
def api_v128_holdings_cached():
    start_sync = str(request.args.get('start_sync','0')).lower() in ['1','true','yes']
    # 화면 응답은 캐시만 즉시 반환. start_sync=1일 때만 백그라운드 동기화 요청.
    if start_sync:
        try:
            if 'v118_start_background_sync' in globals():
                v118_start_background_sync(force=False)
            elif 'v119_start_sync' in globals():
                v119_start_sync(force=False)
        except Exception:
            pass
    cache = v119_read_cache() if 'v119_read_cache' in globals() else {}
    items = []
    updated = ''
    if isinstance(cache, dict):
        items = cache.get('holdings') or cache.get('items') or []
        updated = cache.get('updatedAt') or cache.get('updated') or ''
    if not items:
        items = read_holdings()
    return jsonify(safe_json({
        'ok': True,
        'version': V128_VERSION,
        'holdings': items,
        'items': items,
        'count': len(items),
        'source': 'INSTANT_CACHE',
        'cacheUpdatedAt': updated,
        'sync': {'running': bool(start_sync), 'mode': 'background'},
        'message': 'v130 즉시 보유 캐시 표시. 키움 실잔고 동기화는 백그라운드에서 진행합니다.'
    }))


@app.route('/api/v131_status_light')
def api_v128_status_light():
    st = read_trade_state()
    cache = v119_read_cache() if 'v119_read_cache' in globals() else {}
    hitems = cache.get('holdings', []) if isinstance(cache, dict) else read_holdings()
    with V128_CACHE_LOCK:
        cc = dict(V128_CANDIDATE_CACHE)
    return jsonify(safe_json({
        'ok': True,
        'version': V128_VERSION,
        'state': st,
        'market_open': market_is_open(),
        'kiwoom_ready': kiwoom_ready(),
        'kiwoom_debug': st.get('last_kiwoom_debug', {}),
        'account_cash': {'source':'FAST_SKIP', 'cash':0, 'message':'v130 경량확인은 키움 API를 직접 호출하지 않습니다.'},
        'holding_count': len(hitems),
        'holdings_cache_updated': cache.get('updatedAt','') if isinstance(cache, dict) else '',
        'candidate_cache_updated': cc.get('updated',''),
        'candidate_refreshing': cc.get('running', False),
        'trade_count_today': st.get('trade_count_today',0),
        'max_trades_per_day': st.get('max_trades_per_day',10),
        'min_order_cash': st.get('min_order_cash',0),
        'max_positions': st.get('max_positions',3),
        'target_rate_percent': round(safe_float(st.get('target_rate',0))*100,2),
        'stop_rate_percent': round(safe_float(st.get('stop_rate',0))*100,2),
        'profit_guard_percent': round(safe_float(st.get('profit_guard_rate',0))*100,2),
        'trailing_stop_percent': round(safe_float(st.get('trailing_stop_rate',0))*100,2),
        'force_exit_time': st.get('force_exit_time','15:15'),
        'real_trading_env': KIWOOM_REAL_TRADING,
        'dry_run': KIWOOM_DRY_RUN,
        'message': 'v130 정상: 화면 상태 확인은 캐시만 읽어 즉시 응답합니다.'
    }))

try:
    v128_start_candidate_refresh(v127_params_from_request({}), force=True)
except Exception as _e:
    print('v130 initial candidate refresh skipped:', _e)


# =====================================================================
# v131 AUTO_RELAX_CANDIDATE_CACHE_FIX
# - 파일 JSON 동시 읽기/쓰기 LOCK + atomic write
# - 텔레그램 알림 비동기 큐 분리
# - Render IP 조회 캐시/짧은 timeout
# - 호가 JSON 탐색 최대 깊이 제한
# - watch thread 중복 생성 방지 강화
# =====================================================================
import queue as _v129_queue
import tempfile as _v129_tempfile

V129_VERSION = "v131 AUTO_RELAX_CANDIDATE_CACHE_FIX"
V129_FILE_LOCK = threading.RLock()
V129_THREAD_LOCK = threading.RLock()
V129_TG_QUEUE = _v129_queue.Queue(maxsize=int(os.getenv("TELEGRAM_QUEUE_MAX", "200")))
V129_TG_WORKER_STARTED = False

# 기존 파일 JSON 저장 방식 유지하되, 깨진 JSON 방지를 위해 atomic write 적용
def _v129_atomic_json_write(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = _v129_tempfile.mkstemp(prefix=p.name + '.', suffix='.tmp', dir=str(p.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        os.replace(tmp, str(p))
        return True
    except Exception as e:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        print('v129 atomic write error:', e, flush=True)
        return False

def _v129_safe_json_read(path, default):
    with V129_FILE_LOCK:
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except json.JSONDecodeError as e:
            print('v129 json decode warning:', path, e, flush=True)
        except Exception as e:
            print('v129 json read warning:', path, e, flush=True)
    return default

# 최종 read/write override: 이전 중복 정의보다 뒤에서 다시 정의하여 전역 함수 교체
def read_holdings():
    data = _v129_safe_json_read(HOLDINGS_FILE, [])
    return data if isinstance(data, list) else []

def write_holdings(items):
    with V129_FILE_LOCK:
        return _v129_atomic_json_write(HOLDINGS_FILE, items or [])

def read_trade_state():
    data = _v129_safe_json_read(TRADE_STATE_FILE, {})
    state = dict(TRADE_DEFAULTS)
    if isinstance(data, dict):
        state.update(data)
    return state

def write_trade_state(state):
    with V129_FILE_LOCK:
        return _v129_atomic_json_write(TRADE_STATE_FILE, state or {})

# 텔레그램 발송은 자동매매/감시 루프를 막지 않도록 큐로 분리
def _v129_send_telegram_direct(text):
    token=os.getenv('TELEGRAM_BOT_TOKEN','').strip(); chat_id=os.getenv('TELEGRAM_CHAT_ID','').strip()
    if not token or not chat_id:
        return False,'TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.'
    try:
        r=requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id':chat_id,'text':text,'parse_mode':'HTML','disable_web_page_preview':True},
            timeout=float(os.getenv('TELEGRAM_TIMEOUT_SEC','3.0'))
        )
        return (True,'sent') if r.status_code==200 else (False,r.text[:500])
    except Exception as e:
        return False,str(e)

def _v129_telegram_worker():
    while True:
        text = V129_TG_QUEUE.get()
        try:
            ok, msg = _v129_send_telegram_direct(text)
            try:
                st = read_trade_state()
                st['last_telegram_status'] = {'ok': ok, 'message': msg, 'time': now_kst().strftime('%Y-%m-%d %H:%M:%S')}
                write_trade_state(st)
            except Exception:
                pass
        except Exception as e:
            print('v129 telegram worker error:', e, flush=True)
        finally:
            V129_TG_QUEUE.task_done()

def v129_ensure_telegram_worker():
    global V129_TG_WORKER_STARTED
    if V129_TG_WORKER_STARTED:
        return
    with V129_THREAD_LOCK:
        if V129_TG_WORKER_STARTED:
            return
        t = threading.Thread(target=_v129_telegram_worker, daemon=True, name='v129_telegram_worker')
        t.start()
        V129_TG_WORKER_STARTED = True

v129_ensure_telegram_worker()

def send_telegram_message(text):
    """호출부에는 즉시 성공을 반환하고 실제 발송은 백그라운드 큐에서 처리합니다."""
    try:
        v129_ensure_telegram_worker()
        V129_TG_QUEUE.put_nowait(str(text or ''))
        return True, 'queued'
    except _v129_queue.Full:
        return False, '텔레그램 큐가 가득 찼습니다. 잠시 후 다시 시도하세요.'
    except Exception as e:
        return False, str(e)

# Render public IP는 대시보드 흐름을 막지 않도록 짧은 timeout + 캐시 사용
_V129_RENDER_IP_TS = 0

def get_render_public_ip(force=False):
    global _LAST_RENDER_IP_INFO, _V129_RENDER_IP_TS
    try:
        now_ts = time.time()
        ttl = int(os.getenv('RENDER_IP_CACHE_SEC', '21600'))
        if not force and _LAST_RENDER_IP_INFO.get('ip') and (now_ts - _V129_RENDER_IP_TS) < ttl:
            return _LAST_RENDER_IP_INFO
        timeout = float(os.getenv('RENDER_IP_TIMEOUT_SEC', '1.2'))
        ip = ''; source = ''
        for url, name in [('https://api.ipify.org','api.ipify.org'), ('https://ifconfig.me/ip','ifconfig.me')]:
            try:
                r = requests.get(url, timeout=timeout)
                if r.status_code == 200 and r.text.strip():
                    ip = r.text.strip(); source = name; break
            except Exception:
                pass
        if ip:
            _LAST_RENDER_IP_INFO = {'ok': True, 'ip': ip, 'source': source, 'checked_at': now_kst().strftime('%Y-%m-%d %H:%M:%S'), 'message': '이 IP를 키움 REST API 허용 IP에 등록하세요.'}
            _V129_RENDER_IP_TS = now_ts
            return _LAST_RENDER_IP_INFO
        if _LAST_RENDER_IP_INFO.get('ip'):
            _LAST_RENDER_IP_INFO['message'] = 'IP 재확인은 지연되었지만 마지막 정상 IP 캐시를 유지합니다.'
            return _LAST_RENDER_IP_INFO
        return {'ok': False, 'ip': '', 'source': 'NONE', 'checked_at': now_kst().strftime('%Y-%m-%d %H:%M:%S'), 'message': '공인 IP 확인 지연'}
    except Exception as e:
        return {'ok': False, 'ip': '', 'source': 'ERROR', 'checked_at': now_kst().strftime('%Y-%m-%d %H:%M:%S'), 'message': str(e)}

# 깊이 제한 있는 반복 탐색 함수
def v129_deep_find_number(obj, keys, max_depth=5, max_nodes=300):
    try:
        q = [(obj, 0)]
        seen = 0
        while q and seen < max_nodes:
            cur, depth = q.pop(0); seen += 1
            if depth > max_depth:
                continue
            if isinstance(cur, dict):
                for k in keys:
                    if k in cur:
                        n = abs(safe_float(str(cur.get(k, '')).replace(',', '').replace('+', '').replace('-', ''), 0))
                        if n > 0:
                            return n
                for v in cur.values():
                    if isinstance(v, (dict, list)):
                        q.append((v, depth + 1))
            elif isinstance(cur, list):
                for item in cur[:100]:
                    if isinstance(item, (dict, list)):
                        q.append((item, depth + 1))
    except Exception:
        pass
    return 0

def v109_get_orderbook_metrics(code):
    code = str(code).zfill(6)
    result = {'bid_total': 0, 'ask_total': 0, 'bid_ask_ratio': 0, 'orderbook_source': 'NONE'}
    try:
        if not kiwoom_ready():
            return result
        token = kiwoom_get_token()
        headers = {'Content-Type': 'application/json;charset=UTF-8','authorization': 'Bearer ' + token,'cont-yn': 'N','next-key': '','api-id': 'ka10004'}
        r = requests.post(KIWOOM_BASE_URL + '/api/dostk/stkinfo', json={'stk_cd': code}, headers=headers, timeout=float(os.getenv('KIWOOM_ORDERBOOK_TIMEOUT_SEC','3.0')))
        try:
            data = r.json() if r.text else {}
        except Exception:
            data = {'raw': r.text[:1000]}
        bid = v129_deep_find_number(data, ['tot_bid_req','tot_bid_qty','bid_total','매수호가총잔량','buy_total_qty'])
        ask = v129_deep_find_number(data, ['tot_ask_req','tot_ask_qty','ask_total','매도호가총잔량','sell_total_qty'])
        ratio = round(bid / ask, 3) if ask > 0 else 0
        if bid > 0 or ask > 0:
            result.update({'bid_total': bid, 'ask_total': ask, 'bid_ask_ratio': ratio, 'orderbook_source': 'KIWOOM'})
        return result
    except Exception as e:
        try: update_kiwoom_debug('orderbook_exception', code, 0, str(e))
        except Exception: pass
        return result

# watch thread는 살아있으면 새로 만들지 않고, 죽었을 때만 교체
def ensure_watch_running():
    with V129_THREAD_LOCK:
        WATCH_STATE['running'] = True
        t = WATCH_STATE.get('thread')
        if t is not None and t.is_alive():
            return True
        t = threading.Thread(target=watch_loop, daemon=True, name='watch_loop_v129')
        WATCH_STATE['thread'] = t
        t.start()
    return True

@app.route('/api/v129_status_light')
def api_v129_status_light():
    st = read_trade_state()
    cache = v119_read_cache() if 'v119_read_cache' in globals() else {}
    hitems = cache.get('holdings', []) if isinstance(cache, dict) else read_holdings()
    try:
        cc = dict(V128_CANDIDATE_CACHE)
    except Exception:
        cc = {}
    return jsonify(safe_json({
        'ok': True,
        'version': V129_VERSION,
        'state': st,
        'market_open': market_is_open(),
        'kiwoom_ready': kiwoom_ready(),
        'kiwoom_debug': st.get('last_kiwoom_debug', {}),
        'telegram_queue_size': V129_TG_QUEUE.qsize(),
        'holding_count': len(hitems),
        'holdings_cache_updated': cache.get('updatedAt','') if isinstance(cache, dict) else '',
        'candidate_cache_updated': cc.get('updated',''),
        'candidate_refreshing': cc.get('running', False),
        'message': 'v130 안정화 상태확인: 파일락/비동기텔레그램/캐시 상태 정상'
    }))




# ============================================================
# v131 endpoint aliases: 화면은 v131로 호출해도 기존 안정화 캐시 로직을 사용합니다.
# ============================================================
@app.route('/api/v131_best_pick_cached')
def api_v131_best_pick_cached():
    return api_v128_best_pick_cached()

@app.route('/api/v131_watch_candidates_cached')
def api_v131_watch_candidates_cached():
    return api_v128_watch_candidates_cached()

@app.route('/api/v131_holdings_cached', methods=['GET','POST'])
def api_v131_holdings_cached():
    return api_v128_holdings_cached()

@app.route('/api/v131_status_light')
def api_v131_status_light():
    return api_v127_status_light()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '10000'))
    app.run(host='0.0.0.0', port=port)
