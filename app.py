import streamlit as st
import pandas as pd
import akasha
import dotenv
import os
import sys

# --- 1. 環境設定 ---
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

dotenv_path = os.path.join(BASE_DIR, ".env")
dotenv.load_dotenv(dotenv_path)

MODEL = os.getenv("MODEL")
data_dir = os.getenv("DATA_DIR", "data.xlsx")

# --- 2. 資料讀取 (快取優化) ---
@st.cache_data
def read_excel_sheets():
    # 讀取 Excel 資料
    dfs = pd.read_excel(data_dir, sheet_name=["E管家", "智慧插座", "安裝前中後問題"])
    return dfs

data = read_excel_sheets()

def format_data_for_ai(data_dict):
    full_text = ""
    for name, df in data_dict.items():
        full_text += f"\n--- {name} 知識庫 ---\n"
        full_text += df.to_csv(index=False) # CSV 格式通常對 AI 來說比 to_string 更省 token 且結構清晰
    return full_text

context_data = format_data_for_ai(data)

system_prompt = f"""
你是一名客服人員的助理機器人，請根據輸入的客戶提問，協助客服人員查找相關資料{context_data}，請注意以下事項：
1. 請先分析客戶提問，查找資料中有無類似或相關之資訊。
2. 若資料中有相關資訊，請整理並條列式顯示:歷史提問、歷史回答、裝置世代(如有)、類型、流程階段、關鍵字。
3. 若資料中無相關資訊，請分析客戶提問，並給予類型、流程階段(僅包含APP、安裝前、安裝中、安裝後)、關鍵字。
"""

# --- 3. Streamlit 介面設定 ---
st.set_page_config(page_title="CSAST")
st.title("CSAST")

# 初始化會話狀態 (Session State)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "history_text" not in st.session_state:
    st.session_state.history_text = ""

# 側邊欄：功能按鈕
with st.sidebar:
    if st.button("清除對話歷史"):
        st.session_state.messages = []
        st.session_state.history_text = ""
        st.rerun()

# 顯示現有的對話紀錄
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 4. 對話邏輯 ---
if prompt := st.chat_input("請問我有什麼可以協助的嗎?"):
    # 顯示使用者訊息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 呼叫 Akasha 模型
    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            ak = akasha.ask(
                model=MODEL,
                temperature=0.1,
                max_input_tokens=20000,
                max_output_tokens=20000
            )
            
            final_prompt = (
                system_prompt + 
                f"\n# 客戶提問: {prompt}" + 
                f"\n# 對話歷史: {st.session_state.history_text}"
            )
            
            response = ak(prompt=final_prompt)
            st.markdown(response)

    # 儲存回覆到紀錄中
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.history_text += f"\n客戶提問: {prompt}\n回覆: {response}"