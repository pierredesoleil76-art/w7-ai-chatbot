import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="第四大脑 聊天机器人", page_icon="💬")
st.title("第四大脑 聊天机器人")

client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("你的回答"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model="deepseek-chat",
            messages=st.session_state.messages,
            stream=True,
        )
        response_text = st.write_stream(stream)

    st.session_state.messages.append({"role": "assistant", "content": response_text})