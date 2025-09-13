import streamlit as st
from openai import OpenAI

# 基本页面
st.set_page_config(page_title="第四大脑 聊天机器人", page_icon="💬")
st.title("第四大脑 聊天机器人")

# 初始化 DeepSeek 客户端（OpenAI SDK 兼容）
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)

# 初始化聊天历史
if "messages" not in st.session_state:
    st.session_state.messages = []

# 展示完整历史
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 获取用户输入并流式生成回复
if prompt := st.chat_input("你的回答"):
    # 1) 追加并回显用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2) 生成并流式输出助手消息
    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model="deepseek-chat",  # 直接使用常量
            messages=st.session_state.messages,  # 直接传递，无需重构
            stream=True,  # 启用流式输出
        )
        response_text = st.write_stream(stream)  # 直接把 OpenAI Stream 写到界面

    # 3) 把最终文本加入聊天历史
    st.session_state.messages.append({"role": "assistant", "content": response_text})