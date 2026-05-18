import os, re, json, time, math, threading
from datetime import datetime, timedelta, timezone
import requests
import pandas as pd
import numpy as np
import FinanceDataReader as fdr
from flask import Flask, jsonify, request, render_template_string, Response

app = Flask(__name__)
KST = timezone(timedelta(hours=9))

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

HOLDINGS_FILE=os.getenv('SERVER_HOLDINGS_FILE','/tmp/sungil_holdings_v72.json')
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
        out.append({'code':str(row['Code']).zfill(6),'name':str(row['Name']),'market':str(row.get('Market','')),'theme':normalize_theme(row['theme']),'price':round(p),'score':round(safe_float(row['score']),2),'dayChange':round(safe_float(row['dayChange']),2),'amount':round(safe_float(row['Amount'])),'qtyPossible':qty,'buyZone':round(p*.995),'target':round(p*1.035),'stop':round(p*.975),'comment':'거래대금·거래량·가격구간·AI점수 필터를 통과한 단타 후보입니다. 추격보다 호가 안정 확인 후 접근이 좋습니다.'})
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
    cur=get_live_price(code)
    if cur<10: h['priceError']='현재가 자동조회 실패. 다음 주기에 재시도합니다.'; return h
    h['lastPrice']=cur; h['lastCheckedAt']=now_kst().strftime('%Y-%m-%d %H:%M:%S'); h.pop('priceError',None); WATCH_STATE['last_prices'][code]=cur
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
TRADE_STATE_FILE = os.getenv("TRADE_STATE_FILE", "/tmp/sungil_trade_state_v73.json")
KIWOOM_BASE_URL = os.getenv("KIWOOM_BASE_URL", "https://api.kiwoom.com").rstrip("/")
KIWOOM_APP_KEY = os.getenv("KIWOOM_APP_KEY", "").strip()
KIWOOM_SECRET_KEY = os.getenv("KIWOOM_SECRET_KEY", "").strip()
KIWOOM_REAL_TRADING = os.getenv("KIWOOM_REAL_TRADING", "false").lower() == "true"
KIWOOM_DRY_RUN = os.getenv("KIWOOM_DRY_RUN", "true").lower() == "true"

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
    "panic_stop": False
}
_TOKEN_CACHE = {"token": "", "expires": 0}

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
        raise RuntimeError("KIWOOM_APP_KEY / KIWOOM_SECRET_KEY 환경변수가 필요합니다.")
    r = requests.post(
        KIWOOM_BASE_URL + "/oauth2/token",
        json={"grant_type": "client_credentials", "appkey": KIWOOM_APP_KEY, "secretkey": KIWOOM_SECRET_KEY},
        headers={"Content-Type": "application/json;charset=UTF-8"},
        timeout=8
    )
    data = r.json() if r.text else {}
    if r.status_code != 200 or not data.get("token"):
        raise RuntimeError("키움 토큰 발급 실패: " + str(data)[:500])
    _TOKEN_CACHE["token"] = data["token"]
    _TOKEN_CACHE["expires"] = time.time() + 60 * 50
    return _TOKEN_CACHE["token"]

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

