# -*- coding: utf-8 -*-
"""
污水处理厂 3D 数字孪生虚拟仿真系统 - 交互增强版
============================================
基于 Three.js + Streamlit 的高级 3D 可视化

功能特性：
- 真实水厂级 3D 建模（混凝土水池、设备、管道、建筑物）
- 物理级材质：混凝土、不锈钢、玻璃、水面
- 实时光影效果：阴影、反射、环境光遮蔽
- 动态水面效果：波浪、流动
- 交互功能：旋转、缩放、平移、点击查看详情、双击编辑参数
- 数据联动：甲烷浓度实时颜色映射
- 粒子系统：曝气气泡、气体排放可视化
- 参数编辑：点击工艺区可修改实时运行数值
"""

import streamlit as st
import json
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class Unit3DConfig:
    """3D单元配置 - 真实水厂参数"""
    name: str
    position: List[float]      # x, y, z (米)
    size: List[float]          # width, height, depth (米)
    shape: str                 # 'concrete_tank', 'steel_tank', 'building', 'cylinder', 'pool'
    color: str                 # 基础颜色
    area: str                  # 所属区域
    liquid_level: float = 0.0  # 液位高度 (0-1)
    liquid_color: str = "#4FC3F7"
    description: str = ""
    icon: str = "🏭"
    has_mixer: bool = False    # 是否有搅拌器
    has_aeration: bool = False # 是否有曝气
    has_cover: bool = False    # 是否有盖顶
    emission: float = 0.0      # 甲烷排放量
    enabled: bool = True       # 是否启用


