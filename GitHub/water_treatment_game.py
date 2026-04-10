# -*- coding: utf-8 -*-
"""
污水处理流程闯关小游戏模块 - 1:1复刻版
水厂拼图大挑战 - 完全保留原始界面设计和功能
"""
import streamlit as st
import base64
import json
from pathlib import Path

# ============== 游戏数据配置（1:1复刻原始5关）=============

GAME_LEVELS = [
    {
        "id": 1,
        "name": "第1关：预处理",
        "correct": [
            {"name": "粗格栅", "label": "粗格栅（拦大垃圾）", "img": "coarse_screen.jpg"},
            {"name": "进水泵房", "label": "进水泵房（提升水位）", "img": "pump_station.jpg"},
            {"name": "细格栅", "label": "细格栅（拦小垃圾）", "img": "fine_screen.jpg"},
            {"name": "曝气沉砂池", "label": "曝气沉砂池（去除砂石）", "img": "grit_chamber.jpg"},
            {"name": "初沉池", "label": "初沉池（沉淀杂质）", "img": "primary_clarifier.jpg"}
        ],
        "tips": {
            "粗格栅": ["这里需要先拦截体积较大的垃圾", "通常是最前端的处理设施", "正确答案：粗格栅"],
            "进水泵房": ["这里需要把水提升到后续处理高度", "这是一个输送水的动力设备", "正确答案：进水泵房"],
            "细格栅": ["这里要进一步去除较小颗粒", "它比前面的拦截更精细", "正确答案：细格栅"],
            "曝气沉砂池": ["这里主要去除水中的砂粒", "通过曝气让砂沉降下来", "正确答案：曝气沉砂池"],
            "初沉池": ["这里用于沉淀悬浮物", "一般在预处理的最后阶段", "正确答案：初沉池"]
        }
    },
    {
        "id": 2,
        "name": "第2关：生物处理",
        "correct": [
            {"name": "初沉池", "label": "初沉池（预处理完成）", "img": "primary_clarifier.jpg"},
            {"name": "膜格栅间", "label": "膜格栅间（保护设备）", "img": "membrane_screen.jpg"},
            {"name": "厌氧池", "label": "厌氧池（无氧反应）", "img": "anaerobic_tank.jpg"},
            {"name": "缺氧池", "label": "缺氧池（反硝化）", "img": "anoxic_tank.jpg"},
            {"name": "好氧池", "label": "好氧池（降解污染物）", "img": "aeration_tank.jpg"},
            {"name": "二沉池", "label": "二沉池（泥水分离）", "img": "secondary_clarifier.jpg"}
        ],
        "tips": {
            "厌氧池": ["这里需要在无氧环境下进行反应", "生物处理通常从这里开始", "正确答案：厌氧池"],
            "缺氧池": ["这里需要较低氧气环境", "用于反硝化去除氮", "正确答案：缺氧池"],
            "好氧池": ["这里需要充足氧气", "微生物在这里分解污染物", "正确答案：好氧池"],
            "二沉池": ["这里用于泥水分离", "通常是生物处理的最后一步", "正确答案：二沉池"]
        }
    },
    {
        "id": 3,
        "name": "第3关：深度处理",
        "correct": [
            {"name": "二沉池", "label": "二沉池（出水）", "img": "secondary_clarifier.jpg"},
            {"name": "纤维滤池", "label": "纤维滤池（过滤杂质）", "img": "fiber_filter.jpg"},
            {"name": "紫外线消毒系统", "label": "紫外线消毒（杀菌）", "img": "uv_disinfection.jpg"},
            {"name": "出水泵房", "label": "出水泵房（输送清水）", "img": "outlet_pump.jpg"}
        ],
        "tips": {
            "纤维滤池": ["这里需要先去除悬浮杂质", "过滤步骤应在消毒之前", "正确答案：纤维滤池"],
            "紫外线消毒系统": ["这里用于杀灭细菌", "消毒必须在最后阶段", "正确答案：紫外线消毒系统"],
            "出水泵房": ["这里负责输送处理后的水", "是整个流程的最后出口", "正确答案：出水泵房"]
        }
    },
    {
        "id": 4,
        "name": "第4关：高级处理",
        "correct": [
            {"name": "出水泵房", "label": "出水泵房（进入深度处理）", "img": "outlet_pump.jpg"},
            {"name": "磁混凝沉淀池", "label": "磁混凝沉淀池（强化沉淀）", "img": "magnetic_clarifier.jpg"},
            {"name": "臭氧接触池", "label": "臭氧接触池（氧化污染物）", "img": "ozone_tank.jpg"},
            {"name": "V型好氧生物滤池", "label": "V型滤池（进一步净化）", "img": "v_filter.jpg"},
            {"name": "紫外消毒渠", "label": "紫外消毒渠（最终消毒）", "img": "uv_channel.jpg"}
        ],
        "tips": {
            "磁混凝沉淀池": ["这里用于强化沉淀效果", "应先去除悬浮物", "正确答案：磁混凝沉淀池"],
            "臭氧接触池": ["这里用于氧化难降解污染物", "通常在处理中间阶段", "正确答案：臭氧接触池"],
            "紫外消毒渠": ["这里用于最终消毒", "必须放在流程最后", "正确答案：紫外消毒渠"]
        }
    },
    {
        "id": 5,
        "name": "第5关：污泥处理",
        "correct": [
            {"name": "初沉污泥泵房", "label": "初沉污泥泵房（输送污泥）", "img": "sludge_pump.jpg"},
            {"name": "污泥浓缩系统", "label": "污泥浓缩系统（减少体积）", "img": "sludge_thick.jpg"},
            {"name": "污泥脱水系统", "label": "污泥脱水系统（形成泥饼）", "img": "sludge_dewater.jpg"}
        ],
        "tips": {
            "污泥浓缩系统": ["这里需要先减少污泥体积", "为后续处理降低负担", "正确答案：污泥浓缩系统"],
            "污泥脱水系统": ["这里用于最终脱水", "形成泥饼便于运输", "正确答案：污泥脱水系统"]
        }
    }
]

