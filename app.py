import streamlit as st
import pandas as pd
import akasha
import os
import akasha.helper as ah
import shutil


st.set_page_config(page_title="CSW")
# --- 1. 環境設定 ---
DATA_FOLDER = "/app/data"
DEFAULT_DATA_FILE = "/app/default_data/FAQ_Default.xlsx"
os.makedirs(DATA_FOLDER, exist_ok=True)
DEFAULT_FILE = os.path.join(DATA_FOLDER, "FAQ_Default.xlsx")
if not os.path.exists(DEFAULT_FILE):
    shutil.copy(DEFAULT_DATA_FILE, DEFAULT_FILE)
ACTIVE_FILE = os.path.join(DATA_FOLDER, "FAQ_Active.xlsx")

MODEL_CONFIG = {
    "OpenAI (GPT-4o)": {
        "env_var": "OPENAI_API_KEY",
        "model_name": "openai:gpt-4o"
    },
    "OpenAI (GPT-5)": {
        "env_var": "OPENAI_API_KEY",
        "model_name": "openai:gpt-5"
    },
    "Google Gemini(2.5-flash)": {
        "env_var": "GEMINI_API_KEY",
        "model_name": "gemini:gemini-2.5-flash"
    },
    "Anthropic Claude": {
        "env_var": "ANTHROPIC_API_KEY",
        "model_name": "claude:claude-3-opus-20240229"
    }
}

# 初始化 Session State
if "history_list" not in st.session_state:
    st.session_state.history_list = []
if "messages" not in st.session_state:
    st.session_state.messages = []
# 用來存放讀取好的 Data，避免重複跑 read_excel_sheets
if "current_data" not in st.session_state:
    st.session_state.current_data = None
if "file_processed" not in st.session_state:
    st.session_state.file_processed = False

# 假設圖片路徑
# USER_AVATAR = "static/user_icon.png"
# BOT_AVATAR = "https://your-domain.com/bot-logo.png"
# 用法
# with st.chat_message("user", avatar=USER_AVATAR):

# --- 2. 工具函數 ---
@st.cache_data    
def read_excel_sheets(file_path):
    if not os.path.exists(file_path):
        return None
    target_sheets = ["E管家", "智慧插座", "安裝前中後問題"]
    try:
        return pd.read_excel(file_path, sheet_name=target_sheets)
    except Exception as e:
        st.error(f"讀取 Excel 失敗: {e}")
        return None

def format_data_for_ai(data_dict):
    """將 DataFrame 字典轉為 AI 易讀的字串"""
    if not data_dict: return "目前無參考資料。"
    full_text = ""
    for name, df in data_dict.items():
        full_text += f"\n--- {name} 知識庫 ---\n"
        full_text += df.to_csv(index=False)
    return full_text

# 定義一個內部函數來把 list 轉回字串，方便計算 Token
def get_history_string(h_list):
    return "".join([f"\n提問: {item['q']}\n回覆: {item['a']}" for item in h_list])

# --- 3. 初始資料載入邏輯 ---
# 只有在 current_data 是 None 的時候才去執行讀取
if st.session_state.current_data is None:
    target = ACTIVE_FILE if os.path.exists(ACTIVE_FILE) else DEFAULT_FILE
    st.session_state.current_data = read_excel_sheets(target)