class Plant3DAdvanced:
    """
    污水厂 3D 数字孪生引擎 - 基于 Three.js
    """
    
    def __init__(self, unit_data: Dict[str, Any]):
        self.unit_data = unit_data
        self.units_config = self._initialize_units()
        self.connections = self._initialize_connections()
        self.scene_config = self._initialize_scene()
        
    def _initialize_units(self) -> Dict[str, Unit3DConfig]:
        """初始化所有处理单元的 3D 配置 - 基于真实水厂尺寸"""
        units = {
            # ============ 预处理区 ============
            "粗格栅": Unit3DConfig(
                name="粗格栅",
                position=[-60, 5, 80],
                size=[20, 10, 15],
                shape="concrete_tank",
                color="#78909C",
                area="预处理区",
                description="拦截大颗粒悬浮物及栅渣",
                icon="🚧",
                has_cover=True,
                emission=self.unit_data.get("粗格栅", {}).get("emission", 0),
                enabled=self.unit_data.get("粗格栅", {}).get("enabled", True)
            ),
            "提升泵房": Unit3DConfig(
                name="提升泵房",
                position=[-35, 8, 80],
                size=[18, 16, 18],
                shape="building",
                color="#607D8B",
                area="预处理区",
                description="提升污水水位至后续处理单元",
                icon="⬆️",
                emission=self.unit_data.get("提升泵房", {}).get("emission", 0),
                enabled=self.unit_data.get("提升泵房", {}).get("enabled", True)
            ),
            "细格栅": Unit3DConfig(
                name="细格栅",
                position=[-10, 5, 80],
                size=[18, 10, 15],
                shape="concrete_tank",
                color="#78909C",
                area="预处理区",
                description="去除细小悬浮物",
                icon="🔍",
                has_cover=True,
                emission=self.unit_data.get("细格栅", {}).get("emission", 0),
                enabled=self.unit_data.get("细格栅", {}).get("enabled", True)
            ),
            "曝气沉砂池": Unit3DConfig(
                name="曝气沉砂池",
                position=[20, 6, 80],
                size=[35, 12, 20],
                shape="concrete_tank",
                color="#90A4AE",
                area="预处理区",
                liquid_level=0.70,
                liquid_color="#81D4FA",
                description="曝气去除砂粒及油脂",
                icon="💨",
                has_aeration=True,
                emission=self.unit_data.get("曝气沉砂池", {}).get("emission", 0),
                enabled=self.unit_data.get("曝气沉砂池", {}).get("enabled", True)
            ),
            "膜格栅": Unit3DConfig(
                name="膜格栅",
                position=[60, 5, 80],
                size=[15, 10, 15],
                shape="concrete_tank",
                color="#78909C",
                area="预处理区",
                description="膜前精细过滤",
                icon="🛡️",
                has_cover=True,
                emission=self.unit_data.get("膜格栅", {}).get("emission", 0),
                enabled=self.unit_data.get("膜格栅", {}).get("enabled", True)
            ),
            
            # ============ 生物处理区 (A²O + MBR) ============
            "厌氧池": Unit3DConfig(
                name="厌氧池",
                position=[60, 8, 30],
                size=[25, 16, 22],
                shape="concrete_tank",
                color="#4CAF50",
                area="生物处理区",
                liquid_level=0.85,
                liquid_color="#81C784",
                description="释磷、水解酸化反应区",
                icon="🦠",
                has_mixer=True,
                emission=self.unit_data.get("厌氧池", {}).get("emission", 0),
                enabled=self.unit_data.get("厌氧池", {}).get("enabled", True)
            ),
            "缺氧池": Unit3DConfig(
                name="缺氧池",
                position=[25, 8, 30],
                size=[25, 16, 22],
                shape="concrete_tank",
                color="#388E3C",
                area="生物处理区",
                liquid_level=0.85,
                liquid_color="#A5D6A7",
                description="反硝化脱氮反应区",
                icon="🔄",
                has_mixer=True,
                emission=self.unit_data.get("缺氧池", {}).get("emission", 0),
                enabled=self.unit_data.get("缺氧池", {}).get("enabled", True)
            ),
            "好氧池": Unit3DConfig(
                name="好氧池",
                position=[-10, 8, 30],
                size=[25, 16, 22],
                shape="concrete_tank",
                color="#2E7D32",
                area="生物处理区",
                liquid_level=0.85,
                liquid_color="#C8E6C9",
                description="有机物降解、硝化反应区",
                icon="💨",
                has_aeration=True,
                emission=self.unit_data.get("好氧池", {}).get("emission", 0),
                enabled=self.unit_data.get("好氧池", {}).get("enabled", True)
            ),
            "MBR膜池": Unit3DConfig(
                name="MBR膜池",
                position=[-45, 8, 30],
                size=[25, 16, 22],
                shape="steel_tank",
                color="#00897B",
                area="生物处理区",
                liquid_level=0.80,
                liquid_color="#80CBC4",
                description="膜生物反应器 - 泥水分离",
                icon="🔬",
                has_aeration=True,
                emission=self.unit_data.get("MBR膜池", {}).get("emission", 0),
                enabled=self.unit_data.get("MBR膜池", {}).get("enabled", True)
            ),
            
            # ============ 深度处理区 ============
            "DF系统": Unit3DConfig(
                name="DF系统",
                position=[-45, 6, -10],
                size=[22, 12, 18],
                shape="steel_tank",
                color="#F44336",
                area="深度处理区",
                liquid_level=0.75,
                liquid_color="#FFCDD2",
                description="深床滤池深度过滤",
                icon="🎯",
                emission=self.unit_data.get("DF系统", {}).get("emission", 0),
                enabled=self.unit_data.get("DF系统", {}).get("enabled", True)
            ),
            "催化氧化": Unit3DConfig(
                name="催化氧化",
                position=[-10, 10, -10],
                size=[18, 18, 15],
                shape="cylinder",
                color="#D32F2F",
                area="深度处理区",
                description="臭氧催化氧化高级处理",
                icon="⚡",
                emission=self.unit_data.get("催化氧化", {}).get("emission", 0),
                enabled=self.unit_data.get("催化氧化", {}).get("enabled", True)
            ),
            "消毒接触池": Unit3DConfig(
                name="消毒接触池",
                position=[30, 5, -50],
                size=[25, 10, 18],
                shape="concrete_tank",
                color="#00BCD4",
                area="出水区",
                liquid_level=0.70,
                liquid_color="#B2EBF2",
                description="次氯酸钠消毒杀菌",
                icon="🧪",
                emission=self.unit_data.get("消毒接触池", {}).get("emission", 0),
                enabled=self.unit_data.get("消毒接触池", {}).get("enabled", True)
            ),
            
            # ============ 污泥处理区 ============
            "污泥处理车间": Unit3DConfig(
                name="污泥处理车间",
                position=[-75, 8, -10],
                size=[30, 14, 22],
                shape="building",
                color="#FF9800",
                area="污泥处理区",
                description="污泥浓缩脱水干化处理",
                icon="🏭",
                emission=self.unit_data.get("污泥处理车间", {}).get("emission", 0),
                enabled=self.unit_data.get("污泥处理车间", {}).get("enabled", True)
            ),
            
            # ============ 辅助设施 ============
            "鼓风机房": Unit3DConfig(
                name="鼓风机房",
                position=[60, 8, 65],
                size=[20, 12, 18],
                shape="building",
                color="#9C27B0",
                area="辅助设施",
                description="曝气系统供氧设备",
                icon="🌪️",
                emission=self.unit_data.get("鼓风机房", {}).get("emission", 0),
                enabled=self.unit_data.get("鼓风机房", {}).get("enabled", True)
            ),
            "除臭系统": Unit3DConfig(
                name="除臭系统",
                position=[-85, 5, 55],
                size=[22, 10, 18],
                shape="building",
                color="#7B1FA2",
                area="辅助设施",
                description="生物滤池除臭系统",
                icon="🌿",
                emission=self.unit_data.get("除臭系统", {}).get("emission", 0),
                enabled=self.unit_data.get("除臭系统", {}).get("enabled", True)
            ),
        }
        return units
    
    def _initialize_connections(self) -> List[Dict]:
        """初始化管道连接关系"""
        return [
            {"from": "粗格栅", "to": "提升泵房", "color": "#1976D2", "type": "water_main", "diameter": 0.8},
            {"from": "提升泵房", "to": "细格栅", "color": "#1976D2", "type": "water_main", "diameter": 0.8},
            {"from": "细格栅", "to": "曝气沉砂池", "color": "#1976D2", "type": "water_main", "diameter": 0.8},
            {"from": "曝气沉砂池", "to": "膜格栅", "color": "#1976D2", "type": "water_main", "diameter": 0.8},
            {"from": "膜格栅", "to": "厌氧池", "color": "#388E3C", "type": "water_bio", "diameter": 0.6},
            {"from": "厌氧池", "to": "缺氧池", "color": "#388E3C", "type": "water_bio", "diameter": 0.6},
            {"from": "缺氧池", "to": "好氧池", "color": "#388E3C", "type": "water_bio", "diameter": 0.6},
            {"from": "好氧池", "to": "MBR膜池", "color": "#388E3C", "type": "water_bio", "diameter": 0.6},
            {"from": "MBR膜池", "to": "DF系统", "color": "#D32F2F", "type": "water_advanced", "diameter": 0.5},
            {"from": "DF系统", "to": "消毒接触池", "color": "#00ACC1", "type": "water_effluent", "diameter": 0.5},
            {"from": "MBR膜池", "to": "污泥处理车间", "color": "#795548", "type": "sludge", "diameter": 0.3},
            {"from": "好氧池", "to": "污泥处理车间", "color": "#795548", "type": "sludge", "diameter": 0.3},
            {"from": "鼓风机房", "to": "好氧池", "color": "#9E9E9E", "type": "air", "diameter": 0.4},
            {"from": "鼓风机房", "to": "MBR膜池", "color": "#9E9E9E", "type": "air", "diameter": 0.4},
            {"from": "鼓风机房", "to": "曝气沉砂池", "color": "#9E9E9E", "type": "air", "diameter": 0.3},
        ]
    
    def _initialize_scene(self) -> Dict:
        """初始化场景配置"""
        return {
            "ground_size": 250,
            "ground_color": "#E8F5E9",
            "background_color": "#87CEEB",
            "fog_color": "#E0F7FA",
            "sun_position": [100, 150, 50],
            "camera_position": [120, 80, 120],
        }
    
    def _get_emission_color(self, emission: float, base_color: str) -> str:
        """根据甲烷排放量获取显示颜色"""
        if emission >= 2000:
            return "#B71C1C"  # 深红 - 高排放
        elif emission >= 1000:
            return "#E65100"  # 橙色 - 较高排放
        elif emission >= 500:
            return "#F9A825"  # 琥珀色 - 中等排放
        return base_color  # 原色 - 正常
    
    def get_unit_parameters(self, unit_name: str) -> Dict[str, Any]:
        """获取单元的可编辑参数"""
        unit_info = self.unit_data.get(unit_name, {})
        
        # 基础参数所有单元都有
        params = {
            "甲烷浓度": unit_info.get("methane_concentration", 0.5),  # mg/L
            "流量": unit_info.get("water_flow", 10000),  # m³/d
            "液位": unit_info.get("liquid_level", 50),  # %
            "温度": unit_info.get("temperature", 25),  # °C
            "pH": unit_info.get("ph", 7.0),
            "运行状态": unit_info.get("enabled", True),
            "能耗": unit_info.get("energy", 1000),  # kWh
            "甲烷排放": unit_info.get("emission", 0),  # kgCO2eq
        }
        
        # 生物处理区特有参数
        if unit_name in ["厌氧池", "缺氧池", "好氧池"]:
            params["进水TN"] = unit_info.get("TN_in", 40)
            params["出水TN"] = unit_info.get("TN_out", 15)
            params["进水COD"] = unit_info.get("COD_in", 200)
            params["出水COD"] = unit_info.get("COD_out", 50)
        
        # 污泥处理区特有参数
        if unit_name == "污泥处理车间":
            params["PAM投加量"] = unit_info.get("PAM", 100)
        
        # 深度处理区特有参数
        if unit_name == "DF系统":
            params["PAC投加量"] = unit_info.get("PAC", 300)
        
        return params

    def generate_threejs_html(self, selected_unit: Optional[str] = None) -> str:
        """生成 Three.js HTML 代码 - 增强交互版"""
        
        # 准备单元数据
        units_data = []
        for name, config in self.units_config.items():
            unit_info = self.unit_data.get(name, {})
            emission = unit_info.get("emission", 0)
            enabled = unit_info.get("enabled", True)
            
            # 获取可编辑参数
            params = self.get_unit_parameters(name)
            
            # 获取显示颜色
            display_color = self._get_emission_color(emission, config.color) if enabled else "#9E9E9E"
            is_selected = (name == selected_unit)
            
            unit_dict = {
                "name": config.name,
                "position": config.position,
                "size": config.size,
                "shape": config.shape,
                "color": display_color,
                "baseColor": config.color,
                "area": config.area,
                "description": config.description,
                "icon": config.icon,
                "liquidLevel": config.liquid_level if enabled else 0,
                "liquidColor": config.liquid_color,
                "hasMixer": config.has_mixer and enabled,
                "hasAeration": config.has_aeration and enabled,
                "hasCover": config.has_cover,
                "emission": emission,
                "enabled": enabled,
                "isSelected": is_selected,
                "waterFlow": unit_info.get("water_flow", 0),
                "energy": unit_info.get("energy", 0),
                "parameters": params  # 添加可编辑参数
            }
            units_data.append(unit_dict)
        
        # 转换为JSON
        units_json = json.dumps(units_data, ensure_ascii=False)
        connections_json = json.dumps(self.connections, ensure_ascii=False)
        scene_json = json.dumps(self.scene_config, ensure_ascii=False)
        
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>污水处理厂 3D 数字孪生系统</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            overflow: hidden;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        #container {{ 
            width: 100vw; 
            height: 100vh; 
            position: relative;
        }}
        #info-panel {{
            position: absolute;
            top: 20px;
            right: 20px;
            width: 360px;
            background: rgba(255, 255, 255, 0.97);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
            z-index: 1000;
            max-height: 85vh;
            overflow-y: auto;
            transition: all 0.3s ease;
        }}
        #info-panel.hidden {{ transform: translateX(120%); opacity: 0; }}
        #info-panel h2 {{
            margin: 0 0 15px 0;
            color: #1565C0;
            font-size: 20px;
            border-bottom: 2px solid #E3F2FD;
            padding-bottom: 10px;
        }}
        .info-row {{
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 8px 0;
            border-bottom: 1px solid #ECEFF1;
        }}
        .info-label {{ color: #546E7A; font-weight: 500; }}
        .info-value {{ color: #263238; font-weight: 600; }}
        .emission-high {{ color: #C62828; }}
        .emission-medium {{ color: #EF6C00; }}
        .emission-normal {{ color: #2E7D32; }}
        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }}
        .status-running {{ background: #E8F5E9; color: #2E7D32; }}
        .status-stopped {{ background: #FFEBEE; color: #C62828; }}
        #legend {{
            position: absolute;
            bottom: 30px;
            left: 30px;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 15px 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            z-index: 1000;
        }}
        #legend h4 {{ margin: 0 0 10px 0; color: #37474F; font-size: 14px; }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 6px 0;
            font-size: 12px;
            color: #546E7A;
        }}
        .legend-color {{
            width: 20px;
            height: 12px;
            border-radius: 3px;
            margin-right: 10px;
        }}
        #controls {{
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 15px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            z-index: 1000;
        }}
        #controls h4 {{ margin: 0 0 10px 0; color: #37474F; font-size: 14px; }}
        .control-btn {{
            background: #1976D2;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            margin: 3px;
            transition: all 0.2s;
        }}
        .control-btn:hover {{ background: #1565C0; transform: translateY(-2px); }}
        #loading {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: white;
            font-size: 24px;
            z-index: 2000;
            text-align: center;
        }}
        .spinner {{
            width: 50px;
            height: 50px;
            border: 4px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .area-label {{
            position: absolute;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            pointer-events: none;
            z-index: 100;
        }}
        /* 编辑面板样式 */
        .edit-section {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 2px dashed #E0E0E0;
        }}
        .edit-section h3 {{
            color: #1565C0;
            font-size: 16px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .param-input {{
            margin: 10px 0;
        }}
        .param-input label {{
            display: block;
            color: #546E7A;
            font-size: 12px;
            margin-bottom: 4px;
            font-weight: 500;
        }}
        .param-input input, .param-input select {{
            width: 100%;
            padding: 8px 12px;
            border: 1px solid #BDBDBD;
            border-radius: 6px;
            font-size: 14px;
            transition: all 0.2s;
        }}
        .param-input input:focus, .param-input select:focus {{
            outline: none;
            border-color: #1976D2;
            box-shadow: 0 0 0 3px rgba(25, 118, 210, 0.1);
        }}
        .save-btn {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            width: 100%;
            margin-top: 15px;
            transition: all 0.3s;
        }}
        .save-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }}
        .save-btn.saved {{
            background: linear-gradient(135deg, #4CAF50 0%, #2E7D32 100%);
        }}
        .click-hint {{
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 13px;
            z-index: 1000;
            pointer-events: none;
        }}
    </style>
</head>
<body>
    <div id="container"></div>
    <div id="loading">
        <div class="spinner"></div>
        <div>正在加载 3D 场景...</div>
    </div>
    
    <div id="controls">
        <h4>🎮 视图控制</h4>
        <button class="control-btn" onclick="resetCamera()">重置视角</button>
        <button class="control-btn" onclick="toggleAutoRotate()">自动旋转</button>
        <button class="control-btn" onclick="toggleWaterEffect()">水面效果</button>
    </div>
    
    <div id="info-panel" class="hidden">
        <h2 id="unit-title">选择设备</h2>
        <div id="unit-details"></div>
        <div id="edit-section" class="edit-section" style="display:none;">
            <h3>✏️ 参数编辑</h3>
            <div id="param-inputs"></div>
            <button class="save-btn" onclick="saveParameters()">💾 保存修改</button>
        </div>
    </div>
    
    <div id="legend">
        <h4>📊 甲烷排放等级</h4>
        <div class="legend-item">
            <div class="legend-color" style="background: #B71C1C;"></div>
            <span>🔴 高排放 (>2000 kgCO₂eq)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #E65100;"></div>
            <span>🟠 较高排放 (1000-2000)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #F9A825;"></div>
            <span>🟡 中等排放 (500-1000)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #2E7D32;"></div>
            <span>🟢 正常排放 (<500)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #9E9E9E;"></div>
            <span>⚪ 设备停用</span>
        </div>
    </div>
    
    <div class="click-hint">💡 点击设备查看详情并编辑参数</div>

    <script type="importmap">
    {{
        "imports": {{
            "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
            "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
        }}
    }}
    </script>

    <script type="module">
        import * as THREE from 'three';
        import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';

        // 全局变量
        let scene, camera, renderer, controls;
        let unitMeshes = {{}};
        let particleSystems = [];
        let autoRotate = false;
        let waterEffectEnabled = true;
        let selectedUnit = null;
        let raycaster, mouse;

        // 数据
        const units = {units_json};
        const connections = {connections_json};
        const sceneConfig = {scene_json};

        // 初始化场景
        function init() {{
            // 创建场景
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x87CEEB);
            scene.fog = new THREE.Fog(0xE0F7FA, 50, 400);

            // 创建相机
            camera = new THREE.PerspectiveCamera(
                45, 
                window.innerWidth / window.innerHeight, 
                0.1, 
                1000
            );
            camera.position.set(...sceneConfig.camera_position);

            // 创建渲染器
            renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.setPixelRatio(window.devicePixelRatio);
            renderer.shadowMap.enabled = true;
            renderer.shadowMap.type = THREE.PCFSoftShadowMap;
            renderer.toneMapping = THREE.ACESFilmicToneMapping;
            document.getElementById('container').appendChild(renderer.domElement);

            // 创建控制器
            controls = new OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.maxPolarAngle = Math.PI / 2 - 0.05;
            controls.minDistance = 50;
            controls.maxDistance = 300;
            controls.target.set(0, 10, 0);

            // 光照系统
            setupLighting();

            // 创建地面
            createGround();

            // 创建处理单元
            units.forEach(unit => createUnit(unit));

            // 创建管道
            createPipes();

            // 创建区域标记
            createAreaMarkers();

            // 射线检测
            raycaster = new THREE.Raycaster();
            mouse = new THREE.Vector2();

            // 事件监听
            window.addEventListener('resize', onWindowResize);
            renderer.domElement.addEventListener('click', onMouseClick);
            renderer.domElement.addEventListener('mousemove', onMouseMove);

            // 隐藏加载
            document.getElementById('loading').style.display = 'none';

            // 开始动画
            animate();
        }}

        // 设置光照
        function setupLighting() {{
            // 环境光
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
            scene.add(ambientLight);

            // 主光源（太阳光）
            const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
            dirLight.position.set(...sceneConfig.sun_position);
            dirLight.castShadow = true;
            dirLight.shadow.mapSize.width = 2048;
            dirLight.shadow.mapSize.height = 2048;
            dirLight.shadow.camera.near = 0.5;
            dirLight.shadow.camera.far = 500;
            dirLight.shadow.camera.left = -150;
            dirLight.shadow.camera.right = 150;
            dirLight.shadow.camera.top = 150;
            dirLight.shadow.camera.bottom = -150;
            scene.add(dirLight);

            // 半球光（模拟天空反射）
            const hemiLight = new THREE.HemisphereLight(0x87CEEB, 0xE8F5E9, 0.5);
            scene.add(hemiLight);

            // 点光源（夜间照明效果）
            const pointLights = [
                [-40, 30, 30],
                [20, 30, 30],
                [-20, 30, -20],
            ];
            pointLights.forEach(pos => {{
                const pl = new THREE.PointLight(0xFFD54F, 0.3, 80);
                pl.position.set(...pos);
                scene.add(pl);
            }});
        }}

        // 创建地面
        function createGround() {{
            // 主地面
            const groundGeometry = new THREE.PlaneGeometry(
                sceneConfig.ground_size, 
                sceneConfig.ground_size
            );
            const groundMaterial = new THREE.MeshStandardMaterial({{
                color: 0xE8F5E9,
                roughness: 0.9,
                metalness: 0.0,
            }});
            const ground = new THREE.Mesh(groundGeometry, groundMaterial);
            ground.rotation.x = -Math.PI / 2;
            ground.position.y = -0.1;
            ground.receiveShadow = true;
            scene.add(ground);

            // 道路系统
            createRoads();

            // 网格辅助
            const gridHelper = new THREE.GridHelper(
                sceneConfig.ground_size, 
                25, 
                0xBDBDBD, 
                0xE0E0E0
            );
            gridHelper.position.y = 0.01;
            scene.add(gridHelper);
        }}

        // 创建道路
        function createRoads() {{
            const roadMaterial = new THREE.MeshStandardMaterial({{
                color: 0x9E9E9E,
                roughness: 0.8,
            }});

            // 主道路
            const road1 = new THREE.Mesh(
                new THREE.PlaneGeometry(200, 12),
                roadMaterial
            );
            road1.rotation.x = -Math.PI / 2;
            road1.position.set(0, 0.05, 55);
            road1.receiveShadow = true;
            scene.add(road1);

            // 环形道路
            const road2 = new THREE.Mesh(
                new THREE.PlaneGeometry(12, 120),
                roadMaterial
            );
            road2.rotation.x = -Math.PI / 2;
            road2.position.set(75, 0.05, 10);
            road2.receiveShadow = true;
            scene.add(road2);
        }}

        // 创建处理单元
        function createUnit(unit) {{
            const group = new THREE.Group();
            group.name = unit.name;

            const [x, y, z] = unit.position;
            const [w, h, d] = unit.size;

            // 根据形状创建不同的几何体
            let mainMesh;
            const color = new THREE.Color(unit.color);

            switch(unit.shape) {{
                case 'concrete_tank':
                    mainMesh = createConcreteTank(w, h, d, color, unit);
                    break;
                case 'steel_tank':
                    mainMesh = createSteelTank(w, h, d, color, unit);
                    break;
                case 'building':
                    mainMesh = createBuilding(w, h, d, color, unit);
                    break;
                case 'cylinder':
                    mainMesh = createCylinder(w, h, d, color, unit);
                    break;
                default:
                    mainMesh = createConcreteTank(w, h, d, color, unit);
            }}

            mainMesh.position.set(x, y, z);
            mainMesh.castShadow = true;
            mainMesh.receiveShadow = true;
            mainMesh.userData = {{ unit: unit }};
            group.add(mainMesh);

            // 创建液面
            if (unit.liquidLevel > 0 && !unit.hasCover) {{
                const liquidMesh = createLiquidSurface(w, h, d, unit);
                liquidMesh.position.set(x, y - h/2 + h * unit.liquidLevel, z);
                group.add(liquidMesh);
            }}

            // 创建搅拌器
            if (unit.hasMixer && unit.enabled) {{
                const mixer = createMixer(w, h, d);
                mixer.position.set(x, y + h/2, z);
                group.add(mixer);
            }}

            // 创建曝气效果
            if (unit.hasAeration && unit.enabled) {{
                const aeration = createAeration(w, h, d, x, y, z);
                particleSystems.push(aeration);
                group.add(aeration);
            }}

            // 创建标签
            const label = createLabel(unit.name, unit.icon);
            label.position.set(x, y + h/2 + 8, z);
            group.add(label);

            // 气体排放效果
            if (unit.emission > 500 && unit.enabled) {{
                const emission = createEmissionEffect(unit);
                emission.position.set(x, y + h/2, z);
                particleSystems.push(emission);
                group.add(emission);
            }}

            scene.add(group);
            unitMeshes[unit.name] = group;
        }}

        // 创建混凝土水池
        function createConcreteTank(w, h, d, color, unit) {{
            const group = new THREE.Group();

            // 池体外壁
            const wallThickness = 1.0;
            const geometry = new THREE.BoxGeometry(w, h, d);
            
            // 混凝土材质
            const material = new THREE.MeshStandardMaterial({{
                color: color,
                roughness: 0.9,
                metalness: 0.1,
            }});

            const mesh = new THREE.Mesh(geometry, material);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            group.add(mesh);

            // 顶部边缘
            if (!unit.hasCover) {{
                const edgeGeometry = new THREE.BoxGeometry(w + 1, 0.5, d + 1);
                const edgeMaterial = new THREE.MeshStandardMaterial({{
                    color: 0x5D4037,
                    roughness: 0.8,
                }});
                const edge = new THREE.Mesh(edgeGeometry, edgeMaterial);
                edge.position.y = h/2;
                edge.castShadow = true;
                group.add(edge);
            }} else {{
                // 盖顶
                const coverGeometry = new THREE.BoxGeometry(w + 0.5, 0.3, d + 0.5);
                const coverMaterial = new THREE.MeshStandardMaterial({{
                    color: 0x455A64,
                    roughness: 0.7,
                }});
                const cover = new THREE.Mesh(coverGeometry, coverMaterial);
                cover.position.y = h/2 + 0.15;
                cover.castShadow = true;
                group.add(cover);
            }}

            return group;
        }}

        // 创建不锈钢罐
        function createSteelTank(w, h, d, color, unit) {{
            const group = new THREE.Group();

            // 罐体 - 使用圆角效果
            const geometry = new THREE.CylinderGeometry(w/2, w/2, h, 32);
            const material = new THREE.MeshStandardMaterial({{
                color: color,
                roughness: 0.3,
                metalness: 0.8,
            }});

            const mesh = new THREE.Mesh(geometry, material);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            group.add(mesh);

            // 顶部管道接口
            const pipeGeometry = new THREE.CylinderGeometry(1, 1, 3, 16);
            const pipeMaterial = new THREE.MeshStandardMaterial({{
                color: 0xB0BEC5,
                metalness: 0.9,
                roughness: 0.2,
            }});
            const pipe = new THREE.Mesh(pipeGeometry, pipeMaterial);
            pipe.position.y = h/2 + 1.5;
            group.add(pipe);

            return group;
        }}

        // 创建建筑物
        function createBuilding(w, h, d, color, unit) {{
            const group = new THREE.Group();

            // 主体
            const geometry = new THREE.BoxGeometry(w, h, d);
            const material = new THREE.MeshStandardMaterial({{
                color: color,
                roughness: 0.7,
                metalness: 0.1,
            }});

            const mesh = new THREE.Mesh(geometry, material);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            group.add(mesh);

            // 屋顶
            const roofGeometry = new THREE.ConeGeometry(Math.max(w, d) * 0.7, h * 0.3, 4);
            const roofMaterial = new THREE.MeshStandardMaterial({{
                color: 0x37474F,
                roughness: 0.6,
            }});
            const roof = new THREE.Mesh(roofGeometry, roofMaterial);
            roof.position.y = h/2 + h * 0.15;
            roof.rotation.y = Math.PI / 4;
            roof.castShadow = true;
            group.add(roof);

            // 门
            const doorGeometry = new THREE.PlaneGeometry(w * 0.25, h * 0.4);
            const doorMaterial = new THREE.MeshStandardMaterial({{ color: 0x3E2723 }});
            const door = new THREE.Mesh(doorGeometry, doorMaterial);
            door.position.set(0, -h/2 + h * 0.2, d/2 + 0.1);
            group.add(door);

            // 窗户
            const windowGeometry = new THREE.PlaneGeometry(w * 0.15, h * 0.2);
            const windowMaterial = new THREE.MeshStandardMaterial({{
                color: 0x81D4FA,
                emissive: 0x1A237E,
                emissiveIntensity: 0.2,
            }});
            
            for (let i = -1; i <= 1; i++) {{
                const window = new THREE.Mesh(windowGeometry, windowMaterial);
                window.position.set(i * w * 0.3, 0, d/2 + 0.1);
                group.add(window);
            }}

            return group;
        }}

        // 创建圆柱形储罐
        function createCylinder(w, h, d, color, unit) {{
            const group = new THREE.Group();
            const radius = w / 2;

            const geometry = new THREE.CylinderGeometry(radius, radius, h, 32);
            const material = new THREE.MeshStandardMaterial({{
                color: color,
                roughness: 0.4,
                metalness: 0.6,
            }});

            const mesh = new THREE.Mesh(geometry, material);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            group.add(mesh);

            // 顶部盖
            const topGeometry = new THREE.CircleGeometry(radius, 32);
            const topMaterial = new THREE.MeshStandardMaterial({{
                color: 0xBDBDBD,
                metalness: 0.7,
                roughness: 0.3,
            }});
            const top = new THREE.Mesh(topGeometry, topMaterial);
            top.rotation.x = -Math.PI / 2;
            top.position.y = h/2;
            group.add(top);

            return group;
        }}

        // 创建液面
        function createLiquidSurface(w, h, d, unit) {{
            const geometry = new THREE.PlaneGeometry(w - 1, d - 1, 20, 20);
            const material = new THREE.MeshStandardMaterial({{
                color: unit.liquidColor,
                transparent: true,
                opacity: 0.7,
                roughness: 0.1,
                metalness: 0.1,
            }});

            const mesh = new THREE.Mesh(geometry, material);
            mesh.rotation.x = -Math.PI / 2;
            mesh.userData = {{ isLiquid: true, originalY: mesh.position.y }};

            return mesh;
        }}

        // 创建搅拌器
        function createMixer(w, h, d) {{
            const group = new THREE.Group();

            // 搅拌轴
            const shaftGeometry = new THREE.CylinderGeometry(0.3, 0.3, h * 0.6, 8);
            const shaftMaterial = new THREE.MeshStandardMaterial({{ color: 0x424242 }});
            const shaft = new THREE.Mesh(shaftGeometry, shaftMaterial);
            shaft.position.y = -h * 0.3;
            group.add(shaft);

            // 搅拌桨
            const bladeGeometry = new THREE.BoxGeometry(w * 0.5, 0.2, 0.5);
            const bladeMaterial = new THREE.MeshStandardMaterial({{ color: 0x616161 }});
            const blade = new THREE.Mesh(bladeGeometry, bladeMaterial);
            blade.position.y = -h * 0.4;
            group.add(blade);

            // 动画数据
            group.userData = {{ isMixer: true, rotationSpeed: 0.02 }};

            return group;
        }}

        // 创建曝气气泡效果
        function createAeration(w, h, d, x, y, z) {{
            const group = new THREE.Group();
            const particleCount = 20;

            const geometry = new THREE.SphereGeometry(0.3, 8, 8);
            const material = new THREE.MeshBasicMaterial({{
                color: 0xFFFFFF,
                transparent: true,
                opacity: 0.6,
            }});

            for (let i = 0; i < particleCount; i++) {{
                const bubble = new THREE.Mesh(geometry, material);
                bubble.position.set(
                    (Math.random() - 0.5) * w * 0.6,
                    -h/2 + Math.random() * h * 0.5,
                    (Math.random() - 0.5) * d * 0.6
                );
                bubble.userData = {{
                    speed: 0.05 + Math.random() * 0.1,
                    initialY: bubble.position.y,
                    offset: Math.random() * Math.PI * 2,
                }};
                group.add(bubble);
            }}

            group.userData = {{ isAeration: true }};
            return group;
        }}

        // 创建气体排放效果
        function createEmissionEffect(unit) {{
            const group = new THREE.Group();
            const particleCount = Math.min(Math.floor(unit.emission / 200), 15);
            const color = unit.emission > 1500 ? 0xD32F2F : 0x757575;

            const geometry = new THREE.SphereGeometry(0.5, 8, 8);
            const material = new THREE.MeshBasicMaterial({{
                color: color,
                transparent: true,
                opacity: 0.4,
            }});

            for (let i = 0; i < particleCount; i++) {{
                const particle = new THREE.Mesh(geometry, material);
                const angle = (i / particleCount) * Math.PI * 2;
                particle.position.set(
                    Math.cos(angle) * 3,
                    2 + Math.random() * 3,
                    Math.sin(angle) * 3
                );
                particle.userData = {{
                    speed: 0.03 + Math.random() * 0.05,
                    angle: angle,
                    radius: 3,
                }};
                group.add(particle);
            }}

            group.userData = {{ isEmission: true }};
            return group;
        }}

        // 创建标签
        function createLabel(name, icon) {{
            const canvas = document.createElement('canvas');
            canvas.width = 256;
            canvas.height = 64;
            const ctx = canvas.getContext('2d');

            // 背景
            ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
            ctx.roundRect(0, 0, 256, 64, 8);
            ctx.fill();

            // 文字
            ctx.font = 'bold 20px Arial';
            ctx.fillStyle = '#263238';
            ctx.textAlign = 'center';
            ctx.fillText(icon + ' ' + name, 128, 40);

            const texture = new THREE.CanvasTexture(canvas);
            const material = new THREE.SpriteMaterial({{ map: texture }});
            const sprite = new THREE.Sprite(material);
            sprite.scale.set(20, 5, 1);

            return sprite;
        }}

        // 创建管道
        function createPipes() {{
            connections.forEach(conn => {{
                const fromUnit = units.find(u => u.name === conn.from);
                const toUnit = units.find(u => u.name === conn.to);

                if (!fromUnit || !toUnit) return;
                if (!fromUnit.enabled || !toUnit.enabled) return;

                const start = new THREE.Vector3(...fromUnit.position);
                const end = new THREE.Vector3(...toUnit.position);

                // 管道路径
                const mid = start.clone().add(end).multiplyScalar(0.5);
                mid.y = Math.min(start.y, end.y) - 5;

                const curve = new THREE.CatmullRomCurve3([
                    start,
                    new THREE.Vector3(start.x, mid.y, start.z),
                    new THREE.Vector3(end.x, mid.y, end.z),
                    end
                ]);

                const geometry = new THREE.TubeGeometry(curve, 20, conn.diameter, 8, false);
                const material = new THREE.MeshStandardMaterial({{
                    color: conn.color,
                    roughness: 0.4,
                    metalness: 0.6,
                }});

                const pipe = new THREE.Mesh(geometry, material);
                pipe.castShadow = true;
                scene.add(pipe);

                // 流动效果 - 粒子
                createFlowParticles(curve, conn.color);
            }});
        }}

        // 创建流动粒子
        function createFlowParticles(curve, color) {{
            const particleCount = 5;
            const geometry = new THREE.SphereGeometry(0.4, 8, 8);
            const material = new THREE.MeshBasicMaterial({{ color: color }});

            const group = new THREE.Group();
            for (let i = 0; i < particleCount; i++) {{
                const particle = new THREE.Mesh(geometry, material);
                particle.userData = {{
                    t: i / particleCount,
                    speed: 0.002,
                    curve: curve,
                }};
                group.add(particle);
            }}

            group.userData = {{ isFlow: true }};
            particleSystems.push(group);
            scene.add(group);
        }}

        // 创建区域标记
        function createAreaMarkers() {{
            const areas = [
                {{ name: "预处理区", pos: [-10, 0, 80], color: 0x1565C0, size: [140, 60] }},
                {{ name: "生物处理区", pos: [8, 0, 30], color: 0x2E7D32, size: [180, 80] }},
                {{ name: "深度处理区", pos: [-28, 0, -10], color: 0xC62828, size: [100, 60] }},
                {{ name: "污泥处理区", pos: [-75, 0, -10], color: 0xEF6C00, size: [40, 50] }},
                {{ name: "出水区", pos: [30, 0, -50], color: 0x00838F, size: [40, 40] }},
            ];

            areas.forEach(area => {{
                // 地面标记
                const geometry = new THREE.PlaneGeometry(area.size[0], area.size[1]);
                const material = new THREE.MeshBasicMaterial({{
                    color: area.color,
                    transparent: true,
                    opacity: 0.15,
                }});
                const mesh = new THREE.Mesh(geometry, material);
                mesh.rotation.x = -Math.PI / 2;
                mesh.position.set(...area.pos);
                mesh.position.y = 0.02;
                scene.add(mesh);

                // 边框
                const edges = new THREE.EdgesGeometry(geometry);
                const lineMaterial = new THREE.LineBasicMaterial({{
                    color: area.color,
                    linewidth: 2,
                }});
                const lines = new THREE.LineSegments(edges, lineMaterial);
                lines.rotation.x = -Math.PI / 2;
                lines.position.set(...area.pos);
                lines.position.y = 0.03;
                scene.add(lines);
            }});
        }}

        // 鼠标点击处理
        function onMouseClick(event) {{
            mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

            raycaster.setFromCamera(mouse, camera);

            const intersects = raycaster.intersectObjects(scene.children, true);

            if (intersects.length > 0) {{
                let obj = intersects[0].object;
                while (obj.parent && !obj.userData.unit) {{
                    obj = obj.parent;
                }}

                if (obj.userData && obj.userData.unit) {{
                    selectUnit(obj.userData.unit);
                }}
            }}
        }}

        // 鼠标移动处理
        function onMouseMove(event) {{
            mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(scene.children, true);

            document.body.style.cursor = intersects.length > 0 ? 'pointer' : 'default';
        }}

        // 选择单元
        function selectUnit(unit) {{
            selectedUnit = unit;

            // 发送消息到 Streamlit
            if (window.parent) {{
                window.parent.postMessage({{
                    type: 'unit_selected',
                    unit: unit
                }}, '*');
            }}

            // 更新信息面板
            updateInfoPanel(unit);

            // 高亮效果
            Object.values(unitMeshes).forEach(mesh => {{
                mesh.children.forEach(child => {{
                    if (child.material && child.material.emissive) {{
                        child.material.emissive.setHex(0x000000);
                    }}
                }});
            }});

            const selectedMesh = unitMeshes[unit.name];
            if (selectedMesh) {{
                selectedMesh.children.forEach(child => {{
                    if (child.material && child.material.emissive) {{
                        child.material.emissive.setHex(0x444444);
                    }}
                }});
            }}
        }}

        // 更新信息面板 - 增强版，包含参数编辑
        function updateInfoPanel(unit) {{
            const panel = document.getElementById('info-panel');
            const title = document.getElementById('unit-title');
            const details = document.getElementById('unit-details');
            const editSection = document.getElementById('edit-section');
            const paramInputs = document.getElementById('param-inputs');

            panel.classList.remove('hidden');
            title.innerHTML = unit.icon + ' ' + unit.name;

            const emissionClass = unit.emission >= 2000 ? 'emission-high' :
                                   unit.emission >= 1000 ? 'emission-medium' : 'emission-normal';
            const statusClass = unit.enabled ? 'status-running' : 'status-stopped';
            const statusText = unit.enabled ? '运行中' : '已停用';

            details.innerHTML = `
                <div class="info-row">
                    <span class="info-label">所属区域</span>
                    <span class="info-value">${{unit.area}}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">运行状态</span>
                    <span class="status-badge ${{statusClass}}">${{statusText}}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">甲烷排放</span>
                    <span class="info-value ${{emissionClass}}">${{unit.emission.toFixed(1)}} kgCO₂eq</span>
                </div>
                <div class="info-row">
                    <span class="info-label">处理水量</span>
                    <span class="info-value">${{unit.waterFlow.toFixed(0)}} m³/d</span>
                </div>
                <div class="info-row">
                    <span class="info-label">能耗</span>
                    <span class="info-value">${{unit.energy.toFixed(0)}} kWh/d</span>
                </div>
                <div class="info-row" style="flex-direction: column; align-items: flex-start;">
                    <span class="info-label" style="margin-bottom: 5px;">设备描述</span>
                    <span style="color: #546E7A; font-size: 13px; line-height: 1.5;">${{unit.description}}</span>
                </div>
            `;

            // 显示编辑区域
            editSection.style.display = 'block';
            
            // 生成参数编辑输入框
            const params = unit.parameters;
            let inputsHTML = '';
            
            // 基础参数
            inputsHTML += createNumberInput('甲烷浓度', 'methane_concentration', params['甲烷浓度'], 'mg/L', 0, 100, 0.1);
            inputsHTML += createNumberInput('流量', 'water_flow', params['流量'], 'm³/d', 0, 50000, 100);
            inputsHTML += createNumberInput('液位', 'liquid_level', params['液位'], '%', 0, 100, 1);
            inputsHTML += createNumberInput('温度', 'temperature', params['温度'], '°C', 0, 50, 0.5);
            inputsHTML += createNumberInput('pH', 'ph', params['pH'], '', 0, 14, 0.1);
            inputsHTML += createSelectInput('运行状态', 'enabled', params['运行状态'] ? 'true' : 'false', ['true', 'false']);
            
            // 生物处理区特有参数
            if (unit.name === '厌氧池' || unit.name === '缺氧池' || unit.name === '好氧池') {{
                inputsHTML += '<div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #E0E0E0;"><strong>水质参数</strong></div>';
                inputsHTML += createNumberInput('进水TN', 'TN_in', params['进水TN'] || 40, 'mg/L', 0, 100, 1);
                inputsHTML += createNumberInput('出水TN', 'TN_out', params['出水TN'] || 15, 'mg/L', 0, 100, 1);
                inputsHTML += createNumberInput('进水COD', 'COD_in', params['进水COD'] || 200, 'mg/L', 0, 500, 5);
                inputsHTML += createNumberInput('出水COD', 'COD_out', params['出水COD'] || 50, 'mg/L', 0, 500, 5);
            }}
            
            // 污泥处理区特有参数
            if (unit.name === '污泥处理车间') {{
                inputsHTML += '<div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #E0E0E0;"><strong>药剂参数</strong></div>';
                inputsHTML += createNumberInput('PAM投加量', 'PAM', params['PAM投加量'] || 100, 'kg', 0, 500, 5);
            }}
            
            // 深度处理区特有参数
            if (unit.name === 'DF系统') {{
                inputsHTML += '<div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #E0E0E0;"><strong>药剂参数</strong></div>';
                inputsHTML += createNumberInput('PAC投加量', 'PAC', params['PAC投加量'] || 300, 'kg', 0, 1000, 10);
            }}
            
            paramInputs.innerHTML = inputsHTML;
        }}

        // 创建数字输入框
        function createNumberInput(label, id, value, unit, min, max, step) {{
            return `
                <div class="param-input">
                    <label>${{label}}${{unit ? ' (' + unit + ')' : ''}}</label>
                    <input type="number" id="param_${{id}}" value="${{value}}" 
                           min="${{min}}" max="${{max}}" step="${{step}}">
                </div>
            `;
        }}

        // 创建下拉选择框
        function createSelectInput(label, id, value, options) {{
            const optionHTML = options.map(opt => 
                `<option value="${{opt}}" ${{opt === value ? 'selected' : ''}}>${{opt === 'true' ? '运行中' : '已停用'}}</option>`
            ).join('');
            return `
                <div class="param-input">
                    <label>${{label}}</label>
                    <select id="param_${{id}}">${{optionHTML}}</select>
                </div>
            `;
        }}

        // 保存参数
        window.saveParameters = function() {{
            if (!selectedUnit) return;
            
            const params = {{}};
            params.unit_name = selectedUnit.name;
            params.methane_concentration = parseFloat(document.getElementById('param_methane_concentration').value);
            params.water_flow = parseFloat(document.getElementById('param_water_flow').value);
            params.liquid_level = parseFloat(document.getElementById('param_liquid_level').value);
            params.temperature = parseFloat(document.getElementById('param_temperature').value);
            params.ph = parseFloat(document.getElementById('param_ph').value);
            params.enabled = document.getElementById('param_enabled').value === 'true';
            
            // 生物处理区特有参数
            if (selectedUnit.name === '厌氧池' || selectedUnit.name === '缺氧池' || selectedUnit.name === '好氧池') {{
                params.TN_in = parseFloat(document.getElementById('param_TN_in').value);
                params.TN_out = parseFloat(document.getElementById('param_TN_out').value);
                params.COD_in = parseFloat(document.getElementById('param_COD_in').value);
                params.COD_out = parseFloat(document.getElementById('param_COD_out').value);
            }}
            
            // 污泥处理区特有参数
            if (selectedUnit.name === '污泥处理车间') {{
                params.PAM = parseFloat(document.getElementById('param_PAM').value);
            }}
            
            // 深度处理区特有参数
            if (selectedUnit.name === 'DF系统') {{
                params.PAC = parseFloat(document.getElementById('param_PAC').value);
            }}
            
            // 发送到 Streamlit
            if (window.parent) {{
                window.parent.postMessage({{
                    type: 'unit_parameters_updated',
                    unit_name: selectedUnit.name,
                    parameters: params
                }}, '*');
            }}
            
            // 显示保存成功
            const btn = document.querySelector('.save-btn');
            btn.textContent = '✅ 已保存';
            btn.classList.add('saved');
            setTimeout(() => {{
                btn.textContent = '💾 保存修改';
                btn.classList.remove('saved');
            }}, 2000);
        }};

        // 窗口大小调整
        function onWindowResize() {{
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }}

        // 控制函数
        window.resetCamera = function() {{
            camera.position.set(...sceneConfig.camera_position);
            controls.target.set(0, 10, 0);
            controls.update();
        }};

        window.toggleAutoRotate = function() {{
            autoRotate = !autoRotate;
            controls.autoRotate = autoRotate;
        }};

        window.toggleWaterEffect = function() {{
            waterEffectEnabled = !waterEffectEnabled;
        }};

        // 动画循环
        function animate() {{
            requestAnimationFrame(animate);

            const time = Date.now() * 0.001;

            // 更新粒子系统
            particleSystems.forEach(system => {{
                system.children.forEach(particle => {{
                    if (particle.userData.isAeration) {{
                        particle.position.y += particle.userData.speed;
                        if (particle.position.y > 5) {{
                            particle.position.y = -5;
                        }}
                    }} else if (particle.userData.isEmission) {{
                        particle.position.y += particle.userData.speed;
                        particle.position.x = Math.cos(particle.userData.angle + time * 0.5) * particle.userData.radius;
                        particle.position.z = Math.sin(particle.userData.angle + time * 0.5) * particle.userData.radius;
                        if (particle.position.y > 10) {{
                            particle.position.y = 2;
                        }}
                    }} else if (particle.userData.curve) {{
                        particle.userData.t += particle.userData.speed;
                        if (particle.userData.t > 1) particle.userData.t = 0;
                        const pos = particle.userData.curve.getPoint(particle.userData.t);
                        particle.position.copy(pos);
                    }}
                }});
            }});

            // 液面波动
            scene.traverse(obj => {{
                if (obj.userData.isLiquid && waterEffectEnabled) {{
                    obj.position.y = obj.userData.originalY + Math.sin(time * 2) * 0.1;
                }}
            }});

            // 搅拌器旋转
            scene.traverse(obj => {{
                if (obj.userData.isMixer) {{
                    obj.rotation.y += obj.userData.rotationSpeed;
                }}
            }});

            controls.update();
            renderer.render(scene, camera);
        }}

        // 启动
        init();
    </script>
</body>
</html>'''
        
        return html
    
    def render(self, selected_unit: Optional[str] = None) -> str:
        """渲染 3D 场景"""
        return self.generate_threejs_html(selected_unit)


def render_advanced_3d_tab(unit_data: Dict):
    """
    渲染高级 3D 可视化选项卡（供 app.py 调用）- 交互增强版
    """
    st.markdown("""
    <style>
    .advanced-3d-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin-bottom: 20px;
    }
    .feature-card {
        background-color: #f8f9fa;
        border-left: 4px solid #007bff;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 15px;
    }
    iframe {
        border-radius: 12px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.2);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 标题
    st.markdown("""
    <div class="advanced-3d-header">
        <h2>🏭 污水处理厂 3D 数字孪生系统</h2>
        <p>基于 Three.js 的物理级真实感渲染 | 实时光影 | 动态水面 | 点击编辑</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 特性说明
    with st.expander("📖 系统特性与操作说明", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""
            <div class="feature-card">
                <h4>🎮 交互控制</h4>
                <ul>
                    <li>鼠标左键拖动 - 旋转视角</li>
                    <li>鼠标滚轮 - 缩放视图</li>
                    <li>鼠标右键拖动 - 平移场景</li>
                    <li>点击设备 - 查看详情并编辑</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown("""
            <div class="feature-card">
                <h4>✨ 视觉效果</h4>
                <ul>
                    <li>物理级材质渲染</li>
                    <li>实时光影与阴影</li>
                    <li>动态水面波动</li>
                    <li>粒子系统特效</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown("""
            <div class="feature-card">
                <h4>📊 数据联动</h4>
                <ul>
                    <li>实时甲烷排放监测</li>
                    <li>颜色编码风险等级</li>
                    <li>设备运行状态显示</li>
                    <li>点击编辑实时参数</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
    
    # 初始化引擎
    if 'plant_3d_advanced' not in st.session_state:
        st.session_state.plant_3d_advanced = Plant3DAdvanced(unit_data)
    
    if 'selected_unit_3d_advanced' not in st.session_state:
        st.session_state.selected_unit_3d_advanced = None
    
    # 处理来自3D场景的消息（参数更新）
    import streamlit.components.v1 as components
    
    # 使用JavaScript监听iframe消息
    components.html("""
    <script>
    window.addEventListener('message', function(event) {
        if (event.data && event.data.type === 'unit_parameters_updated') {
            // 将参数更新发送到Streamlit
            const params = event.data.parameters;
            const unitName = event.data.unit_name;
            
            // 使用Streamlit的session_state来传递数据
            window.parent.postMessage({
                type: 'streamlit:setComponentValue',
                value: {
                    unit_name: unitName,
                    parameters: params,
                    action: 'update_unit_params'
                }
            }, '*');
        }
    });
    </script>
    """, height=0)
    
    # 检查是否有参数更新
    if 'component_value' in st.session_state and st.session_state.component_value:
        try:
            update_data = st.session_state.component_value
            if isinstance(update_data, dict) and update_data.get('action') == 'update_unit_params':
                unit_name = update_data.get('unit_name')
                params = update_data.get('parameters', {})
                
                # 更新单元数据
                if unit_name in unit_data:
                    unit_data[unit_name]['methane_concentration'] = params.get('methane_concentration', 0.5)
                    unit_data[unit_name]['water_flow'] = params.get('water_flow', 10000)
                    unit_data[unit_name]['liquid_level'] = params.get('liquid_level', 50)
                    unit_data[unit_name]['temperature'] = params.get('temperature', 25)
                    unit_data[unit_name]['ph'] = params.get('ph', 7.0)
                    unit_data[unit_name]['enabled'] = params.get('enabled', True)
                    
                    # 生物处理区特有参数
                    if unit_name in ['厌氧池', '缺氧池', '好氧池']:
                        unit_data[unit_name]['TN_in'] = params.get('TN_in', 40)
                        unit_data[unit_name]['TN_out'] = params.get('TN_out', 15)
                        unit_data[unit_name]['COD_in'] = params.get('COD_in', 200)
                        unit_data[unit_name]['COD_out'] = params.get('COD_out', 50)
                    
                    # 污泥处理区特有参数
                    if unit_name == '污泥处理车间':
                        unit_data[unit_name]['PAM'] = params.get('PAM', 100)
                    
                    # 深度处理区特有参数
                    if unit_name == 'DF系统':
                        unit_data[unit_name]['PAC'] = params.get('PAC', 300)
                    
                    st.success(f"✅ {unit_name} 参数已更新！")
                    st.session_state.component_value = None
                    st.rerun()
        except Exception as e:
            pass
    
    engine = st.session_state.plant_3d_advanced
    
    # 生成并显示 3D 场景
    html_content = engine.render(st.session_state.selected_unit_3d_advanced)
    
    # 使用 iframe 嵌入 3D 场景
    st.components.v1.html(html_content, height=750, scrolling=False)
    
    # 添加参数编辑面板（Streamlit原生方式）
    st.divider()
    st.subheader("🎛️ 工艺区参数编辑")
    
    # 选择要编辑的工艺区
    selected_area = st.selectbox(
        "选择工艺区进行编辑",
        list(unit_data.keys()),
        key="3d_edit_area_select"
    )
    
    if selected_area:
        unit_params = unit_data[selected_area]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### 基础参数")
            
            # 甲烷浓度
            new_methane = st.number_input(
                "甲烷浓度 (mg/L)",
                value=float(unit_params.get('methane_concentration', 0.5)),
                min_value=0.0, max_value=100.0, step=0.1,
                key=f"edit_methane_{selected_area}"
            )
            
            # 流量
            new_flow = st.number_input(
                "流量 (m³/d)",
                value=float(unit_params.get('water_flow', 10000)),
                min_value=0.0, max_value=50000.0, step=100.0,
                key=f"edit_flow_{selected_area}"
            )
            
            # 液位
            new_level = st.number_input(
                "液位 (%)",
                value=float(unit_params.get('liquid_level', 50)),
                min_value=0.0, max_value=100.0, step=1.0,
                key=f"edit_level_{selected_area}"
            )
            
            # 温度
            new_temp = st.number_input(
                "温度 (°C)",
                value=float(unit_params.get('temperature', 25)),
                min_value=0.0, max_value=50.0, step=0.5,
                key=f"edit_temp_{selected_area}"
            )
            
            # pH
            new_ph = st.number_input(
                "pH",
                value=float(unit_params.get('ph', 7.0)),
                min_value=0.0, max_value=14.0, step=0.1,
                key=f"edit_ph_{selected_area}"
            )
            
            # 运行状态
            new_enabled = st.checkbox(
                "运行状态",
                value=bool(unit_params.get('enabled', True)),
                key=f"edit_enabled_{selected_area}"
            )
        
        with col2:
            # 生物处理区特有参数
            if selected_area in ["厌氧池", "缺氧池", "好氧池"]:
                st.markdown("##### 水质参数")
                
                new_tn_in = st.number_input(
                    "进水TN (mg/L)",
                    value=float(unit_params.get('TN_in', 40)),
                    min_value=0.0, max_value=100.0, step=1.0,
                    key=f"edit_tn_in_{selected_area}"
                )
                
                new_tn_out = st.number_input(
                    "出水TN (mg/L)",
                    value=float(unit_params.get('TN_out', 15)),
                    min_value=0.0, max_value=100.0, step=1.0,
                    key=f"edit_tn_out_{selected_area}"
                )
                
                new_cod_in = st.number_input(
                    "进水COD (mg/L)",
                    value=float(unit_params.get('COD_in', 200)),
                    min_value=0.0, max_value=500.0, step=5.0,
                    key=f"edit_cod_in_{selected_area}"
                )
                
                new_cod_out = st.number_input(
                    "出水COD (mg/L)",
                    value=float(unit_params.get('COD_out', 50)),
                    min_value=0.0, max_value=500.0, step=5.0,
                    key=f"edit_cod_out_{selected_area}"
                )
            
            # 污泥处理区特有参数
            elif selected_area == "污泥处理车间":
                st.markdown("##### 药剂参数")
                
                new_pam = st.number_input(
                    "PAM投加量 (kg)",
                    value=float(unit_params.get('PAM', 100)),
                    min_value=0.0, max_value=500.0, step=5.0,
                    key=f"edit_pam_{selected_area}"
                )
            
            # 深度处理区特有参数
            elif selected_area == "DF系统":
                st.markdown("##### 药剂参数")
                
                new_pac = st.number_input(
                    "PAC投加量 (kg)",
                    value=float(unit_params.get('PAC', 300)),
                    min_value=0.0, max_value=1000.0, step=10.0,
                    key=f"edit_pac_{selected_area}"
                )
            
            # 显示当前甲烷排放
            st.markdown("##### 当前状态")
            st.metric("甲烷排放", f"{unit_params.get('emission', 0):.1f} kgCO₂eq")
            st.metric("能耗", f"{unit_params.get('energy', 0):.0f} kWh")
        
        # 保存按钮
        if st.button("💾 保存参数修改", type="primary", key=f"save_btn_{selected_area}"):
            # 更新参数
            unit_params['methane_concentration'] = new_methane
            unit_params['water_flow'] = new_flow
            unit_params['liquid_level'] = new_level
            unit_params['temperature'] = new_temp
            unit_params['ph'] = new_ph
            unit_params['enabled'] = new_enabled
            
            # 更新生物处理区特有参数
            if selected_area in ["厌氧池", "缺氧池", "好氧池"]:
                unit_params['TN_in'] = new_tn_in
                unit_params['TN_out'] = new_tn_out
                unit_params['COD_in'] = new_cod_in
                unit_params['COD_out'] = new_cod_out
            
            # 更新污泥处理区特有参数
            if selected_area == "污泥处理车间":
                unit_params['PAM'] = new_pam
            
            # 更新深度处理区特有参数
            if selected_area == "DF系统":
                unit_params['PAC'] = new_pac
            
            # 重新计算甲烷排放（简化计算）
            emission_factor = 0.1 if new_enabled else 0
            base_emission = new_flow * new_methane * emission_factor * 0.001
            unit_params['emission'] = max(0, base_emission + (unit_params.get('energy', 0) * 0.3 if new_enabled else 0))
            
            st.success(f"✅ {selected_area} 参数已保存！")
            st.rerun()
    
    # 数据监控面板
    st.divider()
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_emission = sum(u.get("emission", 0) for u in unit_data.values())
    total_water = sum(u.get("water_flow", 0) for u in unit_data.values())
    total_energy = sum(u.get("energy", 0) for u in unit_data.values())
    active_units = sum(1 for u in unit_data.values() if u.get("enabled", True))
    
    with col1:
        st.metric("💨 总甲烷排放", f"{total_emission:.0f}", "kgCO₂eq/d")
    with col2:
        st.metric("💧 总处理水量", f"{total_water:.0f}", "m³/d")
    with col3:
        st.metric("⚡ 总能耗", f"{total_energy:.0f}", "kWh/d")
    with col4:
        st.metric("🔧 运行单元", f"{active_units}", f"/ {len(unit_data)}")
    
    # 排放统计
    st.subheader("📈 排放分布统计")
    
    high = sum(1 for u in unit_data.values() if u.get("emission", 0) >= 2000)
    medium = sum(1 for u in unit_data.values() if 1000 <= u.get("emission", 0) < 2000)
    normal = sum(1 for u in unit_data.values() if 500 <= u.get("emission", 0) < 1000)
    low = sum(1 for u in unit_data.values() if u.get("emission", 0) < 500)
    
    cols = st.columns(4)
    with cols[0]:
        st.markdown(f"<div style='background: #FFEBEE; padding: 15px; border-radius: 10px; text-align: center;'>"
                   f"<h3 style='color: #C62828; margin: 0;'>🔴 {high}</h3>"
                   f"<p style='margin: 5px 0 0 0; color: #666;'>高风险单元</p></div>", unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f"<div style='background: #FFF3E0; padding: 15px; border-radius: 10px; text-align: center;'>"
                   f"<h3 style='color: #EF6C00; margin: 0;'>🟠 {medium}</h3>"
                   f"<p style='margin: 5px 0 0 0; color: #666;'>中风险单元</p></div>", unsafe_allow_html=True)
    with cols[2]:
        st.markdown(f"<div style='background: #FFFDE7; padding: 15px; border-radius: 10px; text-align: center;'>"
                   f"<h3 style='color: #F9A825; margin: 0;'>🟡 {normal}</h3>"
                   f"<p style='margin: 5px 0 0 0; color: #666;'>一般单元</p></div>", unsafe_allow_html=True)
    with cols[3]:
        st.markdown(f"<div style='background: #E8F5E9; padding: 15px; border-radius: 10px; text-align: center;'>"
                   f"<h3 style='color: #2E7D32; margin: 0;'>🟢 {low}</h3>"
                   f"<p style='margin: 5px 0 0 0; color: #666;'>正常单元</p></div>", unsafe_allow_html=True)


# 兼容旧版调用
def Plant3DAdvancedEngine(unit_data):
    """兼容旧版调用的工厂函数"""
    return Plant3DAdvanced(unit_data)
