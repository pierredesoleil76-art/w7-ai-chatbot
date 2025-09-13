import streamlit as st  # Python模块系统、包管理器、依赖管理、命名空间、Web框架抽象
from openai import OpenAI  # API客户端库、REST/HTTP协议、SDK设计模式、类导入机制

st.set_page_config(page_title="第四大脑 聊天机器人", page_icon="💬")  # Web页面元数据、HTML head标签、UTF-8编码、Emoji Unicode支持、单页应用配置
st.title("第四大脑 聊天机器人")  # 响应式UI组件、HTML渲染、Markdown支持、组件状态管理、虚拟DOM

client = OpenAI(  # 面向对象编程、类实例化、依赖注入、客户端-服务器架构
    api_key=st.secrets["DEEPSEEK_API_KEY"],  # 环境变量、密钥管理、安全最佳实践、配置外部化、字典数据结构
    base_url="https://api.deepseek.com",  # RESTful API、HTTPS协议、URL结构、API网关、服务端点
)

if "messages" not in st.session_state:  # 条件语句、成员运算符、会话状态、浏览器存储、有状态Web应用
    st.session_state.messages = []  # 动态属性赋值、Python列表、可变数据结构、内存管理、状态初始化

for message in st.session_state.messages:  # 迭代器协议、for循环、序列遍历、状态持久化、数据流
    with st.chat_message(message["role"]):  # 上下文管理器、with语句、UI容器组件、角色基础访问控制、字典索引
        st.markdown(message["content"])  # Markdown语法、文本渲染、XSS防护、内容安全策略、动态内容生成

if prompt := st.chat_input("你的回答"):  # 海象运算符(:=)、赋值表达式、真值测试、事件驱动编程、用户输入处理
    st.session_state.messages.append({"role": "user", "content": prompt})  # 列表方法、字典字面量、数据模型设计、消息队列模式
    with st.chat_message("user"):  # UI组件复用、用户身份标识、视觉层次结构
        st.markdown(prompt)  # 实时UI更新、数据绑定、单向数据流

    with st.chat_message("assistant"):  # AI角色抽象、对话界面设计、用户体验原则
        stream = client.chat.completions.create(  # 异步流式响应、生成器、API调用、网络请求
            model="deepseek-chat",  # 模型选择、AI模型版本控制、模型即服务(MaaS)
            messages=st.session_state.messages,  # 上下文传递、对话历史、短期记忆、prompt工程
            stream=True,  # 流式传输、服务器推送事件(SSE)、实时通信、带宽优化
        )
        response_text = st.write_stream(stream)  # 流处理、异步渲染、迭代器消费、缓冲区管理、UI响应性

    st.session_state.messages.append({"role": "assistant", "content": response_text})  # 状态更新、数据一致性、事务性操作、响应持久化、对话管理