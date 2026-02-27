import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# 設定頁面
st.set_page_config(page_title="Bingo Bingo 即時對獎", page_icon="🎰", layout="wide")

# --- 獎金與玩法設定 (以基本注 $25 計算) ---
PRIZE_TABLE = {
    1: {1: 50},
    2: {2: 75},
    3: {3: 500, 2: 50},
    4: {4: 1000, 3: 100, 2: 25},
    5: {5: 7500, 4: 500, 3: 50},
    6: {6: 25000, 5: 1000, 4: 200, 3: 25}
}

# --- 爬取最新即時資料 (多源備援機制) ---
@st.cache_data(ttl=60)
def fetch_latest_draws():
    """
    實作多源抓取邏輯：
    1. 先嘗試抓取台灣彩券官方新版 JSON API
    2. 如果失敗，退而求其次抓取第三方開獎網的 HTML 解析
    """
    raw_data = {}
    
    # [來源一] 台灣彩券官方 API (概念示範)
    try:
        # url_official = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/BingoResult"
        # res = requests.get(url_official, timeout=5)
        # res.raise_for_status()
        # raw_data = 解析官方 JSON ...
        pass
    except Exception as e_official:
        st.toast("官方來源無回應，嘗試切換備用來源...")
        
        # [來源二] 備用第三方網站 (例如：樂透雲、開獎網、久久樂透)
        try:
            # url_backup = "https://lotto.arclink.com.tw/Bingo.html"
            # res = requests.get(url_backup, timeout=5)
            # raw_data = 解析備用網站 HTML ...
            pass
        except Exception as e_backup:
            st.error("所有開獎資訊來源皆連線異常，請稍後再試。")

    # 模擬回傳的近期開獎資料 (加入時間欄位)
    return {
        "113000125": {"time": "2026-02-27 20:15:00", "numbers": [2, 4, 10, 15, 20, 26, 31, 35, 41, 46, 51, 56, 59, 62, 67, 71, 74, 75, 78, 80]},
        "113000124": {"time": "2026-02-27 20:10:00", "numbers": [1, 5, 9, 14, 18, 25, 30, 33, 40, 44, 48, 52, 58, 60, 66, 69, 73, 76, 77, 79]},
        "113000123": {"time": "2026-02-27 20:05:00", "numbers": [3, 8, 12, 15, 22, 27, 31, 38, 42, 45, 50, 55, 61, 65, 68, 70, 72, 75, 78, 80]}
    }

latest_data = fetch_latest_draws()

# ==========================================
# 區塊一：使用者輸入區 (移至最上方)
# ==========================================
st.title("🎰 Bingo Bingo 即時對獎系統")
st.markdown("### 📝 設定購買清單")

# 使用欄位排版讓畫面更緊湊
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    play_star = st.selectbox("玩法 (星數)", options=list(range(1, 7)), index=2, format_func=lambda x: f"{x} 星")
with col2:
    multiplier = st.number_input("倍數", min_value=1, value=4, step=1)
with col3:
    draw_counts = st.number_input("連續期數", min_value=1, value=10, step=1)
with col4:
    start_draw = st.text_input("起始期數", placeholder="例如: 113000123")
with col5:
    st.write("") # 排版佔位
    st.write("")
    is_bonus_active = st.checkbox("💰 啟用加碼獎金")

# 選號區拉出來獨立，讓畫面較寬廣
selected_numbers = st.multiselect(
    f"請選擇 {play_star} 個號碼 (您已購買的號碼)", 
    options=list(range(1, 81)),
    max_selections=play_star
)

st.divider()

# ==========================================
# 區塊二：對獎結果與金額 (緊接在輸入區下方)
# ==========================================
if len(selected_numbers) == play_star and start_draw:
    st.markdown("### 🎯 對獎結果與金額")
    
    total_prize = 0
    total_cost = 25 * multiplier * draw_counts
    results = []
    
    for draw_id, data in latest_data.items():
        winning_numbers = data["numbers"]
        draw_time = data["time"]
        
        # 對獎邏輯
        matched_numbers = set(selected_numbers).intersection(set(winning_numbers))
        match_count = len(matched_numbers)
        base_prize = PRIZE_TABLE[play_star].get(match_count, 0)
        
        # 加碼邏輯 (以 1.5 倍為例，可自行調整)
        if is_bonus_active and base_prize > 0:
            base_prize = int(base_prize * 1.5)
            
        final_prize = base_prize * multiplier
        total_prize += final_prize
        
        results.append({
            "期數": draw_id,
            "開獎時間": draw_time,
            "開出號碼": ", ".join([str(n).zfill(2) for n in winning_numbers]),
            "對中號碼": ", ".join([str(n).zfill(2) for n in matched_numbers]) if matched_numbers else "無",
            "本期獎金": f"${final_prize:,}" if final_prize > 0 else "$0"
        })
        
    # 總結算數字 (用 Metrics 大字顯示)
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("購買總成本", f"${total_cost:,}")
    metric_col2.metric("累積獲得獎金", f"${total_prize:,}")
    profit = total_prize - total_cost
    metric_col3.metric("淨賺 / 淨損", f"${profit:,}")
    
    # 詳細對獎明細表
    st.dataframe(pd.DataFrame(results), use_container_width=True)

elif len(selected_numbers) > 0 and len(selected_numbers) != play_star:
    st.warning(f"⚠️ 提示：您選擇了 {play_star} 星玩法，目前選了 {len(selected_numbers)} 個號碼，請選滿 {play_star} 個才能進行對獎。")

st.divider()

# ==========================================
# 區塊三：每期號碼歷史紀錄 (移至最下方)
# ==========================================
st.markdown("### 📊 近期開獎號碼")
col_refresh, col_time = st.columns([1, 4])
with col_refresh:
    if st.button("🔄 手動刷新號碼"):
        fetch_latest_draws.clear()
        st.rerun()
with col_time:
    st.caption(f"最後系統更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (每分鐘自動刷新)")

# 顯示最新的期數卡片，並加上時間
history_cols = st.columns(len(latest_data))
for idx, (draw_id, data) in enumerate(latest_data.items()):
    with history_cols[idx]:
        st.markdown(f"**第 {draw_id} 期**")
        st.caption(f"🕒 {data['time']}")
        # 用漂亮的區塊顯示號碼
        st.info(", ".join([str(n).zfill(2) for n in data["numbers"]]))
