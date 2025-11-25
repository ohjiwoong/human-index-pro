import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ==========================================
# 🔑 [보안] Streamlit 비밀 금고에서 가져오기
import streamlit as st # (맨 위에 import 있는지 확인)

POLYGON_API_KEY = st.secrets["POLYGON_API_KEY"]
# ==========================================

# 🎨 1. 페이지 설정
st.set_page_config(
    page_title="Human Index Pro (Reddit)",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS 디자인
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .block-container { padding: 1rem; }
    
    div[data-testid="stSelectbox"] > div > div {
        background-color: #262730; color: white; border: 1px solid #41424C;
    }
    
    /* 레딧 스타일 박스 */
    .community-box {
        background-color: #1A1A1B;
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 8px;
        border-left: 4px solid #FF4500; /* 레딧 오렌지색 */
    }
    .box-hype { border-left-color: #0079D3; } /* 화력 좋은 글 */
    
    .post-info { font-size: 0.8em; color: #818384; float: right; }
    .sentiment-badge { font-weight: bold; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; margin-right: 5px; }
    .stat-icon { margin-left: 10px; color: #D7DADC; font-size: 0.85em; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 🛠️ 2. 추천 종목 리스트
TICKER_LIST = [
    "SOXL - Semis 3x Bull", "TSLA - Tesla", "NVDA - Nvidia", 
    "AAPL - Apple", "MSFT - Microsoft", "TQQQ - Nasdaq 3x Bull", 
    "AMZN - Amazon", "GOOGL - Google", "AMD - AMD", 
    "COIN - Coinbase", "GME - GameStop", "PLTR - Palantir", 
    "INTC - Intel", "MSTR - MicroStrategy", "➕ 직접 입력"
]

# ==========================================
# 🛠️ 3. 데이터 함수

@st.cache_data(ttl=60)
def get_polygon_data(ticker):
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}?adjusted=true&sort=asc&limit=50000&apiKey={POLYGON_API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        if "results" not in data: return pd.DataFrame()
        df = pd.DataFrame(data["results"])
        df['Date'] = pd.to_datetime(df['t'], unit='ms')
        df['DateStr'] = df['Date'].dt.strftime('%Y-%m-%d')
        df = df.set_index('Date')
        df = df.rename(columns={'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume'})
        return df
    except: return pd.DataFrame()

# 🔥 [핵심] 레딧(Reddit) 크롤링 함수
def get_reddit_sentiment(ticker):
    # 레딧 검색 API (JSON)
    # q={ticker}: 종목명 검색
    # sort=new: 최신순
    # limit=25: 25개 가져오기
    url = f"https://www.reddit.com/search.json?q={ticker}&sort=new&limit=25&type=link"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        
        # 403/429 에러 방어
        if response.status_code != 200:
            st.error(f"레딧 연결 실패 (Code: {response.status_code}) - 잠시 후 다시 시도하세요.")
            return 0, 0, []

        data = response.json()
        posts = data['data']['children']
        
        long_cnt = 0
        short_cnt = 0
        clean_posts = []
        
        # 레딧용 감성 키워드
        bull_kwd = ['buy', 'long', 'moon', 'rocket', 'bull', 'call', 'yolo', 'hold', 'green', 'up']
        bear_kwd = ['sell', 'short', 'drop', 'crash', 'bear', 'put', 'red', 'down', 'dump']
        
        for post in posts:
            p = post['data']
            title = p.get('title', '')
            selftext = p.get('selftext', '')[:100] # 본문은 앞부분만
            full_text = f"{title} {selftext}".lower()
            
            # 시간 변환 (Unix Timestamp -> Readable)
            created_utc = p.get('created_utc', 0)
            dt_object = datetime.fromtimestamp(created_utc)
            post_time = dt_object.strftime('%m-%d %H:%M')
            
            # 통계
            ups = p.get('ups', 0)
            comments = p.get('num_comments', 0)
            subreddit = p.get('subreddit', 'unknown')
            
            # 감성 분석
            sentiment = "Discussion"
            if any(k in full_text for k in bull_kwd):
                sentiment = "🔥 Bullish (호재)"
                long_cnt += 1
            elif any(k in full_text for k in bear_kwd):
                sentiment = "🧊 Bearish (악재)"
                short_cnt += 1
            
            clean_posts.append({
                "text": title,
                "sentiment": sentiment,
                "time": post_time,
                "ups": ups,
                "comments": comments,
                "sub": subreddit
            })
            
        return long_cnt, short_cnt, clean_posts

    except Exception as e:
        return 0, 0, []

# ==========================================
# 🖥️ 메인 화면

st.title("🤖 Human Index Pro (Reddit)")
st.caption("미국 주식의 성지, 레딧(Reddit) 실시간 반응")

# 검색창
selected_item = st.selectbox(
    "종목 검색", options=TICKER_LIST, index=0, label_visibility="collapsed"
)

if "직접 입력" in selected_item:
    input_ticker = st.text_input("티커 입력", value="").upper()
    ticker = input_ticker.replace(" ", "") if input_ticker else "SOXL"
else:
    ticker = selected_item.split(" - ")[0]

# 데이터 로딩
df = get_polygon_data(ticker)
l_score, s_score, posts_data = get_reddit_sentiment(ticker)

# 지표 카드
st.write("")
m1, m2, m3 = st.columns(3)

with m1:
    if not df.empty:
        curr = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        pct = ((curr - prev) / prev) * 100
        st.metric(f"💰 {ticker}", f"${curr:.2f}", f"{pct:.2f}%")
    else: st.metric("주가", "-")

with m2:
    total = l_score + s_score
    if total == 0: total = 1
    idx = int((l_score / total) * 100)
    msg = "👀 Neutral"
    if idx >= 60: msg = "🚀 Hype (과열)"
    elif idx <= 40: msg = "🐻 Fear (공포)"
    st.metric("📊 Reddit Hype", f"{idx}", msg)

with m3:
    st.metric("🗣️ Bull vs Bear", f"{l_score} : {s_score}", f"Last {len(posts_data)} posts")

# 차트
st.markdown("---")
if not df.empty:
    fig = go.Figure(data=[go.Candlestick(
        x=df['DateStr'], open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'],
        increasing_line_color='#00ff00', decreasing_line_color='#ff0000'
    )])
    fig.update_layout(
        title=dict(text=f"{ticker} Daily", font=dict(color="white", size=15)),
        template="plotly_dark", height=400, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", xaxis_rangeslider_visible=False,
        xaxis=dict(type='category', nticks=5), dragmode=False, showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# 게시글
st.markdown("---")
c1, c2 = st.columns([2, 1])
with c1: st.subheader(f"💬 Reddit ({ticker})")
with c2: 
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with st.container(height=450):
    if posts_data:
        for post in posts_data:
            sentiment = post['sentiment']
            text = post['text']
            post_time = post['time']
            ups = post['ups']
            comments = post['comments']
            sub = post['sub']
            
            # 스타일링 (화력 높은 글 강조)
            box_class = "community-box"
            color_style = "color: #bbb;"
            
            if "Bullish" in sentiment: 
                color_style = "color: #00ff00; font-weight:bold;"
            elif "Bearish" in sentiment: 
                color_style = "color: #ff4444; font-weight:bold;"
                
            # 화력(좋아요)이 50개 넘으면 파란 테두리
            if ups > 50: box_class += " box-hype"
            
            st.markdown(f"""
            <div class="{box_class}">
                <div style="margin-bottom:6px; display:flex; justify-content:space-between;">
                    <div>
                        <span class="sentiment-badge" style="{color_style}">● {sentiment}</span>
                        <span style="color:#FF4500; font-weight:bold; font-size:0.8em;">r/{sub}</span>
                    </div>
                    <span class="post-info">{post_time}</span>
                </div>
                <div style="font-size:1.0em; color:#EFEFEF; font-weight:500; margin-bottom:8px;">{text}</div>
                <div style="color:#818384; font-size:0.85em;">
                    ⬆️ {ups} <span style="margin:0 5px;">|</span> 💬 {comments} comments
                </div>
            </div>""", unsafe_allow_html=True)
    else:
        st.warning(f"레딧에서 '{ticker}' 관련 최신 글을 못 찾았습니다.")
        st.caption("팁: 티커가 너무 짧거나(O, T) 인기가 없으면 검색이 안 될 수 있습니다.")