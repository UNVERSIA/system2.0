"""
Coze 扣子平台智能体API接入模块
用于与Coze智能体进行对话交互

使用说明：
1. 在Coze平台创建智能体并发布
2. 获取API密钥和Bot ID
3. 在环境变量或配置中设置COZE_API_KEY和COZE_BOT_ID
"""

import json
import time
import requests
from typing import Dict, List, Optional, Generator
from datetime import datetime


class CozeAPI:
    """Coze智能体API客户端"""
    
    # Coze API基础URL
    BASE_URL = "https://api.coze.cn"
    
    def __init__(self, api_key: Optional[str] = None, bot_id: Optional[str] = None):
        """
        初始化Coze API客户端
        
        Args:
            api_key: Coze API密钥，如未提供则尝试从环境变量获取
            bot_id: Coze Bot ID，如未提供则尝试从环境变量获取
        """
        import os
        
        self.api_key = api_key or os.getenv("COZE_API_KEY", "")
        self.bot_id = bot_id or os.getenv("COZE_BOT_ID", "")
        
        if not self.api_key:
            print("⚠️ 警告: 未设置COZE_API_KEY，请设置环境变量或在初始化时传入")
        if not self.bot_id:
            print("⚠️ 警告: 未设置COZE_BOT_ID，请设置环境变量或在初始化时传入")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 对话历史
        self.conversation_history: List[Dict] = []
        
    def set_credentials(self, api_key: str, bot_id: str):
        """设置API凭证"""
        self.api_key = api_key
        self.bot_id = bot_id
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def chat(self, message: str, stream: bool = False, 
             conversation_id: Optional[str] = None) -> Dict:
        """
        发送消息到Coze智能体
        
        Args:
            message: 用户消息
            stream: 是否使用流式响应
            conversation_id: 对话ID（用于保持上下文）
            
        Returns:
            包含回复内容的字典
        """
        if not self.api_key or not self.bot_id:
            return {
                "success": False,
                "error": "API密钥或Bot ID未设置",
                "response": "请先配置Coze API密钥和Bot ID"
            }
        
        url = f"{self.BASE_URL}/v3/chat"
        
        payload = {
            "bot_id": self.bot_id,
            "user_id": "user_001",  # 可以改为实际用户ID
            "additional_messages": [
                {
                    "role": "user",
                    "content": message,
                    "content_type": "text"
                }
            ],
            "stream": stream
        }
        
        if conversation_id:
            payload["conversation_id"] = conversation_id
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("code") == 0:
                    # 保存到历史记录
                    self.conversation_history.append({
                        "role": "user",
                        "content": message,
                        "time": datetime.now().isoformat()
                    })
                    
                    # 提取智能体回复
                    messages = data.get("data", {}).get("messages", [])
                    assistant_response = ""
                    
                    for msg in messages:
                        if msg.get("role") == "assistant" and msg.get("type") == "answer":
                            assistant_response = msg.get("content", "")
                            break
                    
                    self.conversation_history.append({
                        "role": "assistant", 
                        "content": assistant_response,
                        "time": datetime.now().isoformat()
                    })
                    
                    return {
                        "success": True,
                        "response": assistant_response,
                        "conversation_id": data.get("data", {}).get("conversation_id"),
                        "message_id": data.get("data", {}).get("id")
                    }
                else:
                    return {
                        "success": False,
                        "error": data.get("msg", "未知错误"),
                        "response": f"API调用失败: {data.get('msg', '未知错误')}"
                    }
            else:
                return {
                    "success": False,
                    "error": f"HTTP错误: {response.status_code}",
                    "response": f"请求失败，状态码: {response.status_code}"
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "请求超时",
                "response": "请求超时，请稍后重试"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response": f"发生错误: {str(e)}"
            }
    
    def chat_stream(self, message: str, conversation_id: Optional[str] = None) -> Generator[str, None, None]:
        """
        流式对话（用于实时显示回复）
        
        Args:
            message: 用户消息
            conversation_id: 对话ID
            
        Yields:
            回复内容的片段
        """
        if not self.api_key or not self.bot_id:
            yield "请先配置Coze API密钥和Bot ID"
            return
        
        url = f"{self.BASE_URL}/v3/chat"
        
        payload = {
            "bot_id": self.bot_id,
            "user_id": "user_001",
            "additional_messages": [
                {
                    "role": "user",
                    "content": message,
                    "content_type": "text"
                }
            ],
            "stream": True
        }
        
        if conversation_id:
            payload["conversation_id"] = conversation_id
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, 
                                    stream=True, timeout=60)
            
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line.decode('utf-8').replace('data: ', ''))
                            if data.get("event") == "conversation.message.completed":
                                content = data.get("data", {}).get("content", "")
                                if content:
                                    yield content
                        except:
                            pass
            else:
                yield f"请求失败，状态码: {response.status_code}"
                
        except Exception as e:
            yield f"发生错误: {str(e)}"
    
    def get_conversation_history(self) -> List[Dict]:
        """获取对话历史"""
        return self.conversation_history
    
    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = []
    
    def validate_credentials(self) -> Dict:
        """验证API凭证是否有效"""
        if not self.api_key or not self.bot_id:
            return {
                "valid": False,
                "message": "API密钥或Bot ID未设置"
            }
        
        # 发送测试消息
        test_response = self.chat("你好", stream=False)
        
        if test_response.get("success"):
            return {
                "valid": True,
                "message": "API凭证验证成功"
            }
        else:
            return {
                "valid": False,
                "message": f"API凭证验证失败: {test_response.get('error')}"
            }