# --- 4. Streamlit 側邊欄介面設定 ---
with st.sidebar:
    # 1.下拉式選單選擇模型
    selected_model_display = st.selectbox("選擇模型來源",options=list(MODEL_CONFIG.keys()))
    # 取得對應的配置
    config = MODEL_CONFIG[selected_model_display]

    # 2.加入API_KEY輸入框
    user_api_key = st.text_input(
        "輸入您的 API KEY", 
        type="password",
        help="輸入有效API_KEY後即可進行對話"
    )
    api_valid = False
    if user_api_key:
        os.environ[config["env_var"]] = user_api_key
        # 發送一次測試請求以確認 Key 有效性
        try:
            test_ak = akasha.ask(
                model=config["model_name"],
                temperature=0.1,
            )
            test = test_ak(prompt="return hi")
            st.success("API Key 已就緒！")
            api_valid = True 
        except Exception as e:
            st.error(f"API Key 無效，請檢查後重新輸入。")
            api_valid = False
    else:
        st.warning("請先輸入 API Key")
    st.divider()

    # 3.資料上傳
    uploaded_file = st.file_uploader("上傳更新資料 (xlsx)", type=["xlsx"])

    if uploaded_file is not None and not st.session_state.get("file_processed", False):
        with open(ACTIVE_FILE, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.cache_data.clear()
        st.session_state.current_data = read_excel_sheets(ACTIVE_FILE)
        # 設定開關，防止 rerun 後重複進入此 if
        st.session_state.file_processed = True
        st.rerun()
        st.success("已成功載入並取代現有資料")
    # 顯示目前檔案資訊
    current_path = ACTIVE_FILE if os.path.exists(ACTIVE_FILE) else DEFAULT_FILE
    st.caption(f"目前生效檔案路徑：{current_path}")

    # 讀取當前生效資料

    if os.path.exists(ACTIVE_FILE):
        if st.button("🔄 還原為原始預設"):
            os.remove(ACTIVE_FILE)
            st.cache_data.clear()
            st.session_state.current_data = read_excel_sheets(DEFAULT_FILE)
            st.session_state.file_processed = False
            st.rerun()
    st.divider()
    
    if st.button("清除對話歷史"):
        st.session_state.messages = []
        st.session_state.history_list = []
        st.rerun()

# --- 5. 生成 System Prompt ---
# 確保 context_data 永遠對應到目前選用的資料 (current_data)
context_text = format_data_for_ai(st.session_state.current_data)
system_prompt = f"""
你是一名專屬助理，請注意以下事項：
1. 請先分析提問，是需要一般的問題還是想要從歷史紀錄找出相關資料，如果是一般的問題正常回答即可，如果是想從歷史紀錄找出相關資料，則查找資料{context_text}中有無類似或相關之資訊。
2. 若資料中有相關資訊，請整理並條列式顯示:歷史提問、歷史回答、裝置世代(如有)、類型、流程階段、關鍵字。如有多個相關資訊，請全部條列出來並區隔開來。
3. 若資料中無相關資訊，請分析客戶提問，並給予類型、流程階段(僅包含APP、安裝前、安裝中、安裝後)、關鍵字。
"""

# --- 6. 主介面顯示 ---
st.title("Customer Service Wingman")

# 顯示現有的對話紀錄
for message in st.session_state.messages:
    avatar_icon = "🦥" if message["role"] == "user" else "🐑"
    with st.chat_message(message["role"], avatar=avatar_icon):
        st.markdown(message["content"])

# --- 7. 對話邏輯 ---
if prompt := st.chat_input("請問我有什麼可以協助的嗎?"):

    # 檢查驗證
    if not api_valid:
        st.error("驗證失敗：請檢查後在左側選單重新輸入 API Key")
        st.stop()
    if not st.session_state.current_data:
        st.error("缺少資料庫資料")
        st.stop()

    # 顯示使用者訊息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🦥"):
        st.markdown(prompt)

    # 呼叫 Akasha 回覆
    with st.chat_message("assistant", avatar="🐑"):
        with st.spinner("思考中..."):
            try:
                ak = akasha.ask(
                    model=config["model_name"],
                    temperature=0.1,
                    max_input_tokens=20000,
                    max_output_tokens=20000
                )
                history_text = get_history_string(st.session_state.history_list)
                final_prompt = (
                    system_prompt + 
                    f"\n# 提問: {prompt}" + 
                    f"\n# 對話歷史: {history_text}"
                )
                response = ak(prompt=final_prompt)
                st.markdown(response)

                # --- Token 管理與修剪 --- 
                st.session_state.history_list.append({"q": prompt, "a": response})
                
                # 更新並計算 Token
                current_h_text = get_history_string(st.session_state.history_list)
                total_content = system_prompt + prompt + current_h_text
                
                # 迴圈修剪
                while ah.myTokenizer.compute_tokens(total_content, config["model_name"]) > 8000 and len(st.session_state.history_list) > 1:
                    st.session_state.history_list.pop(0)
                    current_h_text = get_history_string(st.session_state.history_list)
                    total_content = system_prompt + prompt + current_h_text

                # 存回 messages 用於顯示
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as e:
                st.error(f"模型呼叫失敗: {str(e)}")