# ============== 工具函数 ==============

def get_image_base64(image_name):
    """将图片转为base64编码"""
    try:
        image_path = Path("assets") / image_name
        if image_path.exists():
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
    except Exception:
        pass
    return None

def init_game_state():
    """初始化游戏状态"""
    if 'game_current_level' not in st.session_state:
        st.session_state.game_current_level = 0
    if 'game_error_counts' not in st.session_state:
        st.session_state.game_error_counts = {}
    if 'game_completed_levels' not in st.session_state:
        st.session_state.game_completed_levels = []

def reset_game():
    """重置游戏"""
    st.session_state.game_current_level = 0
    st.session_state.game_error_counts = {}
    st.session_state.game_completed_levels = []

# ============== 游戏主渲染函数 ==============

def render_water_treatment_game():
    """主游戏渲染函数 - 1:1复刻原始界面"""
    init_game_state()
    
    # 读取背景图片
    bg_base64 = get_image_base64("bg.jpg")
    
    # 准备游戏数据（包含base64图片）
    levels_data = []
    for level in GAME_LEVELS:
        level_copy = {
            "name": level["name"],
            "tips": level["tips"],
            "correct": []
        }
        for item in level["correct"]:
            img_base64 = get_image_base64(item["img"])
            level_copy["correct"].append({
                "name": item["name"],
                "label": item["label"],
                "img": f"data:image/jpeg;base64,{img_base64}" if img_base64 else ""
            })
        levels_data.append(level_copy)
    
    # 当前关卡和错误计数
    current_level = st.session_state.game_current_level
    error_counts = st.session_state.game_error_counts
    
    # 构建完整的HTML游戏界面（1:1复刻原始设计）
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh">
    <head>
    <meta charset="UTF-8">
    <title>水厂拼图大挑战</title>
    <style>
    body {{
        font-family: Arial;
        text-align: center;
        margin: 0;
        padding: 10px;
        background: url("data:image/jpeg;base64,{bg_base64}") no-repeat center center fixed;
        background-size: cover;
        min-height: 100vh;
    }}

    /* 半透明遮罩 */
    body::before {{
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: url("data:image/jpeg;base64,{bg_base64}") no-repeat center center;
        background-size: cover;
        opacity: 0.4;
        z-index: -1;
    }}

    .container {{
        display: flex;
        justify-content: space-around;
        margin-top: 20px;
    }}

    .box {{
        width: 320px;
        min-height: 350px;
        border: 2px dashed #aaa;
        padding: 10px;
        background: rgba(255,255,255,0.85);
        border-radius: 10px;
    }}

    .item {{
        background: #cdecfe;
        margin: 10px 0;
        padding: 8px;
        cursor: grab;
        border-radius: 8px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2);
        text-align: center;
    }}

    /* 图片样式 */
    .item img {{
        width: 100%;
        height: 100px;
        object-fit: cover;
        border-radius: 6px;
    }}

    /* 文字 */
    .item span {{
        display: block;
        margin-top: 5px;
        font-size: 14px;
        color: #333;
    }}

    .arrow {{
        font-weight: bold;
        margin: 5px;
    }}

    button {{
        margin: 5px;
        padding: 10px 15px;
        border-radius: 6px;
        border: none;
        background: #4CAF50;
        color: white;
        cursor: pointer;
    }}

    button:hover {{
        background: #45a049;
    }}

    #result {{
        font-weight: bold;
        margin-top: 10px;
    }}
    </style>
    </head>

    <body>

    <h2 id="levelTitle"></h2>

    <div class="container">
        <div class="box" id="source">
            <h3>组件库</h3>
        </div>

        <div class="box" id="target">
            <h3>流程区</h3>
        </div>
    </div>

    <br>

    <button onclick="submitOrder()">提交</button>
    <button onclick="resetArea()">重置</button>
    <button onclick="undoLast()">撤销上一步</button>
    <button id="prevBtn" onclick="prevLevel()">上一关</button>
    <button id="nextBtn" onclick="nextLevel()">下一关</button>

    <p id="result"></p>

    <script>
    let levels = {json.dumps(levels_data, ensure_ascii=False)};
    let currentLevel = {current_level};
    let dragged = null;
    let errorCounts = {json.dumps(error_counts)};
    let completedLevels = {json.dumps(st.session_state.game_completed_levels)};

    // ===== 加载关卡 =====
    function loadLevel() {{
        document.getElementById("source").innerHTML = "<h3>组件库</h3>";
        document.getElementById("target").innerHTML = "<h3>流程区</h3>";
        document.getElementById("result").innerText = "";

        document.getElementById("levelTitle").innerText = levels[currentLevel].name;

        document.getElementById("prevBtn").style.display = currentLevel === 0 ? "none" : "inline-block";

        if (currentLevel === levels.length - 1) {{
            document.getElementById("nextBtn").innerText = "重新开始";
        }} else {{
            document.getElementById("nextBtn").innerText = "下一关";
        }}

        let items = levels[currentLevel].correct.slice().sort(() => Math.random() - 0.5);

        items.forEach(item => {{
            let div = document.createElement("div");
            div.className = "item";
            div.draggable = true;

            // ===== 图片 + 文字 =====
            div.innerHTML = `
                <img src="${{item.img}}" onerror="this.style.display='none'">
                <span>${{item.label}}</span>
            `;

            div.setAttribute("data-name", item.name);

            div.addEventListener("dragstart", function() {{
                dragged = this;
            }});

            document.getElementById("source").appendChild(div);
        }});
    }}

    // ===== 拖拽允许 =====
    document.getElementById("target").addEventListener("dragover", function(e) {{
        e.preventDefault();
    }});

    // ===== 放下 =====
    document.getElementById("target").addEventListener("drop", function(e) {{
        e.preventDefault();

        if (dragged) {{
            let clone = dragged.cloneNode(true);
            clone.draggable = true;

            clone.setAttribute("data-name", dragged.getAttribute("data-name"));

            clone.addEventListener("dragstart", function() {{
                dragged = this;
            }});

            let target = document.getElementById("target");

            let items = target.querySelectorAll(".item");
            if (items.length > 0) {{
                let arrow = document.createElement("span");
                arrow.className = "arrow";
                arrow.innerText = "⬇️";
                target.appendChild(arrow);
            }}

            target.appendChild(clone);
        }}
    }});

    // ===== 提交 =====
    function submitOrder() {{
        let items = document.querySelectorAll("#target .item");
        let order = [];

        items.forEach(i => {{
            order.push(i.getAttribute("data-name"));
        }});

        let level = levels[currentLevel];
        let correct = level.correct.map(item => item.name);

        // 检查答案
        for (let i = 0; i < Math.min(order.length, correct.length); i++) {{
            if (order[i] !== correct[i]) {{
                let key = currentLevel + "_" + i;
                errorCounts[key] = (errorCounts[key] || 0) + 1;

                let correctItem = correct[i];
                let tips = level.tips[correctItem] || ["再想想这个步骤的作用", "再想想它的功能特点", "正确答案：" + correctItem];
                let count = errorCounts[key];

                let tip;
                if (count === 1) tip = tips[0] || "再想想这个步骤的作用";
                else if (count === 2) tip = tips[1] || "再想想它的功能特点";
                else tip = tips[2] || "正确答案：" + correctItem;

                showResult("❌ 第" + (i+1) + "步有问题：" + tip);
                return;
            }}
        }}

        if (order.length !== correct.length) {{
            showResult("❌ 还没有完成全部步骤，请继续添加工艺模块");
            return;
        }}

        // 通关成功
        if (!completedLevels.includes(currentLevel)) {{
            completedLevels.push(currentLevel);
        }}

        showResult("🎉 恭喜！完全正确！本关已通过！");

        // 发送消息给Streamlit
        window.parent.postMessage({{
            type: "game_complete",
            level: currentLevel
        }}, "*");
    }}

    // ===== 显示结果 =====
    function showResult(message) {{
        document.getElementById("result").innerText = message;
    }}

    // ===== 撤销 =====
    function undoLast() {{
        let target = document.getElementById("target");
        let children = target.children;

        if (children.length <= 1) return;

        target.removeChild(children[children.length - 1]);

        if (children.length > 1 && children[children.length - 1].className === "arrow") {{
            target.removeChild(children[children.length - 1]);
        }}
    }}

    // ===== 重置 =====
    function resetArea() {{
        loadLevel();
    }}

    // ===== 上一关 =====
    function prevLevel() {{
        if (currentLevel > 0) {{
            currentLevel--;
            window.parent.postMessage({{
                type: "change_level",
                level: currentLevel
            }}, "*");
        }}
    }}

    // ===== 下一关 =====
    function nextLevel() {{
        if (currentLevel < levels.length - 1) {{
            currentLevel++;
            window.parent.postMessage({{
                type: "change_level",
                level: currentLevel
            }}, "*");
        }} else {{
            // 重新开始
            currentLevel = 0;
            errorCounts = {{}};
            completedLevels = [];
            window.parent.postMessage({{
                type: "reset_game"
            }}, "*");
        }}
    }}

    // 初始化
    loadLevel();
    </script>

    </body>
    </html>
    """
    
    # 使用components嵌入HTML游戏
    import streamlit.components.v1 as components
    components.html(html_content, height=700, scrolling=True)
    
    # 显示游戏统计信息
    st.divider()
    cols = st.columns(5)
    for i, level in enumerate(GAME_LEVELS):
        with cols[i]:
            is_completed = i in st.session_state.game_completed_levels
            is_current = i == st.session_state.game_current_level
            
            if is_completed:
                st.success(f"✅ 第{i+1}关")
            elif is_current:
                st.info(f"🎯 第{i+1}关")
            else:
                st.caption(f"🔒 第{i+1}关")
    
    # 游戏说明
    with st.expander("📖 游戏规则说明"):
        st.markdown("""
        ### 🎮 游戏玩法
        1. **选择组件**：从左侧【组件库】中拖拽工艺模块到右侧【流程区】
        2. **排列流程**：按正确顺序排列工艺模块
        3. **撤销操作**：点击【撤销上一步】可移除最后添加的模块
        4. **提交答案**：完成排列后点击【提交】验证
        5. **三层提示**：答错时会依次给出越来越明确的提示
        
        ### 📋 五个关卡
        - **第1关**：预处理（粗格栅→进水泵房→细格栅→曝气沉砂池→初沉池）
        - **第2关**：生物处理（初沉池→膜格栅间→厌氧池→缺氧池→好氧池→二沉池）
        - **第3关**：深度处理（二沉池→纤维滤池→紫外线消毒→出水泵房）
        - **第4关**：高级处理（出水泵房→磁混凝沉淀池→臭氧接触池→V型滤池→紫外消毒渠）
        - **第5关**：污泥处理（污泥泵房→污泥浓缩→污泥脱水）
        
        ### 💡 提示系统
        每关都有独特的三层提示，答错次数越多，提示越明确！
        """)

# ============== 用于独立测试 ==============
if __name__ == "__main__":
    st.set_page_config(
        page_title="水厂拼图大挑战",
        page_icon="🎮",
        layout="wide"
    )
    render_water_treatment_game()
