import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time

# 設定頁面
st.set_page_config(page_title="Bingo Bingo 即時對獎", page_icon="🎰", layout="wide")

st.title("🎰 Bingo Bingo 賓果賓果即時對獎系統")

# --- 獎金與玩法設定 (以基本注 $25 計算) ---
# 字典結構: {星數: {對中個數: 獎金}}
PRIZE_TABLE = {
    1: {1: 50},
    2: {2: 75},
    3: {3: 500, 2: 50},
    4: {4: 1000, 3: 100, 2: 25},
    5: {5: 7500, 4: 500, 3: 50},
    6: {6: 25000, 5: 1000, 4: 200, 3: 25}
}

# --- 爬取最新即時資料 ---
# ttl=60 確保資料最多快取 60 秒，達成每分鐘拉取最新資料的需求
@st.cache_data(ttl=60)
def fetch_latest_draws():
    # 實務上這裡需針對台彩官網或即時 API 進行解析
    # 這裡先建立一個爬蟲框架與模擬數據，以利開發測試
    try:
        # url = "https://www.taiwanlottery.com.tw/lotto/bingobingo/drawing.aspx"
        # res = requests.get(url, timeout=5)
        # soup = BeautifulSoup(res.text, 'html.parser')
        # ... 在此加入實際的解析邏輯 ...
        pass
    except Exception as e:
        st.error(f"連線異常: {e}")

    # 模擬回傳的近期開獎資料 (格式：期數 -> 開獎號碼清單)
    return {
        "113000123": [3, 8, 12, 15, 22, 27, 31, 38, 42, 45, 50, 55, 61, 65, 68, 70, 72, 75, 78, 80],
        "113000124": [1, 5, 9, 14, 18, 25, 30, 33, 40, 44, 48, 52, 58, 60, 66, 69, 73, 76, 77, 79],
        "113000125": [2, 4, 10, 15, 20, 26, 31, 35, 41, 46, 51, 56, 59, 62, 67, 71, 74, 75, 78, 80]
    }

# --- 側邊欄：使用者購買設定 ---
st.sidebar.header("📝 購買清單設定")

# 預設為目前最紅的：三星、四倍、十期
play_star = st.sidebar.selectbox("玩法 (星數)", options=list(range(1, 7)), index=2, format_func=lambda x: f"{x} 星")
multiplier = st.sidebar.number_input("倍數", min_value=1, value=4, step=1)
draw_counts = st.sidebar.number_input("連續期數", min_value=1, value=10, step=1)

st.sidebar.markdown("---")
is_bonus_active = st.sidebar.checkbox("💰 啟用目前加碼活動獎金")

st.sidebar.markdown("---")
start_draw = st.sidebar.text_input("起始對獎期數", placeholder="例如: 113000123")
selected_numbers = st.sidebar.multiselect(
    f"選擇已購買的 {play_star} 個號碼", 
    options=list(range(1, 81)),
    max_selections=play_star
)

# --- 主畫面：對獎邏輯與顯示 ---
latest_data = fetch_latest_draws()

st.subheader("即時開獎動態")
st.caption(f"最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (每分鐘自動刷新判定)")

if st.button("🔄 手動強制刷新資料"):
    fetch_latest_draws.clear()
    st.rerun()

# 顯示最新的三期作為參考
cols = st.columns(3)
for idx, (draw_id, numbers) in enumerate(list(latest_data.items())[-3:]):
    with cols[idx]:
        st.metric(label=f"第 {draw_id} 期", value="已開獎")
        st.write(", ".join([str(n).zfill(2) for n in numbers]))

st.divider()

# --- 執行對獎 ---
if len(selected_numbers) == play_star and start_draw:
    st.subheader("🎯 對獎結果")
    
    total_prize = 0
    total_cost = 25 * multiplier * draw_counts
    
    results = []
    
    # 這裡將模擬從起始期數往後推算連續十期的邏輯
    # 實務上會比對 start_draw 到 start_draw + draw_counts 的資料
    for draw_id, winning_numbers in latest_data.items():
        # 計算中了幾個號碼
        matched_numbers = set(selected_numbers).intersection(set(winning_numbers))
        match_count = len(matched_numbers)
        
        # 計算該期獎金
        base_prize = PRIZE_TABLE[play_star].get(match_count, 0)
        
        # 處理加碼邏輯 (依當前台彩實際加碼倍率調整，此處示範加碼 1.5 倍)
        if is_bonus_active and base_prize > 0:
            base_prize = int(base_prize * 1.5)
            
        final_prize = base_prize * multiplier
        total_prize += final_prize
        
        results.append({
            "期數": draw_id,
            "開出號碼": ", ".join([str(n).zfill(2) for n in winning_numbers]),
            "對中號碼": ", ".join([str(n).zfill(2) for n in matched_numbers]) if matched_numbers else "無",
            "獲得獎金": f"${final_prize:,}" if final_prize > 0 else "$0"
        })
        
    # 顯示結果表格
    df_results = pd.DataFrame(results)
    st.dataframe(df_results, use_container_width=True)
    
    # 總結算
    st.info(f"**購買成本:** ${total_cost:,} NTD")
    if total_prize > 0:
        st.success(f"**恭喜！總共贏得獎金:** ${total_prize:,} NTD")
    else:
        st.warning("**總共贏得獎金:** $0 NTD (再接再厲！)")

elif len(selected_numbers) > 0 and len(selected_numbers) != play_star:
    st.error(f"⚠️ 你選擇了 {play_star} 星玩法，請確保剛好選取 {play_star} 個號碼。")