class MockCozeAPI:
    """模拟Coze API（用于测试和演示）"""
    
    def __init__(self, api_key: Optional[str] = None, bot_id: Optional[str] = None):
        self.api_key = api_key or "mock_key"
        self.bot_id = bot_id or "mock_bot"
        self.conversation_history = []
        
        # 预设的回答模板
        self.responses = {
            "你好": "你好！我是污水处理厂的智能助手「烷仔」，很高兴为你服务！😊",
            "你好啊": "你好！我是「烷仔」，有什么可以帮助你的吗？",
            "hi": "Hi there! 我是「烷仔」，你的污水处理智能助手！",
            "hello": "Hello! 我是「烷仔」，随时为你解答水厂相关问题！",
            
            "甲烷": """关于污水处理甲烷排放，主要包括以下几个方面：

1. **直接排放**：污水处理过程中的厌氧分解会产生甲烷(CH4)
2. **间接排放**：电力消耗产生的间接碳排放
3. **主要来源**：厌氧池、污泥处理车间是主要的甲烷产生单元
4. **计算方法**：使用IPCC方法学和排放因子进行核算

你想了解哪个方面的详细信息？""",

            "监测": """本系统的甲烷监测功能包括：

1. **实时监测**：各工艺单元的甲烷排放数据
2. **趋势分析**：历史数据对比和趋势预测
3. **异常预警**：排放异常自动识别和提醒
4. **热力图**：全厂甲烷排放分布可视化

你可以在"甲烷足迹追踪"标签页查看详细数据。""",

            "预测": """**甲烷排放预测功能说明**：

1. **LSTM深度学习模型**：基于历史数据训练的专业预测模型
2. **预测周期**：支持未来12个月的排放趋势预测
3. **置信区间**：提供预测上下限，评估预测可靠性
4. **优化建议**：根据预测结果给出运行指导

请前往"甲烷排放预测"标签页进行预测。""",

            "优化": """工艺优化建议：

1. **曝气优化**：调整曝气量可减少15-25%能耗
2. **药剂优化**：精准控制PAC/PAM投加量
3. **污泥回流**：优化回流比提高处理效率
4. **设备升级**：高效曝气系统、变频控制等

在"优化与决策"标签页可以进行优化模拟。""",

            "工艺": """本厂污水处理工艺包括：

**预处理区**：粗格栅→提升泵房→细格栅→曝气沉砂池→膜格栅
**生物处理区**：厌氧池→缺氧池→好氧池→MBR膜池
**深度处理区**：DF系统→催化氧化
**污泥处理**：污泥处理车间

点击工艺流程图可以查看各单元详细参数。""",

            "水厂": """欢迎使用「寻清问碳」污水处理甲烷监测调控与智慧科普系统！

本系统功能：
🌍 3D水厂数字孪生可视化
📊 实时甲烷监测与追踪
🔮 LSTM智能预测
⚡ 工艺优化建议
📈 减排技术对比

我是你的智能助手「烷仔」，随时为你提供帮助！""",

            "帮助": """**我可以帮你解答以下问题**：

1. 水厂工艺流程和设备说明
2. 甲烷排放数据解读
3. LSTM预测模型使用方法
4. 工艺优化建议
5. 减排技术选择
6. 运行参数调整指导

请直接输入你的问题，我会尽力为你解答！""",

            "谢谢": "不客气！有其他问题随时找我，「烷仔」随时为你服务！😊",
            "再见": "再见！记得关注甲烷排放数据，祝你工作顺利！👋"
        }
    
    def chat(self, message: str, stream: bool = False, 
             conversation_id: Optional[str] = None) -> Dict:
        """模拟对话功能"""
        
        # 保存用户消息
        self.conversation_history.append({
            "role": "user",
            "content": message,
            "time": datetime.now().isoformat()
        })
        
        # 查找匹配的回答
        response_text = self._generate_response(message)
        
        # 模拟延迟
        time.sleep(0.5)
        
        # 保存助手回复
        self.conversation_history.append({
            "role": "assistant",
            "content": response_text,
            "time": datetime.now().isoformat()
        })
        
        return {
            "success": True,
            "response": response_text,
            "conversation_id": conversation_id or "mock_conv_001",
            "message_id": f"mock_msg_{int(time.time())}"
        }
    
    def _generate_response(self, message: str) -> str:
        """生成回答"""
        message_lower = message.lower()
        
        # 关键词匹配
        for keyword, response in self.responses.items():
            if keyword in message or keyword in message_lower:
                return response
        
        # 智能匹配关键词
        if any(word in message for word in ["排放", "碳", "CO2", "温室"]):
            return self.responses.get("甲烷", "关于甲烷排放问题，建议查看'甲烷足迹追踪'标签页的详细数据。")
        
        if any(word in message for word in ["数据", "监测", "实时", "当前"]):
            return self.responses.get("监测", "系统提供实时甲烷监测功能，各工艺单元数据可在对应页面查看。")
        
        if any(word in message for word in ["未来", "趋势", "明年", "预测"]):
            return self.responses.get("预测", "使用LSTM模型可以进行未来12个月的甲烷排放预测。")
        
        if any(word in message for word in ["建议", "改进", "降低", "减少"]):
            return self.responses.get("优化", "系统提供多种工艺优化方案，可在'优化与决策'页面查看。")
        
        if any(word in message for word in ["设备", "单元", "池", "泵"]):
            return self.responses.get("工艺", "水厂包含多个工艺单元，可点击工艺流程图查看详情。")
        
        # 默认回复
        return f"""感谢你的提问！我是「烷仔」，你的污水处理智能助手。

关于"{message}"，建议你：
1. 查看相关的功能标签页获取详细信息
2. 使用侧边栏的数据上传功能查看实际数据
3. 如有具体问题，我可以帮你联系技术人员

你也可以问：
- 甲烷排放是如何计算的？
- 如何优化工艺降低排放？
- LSTM预测如何使用？"""
    
    def get_conversation_history(self) -> List[Dict]:
        """获取对话历史"""
        return self.conversation_history
    
    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = []
    
    def validate_credentials(self) -> Dict:
        """验证模拟凭证"""
        return {
            "valid": True,
            "message": "模拟模式已启用，无需真实API密钥"
        }


def get_coze_client(use_mock: bool = False, api_key: Optional[str] = None, 
                    bot_id: Optional[str] = None) -> CozeAPI:
    """
    获取Coze客户端实例
    
    Args:
        use_mock: 是否使用模拟模式（用于测试）
        api_key: API密钥
        bot_id: Bot ID
        
    Returns:
        CozeAPI或MockCozeAPI实例
    """
    if use_mock:
        return MockCozeAPI(api_key, bot_id)
    return CozeAPI(api_key, bot_id)


# 测试代码
if __name__ == "__main__":
    # 测试模拟模式
    print("=" * 50)
    print("测试模拟Coze API")
    print("=" * 50)
    
    client = get_coze_client(use_mock=True)
    
    test_messages = ["你好", "甲烷排放怎么计算？", "谢谢"]
    
    for msg in test_messages:
        print(f"\n用户: {msg}")
        response = client.chat(msg)
        print(f"烷仔: {response['response']}")
    
    print("\n" + "=" * 50)
    print("对话历史:")
    for entry in client.get_conversation_history():
        print(f"{entry['role']}: {entry['content'][:50]}...")
