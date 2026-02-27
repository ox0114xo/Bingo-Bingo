import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import collections
import random
import re

# ==========================================
# 區塊零：網頁設定與「自適應」台彩風格 CSS
# ==========================================
st.set_page_config(page_title="Bingo Bingo 智能對獎中心", page_icon="🎰", layout="wide")

# 移除強制文字顏色，讓 Streamlit 自動適應手機的深/淺色模式
st.markdown("""
<style>
    /* 標題加上台彩紅底線 */
    h1, h2, h3 { border-bottom: 2px solid #E63946; padding-bottom: 10px; }
    h1 { text-align: center; margin-top: -30px; }
    
    /* 強調數字使用台彩紅 */
    [data-testid="stMetricValue"] { color: #E63946; font-weight: bold; }
    
    /* 按鈕樣式：台彩紅底金字 */
    div.stButton > button { 
        background-color: #E63946 !important; 
        color: #FFFFFF !important; 
        border-radius: 5px; 
        border: 2px solid #F1C40F !important; 
        font-weight: bold; 
        width: 100%; 
    }
    div.stButton > button:hover { 
        background-color: #C12A35 !important; 
        border-color: #E0B40D !important; 
    }
    
    /* 警示與資訊框配色 */
    .stSuccess { background-color: rgba(46, 204, 113, 0.2) !important; }
    .stWarning { background-color: rgba(243, 156, 18, 0.2) !important; }
    .stError { background-color: rgba(230, 57, 70, 0.2) !important; }
    
    /* 分割線 */
    hr { border-top: 2px solid #E63946; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 區塊一：雙軌制獎金表
# ==========================================
NORMAL_PRIZE_TABLE = {
    1: {1: 50}, 2: {2: 75}, 3: {3: 500, 2: 50},
    4: {4: 1000, 3: 100, 2: 25}, 5: {5: 7500, 4: 500, 3: 50},
    6: {6: 25000, 5: 1000, 4: 200, 3: 25}
}
BONUS_PRIZE_TABLE = {
    1: {1: 50}, 2: {2: 75}, 3: {3: 1000, 2: 50},
    4: {4: 1500, 3: 100, 2: 25}, 5: {5: 7500, 4: 500, 3: 50},
    6: {6: 25000, 5: 1000, 4: 200, 3: 25}
}

# ==========================================
# 區塊二：多源備援爬蟲 (增強海外 IP 存取與錯誤顯示)
# ==========================================
@st.cache_data(ttl=60)
def fetch_real_bingo_data():
    # 強化偽裝，模擬真實台灣瀏覽器
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    
    error_logs = []

    # 策略一：台彩官方 API
    try:
        url_official = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/BingoResult"
        res = requests.get(url_official, headers=headers, timeout=5)
        if res.status_code == 200:
            json_data = res.json()
            parsed_data = []
            for item in json_data.get('content', [])[:20]:
                parsed_data.append({
                    "期數": str(item['period']),
                    "開獎時間": item['openTime'][:16].replace('T', ' '),
                    "開出號碼": [int(x) for x in item['drawNumberSize']]
                })
            if parsed_data:
                return parsed_data, True, "台彩官方 API", ""
        else:
            error_logs.append(f"官方API異常({res.status_code})")
    except Exception as e:
        error_logs.append(f"官方API錯誤")

    # 策略二：Lotto-8 海外開獎網 (較不易擋國外 IP)
    try:
        url_lotto8 = "https://www.lotto-8.com/taiwan/listbingo.asp"
        res = requests.get(url_lotto8, headers=headers, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.content.decode('utf-8', 'ignore'), 'html.parser')
            parsed_data = []
            for row in soup.find_all('tr'):
                cols = row.find_all('td')
                if len(cols) >= 2 and "期" in cols[0].text:
                    draw_id = "".join(filter(str.isdigit, cols[0].text))
                    nums_str = cols[1].text
                    numbers = [int(n) for n in re.findall(r'\d+', nums_str) if int(n) <= 80]
                    if len(numbers) >= 20 and draw_id:
                        parsed_data.append({
                            "期數": draw_id,
                            "開獎時間": "已開獎 (來源無提供精確時間)",
                            "開出號碼": numbers[:20]
                        })
            if parsed_data:
                return parsed_data[:20], True, "Lotto-8 開獎網", ""
        else:
            error_logs.append(f"Lotto8異常({res.status_code})")
    except Exception as e:
        error_logs.append(f"Lotto8錯誤")

    # 策略三：Pilio 樂透大數據網
    try:
        url_pilio = "https://www.pilio.idv.tw/bingo/list.asp"
        res = requests.get(url_pilio, headers=headers, timeout=5)
        if res.status_code == 200:
            # Pilio 常見為 Big5 編碼
            soup = BeautifulSoup(res.content.decode('big5', 'ignore'), 'html.parser')
            parsed_data = []
            rows = soup.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3 and "期" in cols[0].text:
                    draw_id = "".join(filter(str.isdigit, cols[0].text))
                    time_text = cols[1].text.strip()
                    nums_str = cols[2].text
                    numbers = [int(n) for n in re.findall(r'\d+', nums_str) if int(n) <= 80]
                    if len(numbers) >= 20 and draw_id:
                        parsed_data.append({
                            "期數": draw_id,
                            "開獎時間": time_text,
                            "開出號碼": numbers[:20]
                        })
            if parsed_data:
                return parsed_data[:20], True, "Pilio 樂透網", ""
        else:
            error_logs.append(f"Pilio異常({res.status_code})")
    except Exception as e:
        error_logs.append(f"Pilio錯誤")

    # 若全數失敗，產生防呆資料並回傳具體錯誤訊息
    now = datetime.now()
    base_draw = int(now.strftime("%Y%j001")) + ((now.hour * 12) + (now.minute // 5))
    mock_data = []
    for i in range(20): 
        draw_id = str(base_draw - i)
        draw_time = (now - timedelta(minutes=(now.minute % 5) + (i * 5))).strftime("%Y-%m-%d %H:%M")
        mock_data.append({
            "期數": draw_id,
            "開獎時間": draw_time,
            "開出號碼": random.sample(range(1, 81), 20)
        })
    return mock_data, False, "無", " | ".join(error_logs)

# 取得資料
latest_draws_list, fetch_success, data_source_name, error_details = fetch_real_bingo_data()
latest_data_dict = {item['期數']: {"time": item['開獎時間'], "numbers": item['開出號碼']} for item in latest_draws_list}

# ==========================================
# 區塊三：Session State 與介面輸入
# ==========================================
if 'saved_tickets' not in st.session_state:
    st.session_state.saved_tickets = {}

def save_ticket(name, star, multiplier, continuous, start_draw, numbers):
    ticket_id = f"{name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    st.session_state.saved_tickets[ticket_id] = {
        "name": name, "star": star, "multiplier": multiplier,
        "continuous": continuous, "start_draw": start_draw, "numbers": numbers
    }
    st.toast(f"✅ 彩券 '{name}' 已保存！")

def load_ticket(ticket_id):
    ticket = st.session_state.saved_tickets[ticket_id]
    st.session_state.play_star_input = ticket['star']
    st.session_state.multiplier_input = ticket['multiplier']
    st.session_state.draw_counts_input = ticket['continuous']
    st.session_state.start_draw_input = ticket['start_draw']
    st.session_state.selected_numbers_input = ticket['numbers']
    st.toast(f"🔄 已載入 '{ticket['name']}' 設定！")

st.markdown("<h1>🎰 Bingo Bingo 智能對獎中心</h1>", unsafe_allow_html=True)

# 資料來源狀態提示欄
if fetch_success:
    st.success(f"🟢 即時連線正常 | 當前資料來源：{data_source_name}")
else:
    st.error(f"🔴 網路斷線警告 | 目標網站可能阻擋了雲端主機連線。詳細錯誤：{error_details}")

st.markdown("<h3>📝 設定「我的號碼」</h3>", unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    play_star = st.selectbox("玩法 (星數)", options=list(range(1, 7)), index=2, key="play_star_input", format_func=lambda x: f"{x} 星")
with col2:
    multiplier = st.number_input("倍數", min_value=1, value=4, step=1, key="multiplier_input")
with col3:
    draw_counts = st.number_input("連續期數", min_value=1, value=10, step=1, key="draw_counts_input")
with col4:
    start_draw = st.text_input("起始期數", placeholder="例如: 113000123", key="start_draw_input")
with col5:
    st.write("")
    st.write("")
    is_bonus_active = st.checkbox("💰 啟用加碼獎金", value=False)

selected_numbers = st.multiselect(
    f"請選擇你的 {play_star} 個選號", 
    options=list(range(1, 81)), max_selections=play_star, key="selected_numbers_input"
)

with st.expander("💾 保存這張彩券 (長期使用功能)"):
    col_name, col_btn = st.columns([3, 1])
    ticket_name = col_name.text_input("輸入彩券名稱 (例如：我的週五包號)", key="ticket_name_input")
    if col_btn.button("保存這張彩券"):
        if ticket_name and len(selected_numbers) == play_star and start_draw:
            save_ticket(ticket_name, play_star, multiplier, draw_counts, start_draw, selected_numbers)
        else:
            st.error("⚠️ 請確保彩券有名稱、選號已滿、且填寫了起始期數。")

if st.session_state.saved_tickets:
    saved_options = {id: data['name'] for id, data in st.session_state.saved_tickets.items()}
    selected_saved_id = st.selectbox("🔄 載入已保存的彩券", options=list(saved_options.keys()), format_func=lambda id: saved_options[id])
    col_load_btn, _ = st.columns([1, 4])
    if col_load_btn.button("立即載入"):
        load_ticket(selected_saved_id)

st.divider()

# ==========================================
# 區塊四：對獎結果與金額
# ==========================================
if len(selected_numbers) == play_star and start_draw:
    st.markdown("<h3>🎯 實時對獎結果</h3>", unsafe_allow_html=True)
    
    total_prize = 0
    total_cost = 25 * multiplier * draw_counts
    results = []
    
    matched_draws = []
    try:
        current_draw_int = int(start_draw)
        for i in range(draw_counts):
            draw_id = str(current_draw_int + i)
            if draw_id in latest_data_dict:
                matched_draws.append((draw_id, latest_data_dict[draw_id]))
    except ValueError:
        st.error("期數格式錯誤，請輸入純數字。")

    if not matched_draws:
        st.warning(f"⚠️ 找不到從 {start_draw} 期開始的連續期數資料。")
    else:
        current_prize_table = BONUS_PRIZE_TABLE if is_bonus_active else NORMAL_PRIZE_TABLE

        for draw_id, data in matched_draws:
            winning_numbers = data["numbers"]
            draw_time = data["time"]
            
            matched_numbers = set(selected_numbers).intersection(set(winning_numbers))
            match_count = len(matched_numbers)
            
            base_prize = current_prize_table[play_star].get(match_count, 0)
            final_prize = base_prize * multiplier
            total_prize += final_prize
            
            results.append({
                "期數": draw_id,
                "開獎時間": draw_time,
                "開出號碼": ", ".join([str(n).zfill(2) for n in winning_numbers]),
                "對中號碼": ", ".join([str(n).zfill(2) for n in sorted(list(matched_numbers))]) if matched_numbers else "無",
                "本期獎金": f"${final_prize:,}" if final_prize > 0 else "$0"
            })
            
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        metric_col1.metric("購買總成本", f"${total_cost:,}")
        metric_col2.metric("累積獲得獎金", f"${total_prize:,}")
        profit = total_prize - total_cost
        
        if profit > 0:
            metric_col3.metric("淨賺", f"${profit:,}")
            st.success("恭喜！本張彩券目前贏得獎金！")
        elif profit < 0:
            metric_col3.metric("淨損", f"${profit:,}")
        else:
            metric_col3.metric("淨損益", f"${profit:,}")
        
        st.dataframe(pd.DataFrame(results), use_container_width=True)

elif len(selected_numbers) > 0 and len(selected_numbers) != play_star:
    st.warning(f"⚠️ 提示：您選擇了 {play_star} 星玩法，請選滿 {play_star} 個號碼。")

st.divider()

# ==========================================
# 區塊五：冷熱號碼分析
# ==========================================
st.markdown("<h3>📊 近期冷熱號碼分析</h3>", unsafe_allow_html=True)
analysis_N = st.slider("分析最近 N 期的號碼", min_value=10, max_value=50, value=20, step=10)
all_numbers = []
for draw_id, data in list(latest_data_dict.items())[:analysis_N]:
    all_numbers.extend(data['numbers'])

number_counts = collections.Counter(all_numbers)
df_counts = pd.DataFrame(number_counts.items(), columns=['號碼', '開出次數']).sort_values(by='開出次數', ascending=False)
df_counts['號碼'] = df_counts['號碼'].apply(lambda x: str(x).zfill(2))

hot_col, cold_col, chart_col = st.columns([1, 1, 2])
with hot_col:
    st.markdown("**🔥 熱門號碼 Top 10**")
    st.dataframe(df_counts.head(10)[['號碼', '開出次數']], use_container_width=True, hide_index=True)
with cold_col:
    st.markdown("**❄️ 冷門號碼 Top 10**")
    st.dataframe(df_counts.tail(10)[['號碼', '開出次數']].sort_values(by='開出次數'), use_container_width=True, hide_index=True)
with chart_col:
    st.markdown("**📈 全號碼分佈圖**")
    st.bar_chart(df_counts.set_index('號碼'), color='#E63946') # 改用台彩紅繪製圖表

st.divider()

# ==========================================
# 區塊六：每期號碼歷史紀錄
# ==========================================
st.markdown("<h3>📊 近期即時開獎紀錄</h3>", unsafe_allow_html=True)
col_refresh, col_time = st.columns([1, 4])
with col_refresh:
    if st.button("🔄 手動刷新資料"):
        fetch_real_bingo_data.clear()
        st.rerun()
with col_time:
    st.caption(f"🕒 最後刷新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (每分鐘自動抓取最新)")

history_cols = st.columns(min(len(latest_draws_list), 5))
for idx, item in enumerate(latest_draws_list[:5]):
    with history_cols[idx]:
        st.markdown(f"**第 {item['期數']} 期**")
        st.caption(f"🕒 {item['開獎時間']}")
        st.info(", ".join([str(n).zfill(2) for n in item['開出號碼']]))
