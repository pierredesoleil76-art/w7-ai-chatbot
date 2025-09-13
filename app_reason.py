# app.py
import os
import streamlit as st
from openai import OpenAI

# -----------------------------
# 基本页面配置
# -----------------------------
st.set_page_config(page_title="第四大脑 聊天机器人 (DeepSeek)", page_icon="💬")
st.title("第四大脑 聊天机器人 · DeepSeek + Streamlit")

# -----------------------------
# 初始化 DeepSeek 客户端（OpenAI SDK 兼容）
# -----------------------------
api_key = st.secrets.get("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    st.error("未检测到 DEEPSEEK_API_KEY。请在 .streamlit/secrets.toml 中设置或配置环境变量。")
    st.stop()

base_url = st.secrets.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
client = OpenAI(api_key=api_key, base_url=base_url)

# -----------------------------
# 侧边栏设置
# -----------------------------
with st.sidebar:
    st.header("⚙️ 设置")
    model = st.selectbox(
        "选择模型",
        ["deepseek-chat", "deepseek-reasoner"],
        index=0,
        help="deepseek-chat：V3.1 非思维模式；deepseek-reasoner：V3.1 思维模式（会返回 reasoning_content）。"
    )
    show_cot = st.checkbox("显示推理过程（仅 deepseek-reasoner）", value=False,
                           help="推理过程来自 reasoning_content。发送给下一轮请求时请勿包含。")
    system_default = "你是一个乐于助人的中文助手。"
    system_prompt = st.text_area(
        "系统提示词（system）",
        value=st.session_state.get("system_prompt", system_default),
        height=80
    )

    if st.button("🧹 清空对话"):
        st.session_state.clear()
        st.rerun()

# -----------------------------
# 初始化会话状态
# -----------------------------
if "messages" not in st.session_state:
    # 将 system 消息直接存入聊天历史（展示时会过滤掉）
    st.session_state.messages = [{"role": "system", "content": system_prompt}]

# 同步最新的 system prompt
if st.session_state.messages and st.session_state.messages[0]["role"] == "system":
    if st.session_state.messages[0]["content"] != system_prompt:
        st.session_state.messages[0]["content"] = system_prompt
        st.session_state["system_prompt"] = system_prompt

# -----------------------------
# 展示完整聊天历史（不展示 system）
# -----------------------------
for message in st.session_state.messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# -----------------------------
# 处理用户输入
# -----------------------------
if prompt := st.chat_input("你的回答"):
    # 1) 追加用户消息到历史
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 2) 立刻回显用户消息（便于在网络抖动时也有交互反馈）
    with st.chat_message("user"):
        st.markdown(prompt)

    # 3) 生成助手回复（流式）
    with st.chat_message("assistant"):
        # deepseek-reasoner 可选显示思维链
        cot_box = None
        if model == "deepseek-reasoner" and show_cot:
            with st.expander("🧠 模型推理过程（reasoning_content）", expanded=False):
                cot_box = st.empty()

        def stream_generator():
            """将 DeepSeek 的流式响应转为逐段文本产出，交给 st.write_stream 渲染。
               注意：仅 yield 最终答案的 content，reasoning_content 只在 UI 中可选显示，不进入下一轮上下文。"""
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": m["role"], "content": m["content"]}
                              for m in st.session_state.messages],
                    stream=True,
                )

                collected_cot = []  # 累积 reasoning_content，避免闪烁
                for chunk in response:
                    delta = getattr(chunk.choices[0], "delta", None)
                    if not delta:
                        continue

                    # 1) 如为 deepseek-reasoner，会额外带 reasoning_content（思维链）
                    rc = getattr(delta, "reasoning_content", None)
                    if rc:
                        collected_cot.append(rc)
                        if cot_box is not None:
                            # 直接把 CoT 渲染到可折叠区；不写入对话历史
                            cot_box.markdown("".join(collected_cot))

                    # 2) 最终答案内容
                    c = getattr(delta, "content", None)
                    if c:
                        # 由 st.write_stream 以打字机效果写入
                        yield c

            except Exception as e:
                st.error(f"API 调用失败：{e}")

        # st.write_stream 会返回拼接后的完整字符串，便于我们保存到历史
        assistant_text = st.write_stream(stream_generator())

    # 4) 把助手的最终答案加入历史（注意：不要把 reasoning_content 存进去）
    st.session_state.messages.append({"role": "assistant", "content": assistant_text})
