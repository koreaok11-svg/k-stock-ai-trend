# -*- coding: utf-8 -*-
"""
성일의 AI 주식바람 - KIWOOM REAL AUTO SCALPING v88 STORAGE FIX
파일명: app_kiwoom_real_auto_scalping_v88_storage_fix.py

이 파일은 사용자가 업로드한 v88 계열 전체 텍스트를 기반으로 v88 목표 기능을 반영한 업그레이드본입니다.

v88 반영 핵심:
- 기존 키움 REST 토큰/현재가/주문/잔고동기화 구조 유지
- 기존 보유종목 자동등록/Render 재배포 후 복구/localStorage 백업 구조 유지
- AI 단타 후보에 v88 스캘핑 점수 추가
- 거래량 급증/거래대금/등락률/테마가중/체결강도 추정/호가잔량 추정 점수화
- 매도 후 자동 신규 후보 탐색/재매수 구조 유지 및 상태 표시 강화
- 실시간 상태 API /api/v88_dashboard 추가
- 기존 /api/version을 v88로 갱신
- 저장소 확인 중 멈춤 문제 수정: BASE_DIR 정의, Persistent Disk 경로, loadHoldings 중복 함수 제거

주의:
- 실전 주문 전 KIWOOM_DRY_RUN=true 상태에서 충분히 검증하세요.
- 호가/체결강도는 키움 실시간/호가 API 연결 상태에 따라 실제값 또는 추정값으로 표시됩니다.
- 투자 판단과 주문 책임은 사용자에게 있습니다.
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

# v88 FIX: Render 저장소 경로 통합
# - Render Persistent Disk를 쓰면 APP_DATA_DIR=/var/data 로 설정하세요.
# - Persistent Disk가 없으면 /tmp를 사용하므로 재배포 시 서버 파일은 사라질 수 있습니다.
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

HOLDINGS_FILE=os.getenv('SERVER_HOLDINGS_FILE','/tmp/sungil_holdings_v88.json')
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


# =========================================================
# v88 스캘핑 AI 확장 엔진
# =========================================================
def v88_clamp(v, lo=0, hi=100):
    try:
        return max(lo, min(hi, safe_float(v, 0)))
    except Exception:
        return lo

def v88_get_orderbook_metrics(code):
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

def v88_estimate_execution_strength(row):
    """
    체결강도 실제 API가 없을 때 쓰는 추정값.
    거래량순위/거래대금순위/당일등락률이 높을수록 강한 체결로 추정합니다.
    """
    amount_rank = safe_float(row.get("amountRank", 0))
    volume_rank = safe_float(row.get("volumeRank", 0))
    day_change = safe_float(row.get("dayChange", 0))
    base = 80 + amount_rank * 0.35 + volume_rank * 0.35 + max(0, day_change) * 3.0
    return round(v88_clamp(base, 50, 200), 2)

def v88_calculate_scalping_score(row, price, orderbook=None):
    """
    v88 최종 스캘핑 점수.
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
    volume_spike_score = v88_clamp(volume_rank * 0.6 + amount_rank * 0.4, 0, 100)

    # 체결강도
    execution_strength = v88_estimate_execution_strength(row)
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
        orderbook_score = v88_clamp((volume_rank + amount_rank) / 2 * 0.75, 20, 75)

    raw = (
        base_score * 0.30 +
        volume_spike_score * 0.22 +
        execution_score * 0.18 +
        orderbook_score * 0.15 +
        change_score * 0.15
    ) * min(theme_weight, 1.25)

    final_score = round(v88_clamp(raw, 0, 100), 2)

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
        "aiScoreV88": final_score,
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
    out=[]
    for _,row in df.head(20).iterrows():
        p=safe_float(row['Close']); qty=int(cash//p) if p else 0
        if qty<min_qty: continue
        code = str(row['Code']).zfill(6)
        live_p, src = get_trade_live_price(code, fallback=True)
        if live_p >= 10:
            p = live_p
            qty = int(cash // p) if p else 0
        if qty < min_qty:
            continue
        orderbook = v88_get_orderbook_metrics(code)
        v88_ai = v88_calculate_scalping_score(row, p, orderbook)
        base_pick = {'code':code,'name':str(row['Name']),'market':str(row.get('Market','')),'theme':normalize_theme(row['theme']),'price':round(p),'priceSource':src,'score':v88_ai['aiScoreV88'],'dayChange':round(safe_float(row['dayChange']),2),'amount':round(safe_float(row['Amount'])),'qtyPossible':qty,'buyZone':round(p*.995),'target':round(p*1.035),'stop':round(p*.975),'comment':f"v88 스캘핑 AI: {v88_ai['scalpingStatus']} · {', '.join(v88_ai['scalpingReasons'])}. 현재가는 {src} 기준입니다. 추격보다 호가·거래량 유지 확인 후 접근이 좋습니다."}
        base_pick.update(v88_ai)
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
    picks=sorted(picks, key=lambda x: safe_float(x.get('orderPriority', x.get('aiScoreV88', x.get('score', 0)))), reverse=True)
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


# ===============================
# Kiwoom REST 실전 자동매매 모듈
# ===============================
# Render 환경변수 등록명:
# KIWOOM_APP_KEY      = 키움 App Key
# KIWOOM_SECRET_KEY   = 키움 App Secret  (보조 호환: KIWOOM_APP_SECRET)
# KIWOOM_REAL_TRADING = true  -> 실전 주문 허용
# KIWOOM_DRY_RUN      = true  -> 실제 주문 전송 안 함 / false -> 실제 주문 전송

TRADE_STATE_FILE = os.getenv("TRADE_STATE_FILE", "/tmp/sungil_trade_state_v88.json")
KIWOOM_BASE_URL = os.getenv("KIWOOM_BASE_URL", "https://api.kiwoom.com").rstrip("/")
KIWOOM_APP_KEY = os.getenv("KIWOOM_APP_KEY", "").strip()
KIWOOM_SECRET_KEY = (os.getenv("KIWOOM_SECRET_KEY", "") or os.getenv("KIWOOM_APP_SECRET", "")).strip()
KIWOOM_REAL_TRADING = os.getenv("KIWOOM_REAL_TRADING", "false").lower() == "true"
KIWOOM_DRY_RUN = os.getenv("KIWOOM_DRY_RUN", "true").lower() == "true"
AUTO_BUY_IN_WATCH_LOOP = os.getenv("AUTO_BUY_IN_WATCH_LOOP", "false").lower() == "true"
AUTO_REBUY_AFTER_SELL = os.getenv("AUTO_REBUY_AFTER_SELL", "true").lower() == "true"
ORDER_CASH_SAFETY_RATE = safe_float(os.getenv("ORDER_CASH_SAFETY_RATE", "0.96"), 0.96)



PRICE_DIFF_LIMIT = safe_float(os.getenv("PRICE_DIFF_LIMIT", "0.01"), 0.01)
KIWOOM_PRICE_REQUIRED = os.getenv("KIWOOM_PRICE_REQUIRED", "true").lower() == "true"


TRADE_DEFAULTS = {
    "auto_trade_enabled": False,
    "max_total_cash": 500000,
    "max_order_cash": 450000,
    "cash_buffer": 50000,
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
        return "App Key 또는 Secret Key 검증 실패입니다. Render 환경변수 KIWOOM_APP_KEY / KIWOOM_SECRET_KEY 값을 다시 확인하세요."
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

    return {
        "max_total_cash": int(cash),
        "max_order_cash": int(max_order),
        "cash_buffer": int(buffer_cash),
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
        update_kiwoom_debug("token", "", 0, "KIWOOM_APP_KEY / KIWOOM_SECRET_KEY 환경변수가 비어 있습니다.")
        raise RuntimeError("KIWOOM_APP_KEY / KIWOOM_SECRET_KEY 환경변수가 필요합니다.")

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
    if read_holdings():
        return False, "동시 보유 1종목 제한으로 신규 매수하지 않습니다."
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
            "message": "Persistent Disk 사용 중" if persistent else "임시 저장소 사용 중: 재배포 시 서버 보유파일이 사라질 수 있어 브라우저 백업/키움동기화로 복구합니다."
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
            r = requests.post(KIWOOM_BASE_URL + path, json=body, headers=headers, timeout=8)
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

    if args is not None:
        pick, _ = best_pick_from_params(args)
    elif use_latest_ui_pick and state.get("latest_ui_pick"):
        pick = state.get("latest_ui_pick")
    else:
        pick, _ = best_pick_from_params({
            "cash": state.get("max_order_cash", 450000),
            "minQty": 1,
            "maxChange": 7,
            "minAmount": 1000000000,
            "minScore": 70
        })

    if not pick:
        update_trade_status("매수 보류", "현재 조건을 만족하는 AI 후보가 없습니다.")
        return {"ok": False, "message": "candidate not found"}

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

    max_order_cash = safe_float(state.get("max_order_cash", 450000))
    qty = calc_safe_order_qty(max_order_cash, live)

    if qty <= 0:
        reason = "주문 가능 수량이 0입니다."
        update_trade_status("매수 보류", reason, candidate=pick)
        return {"ok": False, "message": reason, "pick": pick}

    update_trade_status("주문 전송중", f"키움 매수 주문 전송 중: {pick.get('name')} {qty}주", candidate=pick)

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

        if read_holdings():
            update_trade_status("재매수 대기", "기존 보유종목이 있어 신규 매수를 진행하지 않습니다.")
            return {"ok": False, "message": "holding exists"}

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


@app.route('/api/restore_holdings', methods=['POST'])
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


@app.route('/api/server_holdings',methods=['GET','POST'])
def api_server_holdings():
    if request.method=='GET':
        holdings = read_holdings()
        if request.args.get('sync') == '1':
            holdings = sync_kiwoom_holdings_to_local()
        if request.args.get('refresh') == '1':
            holdings = [check_one_holding(h) for h in holdings]
            write_holdings(holdings)
        return jsonify({'ok':True,'holdings':holdings})
    data=request.get_json(force=True,silent=True) or {}; action=data.get('action','add'); holdings=read_holdings()
    if action=='add':
        item=normalize_holding(data.get('item',{})); code=item.get('code',''); buy=safe_float(item.get('buyPrice',0)); amount=safe_float(item.get('buyAmount',0)); qty=safe_float(item.get('qty',0)) or (math.floor(amount/buy) if buy and amount else 0)
        item.update({'qty':qty,'target':safe_float(item.get('target',0)) or round(buy*1.035),'stop':safe_float(item.get('stop',0)) or round(buy*.975),'id':item.get('id') or int(time.time()*1000),'lastPrice':(get_trade_live_price(code, fallback=True)[0] or buy)})
        holdings=[h for h in holdings if str(h.get('code','')).zfill(6)!=code]; holdings.append(item); write_holdings(holdings); ensure_watch_running()
    elif action=='remove':
        rid=str(data.get('id','')); code=str(data.get('code','')).zfill(6); holdings=[h for h in holdings if str(h.get('id',''))!=rid and str(h.get('code','')).zfill(6)!=code]; write_holdings(holdings)
    elif action=='clear': holdings=[]; remove_holding_by_code(code)
    elif action=='refresh': holdings=[check_one_holding(h) for h in holdings]; write_holdings(holdings)
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
    state["daily_max_loss"] = rec["daily_max_loss"]
    state["cooldown_minutes"] = rec["cooldown_minutes"]
    state["target_rate"] = rec["target_rate"]
    state["stop_rate"] = rec["stop_rate"]
    state["last_status"] = "AI 추천 설정 적용"
    state["last_status_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
    state["last_order_message"] = f"{rec['mode']} 적용: 목표 {rec['target_rate_percent']}%, 손절 {rec['stop_rate_percent']}%, 1회 진입 {rec['max_order_cash']:,}원"
    write_trade_state(state)
    return jsonify({"ok": True, "recommend": rec, "state": state})


@app.route('/api/auto_trade/status')
def api_auto_trade_status():
    state = read_trade_state()
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
        'target_rate_percent': round(normalize_rate_input(state.get('target_rate', 0.027), 0.027)*100, 3),
        'profit_guard_percent': round(normalize_rate_input(state.get('profit_guard_rate', 0.012), 0.012)*100, 3),
        'trailing_stop_percent': round(normalize_rate_input(state.get('trailing_stop_rate', 0.011), 0.011)*100, 3),
        'max_trades_per_day': int(state.get('max_trades_per_day', 10)),
        'trade_count_today': int(state.get('trade_count_today', 0)),
        'force_exit_time': state.get('force_exit_time', '15:15'),
        'stop_rate_percent': round(normalize_rate_input(state.get('stop_rate', -0.018), -0.018)*100, 3)
    })

@app.route('/api/auto_trade/set', methods=['POST'])
def api_auto_trade_set():
    data = request.get_json(force=True, silent=True) or {}
    state = read_trade_state()
    for key in ['auto_trade_enabled', 'panic_stop']:
        if key in data:
            state[key] = bool(data[key])
    for key in ['max_total_cash', 'max_order_cash', 'cash_buffer', 'daily_max_loss', 'cooldown_minutes', 'max_trades_per_day']:
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
    write_trade_state(state)
    if state.get('auto_trade_enabled'):
        ensure_watch_running()
    return jsonify({'ok': True, 'state': state})

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
    send_telegram_message('🛑 <b>긴급정지 실행</b>\n실전 자동매매를 OFF 했습니다.')
    return jsonify({'ok': True, 'state': state})



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



@app.route('/api/v88_dashboard')
def api_v88_dashboard():
    """
    v88 실시간 수익률/후보/상태 통합 대시보드 API.
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
            "version": "KIWOOM REAL AUTO SCALPING v88 STORAGE FIX",
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
def api_version(): return jsonify({'ok':True,'version':'kiwoom-real-auto-scalping-v88-upgrade','watch_interval':WATCH_INTERVAL,'file':'app_kiwoom_real_auto_scalping_v88_storage_fix.py','v88_dashboard':'/api/v88_dashboard'})

HTML = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>성일의 AI 주식바람 v88</title><style>
:root{--green:#426a49;--deep:#253528;--cream:#fffdf0;--orange:#f3ad4e;--soft:#eef7e7}*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;background:linear-gradient(180deg,#f7faec,#e6f3e5,#fff7de);color:var(--deep)}.app{max-width:880px;margin:0 auto;padding:22px 18px 80px}.card{background:rgba(255,255,255,.86);border:1px solid rgba(90,120,80,.16);border-radius:28px;padding:24px;margin:18px 0;box-shadow:0 16px 38px rgba(69,94,63,.11)}.hero{padding:26px 4px 8px}.hero h1{font-size:36px;line-height:1.15;margin:0 0 8px;font-weight:950}.hero p{margin:0;color:#667085;font-size:16px;line-height:1.5}.badge{display:inline-flex;gap:6px;align-items:center;border-radius:999px;background:#eaf5df;color:#406044;font-weight:900;padding:8px 12px;margin-bottom:10px}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}label{font-size:16px;font-weight:900;margin:12px 0 6px;display:block}input,select{width:100%;border:1px solid #d8e0cf;border-radius:18px;padding:14px 16px;font-size:18px;background:#fffffb}button{border:0;border-radius:20px;padding:16px 18px;font-size:17px;font-weight:900;background:linear-gradient(135deg,#f6af55,#aad889);color:#2b2b22;cursor:pointer}button.dark{background:#33495b;color:white}button.green{background:#5f9366;color:white}button.brown{background:#96622d;color:white}button.light{background:#eef7e7;color:#426a49}.row{display:flex;gap:10px;flex-wrap:wrap}.pick{border-radius:26px;background:#fffef8;border:1px solid #e4e9d7;padding:20px;box-shadow:0 10px 24px #0000000c}.pick h2{font-size:34px;margin:8px 0}.meta{display:flex;gap:8px;flex-wrap:wrap}.meta span{background:#edf4df;padding:8px 12px;border-radius:999px;font-weight:900}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:16px 0}.metric{background:#fbf8eb;border-radius:18px;padding:14px;text-align:center}.metric small{display:block;color:#667085;margin-bottom:6px}.metric b{font-size:20px}.comment{background:#eef8df;border-radius:18px;padding:14px;line-height:1.55;font-weight:800;color:#416246}.empty{padding:18px;border-radius:20px;background:#fff8df;color:#6b5b3f}.holding{background:white;border-radius:24px;padding:18px;margin:12px 0;border:1px solid #e0ead3}.red{color:#d32525}.blue{color:#2563eb}.muted{color:#667085}.tabs{position:sticky;top:0;z-index:10;background:rgba(250,252,239,.92);backdrop-filter:blur(14px);display:grid;grid-template-columns:repeat(6,1fr);gap:8px;padding:10px 0}.tab{padding:12px 6px;border:1px solid #d9e2ce;background:white;border-radius:999px;text-align:center;font-weight:900;font-size:14px}.tab.active{background:#5f8d65;color:white}.loading-screen{position:fixed;inset:0;background:linear-gradient(180deg,#fff8c8,#e7f6df,#d8ebff);z-index:9999;display:flex;align-items:center;justify-content:center;transition:.7s}.loading-screen.hide{opacity:0;pointer-events:none}.loading-card{width:min(86%,380px);border-radius:34px;background:rgba(255,255,255,.62);padding:34px 24px;text-align:center;box-shadow:0 20px 50px #0002}.loading-title{font-size:32px;font-weight:950;color:#34573a}.bar{height:12px;border-radius:99px;background:white;overflow:hidden;margin-top:18px}.bar span{display:block;height:100%;width:45%;background:linear-gradient(90deg,#f3c56f,#a5d987);animation:move 1.2s infinite}@keyframes move{from{margin-left:-50%}to{margin-left:110%}}.lock{position:fixed;inset:0;background:#f4faed;z-index:8888;display:flex;align-items:center;justify-content:center;padding:24px}.lock.hidden{display:none}.lockbox{max-width:460px;width:100%;background:white;border-radius:30px;padding:28px;box-shadow:0 20px 50px #0001}@media(max-width:560px){.hero h1{font-size:31px}.grid,.metrics{grid-template-columns:1fr}.app{padding:18px 14px 70px}.tab{font-size:12px}.metrics{grid-template-columns:1fr 1fr}}

.quick-money{display:flex;flex-wrap:wrap;gap:10px;margin:10px 0 18px}
.quick-money button{padding:12px 16px;border-radius:18px;border:1px solid rgba(51,80,55,.18);background:#eef7e9;font-size:.9em;font-weight:800;color:#31543a}
.quick-money button.darkmini{background:#32475a;color:white}
.quick-money .hint{width:100%;font-size:.82em;color:#6d7782;margin-top:2px}

</style></head><body><div id="loading" class="loading-screen"><div class="loading-card"><div style="font-size:58px">🍃</div><div class="loading-title">성일의 AI 주식바람</div><p class="muted">오늘 시장의 흐름을 읽는 중...</p><div class="bar"><span></span></div></div></div><div id="passwordLock" class="lock hidden"><div class="lockbox"><div class="badge">🔐 SECURE ACCESS</div><h1>성일의 AI 주식바람</h1><p class="muted">비밀번호를 입력하면 앱을 사용할 수 있습니다.</p><input id="passwordInput" type="password" placeholder="비밀번호 입력"><button class="green" onclick="login()" style="width:100%;margin-top:12px">로그인</button><p id="loginMessage" class="muted"></p></div></div><main class="app"><section class="hero"><div class="badge">🌿 KIWOOM REAL AUTO v88</div><h1>성일의 AI 주식바람</h1><p>키움 REST API 연동 · AI 최종 1종목 자동매수 · 목표/손절 자동매도 · 텔레그램 주문 알림</p></section><div class="tabs"><div class="tab active" onclick="go('filter')">⚙️ 설정</div><div class="tab" onclick="go('best')">⚡ 단타AI</div><div class="tab" onclick="go('watch')">👀 후보</div><div class="tab" onclick="go('holdings')">💼 보유</div><div class="tab" onclick="go('autotrade')">🤖 자동</div><div class="tab" onclick="go('telegram')">✉️ 알림</div></div><section id="filter" class="card"><h2>⚙️ 단타AI 필터 설정</h2><label>종목 가격 구간</label><select id="priceRanges" multiple size="4"><option value="1000-5000">1천~5천원</option><option value="5000-20000" selected>5천~2만원</option><option value="20000-50000" selected>2만~5만원</option><option value="50000-200000" selected>5만~20만원</option></select><div class="grid"><div><label>내 투자금</label><input id="cash" value="500000"></div><div class="quick-money">
<button type="button" onclick="setMoneyFast(1000)">1천원</button>
<button type="button" onclick="setMoneyFast(10000)">1만원</button>
<button type="button" onclick="setMoneyFast(100000)">10만원</button>
<button type="button" onclick="setMoneyFast(1000000)">100만원</button>
<button type="button" class="darkmini" onclick="addMoneyFast(10000)">+1만원</button>
<button type="button" class="darkmini" onclick="addMoneyFast(100000)">+10만원</button>
<button type="button" class="warnmini" onclick="clearMoneyFast()">지우기</button>
<div class="hint">먼저 금액 입력칸을 누른 뒤 버튼을 누르면 해당 칸에 금액이 들어갑니다.</div>
</div><div><label>최소 매수 가능 수량</label><input id="minQty" value="5"></div><div><label>최대 당일 등락률(%)</label><input id="maxChange" value="7"></div><div><label>최소 거래대금(원)</label><input id="minAmount" value="1000000000"></div><div class="quick-money">
<button type="button" onclick="setMoneyFast(1000000000)">10억</button>
<button type="button" onclick="setMoneyFast(5000000000)">50억</button>
<button type="button" onclick="setMoneyFast(10000000000)">100억</button>
<button type="button" onclick="setMoneyFast(30000000000)">300억</button>
<button type="button" class="darkmini" onclick="addMoneyFast(1000000000)">+10억</button>
<button type="button" class="warnmini" onclick="clearMoneyFast()">지우기</button>
</div><div><label>최소 AI 점수</label><input id="minScore" value="70"></div></div><div class="row" style="margin-top:16px"><button class="green" onclick="loadBest()">필터 적용/새로고침</button><button class="dark" onclick="loadWatch()">다음 단타 후보 보기</button><button class="brown" onclick="testBetterAlert()">텔레그램 테스트 알림</button></div></section><section id="best" class="card"><h2>⚡ AI 단타 최종 후보</h2><div id="bestBox" class="empty">아직 조회하지 않았습니다.</div></section><section id="watch" class="card"><h2>👀 급등 예상 감시 후보</h2><div id="watchBox" class="empty">다음 단타 후보 보기를 누르면 표시됩니다.</div></section><section id="holdings" class="card"><h2>💼 보유종목 관리</h2><p class="muted">실제 자동매수/키움 실보유 종목은 이곳에 자동 등록됩니다. 앱 업데이트 후에도 키움 계좌 또는 브라우저 백업으로 복구되며, 매도 또는 직접 삭제 전까지 유지됩니다.</p><div id="storageStatus" class="empty">저장소 확인 중...</div><div class="grid"><input id="hName" placeholder="종목명 예: 휴림로봇"><input id="hCode" placeholder="종목코드 예: 090710"><input id="hBuy" placeholder="매수가 예: 13120"><input id="hAmount" placeholder="매수금액 예: 500000"><div id="hAmountQuickMoney"><div class="quick-money">
<button type="button" onclick="setMoneyFast(1000)">1천원</button>
<button type="button" onclick="setMoneyFast(10000)">1만원</button>
<button type="button" onclick="setMoneyFast(100000)">10만원</button>
<button type="button" onclick="setMoneyFast(1000000)">100만원</button>
<button type="button" class="darkmini" onclick="addMoneyFast(10000)">+1만원</button>
<button type="button" class="darkmini" onclick="addMoneyFast(100000)">+10만원</button>
<button type="button" class="warnmini" onclick="clearMoneyFast()">지우기</button>
<div class="hint">먼저 금액 입력칸을 누른 뒤 버튼을 누르면 해당 칸에 금액이 들어갑니다.</div>
</div></div><input id="hQty" placeholder="수량 자동계산 또는 입력"><input id="hTarget" placeholder="목표가 자동 +3.5%"><input id="hStop" placeholder="손절가 자동 -2.5%"></div><div class="row" style="margin-top:14px"><button class="green" onclick="addHolding()">보유종목 등록</button><button class="dark" onclick="refreshHoldings()">현재가 즉시확인</button><button class="green" onclick="loadHoldings()">보유종목 강제 새로고침</button><button class="light" onclick="clearHoldings()">전체 삭제</button></div><div id="holdingStatus" class="empty" style="margin-top:14px">로딩 전입니다.</div><div id="holdingList"></div></section>
<section id="autotrade" class="card">
  <h2>🤖 키움 실전 자동매매</h2>
  <p class="muted">실전 자동매매는 키움 REST API 환경변수가 설정되어야 동작합니다. 처음에는 반드시 소액으로 체결 여부를 확인하세요.<br><b>AI 추천 설정</b>은 총 투자금 기준으로 1회 진입금·하루손실·목표/손절을 자동 계산합니다. 수동 설정도 가능합니다.<br>목표/손절 수익률은 <b>2.5 = +2.5%</b>, <b>-1.8 = -1.8%</b>처럼 입력하면 됩니다.</p>
  <div class="grid">
    <div><label>총 투자금</label><input id="atTotal" value="500000"></div>
    <div><label>1회 최대 진입금</label><input id="atOrder" value="450000"></div><div id="atOrderQuickMoney"><div class="quick-money">
<button type="button" onclick="setMoneyFast(1000)">1천원</button>
<button type="button" onclick="setMoneyFast(10000)">1만원</button>
<button type="button" onclick="setMoneyFast(100000)">10만원</button>
<button type="button" onclick="setMoneyFast(1000000)">100만원</button>
<button type="button" class="darkmini" onclick="addMoneyFast(10000)">+1만원</button>
<button type="button" class="darkmini" onclick="addMoneyFast(100000)">+10만원</button>
<button type="button" class="warnmini" onclick="clearMoneyFast()">지우기</button>
<div class="hint">먼저 금액 입력칸을 누른 뒤 버튼을 누르면 해당 칸에 금액이 들어갑니다.</div>
</div></div>
    <div><label>하루 최대 손실</label><input id="atLoss" value="-30000"></div>
    <div><label>재진입 금지(분)</label><input id="atCool" value="30"></div>
    <div><label>목표 수익률(%)</label><input id="atTarget" value="2.5"></div>
    <div><label>손절 수익률(%)</label><input id="atStop" value="-1.8"></div>
  </div>
  <div class="row" style="margin-top:14px">
    <button class="green" onclick="applyAiSettings()">AI 추천 설정 적용</button>
    <button class="light" onclick="manualSettingsGuide()">수동 설정</button>
  </div>
  <div id="aiSettingBox" class="empty" style="margin-top:10px">총 투자금 입력 후 AI 추천 설정 적용을 누르면 최적 조건이 자동 입력됩니다.</div>
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
    <button class="dark" onclick="panicStop()">긴급정지</button><button class="light" onclick="kiwoomPriceTest()">키움 현재가 테스트</button>
  </div>
  <div id="autoTradeBox" class="empty" style="margin-top:14px">자동매매 상태를 확인해 주세요.</div>
  <div id="autoTradeDetailBox" class="empty" style="margin-top:10px">최근 상태 로그가 여기에 표시됩니다.</div>
</section>

<section id="telegram" class="card"><h2>✉️ 텔레그램 기록/설정</h2><div class="row"><button class="green" onclick="telegramStatus()">설정 확인</button><button class="brown" onclick="telegramTest()">테스트 발송</button><button class="dark" onclick="startWatch()">실전 감시 시작</button></div><div id="telegramBox" class="empty" style="margin-top:14px">텔레그램 상태를 확인해 주세요.</div></section></main><script>
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
function go(id){document.getElementById(id).scrollIntoView({behavior:"smooth"})}function getParams(){return new URLSearchParams({priceRanges:[...$("priceRanges").selectedOptions].map(o=>o.value).join(","),cash:num($("cash").value),minQty:num($("minQty").value),maxChange:num($("maxChange").value),minAmount:num($("minAmount").value),minScore:num($("minScore").value)})}async function fetchJson(url,opts={}){const c=new AbortController(),t=setTimeout(()=>c.abort(),20000);try{const r=await fetch(url,{...opts,cache:"no-store",headers:{Accept:"application/json",...(opts.headers||{})},signal:c.signal});const txt=await r.text();try{return JSON.parse(txt)}catch(e){throw new Error("서버가 JSON이 아닌 응답을 반환했습니다.")}}finally{clearTimeout(t)}}function renderPick(p){if(!p)return"<div class='empty'>조건에 맞는 단타 후보가 없습니다. 조건을 낮춰보세요.</div>";return`<div class="pick"><div class="meta"><span>${p.market}</span><span>${p.code}</span><span>${p.theme}</span><span>AI ${p.score}</span></div><h2>${p.name}</h2><div class="metrics"><div class="metric"><small>현재가</small><b>${fmt(p.price)}</b><br><small>${p.priceSource||"-"}</small></div><div class="metric"><small>당일 흐름</small><b>${p.dayChange}%</b></div><div class="metric"><small>거래대금</small><b>${(p.amount/100000000).toFixed(1)}억</b></div><div class="metric"><small>매수관찰</small><b>${fmt(p.buyZone)}</b></div><div class="metric"><small>목표가</small><b class="red">${fmt(p.target)}</b></div><div class="metric"><small>손절가</small><b class="blue">${fmt(p.stop)}</b></div></div><div class="comment">AI 코멘트: ${p.comment}</div></div>`}async function loadBest(){$("bestBox").innerHTML="조회중...";try{const d=await fetchJson("/api/best_pick?"+getParams().toString());$("bestBox").innerHTML=renderPick(d.pick)}catch(e){$("bestBox").innerHTML="<div class='empty'>조회 오류: "+e.message+"</div>"}}async function loadWatch(){$("watchBox").innerHTML="조회중...";try{const d=await fetchJson("/api/watch_candidates?"+getParams().toString());$("watchBox").innerHTML=(d.items||[]).map(renderPick).join("")||"<div class='empty'>감시 후보가 없습니다.</div>"}catch(e){$("watchBox").innerHTML="<div class='empty'>조회 오류: "+e.message+"</div>"}}async function testBetterAlert(){const d=await fetchJson("/api/best_pick/test_alert?"+getParams().toString());alert(d.ok?"텔레그램 후보 알림 발송 완료":(d.message||"발송 실패"))}async function findCode(){const name=$("hName").value.trim();if(!name||$("hCode").value.trim())return;try{const d=await fetchJson("/api/find_stock?q="+encodeURIComponent(name));if(d.ok){$("hCode").value=d.code;if(!$("hBuy").value&&d.price)$("hBuy").value=Math.round(d.price);calcHolding()}}catch(e){}}function calcHolding(){const buy=num($("hBuy").value),amount=num($("hAmount").value);if(buy&&amount&&!$("hQty").value)$("hQty").value=Math.floor(amount/buy);if(buy&&!$("hTarget").value)$("hTarget").value=Math.round(buy*1.035);if(buy&&!$("hStop").value)$("hStop").value=Math.round(buy*.975)}async function addHolding(){await findCode();calcHolding();const item={name:$("hName").value.trim(),code:$("hCode").value.trim(),buyPrice:num($("hBuy").value),buyAmount:num($("hAmount").value),qty:num($("hQty").value),target:num($("hTarget").value),stop:num($("hStop").value)};if(!item.name||!item.code||!item.buyPrice){alert("종목명, 종목코드, 매수가는 필수입니다.");return}await fetchJson("/api/server_holdings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"add",item})});await refreshHoldings()}async function refreshHoldings(){const d=await fetchJson("/api/server_holdings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"refresh"})});renderHoldings(d.holdings||[])}async function clearHoldings(){if(!confirm("보유종목을 모두 삭제할까요?"))return;const d=await fetchJson("/api/server_holdings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"clear"})});renderHoldings(d.holdings||[])}async function loadHoldings(autoRestore=true){
  await loadStorageStatus();
  let d=await fetchJson("/api/server_holdings?sync=1&refresh=1");
  let list=d.holdings||[];

  if(autoRestore && (!list.length)){
    const backup=getBrowserHoldingBackup();
    if(backup.length){
      await fetchJson("/api/restore_holdings",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({holdings:backup})
      });
      d=await fetchJson("/api/server_holdings?refresh=1");
      list=d.holdings||[];
    }
  }

  if(list.length) backupHoldingsToBrowser(list);
  renderHoldings(list);
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
async function removeHolding(id,code){const d=await fetchJson("/api/server_holdings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"remove",id,code})});renderHoldings(d.holdings||[])}
function backupHoldingsToBrowser(list){
  try{
    if(Array.isArray(list) && list.length){
      localStorage.setItem("stock_ai_holdings_backup", JSON.stringify({time:new Date().toISOString(), holdings:list}));
    }
  }catch(e){console.log("backupHoldingsToBrowser error",e)}
}
function getBrowserHoldingBackup(){
  try{
    const raw=localStorage.getItem("stock_ai_holdings_backup");
    if(!raw) return [];
    const data=JSON.parse(raw);
    return Array.isArray(data.holdings)?data.holdings:[];
  }catch(e){return []}
}
async function restoreHoldingsFromBrowser(){
  const backup=getBrowserHoldingBackup();
  if(!backup.length){alert("브라우저 백업 보유종목이 없습니다.");return}
  const d=await fetchJson("/api/restore_holdings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({holdings:backup})});
  await loadHoldings(false);
  alert(`브라우저 백업 복구 완료: ${d.restored||0}개`);
}
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

// v88 FIX: 아래 중복 loadHoldings 함수가 기존 복구/백업 로직을 덮어써서
// '저장소 확인 중...'이 계속 남고 브라우저 백업 복구가 실행되지 않던 문제를 제거했습니다.

async function applyAiSettings(){
  const cash=num($("atTotal").value)||100000;
  const d=await fetchJson("/api/auto_trade/apply_recommend_settings?cash="+cash,{method:"POST"});
  if(!d.ok){alert("AI 추천 설정 적용 실패");return}
  const r=d.recommend||{};
  $("atTotal").value=r.max_total_cash||cash;
  $("atOrder").value=r.max_order_cash||Math.floor(cash*0.9);
  $("atLoss").value=r.daily_max_loss||-3000;
  $("atCool").value=r.cooldown_minutes||30;
  $("atTarget").value=r.target_rate_percent||2.5;
  $("atStop").value=r.stop_rate_percent||-1.8;
  if($("atMaxTrades")) $("atMaxTrades").value=r.max_trades_per_day||10;
  if($("atProfitGuard")) $("atProfitGuard").value=r.profit_guard_rate_percent||1.2;
  if($("atTrailing")) $("atTrailing").value=r.trailing_stop_rate_percent||1.1;
  if($("atExitTime")) $("atExitTime").value=r.force_exit_time||"15:15";
  $("aiSettingBox").innerHTML=`✅ <b>${r.mode}</b> 적용 완료<br>
  총 투자금 ${Number(r.max_total_cash).toLocaleString()}원 · 1회 최대 진입금 ${Number(r.max_order_cash).toLocaleString()}원 · 현금 여유 ${Number(r.cash_buffer).toLocaleString()}원<br>
  목표 +${r.target_rate_percent}% · 손절 ${r.stop_rate_percent}% · 하루 최대손실 ${Number(r.daily_max_loss).toLocaleString()}원 · 재진입금지 ${r.cooldown_minutes}분<br>
  <span class="muted">${r.note}</span>`;
  await autoTradeStatus();
}

function manualSettingsGuide(){
  $("aiSettingBox").innerHTML=`✍️ <b>수동 설정 모드</b><br>
  성일님이 직접 값을 입력한 뒤 <b>실전 자동매매 ON</b>을 누르면 해당 값이 적용됩니다.<br>
  추천 예시: 목표 2.5 / 손절 -1.8 / 1회 진입금은 총 투자금의 80~85%`;
}


async function autoTradeStatus(){
  const d=await fetchJson("/api/auto_trade/status");
  const s=d.state||{};
  $("autoTradeBox").innerHTML=`상태: <b>${s.auto_trade_enabled?"ON":"OFF"}</b> · 키움설정 ${d.kiwoom_ready?"완료":"필요"} · 실전ENV ${d.real_trading_env?"true":"false"} · DRY_RUN ${d.dry_run?"true":"false"} · 장중 ${d.market_open?"예":"아니오"}<br>
  금일손익 ${Number(s.daily_realized_pnl||0).toLocaleString()}원 · 하루손실제한 ${Number(s.daily_max_loss||-30000).toLocaleString()}원<br>
  적용 목표/손절: +${d.target_rate_percent||0}% / ${d.stop_rate_percent||0}%<br>스캘핑: 거래 ${d.trade_count_today||0}/${d.max_trades_per_day||10}회 · 수익보호 ${d.profit_guard_percent||1.2}% · 트레일링 ${d.trailing_stop_percent||1.1}% · 청산 ${d.force_exit_time||"15:15"}<br>
  <span class="muted">필수 환경변수: KIWOOM_APP_KEY / KIWOOM_SECRET_KEY / KIWOOM_REAL_TRADING / KIWOOM_DRY_RUN</span><br><span class="muted">가격정책: 키움현재가 필수 ${d.kiwoom_price_required?"ON":"OFF"} · 허용오차 ${d.price_diff_limit_pct}% · 백그라운드 자동매수 ${d.auto_buy_in_watch_loop?"ON":"OFF"} · 매도 후 신규매수 ${d.auto_rebuy_after_sell?"ON":"OFF"} · 주문안전비율 ${d.order_cash_safety_rate||0.96}</span>`;

  const cand=s.last_candidate||{};
  const tg=s.last_telegram_status||{};
  $("autoTradeDetailBox").innerHTML=`
    <b>최근 진행상태:</b> ${s.last_status||"대기중"}<br>
    <b>상태시간:</b> ${s.last_status_time||"-"}<br>
    <b>메시지:</b> ${s.last_order_message||"-"}<br>
    <b>최근 후보:</b> ${cand.name?`${cand.name} (${cand.code}) · AI ${cand.score} · 후보가 ${Number(cand.price||0).toLocaleString()}원 · 주문가 ${cand.orderLivePrice?Number(cand.orderLivePrice).toLocaleString()+"원":""} ${cand.orderPriceSource||""}`:"-"}<br>
    <b>텔레그램:</b> ${tg.ok===true?"발송 성공":tg.ok===false?"발송 실패":"-"} ${tg.message?`· ${tg.message}`:""}<br>
    <b>키움조회:</b> ${d.kiwoom_debug?`${d.kiwoom_debug.stage||"-"} · HTTP ${d.kiwoom_debug.http_status||"-"} · ${d.kiwoom_debug.message||"-"}`:"-"}
  `;
}
async function setAutoTrade(on){
  const body={
    auto_trade_enabled:on,
    panic_stop:false,
    max_total_cash:num($("atTotal").value),
    max_order_cash:num($("atOrder").value),
    daily_max_loss:num($("atLoss").value),
    cooldown_minutes:num($("atCool").value),
    target_rate:Number($("atTarget").value||2.5),
    stop_rate:Number($("atStop").value||-1.8),
    max_trades_per_day:num($("atMaxTrades")?.value||10),
    profit_guard_rate:Number($("atProfitGuard")?.value||1.2),
    trailing_stop_rate:Number($("atTrailing")?.value||1.1),
    force_exit_time:$("atExitTime")?.value||"15:15",
    scalp_mode:true
  };
  const d=await fetchJson("/api/auto_trade/set",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  await autoTradeStatus();
  alert(on?"실전 자동매매 ON 요청 완료":"자동매매 OFF 완료");
}
async function buyNow(){
  if(!confirm("현재 화면 필터 기준 AI 최종 1종목을 키움 API로 즉시 매수 시도할까요?\n\n목표/손절은 % 기준입니다. 예: 2.5 = +2.5%, -1.8 = -1.8%")) return;
  const d=await fetchJson("/api/auto_trade/buy_now?"+getParams().toString(),{method:"POST"});
  await autoTradeStatus();
  alert(d.ok?"매수 요청 완료. 텔레그램/HTS 체결 여부를 확인하세요.":"매수 실패/보류: "+(d.message||JSON.stringify(d.order||d)));
}
async function panicStop(){
  await fetchJson("/api/auto_trade/panic_stop",{method:"POST"});
  await autoTradeStatus();
  alert("긴급정지 완료");
}

async function kiwoomPriceTest(){
  const code=prompt("키움 현재가 테스트 종목코드 입력", "005930");
  if(!code) return;
  const d=await fetchJson("/api/kiwoom_price_test/"+code);
  await autoTradeStatus();
  alert(d.ok?`키움 현재가 조회 성공: ${Number(d.price).toLocaleString()}원`:`키움 현재가 조회 실패: ${JSON.stringify(d.debug)}`);
}

async function telegramStatus(){const d=await fetchJson("/api/telegram_status");$("telegramBox").innerHTML=d.ok?"✅ 텔레그램 설정 완료":"⚠️ Render 환경변수 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 확인 필요"}async function telegramTest(){const d=await fetchJson("/api/telegram_test");$("telegramBox").innerHTML=d.ok?"✅ 테스트 발송 완료":"⚠️ 테스트 실패: "+d.message}async function startWatch(){const d=await fetchJson("/api/server_watch/start",{method:"POST"});$("telegramBox").innerHTML=`🟢 실전 감시 시작 · ${d.holdings}개 · ${d.interval}초 간격`}async function login(){const d=await fetchJson("/api/login_check",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:$("passwordInput").value})});if(d.ok){localStorage.setItem("sungil_ai_login_role",d.role);$("passwordLock").classList.add("hidden")}else $("loginMessage").innerText=d.message||"로그인 실패"}function checkLock(){if(!localStorage.getItem("sungil_ai_login_role"))$("passwordLock").classList.remove("hidden")}$("hName").addEventListener("blur",findCode);["hBuy","hAmount"].forEach(id=>$(id).addEventListener("input",calcHolding));window.addEventListener("load",()=>{setTimeout(()=>{$("loading").classList.add("hide");setTimeout(()=>$("loading").remove(),700)},3500);checkLock();bindMoneyInputs();loadBest();loadHoldings();telegramStatus();autoTradeStatus();setInterval(loadHoldings,20000);setInterval(autoTradeStatus,10000)});
</script></body></html>'''

if __name__=='__main__':
    port=int(os.environ.get('PORT','10000'))
    app.run(host='0.0.0.0',port=port)