def auto_buy_best_pick():
    state = read_trade_state()
    if not state.get("auto_trade_enabled"):
        return {"ok": False, "message": "auto trade off"}
    pick, _ = best_pick_from_params({
        "cash": state.get("max_order_cash", 450000),
        "minQty": 1,
        "maxChange": 7,
        "minAmount": 1000000000,
        "minScore": 70
    })
    if not pick:
        return {"ok": False, "message": "candidate not found"}
    code = pick["code"]
    live = get_live_price(code) or safe_float(pick.get("price", 0))
    allowed, reason = trade_can_buy(code, live)
    if not allowed:
        return {"ok": False, "message": reason, "pick": pick}
    qty = int(safe_float(state.get("max_order_cash", 450000)) // live)
    if qty <= 0:
        return {"ok": False, "message": "주문 가능 수량이 0입니다."}
    order = kiwoom_order("buy", code, qty, price=0, order_type="market")
    buy_amount = live * qty
    if order.get("ok"):
        target_rate = safe_float(state.get("target_rate", 0.027))
        stop_rate = safe_float(state.get("stop_rate", -0.018))
        holding = {
            "id": int(time.time() * 1000),
            "name": pick["name"],
            "code": code,
            "buyPrice": live,
            "buyAmount": buy_amount,
            "qty": qty,
            "target": round(live * (1 + target_rate)),
            "stop": round(live * (1 + stop_rate)),
            "lastPrice": live,
            "autoTrade": True,
            "buyOrder": order,
            "createdAt": now_kst().strftime("%Y-%m-%d %H:%M:%S")
        }
        write_holdings([holding])
        state["last_buy_code"] = code
        state["last_buy_time"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        trade_log_append(state, {"type": "BUY", "name": pick["name"], "code": code, "qty": qty, "price": live, "amount": buy_amount, "order": order})
        send_telegram_message(
            f"🚀 <b>AI 자동매수 {'DRY-RUN ' if order.get('dry_run') else ''}진행</b>\n"
            f"종목: <b>{pick['name']}</b> ({code})\n"
            f"매수가 기준: {live:,.0f}원\n"
            f"수량: {qty:,}주\n"
            f"매수금액: {buy_amount:,.0f}원\n"
            f"목표가: {holding['target']:,.0f}원\n"
            f"손절가: {holding['stop']:,.0f}원\n"
            f"AI 점수: {pick.get('score', 0):.2f}\n"
            f"테마: {pick.get('theme', '')}\n\n"
            "※ 실전 자동매매 모드입니다. HTS/MTS 체결 여부를 반드시 확인하세요."
        )
    else:
        send_telegram_message(f"⚠️ <b>AI 자동매수 실패</b>\n종목: {pick['name']} ({code})\n사유: {order.get('message') or order.get('response')}")
    return {"ok": bool(order.get("ok")), "pick": pick, "order": order}

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
    if pick: WATCH_STATE['best_code']=pick['code']; WATCH_STATE['best_score']=pick['score']
    return jsonify(safe_json({'ok':bool(pick),'pick':pick,'next':picks[1:6],'updated':now_kst().strftime('%Y-%m-%d %H:%M:%S')}))
@app.route('/api/watch_candidates')
def api_watch_candidates():
    _,picks=best_pick_from_params(request.args); return jsonify(safe_json({'ok':True,'items':picks[:8],'updated':now_kst().strftime('%Y-%m-%d %H:%M:%S')}))
@app.route('/api/best_pick/test_alert',methods=['GET','POST'])
def api_best_pick_test_alert():
    pick,_=best_pick_from_params(request.args)
    if not pick: return jsonify({'ok':False,'message':'현재 조건에 맞는 후보가 없습니다.'})
    return jsonify({'ok':send_better_pick_alert(pick,0),'pick':pick})
@app.route('/api/server_holdings',methods=['GET','POST'])
def api_server_holdings():
    if request.method=='GET': return jsonify({'ok':True,'holdings':read_holdings()})
    data=request.get_json(force=True,silent=True) or {}; action=data.get('action','add'); holdings=read_holdings()
    if action=='add':
        item=normalize_holding(data.get('item',{})); code=item.get('code',''); buy=safe_float(item.get('buyPrice',0)); amount=safe_float(item.get('buyAmount',0)); qty=safe_float(item.get('qty',0)) or (math.floor(amount/buy) if buy and amount else 0)
        item.update({'qty':qty,'target':safe_float(item.get('target',0)) or round(buy*1.035),'stop':safe_float(item.get('stop',0)) or round(buy*.975),'id':item.get('id') or int(time.time()*1000),'lastPrice':get_live_price(code) or buy})
        holdings=[h for h in holdings if str(h.get('code','')).zfill(6)!=code]; holdings.append(item); write_holdings(holdings); ensure_watch_running()
    elif action=='remove':
        rid=str(data.get('id','')); code=str(data.get('code','')).zfill(6); holdings=[h for h in holdings if str(h.get('id',''))!=rid and str(h.get('code','')).zfill(6)!=code]; write_holdings(holdings)
    elif action=='clear': holdings=[]; write_holdings([])
    elif action=='refresh': holdings=[check_one_holding(h) for h in holdings]; write_holdings(holdings)
    return jsonify({'ok':True,'holdings':holdings})
@app.route('/api/server_watch/start',methods=['GET','POST'])
def api_watch_start(): ensure_watch_running(); return jsonify({'ok':True,'running':True,'holdings':len(read_holdings()),'interval':WATCH_INTERVAL})
@app.route('/api/server_watch/stop',methods=['GET','POST'])
def api_watch_stop(): WATCH_STATE['running']=False; return jsonify({'ok':True,'running':False})
@app.route('/api/server_watch/status')
def api_watch_status(): return jsonify({'ok':True,'state':{k:v for k,v in WATCH_STATE.items() if k!='thread'},'holdings':read_holdings(),'interval':WATCH_INTERVAL})
@app.route('/api/live_price/<code>')
def api_live_price(code): p=get_live_price(code); return jsonify({'ok':p>=10,'code':str(code).zfill(6),'price':p,'updated':now_kst().strftime('%Y-%m-%d %H:%M:%S')})
@app.route('/api/find_stock')
def api_find_stock():
    q=str(request.args.get('q','')).strip(); code=resolve_code_by_name(q); price=get_live_price(code) if code else 0; return jsonify({'ok':bool(code),'name':q,'code':code,'price':price})
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

@app.route('/api/auto_trade/status')
def api_auto_trade_status():
    state = read_trade_state()
    return jsonify({
        'ok': True,
        'state': state,
        'kiwoom_ready': kiwoom_ready(),
        'real_trading_env': KIWOOM_REAL_TRADING,
        'dry_run': KIWOOM_DRY_RUN,
        'market_open': market_is_open()
    })

@app.route('/api/auto_trade/set', methods=['POST'])
def api_auto_trade_set():
    data = request.get_json(force=True, silent=True) or {}
    state = read_trade_state()
    for key in ['auto_trade_enabled', 'panic_stop']:
        if key in data:
            state[key] = bool(data[key])
    for key in ['max_total_cash', 'max_order_cash', 'cash_buffer', 'daily_max_loss', 'target_rate', 'stop_rate', 'cooldown_minutes']:
        if key in data:
            state[key] = safe_float(data[key], state.get(key, TRADE_DEFAULTS.get(key, 0)))
    write_trade_state(state)
    if state.get('auto_trade_enabled'):
        ensure_watch_running()
    return jsonify({'ok': True, 'state': state})

@app.route('/api/auto_trade/buy_now', methods=['POST', 'GET'])
def api_auto_trade_buy_now():
    result = auto_buy_best_pick()
    return jsonify(safe_json(result))

@app.route('/api/auto_trade/panic_stop', methods=['POST', 'GET'])
def api_auto_trade_panic_stop():
    state = read_trade_state()
    state['auto_trade_enabled'] = False
    state['panic_stop'] = True
    write_trade_state(state)
    send_telegram_message('🛑 <b>긴급정지 실행</b>\n실전 자동매매를 OFF 했습니다.')
    return jsonify({'ok': True, 'state': state})


@app.route('/api/version')
def api_version(): return jsonify({'ok':True,'version':'kiwoom-real-auto-v73','watch_interval':WATCH_INTERVAL})

HTML = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>성일의 AI 주식바람 v72</title><style>
:root{--green:#426a49;--deep:#253528;--cream:#fffdf0;--orange:#f3ad4e;--soft:#eef7e7}*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;background:linear-gradient(180deg,#f7faec,#e6f3e5,#fff7de);color:var(--deep)}.app{max-width:880px;margin:0 auto;padding:22px 18px 80px}.card{background:rgba(255,255,255,.86);border:1px solid rgba(90,120,80,.16);border-radius:28px;padding:24px;margin:18px 0;box-shadow:0 16px 38px rgba(69,94,63,.11)}.hero{padding:26px 4px 8px}.hero h1{font-size:36px;line-height:1.15;margin:0 0 8px;font-weight:950}.hero p{margin:0;color:#667085;font-size:16px;line-height:1.5}.badge{display:inline-flex;gap:6px;align-items:center;border-radius:999px;background:#eaf5df;color:#406044;font-weight:900;padding:8px 12px;margin-bottom:10px}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}label{font-size:16px;font-weight:900;margin:12px 0 6px;display:block}input,select{width:100%;border:1px solid #d8e0cf;border-radius:18px;padding:14px 16px;font-size:18px;background:#fffffb}button{border:0;border-radius:20px;padding:16px 18px;font-size:17px;font-weight:900;background:linear-gradient(135deg,#f6af55,#aad889);color:#2b2b22;cursor:pointer}button.dark{background:#33495b;color:white}button.green{background:#5f9366;color:white}button.brown{background:#96622d;color:white}button.light{background:#eef7e7;color:#426a49}.row{display:flex;gap:10px;flex-wrap:wrap}.pick{border-radius:26px;background:#fffef8;border:1px solid #e4e9d7;padding:20px;box-shadow:0 10px 24px #0000000c}.pick h2{font-size:34px;margin:8px 0}.meta{display:flex;gap:8px;flex-wrap:wrap}.meta span{background:#edf4df;padding:8px 12px;border-radius:999px;font-weight:900}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:16px 0}.metric{background:#fbf8eb;border-radius:18px;padding:14px;text-align:center}.metric small{display:block;color:#667085;margin-bottom:6px}.metric b{font-size:20px}.comment{background:#eef8df;border-radius:18px;padding:14px;line-height:1.55;font-weight:800;color:#416246}.empty{padding:18px;border-radius:20px;background:#fff8df;color:#6b5b3f}.holding{background:white;border-radius:24px;padding:18px;margin:12px 0;border:1px solid #e0ead3}.red{color:#d32525}.blue{color:#2563eb}.muted{color:#667085}.tabs{position:sticky;top:0;z-index:10;background:rgba(250,252,239,.92);backdrop-filter:blur(14px);display:grid;grid-template-columns:repeat(6,1fr);gap:8px;padding:10px 0}.tab{padding:12px 6px;border:1px solid #d9e2ce;background:white;border-radius:999px;text-align:center;font-weight:900;font-size:14px}.tab.active{background:#5f8d65;color:white}.loading-screen{position:fixed;inset:0;background:linear-gradient(180deg,#fff8c8,#e7f6df,#d8ebff);z-index:9999;display:flex;align-items:center;justify-content:center;transition:.7s}.loading-screen.hide{opacity:0;pointer-events:none}.loading-card{width:min(86%,380px);border-radius:34px;background:rgba(255,255,255,.62);padding:34px 24px;text-align:center;box-shadow:0 20px 50px #0002}.loading-title{font-size:32px;font-weight:950;color:#34573a}.bar{height:12px;border-radius:99px;background:white;overflow:hidden;margin-top:18px}.bar span{display:block;height:100%;width:45%;background:linear-gradient(90deg,#f3c56f,#a5d987);animation:move 1.2s infinite}@keyframes move{from{margin-left:-50%}to{margin-left:110%}}.lock{position:fixed;inset:0;background:#f4faed;z-index:8888;display:flex;align-items:center;justify-content:center;padding:24px}.lock.hidden{display:none}.lockbox{max-width:460px;width:100%;background:white;border-radius:30px;padding:28px;box-shadow:0 20px 50px #0001}@media(max-width:560px){.hero h1{font-size:31px}.grid,.metrics{grid-template-columns:1fr}.app{padding:18px 14px 70px}.tab{font-size:12px}.metrics{grid-template-columns:1fr 1fr}}
</style></head><body><div id="loading" class="loading-screen"><div class="loading-card"><div style="font-size:58px">🍃</div><div class="loading-title">성일의 AI 주식바람</div><p class="muted">오늘 시장의 흐름을 읽는 중...</p><div class="bar"><span></span></div></div></div><div id="passwordLock" class="lock hidden"><div class="lockbox"><div class="badge">🔐 SECURE ACCESS</div><h1>성일의 AI 주식바람</h1><p class="muted">비밀번호를 입력하면 앱을 사용할 수 있습니다.</p><input id="passwordInput" type="password" placeholder="비밀번호 입력"><button class="green" onclick="login()" style="width:100%;margin-top:12px">로그인</button><p id="loginMessage" class="muted"></p></div></div><main class="app"><section class="hero"><div class="badge">🌿 CLEAN VERSION v72</div><h1>성일의 AI 주식바람</h1><p>무한 로딩 제거 · 단타 최종 1종목 집중 · 더 좋은 후보 텔레그램 알림 · 보유종목 목표/손절 감시</p></section><div class="tabs"><div class="tab active" onclick="go('filter')">⚙️ 설정</div><div class="tab" onclick="go('best')">⚡ 단타AI</div><div class="tab" onclick="go('watch')">👀 후보</div><div class="tab" onclick="go('holdings')">💼 보유</div><div class="tab" onclick="go('autotrade')">🤖 자동</div><div class="tab" onclick="go('telegram')">✉️ 알림</div></div><section id="filter" class="card"><h2>⚙️ 단타AI 필터 설정</h2><label>종목 가격 구간</label><select id="priceRanges" multiple size="4"><option value="1000-5000">1천~5천원</option><option value="5000-20000" selected>5천~2만원</option><option value="20000-50000" selected>2만~5만원</option><option value="50000-200000" selected>5만~20만원</option></select><div class="grid"><div><label>내 투자금</label><input id="cash" value="500000"></div><div><label>최소 매수 가능 수량</label><input id="minQty" value="5"></div><div><label>최대 당일 등락률(%)</label><input id="maxChange" value="7"></div><div><label>최소 거래대금(원)</label><input id="minAmount" value="1000000000"></div><div><label>최소 AI 점수</label><input id="minScore" value="70"></div></div><div class="row" style="margin-top:16px"><button class="green" onclick="loadBest()">필터 적용/새로고침</button><button class="dark" onclick="loadWatch()">다음 단타 후보 보기</button><button class="brown" onclick="testBetterAlert()">텔레그램 테스트 알림</button></div></section><section id="best" class="card"><h2>⚡ AI 단타 최종 후보</h2><div id="bestBox" class="empty">아직 조회하지 않았습니다.</div></section><section id="watch" class="card"><h2>👀 급등 예상 감시 후보</h2><div id="watchBox" class="empty">다음 단타 후보 보기를 누르면 표시됩니다.</div></section><section id="holdings" class="card"><h2>💼 보유종목 관리</h2><p class="muted">등록한 종목은 삭제 전까지 유지되며, 서버가 목표가/손절가를 감시합니다.</p><div class="grid"><input id="hName" placeholder="종목명 예: 휴림로봇"><input id="hCode" placeholder="종목코드 예: 090710"><input id="hBuy" placeholder="매수가 예: 13120"><input id="hAmount" placeholder="매수금액 예: 500000"><input id="hQty" placeholder="수량 자동계산 또는 입력"><input id="hTarget" placeholder="목표가 자동 +3.5%"><input id="hStop" placeholder="손절가 자동 -2.5%"></div><div class="row" style="margin-top:14px"><button class="green" onclick="addHolding()">보유종목 등록</button><button class="dark" onclick="refreshHoldings()">현재가 즉시확인</button><button class="light" onclick="clearHoldings()">전체 삭제</button></div><div id="holdingStatus" class="empty" style="margin-top:14px">로딩 전입니다.</div><div id="holdingList"></div></section>
<section id="autotrade" class="card">
  <h2>🤖 키움 실전 자동매매</h2>
  <p class="muted">실전 자동매매는 키움 REST API 환경변수가 설정되어야 동작합니다. 처음에는 반드시 소액으로 체결 여부를 확인하세요.</p>
  <div class="grid">
    <div><label>총 투자금</label><input id="atTotal" value="500000"></div>
    <div><label>1회 최대 진입금</label><input id="atOrder" value="450000"></div>
    <div><label>하루 최대 손실</label><input id="atLoss" value="-30000"></div>
    <div><label>재진입 금지(분)</label><input id="atCool" value="30"></div>
    <div><label>목표 수익률</label><input id="atTarget" value="0.027"></div>
    <div><label>손절 수익률</label><input id="atStop" value="-0.018"></div>
  </div>
  <div class="row" style="margin-top:14px">
    <button class="green" onclick="setAutoTrade(true)">실전 자동매매 ON</button>
    <button class="light" onclick="setAutoTrade(false)">자동매매 OFF</button>
    <button class="brown" onclick="buyNow()">AI 최종 1종목 즉시매수</button>
    <button class="dark" onclick="panicStop()">긴급정지</button>
  </div>
  <div id="autoTradeBox" class="empty" style="margin-top:14px">자동매매 상태를 확인해 주세요.</div>
</section>

<section id="telegram" class="card"><h2>✉️ 텔레그램 기록/설정</h2><div class="row"><button class="green" onclick="telegramStatus()">설정 확인</button><button class="brown" onclick="telegramTest()">테스트 발송</button><button class="dark" onclick="startWatch()">실전 감시 시작</button></div><div id="telegramBox" class="empty" style="margin-top:14px">텔레그램 상태를 확인해 주세요.</div></section></main><script>
const $=id=>document.getElementById(id),fmt=n=>Number(n||0).toLocaleString()+"원",num=v=>Number(String(v||"").replace(/[^0-9.-]/g,""))||0;function go(id){document.getElementById(id).scrollIntoView({behavior:"smooth"})}function getParams(){return new URLSearchParams({priceRanges:[...$("priceRanges").selectedOptions].map(o=>o.value).join(","),cash:num($("cash").value),minQty:num($("minQty").value),maxChange:num($("maxChange").value),minAmount:num($("minAmount").value),minScore:num($("minScore").value)})}async function fetchJson(url,opts={}){const c=new AbortController(),t=setTimeout(()=>c.abort(),20000);try{const r=await fetch(url,{...opts,cache:"no-store",headers:{Accept:"application/json",...(opts.headers||{})},signal:c.signal});const txt=await r.text();try{return JSON.parse(txt)}catch(e){throw new Error("서버가 JSON이 아닌 응답을 반환했습니다.")}}finally{clearTimeout(t)}}function renderPick(p){if(!p)return"<div class='empty'>조건에 맞는 단타 후보가 없습니다. 조건을 낮춰보세요.</div>";return`<div class="pick"><div class="meta"><span>${p.market}</span><span>${p.code}</span><span>${p.theme}</span><span>AI ${p.score}</span></div><h2>${p.name}</h2><div class="metrics"><div class="metric"><small>현재가</small><b>${fmt(p.price)}</b></div><div class="metric"><small>당일 흐름</small><b>${p.dayChange}%</b></div><div class="metric"><small>거래대금</small><b>${(p.amount/100000000).toFixed(1)}억</b></div><div class="metric"><small>매수관찰</small><b>${fmt(p.buyZone)}</b></div><div class="metric"><small>목표가</small><b class="red">${fmt(p.target)}</b></div><div class="metric"><small>손절가</small><b class="blue">${fmt(p.stop)}</b></div></div><div class="comment">AI 코멘트: ${p.comment}</div></div>`}async function loadBest(){$("bestBox").innerHTML="조회중...";try{const d=await fetchJson("/api/best_pick?"+getParams().toString());$("bestBox").innerHTML=renderPick(d.pick)}catch(e){$("bestBox").innerHTML="<div class='empty'>조회 오류: "+e.message+"</div>"}}async function loadWatch(){$("watchBox").innerHTML="조회중...";try{const d=await fetchJson("/api/watch_candidates?"+getParams().toString());$("watchBox").innerHTML=(d.items||[]).map(renderPick).join("")||"<div class='empty'>감시 후보가 없습니다.</div>"}catch(e){$("watchBox").innerHTML="<div class='empty'>조회 오류: "+e.message+"</div>"}}async function testBetterAlert(){const d=await fetchJson("/api/best_pick/test_alert?"+getParams().toString());alert(d.ok?"텔레그램 후보 알림 발송 완료":(d.message||"발송 실패"))}async function findCode(){const name=$("hName").value.trim();if(!name||$("hCode").value.trim())return;try{const d=await fetchJson("/api/find_stock?q="+encodeURIComponent(name));if(d.ok){$("hCode").value=d.code;if(!$("hBuy").value&&d.price)$("hBuy").value=Math.round(d.price);calcHolding()}}catch(e){}}function calcHolding(){const buy=num($("hBuy").value),amount=num($("hAmount").value);if(buy&&amount&&!$("hQty").value)$("hQty").value=Math.floor(amount/buy);if(buy&&!$("hTarget").value)$("hTarget").value=Math.round(buy*1.035);if(buy&&!$("hStop").value)$("hStop").value=Math.round(buy*.975)}async function addHolding(){await findCode();calcHolding();const item={name:$("hName").value.trim(),code:$("hCode").value.trim(),buyPrice:num($("hBuy").value),buyAmount:num($("hAmount").value),qty:num($("hQty").value),target:num($("hTarget").value),stop:num($("hStop").value)};if(!item.name||!item.code||!item.buyPrice){alert("종목명, 종목코드, 매수가는 필수입니다.");return}await fetchJson("/api/server_holdings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"add",item})});await refreshHoldings()}async function refreshHoldings(){const d=await fetchJson("/api/server_holdings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"refresh"})});renderHoldings(d.holdings||[])}async function clearHoldings(){if(!confirm("보유종목을 모두 삭제할까요?"))return;const d=await fetchJson("/api/server_holdings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"clear"})});renderHoldings(d.holdings||[])}function renderHoldings(list){$("holdingStatus").innerHTML=`등록 보유종목 ${list.length}개 감시 중`;$("holdingList").innerHTML=list.map(h=>{const cur=Number(h.lastPrice||0),buy=Number(h.buyPrice||0),qty=Number(h.qty||0),pnl=(cur-buy)*qty,rate=buy?((cur-buy)/buy*100):0;return`<div class="holding"><b>${h.name} (${h.code})</b><br>매수가 ${fmt(buy)} · 현재가 ${cur?fmt(cur):"조회중"}<br>목표가 <span class="red">${fmt(h.target)}</span> · 손절가 <span class="blue">${fmt(h.stop)}</span><br>평가손익 <b class="${pnl>=0?'red':'blue'}">${pnl.toLocaleString()}원</b> · ${rate.toFixed(2)}% · 수량 ${qty}주${h.priceError?`<div class="empty">⚠️ ${h.priceError}</div>`:""}<div class="row" style="margin-top:10px"><button class="light" onclick="removeHolding('${h.id}','${h.code}')">삭제</button></div></div>`}).join("")}async function removeHolding(id,code){const d=await fetchJson("/api/server_holdings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"remove",id,code})});renderHoldings(d.holdings||[])}async function loadHoldings(){const d=await fetchJson("/api/server_holdings");renderHoldings(d.holdings||[])}
async function autoTradeStatus(){
  const d=await fetchJson("/api/auto_trade/status");
  const s=d.state||{};
  $("autoTradeBox").innerHTML=`상태: <b>${s.auto_trade_enabled?"ON":"OFF"}</b> · 키움설정 ${d.kiwoom_ready?"완료":"필요"} · 실전ENV ${d.real_trading_env?"true":"false"} · DRY_RUN ${d.dry_run?"true":"false"} · 장중 ${d.market_open?"예":"아니오"}<br>금일손익 ${Number(s.daily_realized_pnl||0).toLocaleString()}원 · 하루손실제한 ${Number(s.daily_max_loss||-30000).toLocaleString()}원`;
}
async function setAutoTrade(on){
  const body={auto_trade_enabled:on,panic_stop:false,max_total_cash:num($("atTotal").value),max_order_cash:num($("atOrder").value),daily_max_loss:num($("atLoss").value),cooldown_minutes:num($("atCool").value),target_rate:Number($("atTarget").value||0.027),stop_rate:Number($("atStop").value||-0.018)};
  const d=await fetchJson("/api/auto_trade/set",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  await autoTradeStatus();
  alert(on?"실전 자동매매 ON 요청 완료":"자동매매 OFF 완료");
}
async function buyNow(){
  if(!confirm("AI 최종 1종목을 키움 API로 즉시 매수 시도할까요?")) return;
  const d=await fetchJson("/api/auto_trade/buy_now",{method:"POST"});
  await autoTradeStatus();
  alert(d.ok?"매수 요청 완료. 텔레그램/HTS 체결 여부를 확인하세요.":"매수 실패/보류: "+(d.message||JSON.stringify(d.order||d)));
}
async function panicStop(){
  await fetchJson("/api/auto_trade/panic_stop",{method:"POST"});
  await autoTradeStatus();
  alert("긴급정지 완료");
}
async function telegramStatus(){const d=await fetchJson("/api/telegram_status");$("telegramBox").innerHTML=d.ok?"✅ 텔레그램 설정 완료":"⚠️ Render 환경변수 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 확인 필요"}async function telegramTest(){const d=await fetchJson("/api/telegram_test");$("telegramBox").innerHTML=d.ok?"✅ 테스트 발송 완료":"⚠️ 테스트 실패: "+d.message}async function startWatch(){const d=await fetchJson("/api/server_watch/start",{method:"POST"});$("telegramBox").innerHTML=`🟢 실전 감시 시작 · ${d.holdings}개 · ${d.interval}초 간격`}async function login(){const d=await fetchJson("/api/login_check",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:$("passwordInput").value})});if(d.ok){localStorage.setItem("sungil_ai_login_role",d.role);$("passwordLock").classList.add("hidden")}else $("loginMessage").innerText=d.message||"로그인 실패"}function checkLock(){if(!localStorage.getItem("sungil_ai_login_role"))$("passwordLock").classList.remove("hidden")}$("hName").addEventListener("blur",findCode);["hBuy","hAmount"].forEach(id=>$(id).addEventListener("input",calcHolding));window.addEventListener("load",()=>{setTimeout(()=>{$("loading").classList.add("hide");setTimeout(()=>$("loading").remove(),700)},3500);checkLock();loadBest();loadHoldings();telegramStatus();autoTradeStatus();setInterval(loadHoldings,20000)});
</script></body></html>'''

if __name__=='__main__':
    port=int(os.environ.get('PORT','10000'))
    app.run(host='0.0.0.0',port=port)
