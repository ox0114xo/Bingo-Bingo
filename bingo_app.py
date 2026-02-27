import streamlit as st
import streamlit.components.v1 as components
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import collections
import re
import urllib.parse

# ==========================================
# 區塊零：網頁設定與高質感 CSS
# ==========================================
st.set_page_config(page_title="Bingo Bingo 專業對獎終端", page_icon="🎰", layout="wide")

st.markdown("""
<style>
    /* 全局與標題樣式 */
    h1, h2, h3 { border-bottom: 2px solid #E63946; padding-bottom: 10px; }
    h1 { text-align: center; margin-top: -30px; }
    [data-testid="stMetricValue"] { color: #E63946; font-weight: bold; }
    
    /* Streamlit 原生按鈕樣式 */
    div.stButton > button { background-color: #E63946 !important; color: #FFFFFF !important; border-radius: 5px; border: 2px solid #F1C40F !important; font-weight: bold; width: 100%; }
    div.stButton > button:hover { background-color: #C12A35 !important; border-color: #E0B40D !important; }
    
    /* 讓 radio 選項橫向排版 */
    div.row-widget.stRadio > div { flex-direction: row; gap: 20px; }
    
    /* 頁籤 (Tabs) 樣式優化 */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { background-color: #0A1931; color: #FFFFFF; border-radius: 5px 5px 0 0; padding: 10px 20px; }
    .stTabs [aria-selected="true"] { background-color: #E63946; border-bottom-color: #E63946; }
    
    hr { border-top: 2px solid #E63946; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 區塊一：獎金表
# ==========================================
NORMAL_STAR_PRIZE = {
    1: {1: 50}, 2: {2: 75}, 3: {3: 500, 2: 50}, 4: {4: 1000, 3: 100, 2: 25}, 
    5: {5: 7500, 4: 500, 3: 50}, 6: {6: 25000, 5: 1000, 4: 200, 3: 25},
    7: {7: 80000, 6: 3000, 5: 300, 4: 50, 3: 25}, 8: {8: 500000, 7: 20000, 6: 1000, 5: 400, 4: 100, 0: 25},
    9: {9: 1000000, 8: 100000, 7: 3000, 6: 500, 5: 100, 4: 25, 0: 25}, 10: {10: 5000000, 9: 250000, 8: 25000, 7: 2500, 6: 250, 5: 25, 0: 25}
}
BONUS_STAR_PRIZE = NORMAL_STAR_PRIZE.copy()
BONUS_STAR_PRIZE[3] = {3: 1000, 2: 50}
BONUS_STAR_PRIZE[4] = {4: 1500, 3: 100, 2: 25}
BS_PRIZE_TABLE = {"大": 150, "小": 150}
OE_PRIZE_TABLE = {"單": 150, "雙": 150, "小單": 45, "小雙": 45, "和": 70}

# ==========================================
# 區塊二：無假資料爬蟲 (10重火力)
# ==========================================
def parse_official_api(res):
    return [{"期數": str(i['period']), "開獎時間": i['openTime'][:16].replace('T', ' '), "開出號碼": [int(x) for x in i['drawNumberSize']]} for i in res.json().get('content', [])[:20]]

def parse_html_table(res, encoding='utf-8'):
    soup = BeautifulSoup(res.content.decode(encoding, errors='ignore'), 'html.parser')
    parsed = []
    for row in soup.find_all('tr'):
        text = row.get_text()
        if '期' in text:
            nums = [int(n) for n in re.findall(r'\d+', text)]
            valid_nums = [n for n in nums if 1 <= n <= 80]
            if len(valid_nums) >= 20:
                draw_ids = re.findall(r'11[0-9]{7}', text)
                if draw_ids:
                    parsed.append({"期數": draw_ids[0], "開獎時間": "已開獎", "開出號碼": valid_nums[:20]})
    return parsed

@st.cache_data(ttl=60)
def fetch_real_bingo_data():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0', 'Accept': '*/*'}
    url_official = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/BingoResult"
    url_pilio = "https://www.pilio.idv.tw/bingo/list.asp"
    url_lotto8 = "https://www.lotto-8.com/taiwan/listbingo.asp"
    
    strategies = [
        {"name": "1. 官方API (CodeTabs跳板)", "url": f"https://api.codetabs.com/v1/proxy?quest={url_official}", "type": "official"},
        {"name": "2. Pilio 樂透 (CodeTabs跳板)", "url": f"https://api.codetabs.com/v1/proxy?quest={url_pilio}", "type": "html_big5"},
        {"name": "3. 官方API (直連)", "url": url_official, "type": "official"},
        {"name": "4. 官方API (AllOrigins)", "url": f"https://api.allorigins.win/raw?url={urllib.parse.quote(url_official)}", "type": "official"},
        {"name": "5. Pilio 樂透 (直連)", "url": url_pilio, "type": "html_big5"},
        {"name": "6. Lotto8 開獎 (CodeTabs)", "url": f"https://api.codetabs.com/v1/proxy?quest={url_lotto8}", "type": "html_utf8"},
        {"name": "7. 官方API (CorsProxy)", "url": f"https://corsproxy.io/?{urllib.parse.quote(url_official)}", "type": "official"},
        {"name": "8. Pilio 樂透 (AllOrigins)", "url": f"https://api.allorigins.win/raw?url={urllib.parse.quote(url_pilio)}", "type": "html_big5"},
        {"name": "9. Lotto8 開獎 (直連)", "url": url_lotto8, "type": "html_utf8"},
        {"name": "10. 官方API (ThingProxy)", "url": f"https://thingproxy.freeboard.io/fetch/{url_official}", "type": "official"},
    ]
    
    error_logs = []
    for strat in strategies:
        try:
            res = requests.get(strat["url"], headers=headers, timeout=4)
            if res.status_code == 200:
                parsed_data = parse_official_api(res) if strat["type"] == "official" else parse_html_table(res, encoding='big5' if strat["type"] == "html_big5" else 'utf-8')
                if parsed_data: return parsed_data, True, strat["name"], ""
            else: error_logs.append(f"{strat['name'][:5]}錯({res.status_code})")
        except Exception: error_logs.append(f"{strat['name'][:5]}逾時")

    # 拔除假資料！全部失敗時回傳空陣列
    return [], False, "無", " | ".join(error_logs)

latest_draws_list, fetch_success, data_source_name, error_details = fetch_real_bingo_data()
latest_data_dict = {item['期數']: {"time": item['開獎時間'], "numbers": item['開出號碼']} for item in latest_draws_list}

# ==========================================
# 頂部動態區塊：倒數計時器
# ==========================================
st.markdown("<h1>🎰 Bingo Bingo 專業對獎終端</h1>", unsafe_allow_html=True)

components.html("""
    <div style="font-family: sans-serif; text-align: center; padding: 15px; background-color: #0A1931; color: white; border-radius: 10px; margin-bottom: 10px; border: 2px solid #E63946;">
        <span style="font-size: 1.2rem;">⏳ 距離下一期開獎還有：</span>
        <span id="timer" style="font-size: 2.2rem; color: #F1C40F; font-weight: bold; font-family: monospace;">--:--</span>
    </div>
    <script>
        function updateTime() {
            var now = new Date();
            var sec = now.getSeconds();
            var min = now.getMinutes();
            var nextMin = Math.ceil((min + 1) / 5) * 5;
            var remainMin = nextMin - min - 1;
            var remainSec = 60 - sec;
            if(remainSec === 60) { remainMin += 1; remainSec = 0; }
            document.getElementById('timer').innerText =
                (remainMin < 10 ? "0" : "") + remainMin + ":" +
                (remainSec < 10 ? "0" : "") + remainSec;
        }
        setInterval(updateTime, 1000);
        updateTime();
    </script>
""", height=100)

if fetch_success: 
    st.success(f"🟢 即時連線成功 | 資料來源：**{data_source_name}**")
else: 
    st.error(f"🔴 網路斷線警告 | 被阻擋，無最新資料。日誌：{error_details}")

# ==========================================
# Session State 與彩券保存
# ==========================================
if 'saved_tickets' not in st.session_state: st.session_state.saved_tickets = {}

def save_ticket(name, mode, detail, multiplier, continuous, start_draw):
    ticket_id = f"{name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    st.session_state.saved_tickets[ticket_id] = {
        "name": name, "mode": mode, "detail": detail, 
        "multiplier": multiplier, "continuous": continuous, "start_draw": start_draw
    }
    st.toast(f"✅ 彩券 '{name}' 已保存！")

# ==========================================
# 採用「頁籤 (Tabs)」取代舊式按鈕，提升 UI 質感
# ==========================================
tab1, tab2, tab3 = st.tabs(["📝 投注與對獎", "📊 開獎紀錄", "🔥 冷熱分析"])

# ----------------- Tab 1: 投注與對獎 -----------------
with tab1:
    st.markdown("### 📝 設定你的投注單")
    game_mode = st.radio("🎲 選擇遊戲模式", ["🔢 星號玩法 (1~10星)", "⚖️ 猜大小", "☯️ 猜單雙"])

    col_play, col_mult, col_draw, col_start, col_bonus = st.columns([2, 1, 1, 1.5, 1])

    with col_mult: multiplier = st.number_input("倍數", min_value=1, value=4, step=1)
    with col_draw: draw_counts = st.number_input("連續期數", min_value=1, value=10, step=1)
    with col_start: start_draw = st.text_input("起始期數", placeholder="例如: 113000123")
    with col_bonus:
        st.write("")
        st.write("")
        is_bonus_active = st.checkbox("💰 啟用加碼獎金", value=False)

    bet_detail = None
    if game_mode == "🔢 星號玩法 (1~10星)":
        with col_play: play_star = st.selectbox("星數", options=list(range(1, 11)), index=2, format_func=lambda x: f"{x} 星")
        selected_numbers = st.multiselect(f"請選擇你的 {play_star} 個號碼", options=list(range(1, 81)), max_selections=play_star)
        bet_detail = {"star": play_star, "numbers": selected_numbers}
        is_valid_bet = (len(selected_numbers) == play_star)
    elif game_mode == "⚖️ 猜大小":
        with col_play: bs_choice = st.selectbox("選擇大小", ["大", "小"], format_func=lambda x: "大 (41~80)" if x == "大" else "小 (01~40)")
        bet_detail = {"choice": bs_choice}
        is_valid_bet = True
    elif game_mode == "☯️ 猜單雙":
        with col_play: oe_choice = st.selectbox("選擇單雙", ["單", "雙", "小單", "小雙", "和"])
        bet_detail = {"choice": oe_choice}
        is_valid_bet = True

    with st.expander("💾 保存彩券配置 (無資料時亦可儲存)"):
        col_name, col_btn = st.columns([3, 1])
        ticket_name = col_name.text_input("輸入彩券名稱進行保存")
        if col_btn.button("保存彩券"):
            if ticket_name and is_valid_bet and start_draw: save_ticket(ticket_name, game_mode, bet_detail, multiplier, draw_counts, start_draw)
            else: st.error("請確認資料填寫完整。")

    st.divider()
    st.markdown("### 🎯 實時對獎結果")

    if not fetch_success:
        st.warning("📡 目前無法連線取得開獎資料。請稍後重試，或考慮將本程式部署至 Hugging Face Spaces 或本地端執行以解除 IP 封鎖。")
    elif is_valid_bet and start_draw:
        total_prize = 0
        total_cost = 25 * multiplier * draw_counts
        results = []
        
        matched_draws = []
        try:
            for i in range(draw_counts):
                draw_id = str(int(start_draw) + i)
                if draw_id in latest_data_dict: matched_draws.append((draw_id, latest_data_dict[draw_id]))
        except ValueError:
            pass 

        if not matched_draws:
            st.info(f"⚠️ 資料庫中尚無起始期數 {start_draw} 的相關紀錄，可能尚未開獎。")
        else:
            for draw_id, data in matched_draws:
                winning_numbers = data["numbers"]
                base_prize = 0
                match_str = ""
                
                if game_mode == "🔢 星號玩法 (1~10星)":
                    matched_nums = set(bet_detail["numbers"]).intersection(set(winning_numbers))
                    match_count = len(matched_nums)
                    prize_table = BONUS_STAR_PRIZE if is_bonus_active else NORMAL_STAR_PRIZE
                    base_prize = prize_table[bet_detail["star"]].get(match_count, 0)
                    match_str = f"中 {match_count} 個: " + (", ".join([str(n).zfill(2) for n in sorted(list(matched_nums))]) if matched_nums else "無")

                elif game_mode == "⚖️ 猜大小":
                    big_count = sum(1 for n in winning_numbers if n >= 41)
                    actual_result = "大" if big_count >= 13 else ("小" if big_count <= 7 else "無 (8~12個)")
                    if bet_detail["choice"] == actual_result: base_prize = BS_PRIZE_TABLE[bet_detail["choice"]]
                    match_str = f"開出: {actual_result} (大{big_count}/小{20-big_count})"

                elif game_mode == "☯️ 猜單雙":
                    odd_count = sum(1 for n in winning_numbers if n % 2 != 0)
                    actual_result = "單" if odd_count >= 13 else ("雙" if odd_count <= 7 else ("小單" if odd_count in [11,12] else ("小雙" if odd_count in [8,9] else "和")))
                    if bet_detail["choice"] == actual_result: base_prize = OE_PRIZE_TABLE[bet_detail["choice"]]
                    match_str = f"開出: {actual_result} (單{odd_count}/雙{20-odd_count})"
                
                final_prize = base_prize * multiplier
                total_prize += final_prize
                
                results.append({
                    "期數": draw_id, "開出號碼": ", ".join([str(n).zfill(2) for n in winning_numbers]),
                    "對獎結果": match_str, "本期獎金": f"${final_prize:,}" if final_prize > 0 else "$0"
                })
                
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            metric_col1.metric("購買總成本", f"${total_cost:,}")
            metric_col2.metric("累積獲得獎金", f"${total_prize:,}")
            profit = total_prize - total_cost
            
            if profit > 0:
                metric_col3.metric("淨賺", f"${profit:,}")
                st.success("恭喜！本張彩券目前贏得獎金！")
            else:
                metric_col3.metric("淨損益", f"${profit:,}")
            
            st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.info("👆 請完成投注設定與起始期數，系統將在此顯示對獎結果。")

# ----------------- Tab 2: 開獎紀錄 -----------------
with tab2:
    st.markdown("### 📊 近期即時開獎紀錄")
    col_refresh, col_time = st.columns([1, 4])
    with col_refresh:
        if st.button("🔄 手動刷新資料"):
            fetch_real_bingo_data.clear()
            st.rerun()
    with col_time:
        st.caption(f"🕒 最後刷新嘗試: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not latest_draws_list:
        st.warning("❌ 目前無資料可顯示。")
    else:
        # 使用多欄排版顯示紀錄，版面更緊湊
        history_cols = st.columns(min(len(latest_draws_list), 4))
        for idx, item in enumerate(latest_draws_list[:8]): # 最多顯示8期，4個一排
            with history_cols[idx % 4]:
                st.markdown(f"**第 {item['期數']} 期**")
                st.caption(f"🕒 {item['開獎時間']}")
                st.info(", ".join([str(n).zfill(2) for n in item['開出號碼']]))

# ----------------- Tab 3: 冷熱分析 -----------------
with tab3:
    st.markdown("### 🔥 近期冷熱號碼分析")
    
    if not latest_draws_list:
        st.warning("❌ 需要取得真實開獎資料才能進行大數據分析。")
    else:
        analysis_N = st.slider("分析最近 N 期的號碼", min_value=10, max_value=50, value=20, step=10)
        all_numbers = []
        for draw_id, data in list(latest_data_dict.items())[:analysis_N]:
            all_numbers.extend(data['numbers'])

        if all_numbers:
            number_counts = collections.Counter(all_numbers)
            df_counts = pd.DataFrame(number_counts.items(), columns=['號碼', '開出次數']).sort_values(by='開出次數', ascending=False)
            df_counts['號碼'] = df_counts['號碼'].apply(lambda x: str(x).zfill(2))

            hot_col, cold_col, chart_col = st.columns([1, 1, 2])
            with hot_col:
                st.markdown("**🔥 熱門 Top 10**")
                st.dataframe(df_counts.head(10)[['號碼', '開出次數']], use_container_width=True, hide_index=True)
            with cold_col:
                st.markdown("**❄️ 冷門 Top 10**")
                st.dataframe(df_counts.tail(10)[['號碼', '開出次數']].sort_values(by='開出次數'), use_container_width=True, hide_index=True)
            with chart_col:
                st.markdown("**📈 全號碼分佈圖**")
                st.bar_chart(df_counts.set_index('號碼'), color='#E63946')
