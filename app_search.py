import os
import json
import time
import requests
import streamlit as st
from openai import OpenAI

# -----------------------------
# 页面 & 标题
# -----------------------------
st.set_page_config(page_title="第四大脑 聊天机器人 (DeepSeek, 可选联网)", page_icon="💬")
st.title("第四大脑 聊天机器人 · DeepSeek + Streamlit")

# -----------------------------
# 初始化 DeepSeek 客户端
# -----------------------------
API_KEY = st.secrets.get("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
BASE_URL = st.secrets.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

if not API_KEY:
    st.error("未检测到 DEEPSEEK_API_KEY。请在 .streamlit/secrets.toml 配置。")
    st.stop()

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# -----------------------------
# 侧边栏：设置
# -----------------------------
with st.sidebar:
    st.header("⚙️ 设置")

    model = st.selectbox(
        "选择模型",
        options=["deepseek-chat", "deepseek-reasoner"],
        index=0,
        help="deepseek-chat：V3.1 非思维模式；deepseek-reasoner：V3.1 思维模式。"
    )

    # 新增：是否启用联网（Web 搜索）
    web_enabled = st.checkbox(
        "🔎 启用联网（Web 搜索）",
        value=False,
        help="开启后，模型可自动调用内置的 web_search 工具检索互联网信息，仅在 deepseek-chat 下生效。"
    )

    # 推理过程显示（仅 reasoner）
    show_cot = st.checkbox("显示推理过程（仅 deepseek-reasoner）", value=False)

    # 可编辑的 system 提示
    system_default = "你是一个乐于助人的中文助手。回答尽量给出要点、小结与必要引用。"
    system_prompt = st.text_area("系统提示词（system）", value=st.session_state.get("system_prompt", system_default), height=80)

    if st.button("🧹 清空对话"):
        st.session_state.clear()
        st.rerun()

# -----------------------------
# 会话状态：system & 历史消息
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": system_prompt}]
if st.session_state.messages and st.session_state.messages[0]["role"] == "system":
    if st.session_state.messages[0]["content"] != system_prompt:
        st.session_state.messages[0]["content"] = system_prompt
        st.session_state["system_prompt"] = system_prompt

# -----------------------------
# 联网提供商自动识别（按优先级）
# -----------------------------
def detect_provider():
    if st.secrets.get("TAVILY_API_KEY"):
        return "tavily"
    if st.secrets.get("BRAVE_API_KEY"):
        return "brave"
    if st.secrets.get("SERPAPI_API_KEY"):
        return "serpapi"
    return None

provider = detect_provider()

with st.sidebar:
    if web_enabled and model == "deepseek-reasoner":
        st.warning("deepseek-reasoner 当前不支持 Function Calling，联网将自动禁用（改用纯模型）。", icon="⚠️")
    if web_enabled and provider is None and model == "deepseek-chat":
        st.info("未配置联网提供商（Tavily/Brave/SerpAPI）。将退回纯模型回答。", icon="ℹ️")

# -----------------------------
# 渲染历史（不显示 system/tool）
# -----------------------------
for m in st.session_state.messages:
    if m["role"] in ("user", "assistant"):
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

# -----------------------------
# 统一的：联网搜索函数（工具的真实实现）
# -----------------------------
def run_web_search(query: str, max_results: int = 5):
    """调用 Tavily / Brave / SerpAPI 执行联网检索，返回标准化结果列表"""
    results = []
    try:
        if provider == "tavily":
            # Tavily: POST /search + Bearer 认证
            # 文档: https://docs.tavily.com/... （POST /search，返回 results[ {title,url,content,...} ]）
            # 仅取必要字段，避免 token 占用
            url = "https://api.tavily.com/search"
            headers = {"Authorization": f"Bearer {st.secrets['TAVILY_API_KEY']}"}
            payload = {"query": query, "search_depth": "basic", "max_results": max_results, "include_answer": False}
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            data = resp.json()
            for r in data.get("results", [])[:max_results]:
                results.append({
                    "title": r.get("title"),
                    "url": r.get("url"),
                    "snippet": r.get("content")
                })

        elif provider == "brave":
            # Brave: GET /res/v1/web/search + X-Subscription-Token
            # 文档: 端点与头信息、响应对象结构
            # Search 结果位于 data["web"]["results"], 字段含 title/url/description 等
            url = "https://api.search.brave.com/res/v1/web/search"
            headers = {"Accept": "application/json", "X-Subscription-Token": st.secrets["BRAVE_API_KEY"]}
            params = {"q": query, "count": max_results}
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            data = resp.json()
            for r in (data.get("web", {}) or {}).get("results", [])[:max_results]:
                results.append({
                    "title": r.get("title"),
                    "url": r.get("url"),
                    "snippet": r.get("description")
                })

        elif provider == "serpapi":
            # SerpAPI: GET /search.json?engine=google&api_key=...
            # 文档: organic_results 列表，含 title/link/snippet
            url = "https://serpapi.com/search.json"
            params = {"engine": "google", "q": query, "num": max_results, "api_key": st.secrets["SERPAPI_API_KEY"]}
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            for r in data.get("organic_results", [])[:max_results]:
                results.append({
                    "title": r.get("title"),
                    "url": r.get("link"),
                    "snippet": r.get("snippet")
                })
        else:
            # 未配置任何提供商
            return []

    except Exception as e:
        # 把错误也返回给模型，便于它调整策略
        return [{"title": "搜索错误", "url": "", "snippet": f"provider={provider}, error={e}"}]

    return results

# -----------------------------
# 主流程：接收输入 →（可选）联网 → 流式输出
# -----------------------------
if prompt := st.chat_input("你的回答"):
    # 1) 追加用户消息并立即显示
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2) 生成助手回复
    with st.chat_message("assistant"):
        # 如果选择 reasoner，提供可选推理过程展开区
        cot_box = None
        if model == "deepseek-reasoner" and show_cot:
            with st.expander("🧠 模型推理过程（reasoning_content）", expanded=False):
                cot_box = st.empty()

        # ---- 情况 A：支持联网（deepseek-chat & 已配置提供商）----
        can_use_tools = (web_enabled and model == "deepseek-chat" and provider is not None)

        # 将现有历史（仅 role/content）送入模型
        base_messages = [{"role": m["role"], "content": m["content"]}
                         for m in st.session_state.messages if m.get("role") in ("system", "user", "assistant")]

        if can_use_tools:
            # 先不流式，探测 tools 调用
            tools = [{
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "在互联网上检索与问题最相关的结果；返回含 title/url/snippet 的结果数组。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "检索查询（可包含关键实体、时间约束等）"},
                            "max_results": {"type": "integer", "minimum": 1, "maximum": 8, "default": 5}
                        },
                        "required": ["query"]
                    }
                }
            }]

            try:
                probe = client.chat.completions.create(
                    model=model,
                    messages=base_messages,
                    tools=tools,
                    tool_choice="auto",
                    stream=False,
                )
                message = probe.choices[0].message

                # 如果模型请求调用工具，则按调用逐个执行
                if getattr(message, "tool_calls", None):
                    # 把 assistant(带 tool_calls) 先放入会话
                    assistant_with_tools = {
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [tc.model_dump(exclude_none=True) for tc in message.tool_calls]
                    }
                    base_messages.append(assistant_with_tools)

                    # 执行每个工具调用，并以 role="tool" 回传
                    for tc in message.tool_calls:
                        if tc.type == "function" and tc.function.name == "web_search":
                            args = {}
                            try:
                                args = json.loads(tc.function.arguments or "{}")
                            except Exception:
                                pass
                            query = args.get("query") or prompt
                            max_results = int(args.get("max_results", 5))
                            search_results = run_web_search(query, max_results=max_results)

                            tool_content = json.dumps({
                                "provider": provider,
                                "queried_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "results": search_results
                            }, ensure_ascii=False)

                            base_messages.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": tool_content
                            })

                    # 工具执行完，进行最终回答（这次用流式输出）
                    def final_stream():
                        try:
                            resp = client.chat.completions.create(
                                model=model,
                                messages=base_messages,
                                stream=True,
                            )
                            for chunk in resp:
                                delta = getattr(chunk.choices[0], "delta", None)
                                if not delta:
                                    continue
                                c = getattr(delta, "content", None)
                                if c:
                                    yield c
                        except Exception as e:
                            st.error(f"API 调用失败：{e}")

                    assistant_text = st.write_stream(final_stream())
                    st.session_state.messages.append({"role": "assistant", "content": assistant_text})
                    st.stop()
                # 若没有工具调用，退回普通流式
            except Exception as e:
                st.info(f"联网探测失败，将退回纯模型：{e}")

        # ---- 情况 B：普通流式（reasoner 或未配置提供商等）----
        def stream_generator():
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=base_messages,
                    stream=True,
                )
                # reasoner 的思维链（reasoning_content）仅展示，不入历史
                collected_cot = []
                for chunk in resp:
                    delta = getattr(chunk.choices[0], "delta", None)
                    if not delta:
                        continue
                    rc = getattr(delta, "reasoning_content", None)
                    if rc and cot_box is not None:
                        collected_cot.append(rc)
                        cot_box.markdown("".join(collected_cot))
                    c = getattr(delta, "content", None)
                    if c:
                        yield c
            except Exception as e:
                st.error(f"API 调用失败：{e}")

        assistant_text = st.write_stream(stream_generator())
        st.session_state.messages.append({"role": "assistant", "content": assistant_text})
