"""
污水处理智能助手模块
集成Coze智能体，实现用户与智能助手实时对话
"""

import os
import json
import base64
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

import streamlit as st
from streamlit.components.v1 import html

# 导入Coze API
from coze_api import get_coze_client, CozeAPI, MockCozeAPI


# ============== 3D数字人HTML/CSS/JS ==============

def get_digital_human_html(image_path: str = "assets/digital_human.jpg") -> str:
    """
    生成3D数字人展示HTML
    包含呼吸动画、悬浮效果、点击交互
    """
    
    # 读取图片并转换为base64
    try:
        if os.path.exists(image_path):
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()
            image_src = f"data:image/jpeg;base64,{image_data}"
        else:
            # 使用默认占位图
            image_src = "https://via.placeholder.com/300x400/4CAF50/FFFFFF?text=烷仔"
    except Exception as e:
        image_src = "https://via.placeholder.com/300x400/4CAF50/FFFFFF?text=烷仔"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            .digital-human-container {{
                width: 100%;
                height: 100%;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 20px;
                padding: 20px;
                position: relative;
                overflow: hidden;
            }}
            
            .digital-human-container::before {{
                content: '';
                position: absolute;
                top: -50%;
                left: -50%;
                width: 200%;
                height: 200%;
                background: radial-gradient(circle, rgba(255,255,255,0.1) 1px, transparent 1px);
                background-size: 20px 20px;
                animation: backgroundMove 20s linear infinite;
            }}
            
            @keyframes backgroundMove {{
                0% {{ transform: translate(0, 0); }}
                100% {{ transform: translate(50px, 50px); }}
            }}
            
            .avatar-wrapper {{
                position: relative;
                width: 280px;
                height: 350px;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            
            .avatar-container {{
                position: relative;
                width: 250px;
                height: 320px;
                border-radius: 20px;
                overflow: hidden;
                box-shadow: 
                    0 20px 60px rgba(0,0,0,0.3),
                    0 0 100px rgba(102, 126, 234, 0.5),
                    inset 0 0 60px rgba(255,255,255,0.2);
                animation: float 3s ease-in-out infinite;
                cursor: pointer;
                transition: transform 0.3s ease;
            }}
            
            .avatar-container:hover {{
                transform: scale(1.05);
            }}
            
            @keyframes float {{
                0%, 100% {{ transform: translateY(0px); }}
                50% {{ transform: translateY(-15px); }}
            }}
            
            .avatar-container::before {{
                content: '';
                position: absolute;
                top: 0;
                left: -100%;
                width: 100%;
                height: 100%;
                background: linear-gradient(
                    90deg,
                    transparent,
                    rgba(255,255,255,0.3),
                    transparent
                );
                animation: shine 3s infinite;
                z-index: 10;
            }}
            
            @keyframes shine {{
                0% {{ left: -100%; }}
                50%, 100% {{ left: 100%; }}
            }}
            
            .avatar-image {{
                width: 100%;
                height: 100%;
                object-fit: cover;
                border-radius: 20px;
            }}
            
            .glow-ring {{
                position: absolute;
                width: 300px;
                height: 300px;
                border: 3px solid rgba(255,255,255,0.3);
                border-radius: 50%;
                animation: pulse 2s ease-in-out infinite;
            }}
            
            .glow-ring:nth-child(2) {{
                width: 340px;
                height: 340px;
                animation-delay: 0.5s;
                border-color: rgba(118, 75, 162, 0.3);
            }}
            
            .glow-ring:nth-child(3) {{
                width: 380px;
                height: 380px;
                animation-delay: 1s;
                border-color: rgba(102, 126, 234, 0.3);
            }}
            
            @keyframes pulse {{
                0%, 100% {{
                    transform: scale(1);
                    opacity: 0.5;
                }}
                50% {{
                    transform: scale(1.1);
                    opacity: 0.8;
                }}
            }}
            
            .status-indicator {{
                position: absolute;
                bottom: 30px;
                right: 30px;
                width: 20px;
                height: 20px;
                background: #4CAF50;
                border-radius: 50%;
                box-shadow: 0 0 20px #4CAF50;
                animation: blink 2s infinite;
                z-index: 20;
            }}
            
            @keyframes blink {{
                0%, 100% {{ opacity: 1; }}
                50% {{ opacity: 0.5; }}
            }}
            
            .name-tag {{
                margin-top: 20px;
                padding: 10px 30px;
                background: rgba(255,255,255,0.15);
                backdrop-filter: blur(10px);
                border-radius: 30px;
                border: 1px solid rgba(255,255,255,0.3);
                color: white;
                font-size: 18px;
                font-weight: bold;
                text-shadow: 0 2px 10px rgba(0,0,0,0.3);
                z-index: 10;
            }}
            
            .role-tag {{
                margin-top: 10px;
                color: rgba(255,255,255,0.8);
                font-size: 14px;
                z-index: 10;
            }}
            
            .speaking-indicator {{
                position: absolute;
                top: 20px;
                left: 50%;
                transform: translateX(-50%);
                display: none;
                z-index: 20;
            }}
            
            .speaking-indicator.active {{
                display: flex;
                gap: 5px;
            }}
            
            .sound-wave {{
                width: 4px;
                height: 20px;
                background: white;
                border-radius: 2px;
                animation: soundWave 0.5s ease-in-out infinite;
            }}
            
            .sound-wave:nth-child(2) {{ animation-delay: 0.1s; }}
            .sound-wave:nth-child(3) {{ animation-delay: 0.2s; }}
            .sound-wave:nth-child(4) {{ animation-delay: 0.3s; }}
            .sound-wave:nth-child(5) {{ animation-delay: 0.4s; }}
            
            @keyframes soundWave {{
                0%, 100% {{ height: 10px; }}
                50% {{ height: 30px; }}
            }}
            
            .loading-spinner {{
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 60px;
                height: 60px;
                border: 4px solid rgba(255,255,255,0.3);
                border-top-color: white;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                display: none;
                z-index: 30;
            }}
            
            @keyframes spin {{
                0% {{ transform: translate(-50%, -50%) rotate(0deg); }}
                100% {{ transform: translate(-50%, -50%) rotate(360deg); }}
            }}
        </style>
    </head>
    <body>
        <div class="digital-human-container">
            <div class="speaking-indicator" id="speakingIndicator">
                <div class="sound-wave"></div>
                <div class="sound-wave"></div>
                <div class="sound-wave"></div>
                <div class="sound-wave"></div>
                <div class="sound-wave"></div>
            </div>
            
            <div class="avatar-wrapper">
                <div class="glow-ring"></div>
                <div class="glow-ring"></div>
                <div class="glow-ring"></div>
                
                <div class="avatar-container" id="avatarContainer" onclick="handleClick()">
                    <img src="{image_src}" alt="数字人" class="avatar-image" id="avatarImage">
                    <div class="status-indicator"></div>
                    <div class="loading-spinner" id="loadingSpinner"></div>
                </div>
            </div>
            
            <div class="name-tag">烷仔</div>
            <div class="role-tag">污水处理智能助手</div>
        </div>
        
        <script>
            let isSpeaking = false;
            
            function setSpeaking(speaking) {{
                isSpeaking = speaking;
                const indicator = document.getElementById('speakingIndicator');
                if (speaking) {{
                    indicator.classList.add('active');
                }} else {{
                    indicator.classList.remove('active');
                }}
            }}
            
            function setLoading(loading) {{
                const spinner = document.getElementById('loadingSpinner');
                spinner.style.display = loading ? 'block' : 'none';
            }}
            
            function handleClick() {{
                // 发送点击事件到Streamlit
                if (window.parent && window.parent.streamlit) {{
                    window.parent.streamlit.setComponentValue('avatar_clicked');
                }}
            }}
            
            // 监听来自Streamlit的消息
            window.addEventListener('message', function(e) {{
                if (e.data.type === 'speaking') {{
                    setSpeaking(e.data.value);
                }} else if (e.data.type === 'loading') {{
                    setLoading(e.data.value);
                }}
            }});
        </script>
    </body>
    </html>
    """
    return html_content


# ============== 对话历史管理 ==============

class ChatHistoryManager:
    """对话历史管理器"""
    
    HISTORY_FILE = "chat_history.json"
    MAX_HISTORY = 100  # 最大保存对话条数
    
    def __init__(self):
        self.history_file = Path(self.HISTORY_FILE)
        self.history = self.load_history()
    
    def load_history(self) -> List[Dict]:
        """加载历史对话"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载历史对话失败: {e}")
                return []
        return []
    
    def save_history(self):
        """保存对话历史"""
        try:
            # 限制历史记录数量
            if len(self.history) > self.MAX_HISTORY:
                self.history = self.history[-self.MAX_HISTORY:]
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存历史对话失败: {e}")
    
    def add_message(self, role: str, content: str):
        """添加消息到历史"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        self.history.append(message)
        self.save_history()
    
    def get_history(self, limit: int = 50) -> List[Dict]:
        """获取历史对话"""
        return self.history[-limit:]
    
    def clear_history(self):
        """清空历史对话"""
        self.history = []
        self.save_history()
    
    def export_history(self, filename: str = None) -> str:
        """导出历史对话"""
        if filename is None:
            filename = f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            return filename
        except Exception as e:
            print(f"导出历史对话失败: {e}")
            return ""


# ============== 数字人助手页面 ==============

def init_session_state():
    """初始化Session State"""
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    if 'coze_client' not in st.session_state:
        st.session_state.coze_client = None
    if 'chat_history_manager' not in st.session_state:
        st.session_state.chat_history_manager = ChatHistoryManager()
    if 'is_speaking' not in st.session_state:
        st.session_state.is_speaking = False
    if 'use_mock_api' not in st.session_state:
        st.session_state.use_mock_api = True  # 默认使用模拟模式
    
    # 尝试从配置文件加载 Coze API 凭证
    if 'coze_api_key' not in st.session_state or not st.session_state.coze_api_key:
        try:
            import json
            import os
            config_path = "coze_config.json"
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    st.session_state.coze_api_key = config.get('pat', '')
                    st.session_state.coze_bot_id = config.get('bot_id', '')
                    # 如果有配置，默认关闭模拟模式
                    if st.session_state.coze_api_key and st.session_state.coze_bot_id:
                        st.session_state.use_mock_api = False
        except Exception as e:
            print(f"加载Coze配置文件失败: {e}")


def get_coze_client_instance():
    """获取或创建Coze客户端实例"""
    if st.session_state.coze_client is None:
        api_key = st.session_state.get('coze_api_key', '')
        bot_id = st.session_state.get('coze_bot_id', '')
        use_mock = st.session_state.get('use_mock_api', True)
        
        st.session_state.coze_client = get_coze_client(
            use_mock=use_mock,
            api_key=api_key,
            bot_id=bot_id
        )
    return st.session_state.coze_client


def render_chat_interface():
    """渲染聊天界面"""
    st.subheader("💬 与烷仔对话")
    
    # 显示对话历史
    chat_container = st.container()
    
    with chat_container:
        # 加载保存的历史对话
        history_manager = st.session_state.chat_history_manager
        saved_history = history_manager.get_history()
        
        # 合并session中的消息和历史
        all_messages = saved_history + st.session_state.chat_messages
        
        for msg in all_messages:
            role = msg.get('role', '')
            content = msg.get('content', '')
            
            if role == 'user':
                with st.chat_message("user", avatar="👤"):
                    st.write(content)
            elif role == 'assistant':
                with st.chat_message("assistant", avatar="🤖"):
                    st.write(content)
    
    # 输入框
    user_input = st.chat_input("输入你的问题...")
    
    if user_input:
        # 添加用户消息
        st.session_state.chat_messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat()
        })
        
        # 保存到历史管理器
        history_manager.add_message("user", user_input)
        
        # 获取智能体回复
        with st.spinner("烷仔正在思考..."):
            client = get_coze_client_instance()
            response = client.chat(user_input)
            
            assistant_response = response.get('response', '抱歉，我暂时无法回答这个问题。')
            
            # 添加助手回复
            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": assistant_response,
                "timestamp": datetime.now().isoformat()
            })
            
            # 保存到历史管理器
            history_manager.add_message("assistant", assistant_response)
        
        # 刷新页面显示新消息
        st.rerun()


def render_settings_panel():
    """渲染设置面板"""
    with st.sidebar:
        st.header("🔧 数字人助手设置")
        
        # API模式选择
        st.subheader("API模式")
        use_mock = st.toggle("使用模拟模式（无需API密钥）", value=st.session_state.use_mock_api)
        
        if use_mock != st.session_state.use_mock_api:
            st.session_state.use_mock_api = use_mock
            st.session_state.coze_client = None  # 重置客户端
            st.rerun()
        
        if not use_mock:
            st.info("使用真实Coze API需要配置以下信息：")
            
            # API密钥输入
            api_key = st.text_input(
                "Coze API密钥 (PAT)",
                value=st.session_state.get('coze_api_key', ''),
                type="password",
                help="在Coze平台获取Personal Access Token (以pat_开头)"
            )
            
            bot_id = st.text_input(
                "Bot ID",
                value=st.session_state.get('coze_bot_id', ''),
                help="你的Coze智能体ID (19位数字)"
            )
            
            if api_key:
                st.session_state.coze_api_key = api_key
            if bot_id:
                st.session_state.coze_bot_id = bot_id
            
            # 验证按钮
            if st.button("验证API凭证"):
                if api_key and bot_id:
                    client = get_coze_client(use_mock=False, api_key=api_key, bot_id=bot_id)
                    result = client.validate_credentials()
                    
                    if result['valid']:
                        st.success(result['message'])
                        st.session_state.coze_client = client
                        st.session_state.use_mock_api = False
                    else:
                        st.error(result['message'])
                        st.info("提示: 请确认Bot已发布，且PAT有正确的权限")
                else:
                    st.warning("请输入API密钥和Bot ID")
            
            # 显示当前配置状态
            if st.session_state.get('coze_api_key') and st.session_state.get('coze_bot_id'):
                st.caption(f"当前配置: Bot ID = {st.session_state.coze_bot_id[:10]}...")
        
        st.divider()
        
        # 历史对话管理
        st.subheader("📚 历史对话")
        
        if st.button("🗑️ 清空当前对话"):
            st.session_state.chat_messages = []
            st.session_state.chat_history_manager.clear_history()
            st.success("对话已清空！")
            st.rerun()
        
        if st.button("📥 导出历史对话"):
            filename = st.session_state.chat_history_manager.export_history()
            if filename:
                st.success(f"历史对话已导出到: {filename}")
            else:
                st.error("导出失败")
        
        # 显示历史对话数量
        history_count = len(st.session_state.chat_history_manager.get_history())
        st.caption(f"已保存 {history_count} 条对话记录")


def render_quick_questions():
    """渲染快捷问题"""
    st.subheader("❓ 常见问题")
    
    questions = [
        "水厂有哪些工艺流程？",
        "甲烷排放是如何计算的？",
        "如何优化工艺降低排放？",
        "LSTM预测如何使用？",
        "有哪些减排技术？"
    ]
    
    cols = st.columns(2)
    for i, question in enumerate(questions):
        with cols[i % 2]:
            if st.button(f"💡 {question}", key=f"q_{i}", use_container_width=True):
                # 模拟用户输入
                st.session_state.chat_messages.append({
                    "role": "user",
                    "content": question,
                    "timestamp": datetime.now().isoformat()
                })
                
                # 获取回复
                client = get_coze_client_instance()
                response = client.chat(question)
                
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": response.get('response', ''),
                    "timestamp": datetime.now().isoformat()
                })
                
                st.rerun()


def render_digital_human_tab():
    """
    渲染数字人助手标签页
    这是主入口函数，在app.py中调用
    """
    init_session_state()
    
    st.header("🤖 污水处理智能助手")
    
    # 页面说明
    st.info("""
    🎉 欢迎来到智能助手！我是「烷仔」，你的污水处理智能助手。
    
    我可以帮你：
    - 解答水厂工艺流程相关问题
    - 解释甲烷排放数据和计算方法
    - 提供工艺优化建议
    - 指导系统功能使用
    
    💡 **使用方式**：在下方输入框输入问题，或点击右侧快捷问题快速开始对话！
    """)
    
    # 创建两列布局
    col1, col2 = st.columns([1, 1.2])
    
    with col1:
        # 3D数字人展示
        st.subheader("👋 我是烷仔")
        
        # 检查图片路径
        image_path = "assets/digital_human.jpg"
        if not os.path.exists(image_path):
            # 尝试其他路径
            alt_paths = [
                "assets/烷仔.jpg",
                "烷仔.jpg",
                "../烷仔.jpg"
            ]
            for path in alt_paths:
                if os.path.exists(path):
                    image_path = path
                    break
        
        # 渲染数字人HTML
        digital_human_html = get_digital_human_html(image_path)
        html(digital_human_html, height=500)
        
        # 快捷问题
        render_quick_questions()
    
    with col2:
        # 聊天界面
        render_chat_interface()
    
    # 侧边栏设置
    render_settings_panel()


# ============== 悬浮数字人组件（可选） ==============

def get_floating_digital_human_html() -> str:
    """
    获取悬浮数字人HTML（用于在其他页面显示）
    点击后跳转到数字人助手页面
    """
    html_content = """
    <style>
        .floating-avatar {
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.5);
            animation: floatAvatar 3s ease-in-out infinite;
            z-index: 9999;
            border: 3px solid white;
            transition: transform 0.3s ease;
        }
        
        .floating-avatar:hover {
            transform: scale(1.1);
        }
        
        @keyframes floatAvatar {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-10px); }
        }
        
        .floating-avatar img {
            width: 70px;
            height: 70px;
            border-radius: 50%;
            object-fit: cover;
        }
        
        .notification-badge {
            position: absolute;
            top: -5px;
            right: -5px;
            width: 20px;
            height: 20px;
            background: #ff4757;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 12px;
            font-weight: bold;
        }
        
        .tooltip {
            position: absolute;
            right: 100px;
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 8px 15px;
            border-radius: 20px;
            white-space: nowrap;
            opacity: 0;
            transition: opacity 0.3s;
            font-size: 14px;
        }
        
        .floating-avatar:hover .tooltip {
            opacity: 1;
        }
    </style>
    
    <div class="floating-avatar" onclick="openDigitalHumanPage()">
        <span class="tooltip">点击与我对话</span>
        <img src="assets/digital_human.jpg" alt="烷仔" onerror="this.src='https://via.placeholder.com/70/4CAF50/FFFFFF?text=烷'">
        <span class="notification-badge">?</span>
    </div>
    
    <script>
        function openDigitalHumanPage() {
            // 发送消息到Streamlit切换到数字人标签页
            if (window.parent && window.parent.streamlit) {
                window.parent.streamlit.setComponentValue('open_digital_human_tab');
            }
        }
    </script>
    """
    return html_content


if __name__ == "__main__":
    # 独立运行测试
    render_digital_human_tab()
