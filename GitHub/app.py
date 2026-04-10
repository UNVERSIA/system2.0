# app.py
import joblib
import plotly.express as px
import streamlit as st
import pandas as pd
import re
import numpy as np
import math
import time
import os
import sys
import json
from datetime import datetime, timedelta
from PIL import Image
import plotly.graph_objects as go
from streamlit.components.v1 import html

# 添加当前目录到系统路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入自定义模块
try:
    from carbon_calculator import CarbonCalculator
    import visualization as vis
    from plant_diagram import PlantDiagramEngine
    from factor_database import CarbonFactorDatabase
    from optimization_engine import OptimizationEngine
    from data_simulator import DataSimulator
    # 导入新的高级3D可视化模块（Three.js数字孪生）
    from plant_3d_advanced import Plant3DAdvanced, render_advanced_3d_tab
    # 导入污水处理智能助手模块
    from digital_human_agent import render_digital_human_tab
    # 导入污水处理闯关小游戏模块
    from water_treatment_game import render_water_treatment_game

    ADVANCED_3D_AVAILABLE = True
    DIGITAL_HUMAN_AVAILABLE = True
    WATER_GAME_AVAILABLE = True
except ImportError as e:
    st.error(f"导入模块错误: {e}")
    st.info("请确保所有依赖文件都在同一目录下")
    st.stop()

# 游戏模块导入失败处理
try:
    from water_treatment_game import render_water_treatment_game

    WATER_GAME_AVAILABLE = True
except ImportError:
    WATER_GAME_AVAILABLE = False

# 单独导入LSTM预测器（TensorFlow可能加载失败）
try:
    from lstm_predictor import CarbonLSTMPredictor, TENSORFLOW_AVAILABLE

    if not TENSORFLOW_AVAILABLE:
        st.sidebar.warning("⚠️ TensorFlow加载失败，预测功能将使用备用模式（基于统计方法）")
except ImportError as e:
    st.sidebar.warning(f"⚠️ LSTM预测模块加载失败: {e}")


    # 创建虚拟预测器类
    class CarbonLSTMPredictor:
        def __init__(self, *args, **kwargs):
            pass

        def load_model(self, *args, **kwargs):
            return False

        def predict(self, *args, **kwargs):
            import pandas as pd
            return pd.DataFrame({'日期': [], 'predicted_CO2eq': [], 'lower_bound': [], 'upper_bound': []})

# 页面配置
st.set_page_config(page_title="污水处理甲烷监测调控与智慧科普系统", layout="wide", page_icon="🌍")
st.header("寻清问碳：基于智能体与数字孪生的污水处理甲烷监测调控与智慧科普系统")


# ========== 智能数据适配器 ==========
def detect_and_convert_data(file_path_or_buffer):
    """
    智能数据适配器 - 自动检测并转换不同格式的数据
    支持两种格式：
    1. 标准月数据格式（系统原生格式）
    2. 用户日数据格式（如 D:\大创\kimi-code\data.xlsx）

    返回: (df, is_daily_data, conversion_info)
    """
    conversion_info = []

    # 尝试不同的header方式读取
    df = None
    header_type = None

    try:
        # 方式1: 多级表头（标准格式）
        df = pd.read_excel(file_path_or_buffer, header=[0, 1])
        header_type = "multi"
    except:
        try:
            # 方式2: 单级表头+说明行（用户格式）
            df_raw = pd.read_excel(file_path_or_buffer, header=0)
            # 检查第一行是否是说明行（包含"进水"/"出水"等字样）
            first_row = df_raw.iloc[0]
            has_indicator = any(str(v) in ['进水', '出水', '进水.1', '出水.1'] for v in first_row.values if pd.notna(v))
            if has_indicator:
                df = df_raw.iloc[1:].reset_index(drop=True)
                header_type = "user_with_header"
            else:
                df = df_raw
                header_type = "single"
        except Exception as e:
            raise ValueError(f"无法解析Excel文件: {e}")

    # 处理多级表头
    if header_type == "multi":
        new_columns = []
        for col in df.columns:
            if isinstance(col, tuple):
                main_col = str(col[0]).strip().replace('\n', ' ')
                sub_col = str(col[1]).strip().replace('\n', ' ') if not pd.isna(col[1]) else ""
                combined = f"{main_col}_{sub_col}" if sub_col else main_col
                new_columns.append(combined)
            else:
                new_columns.append(str(col).strip().replace('\n', ' '))
        df.columns = new_columns

    # 列名映射和检测
    column_mapping = {}
    is_daily_data = False

    for col in df.columns:
        col_str = str(col).strip()

        # 日期列检测
        if '日期' in col_str or 'Unnamed: 0' == col_str:
            column_mapping[col] = '日期'
        # 处理水量检测
        elif '处理水量' in col_str or 'Unnamed: 1' == col_str:
            if '/d' in col_str or 'm3/d' in col_str.lower() or 'm³/d' in col_str.lower():
                is_daily_data = True
                conversion_info.append(f"检测到日处理水量数据: {col_str}")
            column_mapping[col] = '处理水量_raw'
        # 电耗检测
        elif ('能耗' in col_str or '电耗' in col_str or 'Unnamed: 2' == col_str) and 'kWh' in col_str:
            if '/d' in col_str:
                conversion_info.append(f"检测到日电耗数据: {col_str}")
            column_mapping[col] = '电耗'
        # COD检测
        elif ('COD' in col_str or col_str == 'Unnamed: 4'):
            if '进水' in col_str or col_str == 'Unnamed: 4':
                column_mapping[col] = '进水COD'
            elif '出水' in col_str or col_str == 'Unnamed: 5':
                column_mapping[col] = '出水COD'
        # TN检测
        elif ('TN' in col_str or col_str == 'Unnamed: 10'):
            if '进水' in col_str or col_str == 'Unnamed: 10':
                column_mapping[col] = '进水TN'
            elif '出水' in col_str or col_str == 'Unnamed: 11':
                column_mapping[col] = '出水TN'
        # PAC检测
        elif ('PAC' in col_str or col_str == 'Unnamed: 12') and (
                '消耗' in col_str or '投加' in col_str or 'Unnamed' in col_str):
            if '/d' in col_str or 'kg/d' in col_str:
                is_daily_data = True
                conversion_info.append(f"检测到日PAC数据: {col_str}")
            column_mapping[col] = 'PAC_raw'
        # 次氯酸钠检测
        elif ('次氯酸钠' in col_str or col_str == 'Unnamed: 13') and (
                '消耗' in col_str or '投加' in col_str or 'Unnamed' in col_str):
            if '/d' in col_str or 'kg/d' in col_str:
                is_daily_data = True
            column_mapping[col] = '次氯酸钠_raw'
        # PAM检测
        elif (('PAM' in col_str or '污泥脱水' in col_str) or col_str == 'Unnamed: 14') and (
                '消耗' in col_str or '投加' in col_str or '药剂' in col_str or 'Unnamed' in col_str):
            if '/d' in col_str or 'kg/d' in col_str:
                is_daily_data = True
            column_mapping[col] = 'PAM_raw'

    # 应用列名映射
    df = df.rename(columns=column_mapping)

    # 处理日期列
    if '日期' in df.columns:
        if df['日期'].dtype in ['int64', 'float64']:
            # Excel序列日期
            df['日期'] = pd.to_datetime(df['日期'], unit='D', origin='1899-12-30')
        else:
            df['日期'] = pd.to_datetime(df['日期'], errors='coerce')

    # 转换数值列
    numeric_cols = ['处理水量_raw', '电耗', '进水COD', '出水COD', '进水TN', '出水TN', 'PAC_raw', '次氯酸钠_raw',
                    'PAM_raw']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 日数据 -> 月数据 转换
    if is_daily_data:
        conversion_info.append("\n📊 正在进行日数据到月数据的转换：")

        # 处理水量：日 -> 月
        if '处理水量_raw' in df.columns:
            df['处理水量(m³)'] = df['处理水量_raw'] * 30
            conversion_info.append(
                f"  • 处理水量: 日数据 × 30 = 月数据 (示例: {df['处理水量_raw'].iloc[0]:,.0f} × 30 = {df['处理水量(m³)'].iloc[0]:,.0f})")

        # 电耗：日 -> 月
        if '电耗' in df.columns:
            df['电耗(kWh)'] = df['电耗'] * 30
            conversion_info.append(
                f"  • 电耗: 日数据 × 30 = 月数据 (示例: {df['电耗'].iloc[0]:,.0f} × 30 = {df['电耗(kWh)'].iloc[0]:,.0f})")

        # PAC：日 -> 月
        if 'PAC_raw' in df.columns:
            df['PAC投加量(kg)'] = df['PAC_raw'] * 30
            conversion_info.append(
                f"  • PAC: 日数据 × 30 = 月数据 (示例: {df['PAC_raw'].iloc[0]:,.1f} × 30 = {df['PAC投加量(kg)'].iloc[0]:,.1f})")

        # 次氯酸钠：日 -> 月
        if '次氯酸钠_raw' in df.columns:
            df['次氯酸钠投加量(kg)'] = df['次氯酸钠_raw'] * 30
            conversion_info.append(f"  • 次氯酸钠: 日数据 × 30 = 月数据")

        # PAM：日 -> 月
        if 'PAM_raw' in df.columns:
            df['PAM投加量(kg)'] = df['PAM_raw'] * 30
            conversion_info.append(f"  • PAM: 日数据 × 30 = 月数据")
    else:
        # 已经是月数据，直接重命名
        if '处理水量_raw' in df.columns:
            df['处理水量(m³)'] = df['处理水量_raw']
        if '电耗' in df.columns:
            df['电耗(kWh)'] = df['电耗']
        if 'PAC_raw' in df.columns:
            df['PAC投加量(kg)'] = df['PAC_raw']
        if '次氯酸钠_raw' in df.columns:
            df['次氯酸钠投加量(kg)'] = df['次氯酸钠_raw']
        if 'PAM_raw' in df.columns:
            df['PAM投加量(kg)'] = df['PAM_raw']
        conversion_info.append("✓ 检测到标准月数据格式，无需单位转换")

    # 重命名COD和TN列
    column_rename = {
        '进水COD': '进水COD(mg/L)',
        '出水COD': '出水COD(mg/L)',
        '进水TN': '进水TN(mg/L)',
        '出水TN': '出水TN(mg/L)'
    }
    df = df.rename(columns=column_rename)

    # 删除包含关键NaN的行
    df = df.dropna(subset=['日期', '处理水量(m³)'], how='any')

    # 清理临时列
    for col in ['处理水量_raw', '电耗', 'PAC_raw', '次氯酸钠_raw', 'PAM_raw']:
        if col in df.columns:
            df = df.drop(columns=[col])

    return df, is_daily_data, '\n'.join(conversion_info)


# 初始化session_state
def initialize_session_state():
    """初始化所有session_state变量"""
    if 'df' not in st.session_state:
        st.session_state.df = None
    if 'df_calc' not in st.session_state:
        st.session_state.df_calc = None
    if 'selected_month' not in st.session_state:
        st.session_state.selected_month = None
    if 'unit_data' not in st.session_state:
        st.session_state.unit_data = {
            "粗格栅": {"water_flow": 10000.0, "energy": 1500.0, "emission": 450.0, "enabled": True},
            "提升泵房": {"water_flow": 10000.0, "energy": 3500.0, "emission": 1050.0, "enabled": True},
            "细格栅": {"water_flow": 10000.0, "energy": 800.0, "emission": 240.0, "enabled": True},
            "曝气沉砂池": {"water_flow": 10000.0, "energy": 1200.0, "emission": 360.0, "enabled": True},
            "膜格栅": {"water_flow": 10000.0, "energy": 1000.0, "emission": 300.0, "enabled": True},
            "厌氧池": {"water_flow": 10000.0, "energy": 3000.0, "TN_in": 40.0, "TN_out": 30.0, "COD_in": 200.0,
                       "COD_out": 180.0, "emission": 1200.0, "enabled": True},
            "缺氧池": {"water_flow": 10000.0, "energy": 3500.0, "TN_in": 30.0, "TN_out": 20.0, "COD_in": 180.0,
                       "COD_out": 100.0, "emission": 1500.0, "enabled": True},
            "好氧池": {"water_flow": 10000.0, "energy": 5000.0, "TN_in": 20.0, "TN_out": 15.0, "COD_in": 100.0,
                       "COD_out": 50.0, "emission": 1800.0, "enabled": True},
            "MBR膜池": {"water_flow": 10000.0, "energy": 4000.0, "emission": 1200.0, "enabled": True},
            "污泥处理车间": {"water_flow": 500.0, "energy": 2000.0, "PAM": 100.0, "emission": 800.0, "enabled": True},
            "DF系统": {"water_flow": 10000.0, "energy": 2500.0, "PAC": 300.0, "emission": 1000.0, "enabled": True},
            "催化氧化": {"water_flow": 10000.0, "energy": 1800.0, "emission": 700.0, "enabled": True},
            "鼓风机房": {"water_flow": 0.0, "energy": 2500.0, "emission": 900.0, "enabled": True},
            "消毒接触池": {"water_flow": 10000.0, "energy": 1000.0, "emission": 400.0, "enabled": True},
            "除臭系统": {"water_flow": 0.0, "energy": 1800.0, "emission": 600.0, "enabled": True}
        }
    if 'custom_calculations' not in st.session_state:
        st.session_state.custom_calculations = {}
    if 'emission_data' not in st.session_state:
        st.session_state.emission_data = {}
    if 'df_selected' not in st.session_state:
        st.session_state.df_selected = None
    if 'selected_unit' not in st.session_state:
        st.session_state.selected_unit = "粗格栅"
    if 'animation_active' not in st.session_state:
        st.session_state.animation_active = True
    if 'formula_results' not in st.session_state:
        st.session_state.formula_results = {}
    if 'flow_position' not in st.session_state:
        st.session_state.flow_position = 0
    if 'water_quality' not in st.session_state:
        st.session_state.water_quality = {
            "COD": {"in": 200, "out": 50},
            "TN": {"in": 40, "out": 15},
            "SS": {"in": 150, "out": 10},
            "flow_rate": 10000
        }
    if 'last_clicked_unit' not in st.session_state:
        st.session_state.last_clicked_unit = None
    if 'unit_details' not in st.session_state:
        st.session_state.unit_details = {}
    if 'flow_data' not in st.session_state:
        st.session_state.flow_data = {
            "flow_rate": 10000,
            "direction": "right"
        }
    if 'unit_status' not in st.session_state:
        st.session_state.unit_status = {unit: "正常运行" for unit in st.session_state.unit_data.keys()}
    if 'plant_3d_engine' not in st.session_state:
        st.session_state.plant_3d_engine = None
    if 'animation_time_3d' not in st.session_state:
        st.session_state.animation_time_3d = 0.0
    if 'selected_unit_3d' not in st.session_state:
        st.session_state.selected_unit_3d = None

    if 'lstm_predictor' not in st.session_state:
        st.session_state.lstm_predictor = None

    # 修复因子数据库初始化问题
    if 'factor_db' not in st.session_state:
        try:
            # 确保目录存在
            os.makedirs("data", exist_ok=True)
            # 直接导入并初始化 CarbonFactorDatabase
            from factor_database import CarbonFactorDatabase
            st.session_state.factor_db = CarbonFactorDatabase()
            # 检查是否是回退模式
            if hasattr(st.session_state.factor_db, 'is_fallback') and st.session_state.factor_db.is_fallback:
                st.warning("⚠️ 当前处于回退模式，使用默认因子值。某些功能可能受限。")
        except Exception as e:
            st.error(f"初始化甲烷因子数据库失败: {e}")

            # 创建一个完整的回退数据库实例
            class FallbackCarbonFactorDatabase:
                def __init__(self):
                    self.is_fallback = True

                def get_factor(self, factor_type, region="中国", date=None):
                    # 默认因子值 - 使用提供的最新数据
                    factors = {
                        "电力": 0.5568 if date and "2022" in date else 0.5366,
                        "PAC": 1.62,
                        "PAM": 1.5,
                        "次氯酸钠": 0.92,
                        "臭氧": 0.8,
                        "N2O": 273,
                        "CH4": 27.9,
                        "沼气发电": 2.5,
                        "光伏发电": 0.85,
                        "热泵技术": 1.2,
                        "污泥资源化": 0.3
                    }
                    return factors.get(factor_type, 0.0)

                def get_factor_history(self, factor_type, region="中国", start_date=None, end_date=None):
                    # 返回空的DataFrame
                    return pd.DataFrame(columns=['factor_type', 'factor_value', 'unit', 'region',
                                                 'effective_date', 'expiry_date', 'data_source', 'description'])

                def update_factor(self, factor_type, factor_value, unit, region, effective_date,
                                  expiry_date=None, data_source="用户输入", description="",
                                  change_reason="手动更新"):
                    st.warning("回退模式下无法更新因子")

                def fetch_latest_electricity_factor(self, region="中国"):
                    return None, None

                def get_regional_factors(self, factor_type, date=None):
                    return {}

                def export_factors(self, export_path, format="csv"):
                    # 创建默认因子数据
                    default_factors = [
                        ("电力", 0.5366, "kgCO2/kWh", "中国", "2021-01-01", "2021-12-31", "生态环境部公告2024年第12号",
                         "2021年全国电力平均二氧化碳排放因子"),
                        ("电力", 0.5568, "kgCO2/kWh", "中国", "2022-01-01", "2022-12-31", "生态环境部公告2024年第33号",
                         "2022年全国电力平均二氧化碳排放因子"),
                        ("CH4", 27.9, "kgCO2/kgCH4", "通用", "2020-01-01", None, "IPCC AR6", "甲烷全球变暖潜能值(GWP)"),
                        ("N2O", 273, "kgCO2/kgN2O", "通用", "2020-01-01", None, "IPCC AR6",
                         "氧化亚氮全球变暖潜能值(GWP)"),
                        ("PAC", 1.62, "kgCO2/kg", "通用", "2020-01-01", None, "T/CAEPI 49-2022", "聚合氯化铝排放因子"),
                        ("PAM", 1.5, "kgCO2/kg", "通用", "2020-01-01", None, "T/CAEPI 49-2022", "聚丙烯酰胺排放因子"),
                        ("次氯酸钠", 0.92, "kgCO2/kg", "通用", "2020-01-01", None, "T/CAEPI 49-2022",
                         "次氯酸钠排放因子"),
                        ("臭氧", 0.8, "kgCO2/kg", "通用", "2020-01-01", None, "研究文献", "臭氧排放因子"),
                        ("沼气发电", 2.5, "kgCO2eq/kWh", "通用", "2020-01-01", None, "研究文献",
                         "沼气发电甲烷抵消因子"),
                        ("光伏发电", 0.85, "kgCO2eq/kWh", "通用", "2020-01-01", None, "研究文献",
                         "光伏发电甲烷抵消因子"),
                        ("热泵技术", 1.2, "kgCO2eq/kWh", "通用", "2020-01-01", None, "研究文献",
                         "热泵技术甲烷抵消因子"),
                        ("污泥资源化", 0.3, "kgCO2eq/kgDS", "通用", "2020-01-01", None, "研究文献",
                         "污泥资源化甲烷抵消因子")
                    ]

                    df = pd.DataFrame(default_factors, columns=[
                        'factor_type', 'factor_value', 'unit', 'region',
                        'effective_date', 'expiry_date', 'data_source', 'description'
                    ])

                    if format.lower() == "csv":
                        df.to_csv(export_path, index=False, encoding='utf-8-sig')
                    elif format.lower() == "excel":
                        df.to_excel(export_path, index=False)

                    return df

            st.session_state.factor_db = FallbackCarbonFactorDatabase()
            st.warning("⚠️ 当前处于回退模式，使用默认因子值。某些功能可能受限。")

    if 'optimization_engine' not in st.session_state:
        st.session_state.optimization_engine = None
    if 'tech_comparison_data' not in st.session_state:
        st.session_state.tech_comparison_data = pd.DataFrame({
            '技术名称': ['厌氧消化产沼', '光伏发电', '高效曝气', '热泵技术', '污泥干化'],
            '减排量_kgCO2eq': [15000, 8000, 6000, 4500, 3000],
            '投资成本_万元': [500, 300, 200, 150, 100],
            '回收期_年': [5, 8, 4, 6, 7],
            '适用性': ['高', '中', '高', '中', '低'],
            '甲烷减排贡献率_%': [25, 15, 20, 12, 8],
            '能源中和率_%': [30, 40, 10, 15, 5]
        })
    if 'component_value' not in st.session_state:
        st.session_state.component_value = None
    if 'carbon_offset_data' not in st.session_state:
        st.session_state.carbon_offset_data = {
            "沼气发电": 0,
            "光伏发电": 0,
            "热泵技术": 0,
            "污泥资源化": 0
        }
    if 'optimization_scenarios' not in st.session_state:
        st.session_state.optimization_scenarios = {
            "基准情景": {"aeration_adjust": 0, "pac_adjust": 0, "sludge_ratio": 0.5},
            "节能情景": {"aeration_adjust": -15, "pac_adjust": -10, "sludge_ratio": 0.6},
            "减排情景": {"aeration_adjust": -20, "pac_adjust": -20, "sludge_ratio": 0.7}
        }
    if 'selected_scenario' not in st.session_state:
        st.session_state.selected_scenario = "基准情景"

    if 'prediction_made' not in st.session_state:
        st.session_state.prediction_made = False

    if 'historical_data' not in st.session_state:
        st.session_state.historical_data = pd.DataFrame()
    if 'prediction_data' not in st.session_state:
        st.session_state.prediction_data = pd.DataFrame()


# 初始化session state
initialize_session_state()


# 工艺流程图HTML组件
def create_plant_diagram(selected_unit=None, flow_position=0, flow_rate=10000, animation_active=True):
    # 创建动态水流效果
    flow_animation = "animation: flow 10s linear infinite;" if animation_active else ""

    # 创建工艺流程图HTML
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>污水处理厂工艺流程</title>
        <style>
            .plant-container {{
                position: relative;
                width: 100%;
                height: 900px;
                background-color: #e6f7ff;
                border: 2px solid #0078D7;
                border-radius: 10px;
                overflow: hidden;
                font-family: Arial, sans-serif;
            }}

            .unit {{
                position: absolute;
                border: 2px solid #2c3e50;
                border-radius: 8px;
                padding: 10px;
                text-align: center;
                cursor: pointer;
                transition: all 0.3s;
                font-weight: bold;
                color: white;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                z-index: 10;
            }}

            .unit:hover {{
                transform: scale(1.05);
                box-shadow: 0 5px 15px rgba(0,0,0,0.3);
                z-index: 20;
            }}

            .unit.active {{
                border: 3px solid #FFD700;
                box-shadow: 0 0 10px #FFD700;
            }}

            .unit.disabled {{
                background-color: #cccccc !important;
                opacity: 0.7;
            }}

            .unit-name {{
                font-size: 15px;
                margin-bottom: 5px;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.7);
            }}

            .unit-status {{
                font-size: 12px;
                padding: 2px 5px;
                border-radius: 3px;
                background-color: rgba(255,255,255,0.2);
            }}

            .pre-treatment {{ background-color: #3498db; }}
            .bio-treatment {{ background-color: #2ecc71; }}
            .advanced-treatment {{ background-color: #e74c3c; }}
            .sludge-treatment {{ background-color: #f39c12; }}
            .auxiliary {{ background-color: #9b59b6; }}
            .effluent-area {{ background-color: #1abc9c; }}

            .flow-line {{
                position: absolute;
                background-color: #1e90ff;
                z-index: 5;
            }}

            .water-flow {{
                position: absolute;
                background: linear-gradient(90deg, transparent, rgba(30, 144, 255, 0.8), transparent);
                {flow_animation}
                z-index: 6;
                border-radius: 3px;
            }}

            .gas-flow {{
                position: absolute;
                background: linear-gradient(90deg, transparent, rgba(169, 169, 169, 0.8), transparent);
                {flow_animation}
                z-index: 6;
                border-radius: 3px;
            }}

            .sludge-flow {{
                position: absolute;
                background: linear-gradient(90deg, transparent, rgba(139, 69, 19, 0.8), transparent);
                {flow_animation}
                z-index: 6;
                border-radius: 3px;
            }}

            .air-flow {{
                position: absolute;
                background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.6), transparent);
                {flow_animation}
                z-index: 6;
                border-radius: 3px;
            }}

            .flow-arrow {{
                position: absolute;
                width: 0;
                height: 0;
                border-style: solid;
                z-index: 7;
            }}

            .flow-label {{
                position: absolute;
                font-size: 13px;
                background: rgba(255, 255, 255, 0.7);
                padding: 2px 5px;
                border-radius: 3px;
                z-index: 8;
            }}

            .special-flow-label {{
                position: absolute;
                color: black;
                font-size: 15px;
                background:none;
            }}

            .particle {{
                position: absolute;
                width: 4px;
                height: 4px;
                border-radius: 50%;
                background-color: #1e90ff;
                z-index: 9;
                opacity: 0.7;
            }}

            .sludge-particle {{
                background-color: #8B4513;
            }}

            .gas-particle {{
                background-color: #A9A9A9;
            }}

            .waste-particle {{
                background-color: #FF6347;
            }}

            .air-particle {{
                background-color: #FFFFFF;
            }}

            .info-panel {{
                position: absolute;
                bottom: 10px;
                left: 10px;
                background-color: rgba(255, 255, 255, 0.9);
                padding: 10px;
                border-radius: 5px;
                border: 1px solid #ccc;
                z-index: 100;
                font-size: 12px;
                max-width: 250px;
            }}

            .bio-deodorization {{
                position: absolute;
                text-align: center;
                font-weight: bold;
                color: #333;
                z-index: 10;
            }}

            /* 区域标注样式 */
            .region-box {{
                position: absolute;
                border: 3px solid;
                border-radius: 10px;
                z-index: 3;
                opacity: 0.3;
            }}

            .region-label {{
                position: absolute;
                font-weight: bold;
                font-size: 16px;
                color: black;
                text-shadow: 1px 1px 2px white;
                z-index: 4;
            }}

            .region-pre-treatment {{
                background-color: rgba(52, 152, 219, 0.3);
                border-color: #3498db;
            }}

            .region-bio-treatment {{
                background-color: rgba(46, 204, 113, 0.3);
                border-color: #2ecc71;
            }}

            .region-advanced-treatment {{
                background-color: rgba(231, 76, 60, 0.3);
                border-color: #e74c3c;
            }}

            .region-sludge-treatment {{
                background-color: rgba(243, 156, 18, 0.3);
                border-color: #f39c12;
            }}

            .region-effluent-area {{
                background-color: rgba(26, 188, 156, 0.3);
                border-color: #1abc9c;
            }}

            @keyframes flow {{
                0% {{ background-position: -100% 0; }}
                100% {{ background-position: 200% 0; }}
            }}

            @keyframes moveParticle {{
                0% {{ transform: translateX(0); }}
                100% {{ transform: translateX(50px); }}
            }}
        </style>
    </head>
    <body>
        <div class="plant-container">
            <!-- 区域标注框 -->
            <!-- 预处理区 -->
            <div class="region-box region-pre-treatment" style="top: 126px; left: 110px; width: 783px; height: 142px;"></div>
            <div class="region-label" style="top: 133px; left: 120px;">预处理区</div>

            <!-- 生物处理区 -->
            <div class="region-box region-bio-treatment" style="top: 400px; left: 490px; width: 415px; height: 140px;"></div>
            <div class="region-label" style="top: 405px; left: 500px;">生物处理区</div>

            <!-- 深度处理区 -->
            <div class="region-box region-advanced-treatment" style="top: 620px; left: 500px; width: 370px; height: 140px;"></div>
            <div class="region-label" style="top: 735px; left: 520px;">深度处理区</div>

            <!-- 泥处理区 -->
            <div class="region-box region-sludge-treatment" style="top: 400px; left: 270px; width: 170px; height: 200px;"></div>
            <div class="region-label" style="top: 405px; left: 280px;">泥处理区</div>

            <!-- 出水区 -->
            <div class="region-box region-effluent-area" style="top: 640px; left: 180px; width: 250px; height: 100px;"></div>
            <div class="region-label" style="top: 650px; left: 190px;">出水区</div>

            <!-- 新增除臭系统区域标注框 -->
            <div class="region-box region-effluent-area" style="top: 282px; left: 26px; width: 135px; height: 160px;"></div>
            <div class="region-label" style="top: 286px; left: 35px;">出水区</div>

            <!-- 工艺单元 -->
            <!-- 第一行：预处理区 -->
            <div class="unit pre-treatment {'disabled' if not st.session_state.unit_data['粗格栅']['enabled'] else ''}" style="top: 160px; left: 150px; width: 90px; height: 60px;" onclick="selectUnit('粗格栅')">
                <div class="unit-name">粗格栅</div>
                <div class="unit-status">{st.session_state.unit_status['粗格栅']}</div>
            </div>

            <div class="unit pre-treatment {'disabled' if not st.session_state.unit_data['提升泵房']['enabled'] else ''}" style="top: 160px; left: 300px; width: 90px; height: 60px;" onclick="selectUnit('提升泵房')">
                <div class="unit-name">提升泵房</div>
                <div class="unit-status">{st.session_state.unit_status['提升泵房']}</div>
            </div>

            <div class="unit pre-treatment {'disabled' if not st.session_state.unit_data['细格栅']['enabled'] else ''}" style="top: 160px; left: 450px; width: 90px; height: 60px;" onclick="selectUnit('细格栅')">
                <div class="unit-name">细格栅</div>
                <div class="unit-status">{st.session_state.unit_status['细格栅']}</div>
            </div>

            <div class="unit pre-treatment {'disabled' if not st.session_state.unit_data['曝气沉砂池']['enabled'] else ''}" style="top: 160px; left: 600px; width: 90px; height: 60px;" onclick="selectUnit('曝气沉砂池')">
                <div class="unit-name">曝气沉砂池</div>
                <div class="unit-status">{st.session_state.unit_status['曝气沉砂池']}</div>
            </div>

            <div class="unit pre-treatment {'disabled' if not st.session_state.unit_data['膜格栅']['enabled'] else ''}" style="top: 160px; left: 750px; width: 90px; height: 60px;" onclick="selectUnit('膜格栅')">
                <div class="unit-name">膜格栅</div>
                <div class="unit-status">{st.session_state.unit_status['膜格栅']}</div>
            </div>

            <!-- 第二行：生物处理区（中行） -->
            <div class="unit bio-treatment {'disabled' if not st.session_state.unit_data['厌氧池']['enabled'] else ''}" style="top: 430px; left: 810px; width: 50px; height: 60px;" onclick="selectUnit('厌氧池')">
                <div class="unit-name">厌氧池</div>
                <div class="unit-status">{st.session_state.unit_status['厌氧池']}</div>
            </div>

            <div class="unit bio-treatment {'disabled' if not st.session_state.unit_data['缺氧池']['enabled'] else ''}" style="top: 430px; left: 750px; width: 50px; height: 60px;" onclick="selectUnit('缺氧池')">
                <div class="unit-name">缺氧池</div>
                <div class="unit-status">{st.session_state.unit_status['缺氧池']}</div>
            </div>

            <div class="unit bio-treatment {'disabled' if not st.session_state.unit_data['好氧池']['enabled'] else ''}" style="top: 430px; left: 690px; width: 50px; height: 60px;" onclick="selectUnit('好氧池')">
                <div class="unit-name">好氧池</div>
                <div class="unit-status">{st.session_state.unit_status['好氧池']}</div>
            </div>

            <div class="unit bio-treatment {'disabled' if not st.session_state.unit_data['MBR膜池']['enabled'] else ''}" style="top: 430px; left: 520px; width: 90px; height: 60px;" onclick="selectUnit('MBR膜池')">
                <div class="unit-name">MBR膜池</div>
                <div class="unit-status">{st.session_state.unit_status['MBR膜池']}</div>
            </div>

            <div class="unit sludge-treatment {'disabled' if not st.session_state.unit_data['污泥处理车间']['enabled'] else ''}" style="top: 430px; left: 300px; width: 90px; height: 60px;" onclick="selectUnit('污泥处理车间')">
                <div class="unit-name">污泥处理车间</div>
                <div class="unit-status">{st.session_state.unit_status['污泥处理车间']}</div>
            </div>

            <!-- 中行最右侧：鼓风机房 -->
            <div class="unit auxiliary {'disabled' if not st.session_state.unit_data['鼓风机房']['enabled'] else ''}" style="top: 430px; left: 930px; width: 90px; height: 60px;" onclick="selectUnit('鼓风机房')">
                <div class="unit-name">鼓风机房</div>
                <div class="unit-status">{st.session_state.unit_status['鼓风机房']}</div>
            </div>

            <!-- 除臭系统单元 -->
            <div class="unit effluent-area {'disabled' if not st.session_state.unit_data['除臭系统']['enabled'] else ''}" style="top: 310px; left: 50px; width: 70px; height: 40px;" onclick="selectUnit('除臭系统')">
                <div class="unit-name">除臭系统</div>
                <div class="unit-status">{st.session_state.unit_status['除臭系统']}</div>
            </div>

            <!-- 第三行：深度处理区 -->
            <div class="unit advanced-treatment {'disabled' if not st.session_state.unit_data['DF系统']['enabled'] else ''}" style="top: 650px; left: 520px; width: 90px; height: 60px;" onclick="selectUnit('DF系统')">
                <div class="unit-name">DF系统</div>
                <div class="unit-status">{st.session_state.unit_status['DF系统']}</div>
            </div>

            <div class="unit advanced-treatment {'disabled' if not st.session_state.unit_data['催化氧化']['enabled'] else ''}" style="top: 650px; left: 740px; width: 90px; height: 60px;" onclick="selectUnit('催化氧化')">
                <div class="unit-name">催化氧化</div>
                <div class="unit-status">{st.session_state.unit_status['催化氧化']}</div>
            </div>

            <!-- 出水区单元 -->
            <div class="unit effluent-area {'disabled' if not st.session_state.unit_data['消毒接触池']['enabled'] else ''}" style="top: 660px; left: 325px; width: 76px; height: 40px;" onclick="selectUnit('消毒接触池')">
                <div class="unit-name">消毒接触池</div>
                <div class="unit-status">{st.session_state.unit_status['消毒接触池']}</div>
            </div>

            <!-- 水流线条与箭头 -->

            <!-- 污泥流向 -->
            <div class="flow-line" style="top: 410px; left: 460px; width: 5px; height: 120px; transform: rotate(90deg); background-color: #8B4513;"></div>
            <div class="flow-line" style="top: 540px; left: 322px; width: 68px; height: 5px; transform: rotate(90deg); background-color: #8B4513;"></div>
            <div class="flow-arrow" style="top: 573px; left: 349px; width: 0; height: 0; border-style: solid;border-width: 7px 7px 0 7px;border-color: #8B4513 transparent transparent transparent;"></div>
            <div class="flow-arrow" style="top: 463px; left: 412px; width: 0; height: 0; border-style: solid;border-width: 7px 7px 7px 0;border-color: transparent #8B4513 transparent transparent;"></div>

            <!-- 鼓风机到MBR膜池的气流 -->
            <div class="flow-line" style="top: 470px; left: 770px; width: 180px; height: 5px; background-color: #999999; opacity: 0.6;"></div>

            <!-- 水流动画 -->
            <div class="water-flow" style="top: 197px; left: 80px; width: 66px; height: 7px;"></div>
            <div class="water-flow" style="top: 197px; left: 270px; width: 30px; height: 7px;"></div>
            <div class="water-flow" style="top: 197px; left: 411px; width: 40px; height: 7px;"></div>
            <div class="water-flow" style="top: 197px; left: 560px; width: 42px; height: 7px;"></div>
            <div class="water-flow" style="top: 197px; left: 709px; width: 42px; height: 7px;"></div>
            <div class="water-flow" style="top: 197px; left: 100px; width: 30px; height: 7px; transform: rotate(180deg);"></div>
            <div class="water-flow" style="top: 197px; left: 290px; width: 30px; height: 7px; transform: rotate(180deg);"></div>
            <div class="water-flow" style="top: 197px; left: 431px; width: 30px; height: 7px; transform: rotate(180deg);"></div>
            <div class="water-flow" style="top: 197px; left: 580px; width: 30px; height: 7px; transform: rotate(180deg);"></div>
            <div class="water-flow" style="top: 197px; left: 729px; width: 30px; height: 7px; transform: rotate(180deg);"></div>
            <div class="water-flow" style="top: 467px; left: 629px; width: 66px; height: 7px;"></div>
            <div class="water-flow" style="top: 197px; left: 850px; width: 56px; height: 7px;"></div>
            <div class="water-flow" style="top: 197px; left: 896px; width: 8px; height: 250px;"></div>
            <div class="water-flow" style="top: 443px; left: 874px; width: 30px; height: 7px;"></div>
            <div class="water-flow" style="top: 685px; left: 850px; width: 50px; height: 7px;"></div>

            <div class="water-flow" style="top: 500px; left: 896px; width: 8px; height: 190px;"></div>
            <div class="water-flow" style="top: 500px; left: 880px; width: 20px; height: 7px;"></div>

            <div class="water-flow" style="top: 685px; left: 626px; width: 125px; height: 7px;"></div>
            <div class="water-flow" style="top: 685px; left: 305px; width: 220px; height: 7px;"></div>
            <div class="water-flow" style="top: 685px; left: 205px; width: 220px; height: 7px;"></div>

            <div class="water-flow" style="top: 510px; left: 575px; width: 8px; height: 200px;"></div>

            <!-- 污泥流动画 -->
            <div class="sludge-flow" style="top: 120px; left: 207px; width: 5px; height: 40px;"></div>
            <div class="sludge-flow" style="top: 120px; left: 508px; width: 5px; height: 40px;"></div>
            <div class="sludge-flow" style="top: 120px; left: 658px; width: 5px; height: 40px;"></div>
            <div class="sludge-flow" style="top: 120px; left: 807px; width: 5px; height: 40px;"></div>
            <div class="flow-arrow" style="top: 123px; left: 204px; width: 0; height: 0; border-style: solid; border-width: 0 6px 6px 6px; border-color: transparent transparent #8B4513 transparent;"></div>
            <div class="flow-arrow" style="top: 123px; left: 505px; width: 0; height: 0; border-style: solid; border-width: 0 6px 6px 6px; border-color: transparent transparent #8B4513 transparent;"></div>
            <div class="flow-arrow" style="top: 123px; left: 655px; width: 0; height: 0; border-style: solid; border-width: 0 6px 6px 6px; border-color: transparent transparent #8B4513 transparent;"></div>
            <div class="flow-arrow" style="top: 123px; left: 804px; width: 0; height: 0; border-style: solid; border-width: 0 6px 6px 6px; border-color: transparent transparent #8B4513 transparent;"></div>

            <!-- 臭气流动画 -->
            <div class="gas-flow" style="top: 243px; left: 202px; width: 6px; height: 100px;"></div>
            <div class="gas-flow" style="top: 243px; left: 503px; width: 6px; height: 100px;"></div>
            <div class="gas-flow" style="top: 243px; left: 652px; width: 6px; height: 100px;"></div>
            <div class="gas-flow" style="top: 243px; left: 802px; width: 6px; height: 190px;"></div>
            <div class="gas-flow" style="top: 340px; left: 350px; width: 6px; height: 100px;"></div>
            <div class="gas-flow" style="top: 340px; left: 570px; width: 6px; height: 100px;"></div>
            <div class="gas-flow" style="top: 340px; left: 35px; width: 800px; height: 4px;"></div>
            <div class="gas-flow" style="top: 340px; left: 660px; width: 150px; height: 3px;"></div>
            <div class="gas-flow" style="top: 352px; left: 90px; width: 6px; height: 61px;"></div>

            <!-- 鼓风机到MBR膜池的气流动画 -->
            <div class="air-flow" style="top: 900px; left: 770px; width: 230px; height: 5px;"></div>

            <!-- 水流箭头 -->
            <div class="flow-arrow" style="top: 193px; left: 136px; border-width: 8px 0 8px 8px; border-color: transparent transparent transparent #1e90ff;"></div>
            <div class="flow-arrow" style="top: 193px; left: 293px; border-width: 8px 0 8px 8px; border-color: transparent transparent transparent #1e90ff;"></div>
            <div class="flow-arrow" style="top: 193px; left: 442px; border-width: 8px 0 8px 8px; border-color: transparent transparent transparent #1e90ff;"></div>
            <div class="flow-arrow" style="top: 193px; left: 593px; border-width: 8px 0 8px 8px; border-color: transparent transparent transparent #1e90ff;"></div>
            <div class="flow-arrow" style="top: 193px; left: 741px; border-width: 8px 0 8px 8px; border-color: transparent transparent transparent #1e90ff;"></div>
            <div class="flow-arrow" style="top: 642px; left: 572px; border-width: 8px 8px 0 8px; border-color: #1e90ff transparent transparent transparent;"></div>

            <div class="flow-arrow" style="top: 464px; left: 633px; border-width: 8px 8px 8px 0; border-color: transparent #1e90ff transparent transparent;"></div>
            <div class="flow-arrow" style="top: 439px; left: 882px; border-width: 8px 8px 8px 0; border-color: transparent #1e90ff transparent transparent;"></div>
            <div class="flow-arrow" style="top: 496px; left: 882px; border-width: 8px 8px 8px 0; border-color: transparent #1e90ff transparent transparent;"></div>
            <div class="flow-arrow" style="top: 682px; left: 423px; border-width: 8px 8px 8px 0; border-color: transparent #1e90ff transparent transparent;"></div>
            <div class="flow-arrow" style="top: 682px; left: 222px; border-width: 8px 8px 8px 0; border-color: transparent #1e90ff transparent transparent;"></div>

            <div class="flow-arrow" style="top: 682px; left: 732px; border-width: 8px 8px 8px 0; border-color: transparent #1e90ff transparent transparent; transform: rotate(180deg);"></div>

            <!-- 臭气箭头 -->
            <div class="flow-arrow" style="top: 410px; left: 85px; border-width: 8px 8px 0 8px; border-color: #A9A9A9 transparent transparent transparent;"></div>
            <div class="flow-arrow" style="top: 334px; left: 144px; border-width: 8px 8px 8px 0; border-color: transparent #A9A9A9 transparent transparent;"></div>
            <div class="flow-arrow" style="top: 464px; left: 883px; border-width: 8px 8px 8px 0; border-color: transparent #A9A9A9 transparent transparent;"></div>

            <!-- 鼓风机到MBR膜池的箭头（白灰色透明） -->
            <div class="flow-arrow" style="top: 450px; left: 775px; border-width: 5px 0 5px 8px; border-color: transparent transparent transparent rgba(255, 255, 255, 0.8);"></div>

            <!-- 流向标签 -->
            <div class="flow-label" style="top: 190px; left: 40px;">污水</div>
            <div class="flow-label" style="top: 540px; left: 308px;">污泥</div>
            <div class="flow-label" style="top: 435px; left: 440px;">污泥S5</div>
            <div class="flow-label" style="top: 290px; left: 180px;">臭气G1</div>
            <div class="flow-label" style="top: 290px; left: 480px;">臭气G2</div>
            <div class="flow-label" style="top: 290px; left: 635px;">臭气G3</div>
            <div class="flow-label" style="top: 290px; left: 780px;">臭气G4</div>
            <div class="flow-label" style="top: 370px; left: 780px;">臭气G5</div>
            <div class="flow-label" style="top: 370px; left: 545px;">臭气G6</div>
            <div class="flow-label" style="top: 370px; left: 325px;">臭气G7</div>
            <div class="flow-label" style="top: 415px; left: 46px;background:none;">处理后的臭气排放</div>
            <div class="flow-label" style="top: 645px; left: 672px;">浓水</div>
            <div class="flow-label" style="top: 710px; left: 672px;">臭氧</div>

            <!-- 排出物标签 -->
            <div class="flow-label" style="top: 100px; left: 185px; background: #FF6347;">栅渣S1</div>
            <div class="flow-label" style="top: 100px; left: 485px; background: #FF6347;">栅渣S2</div>
            <div class="flow-label" style="top: 100px; left: 635px; background: #FF6347;">沉渣S3</div>
            <div class="flow-label" style="top: 100px; left: 785px; background: #FF6347;">栅渣S4</div>
            <div class="flow-label" style="top: 580px; left: 340px; background: none;">外运</div>
            <div class="flow-label" style="top: 675px; left: 190px; background: none;">排河</div>
            <div class="special-flow-label" style="top: 520px; left: 750px;">MBR生物池</div>

            <!-- 动态粒子 -->
            <div class="particle" id="particle1" style="top: 197px; left: 80px;"></div>
            <div class="particle" id="particle2" style="top: 197px; left: 411px;"></div>
            <div class="particle" id="particle3" style="top: 197px; left: 560px;"></div>
            <div class="particle" id="particle4" style="top: 197px; left: 709px;"></div>
            <div class="particle" id="particle5" style="top: 197px; left: 270px;"></div>
            <div class="particle" id="particle6" style="top: 685px; left: 660px;"></div>
            <div class="particle" id="particle7" style="top: 685px; left: 675px;"></div>

            <!-- 信息面板 -->
            <div class="info-panel">
                <h3>当前水流状态</h3>
                <p>流量: {flow_rate} m³/d</p>
                <p>COD: {st.session_state.water_quality["COD"]["in"]} → {st.session_state.water_quality["COD"]["out"]} mg/L</p>
                <p>TN: {st.session_state.water_quality["TN"]["in"]} → {st.session_state.water_quality["TN"]["out"]} mg/L</p>
            </div>
        </div>

        <script>
            // 设置选中单元
            function selectUnit(unitName) {{
                // 高亮显示选中的单元
                document.querySelectorAll('.unit').forEach(unit => {{
                    unit.classList.remove('active');
                }});

                // 找到并高亮选中的单元
                const units = document.querySelectorAll('.unit');
                units.forEach(unit => {{
                    if (unit.querySelector('.unit-name').textContent === unitName) {{
                        unit.classList.add('active');
                    }}
                }});

                // 发送单元选择信息到Streamlit
                if (window.Streamlit) {{
                    window.Streamlit.setComponentValue(unitName);
                }}
            }}

            // 初始化选中单元
            document.addEventListener('DOMContentLoaded', function() {{
                const units = document.querySelectorAll('.unit');
                units.forEach(unit => {{
                    if (unit.querySelector('.unit-name').textContent === "{selected_unit}") {{
                        unit.classList.add('active');
                    }}
                }});

                // 粒子动画
                function animateParticles() {{
                    for (let i = 1; i <= 12; i++) {{
                        const particle = document.getElementById(`particle${{i}}`);
                        if (particle) {{
                            const top = Math.random() * 5;
                            const left = Math.random() * 50;
                            particle.style.animation = `moveParticle ${{1 + Math.random()}}s linear infinite`;
                        }}
                    }}
                    requestAnimationFrame(animateParticles);
                }}
                animateParticles();
            }});
        </script>
    </body>
    </html>
    """
    return html_content


# 侧边栏：数据输入与处理
with st.sidebar:
    st.header("数据输入与设置")
    # 上传运行数据（表格）
    data_file = st.file_uploader("上传运行数据（Excel）", type=["xlsx"])

    if data_file:
        try:
            # 使用智能数据适配器自动检测并转换数据格式
            with st.spinner("正在智能识别数据格式..."):
                df, is_daily_data, conversion_info = detect_and_convert_data(data_file)

            # 显示转换信息
            if conversion_info:
                with st.expander("📋 数据格式识别结果", expanded=True):
                    st.info(conversion_info)
                    if is_daily_data:
                        st.success("✅ 已自动将日数据转换为月数据（乘以30天）")

            # 确保必需的列存在
            required_columns = ["日期", "处理水量(m³)", "电耗(kWh)"]
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                st.error(f"错误：缺少必需列 {missing_cols}，请检查Excel文件格式")
                st.stop()

            # 删除包含NaN的行
            df = df.dropna(subset=required_columns)

            if len(df) == 0:
                st.error("错误：没有有效数据，请检查Excel文件内容")
                st.stop()

            # 创建年月选择
            df["年月"] = df["日期"].dt.strftime("%Y年%m月")

            unique_months = df["年月"].unique().tolist()

            st.success(f"数据加载成功！共{len(df)}条历史记录用于预测")

            # 月份选择器
            selected_month = st.selectbox(
                "选择月份",
                unique_months,
                index=len(unique_months) - 1 if unique_months else 0
            )

            df_selected = df[df["年月"] == selected_month]
            st.session_state.df = df
            st.session_state.df_selected = df_selected
            st.session_state.selected_month = selected_month

        except Exception as e:
            st.error(f"数据加载错误: {str(e)}")
            st.stop()

    # 工艺优化参数
    st.header("工艺优化模拟")
    aeration_adjust = st.slider("曝气时间调整（%）", -30, 30, 0)
    pac_adjust = st.slider("PAC投加量调整（%）", -20, 20, 0)
    sludge_ratio = st.slider("污泥回流比", 0.3, 0.8, 0.5, 0.05)

    # 动态效果控制
    st.header("动态效果设置")
    st.session_state.animation_active = st.checkbox("启用动态水流效果", value=True)
    st.session_state.flow_data["flow_rate"] = st.slider("水流速度", 1000, 20000, 10000)

    # 高级功能设置
    st.header("高级功能设置")

    # 因子库管理
    if st.button("更新电力排放因子"):
        try:
            latest_factor, year = st.session_state.factor_db.fetch_latest_electricity_factor()
            if latest_factor:
                st.success(f"已更新{year}年电力排放因子: {latest_factor} kgCO2/kWh")
            else:
                st.error("获取最新因子失败，请检查网络连接或手动更新")
        except Exception as e:
            st.error(f"更新电力排放因子失败: {e}")

    # 数据生成
    if st.button("生成模拟数据"):
        with st.spinner("正在生成模拟数据..."):
            simulator = DataSimulator()
            simulated_data = simulator.generate_simulated_data()
            st.session_state.df = simulated_data
            st.session_state.df_selected = simulated_data.tail(30)  # 使用最近30天数据
            st.success("模拟数据生成完成！")

    if st.button("重置甲烷因子数据库"):
        try:
            # 删除数据库文件
            import os

            if os.path.exists("data/carbon_factors.db"):
                os.remove("data/carbon_factors.db")
                st.success("数据库已重置，将在下次运行时重新初始化")
            else:
                st.info("数据库文件不存在，无需重置")
        except Exception as e:
            st.error(f"重置数据库失败: {e}")

# 主界面使用选项卡组织内容
tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "3D水厂仿真", "工艺流程仿真", "甲烷足迹追踪", "甲烷账户管理", "优化与决策",
    "甲烷排放预测", "减排技术分析", "因子库管理", "🤖数字人助手", "🎮AI实验室·污水处理闯关"
])

with tab0:
    st.header("3D 水厂数字孪生虚拟仿真")

    # 显示模式说明
    st.divider()

    # 使用Three.js数字孪生3D可视化（已删除Plotly 3D）
    render_advanced_3d_tab(st.session_state.unit_data)

with tab1:
    st.header("2D水厂工艺流程仿真")

    # 创建两列布局
    col1, col2 = st.columns([3, 1])

    with col1:
        # 渲染工艺流程图
        plant_html = create_plant_diagram(
            selected_unit=st.session_state.get('selected_unit', "粗格栅"),
            flow_rate=st.session_state.flow_data["flow_rate"],
            animation_active=st.session_state.animation_active
        )
        html(plant_html, height=920)

        # 处理单元选择事件
        selected_unit = st.session_state.get('last_clicked_unit', "粗格栅")
        if st.session_state.get('component_value'):
            selected_unit = st.session_state.component_value
            st.session_state.last_clicked_unit = selected_unit
            st.session_state.selected_unit = selected_unit
            st.experimental_rerun()

        # 显示当前选中单元
        if selected_unit:
            st.success(f"当前选中单元: {selected_unit}")

    with col2:
        # 根据点击事件或下拉框选择单元
        if st.session_state.get('last_clicked_unit'):
            selected_unit = st.session_state.last_clicked_unit
        else:
            # 下拉框选项中包含除臭系统
            selected_unit = st.selectbox(
                "选择工艺单元",
                list(st.session_state.unit_data.keys()),
                key="unit_selector"
            )
        st.subheader(f"{selected_unit} - 参数设置")
        unit_params = st.session_state.unit_data[selected_unit]
        # 单元开关
        unit_enabled = st.checkbox("启用单元", value=unit_params["enabled"], key=f"{selected_unit}_enabled")
        st.session_state.unit_data[selected_unit]["enabled"] = unit_enabled

        # 更新单元状态文字
        status_text = "运行中" if unit_enabled else "已停用"
        st.session_state.unit_status[selected_unit] = status_text

        # 通用参数
        if "water_flow" in unit_params:
            unit_params["water_flow"] = st.number_input(
                "处理水量(m³)",
                value=unit_params["water_flow"],
                min_value=0.0
            )
        if "energy" in unit_params:
            unit_params["energy"] = st.number_input(
                "能耗(kWh)",
                value=unit_params["energy"],
                min_value=0.0
            )
        # 特殊参数
        if selected_unit in ["厌氧池", "缺氧池", "好氧池"]:
            unit_params["TN_in"] = st.number_input(
                "进水TN(mg/L)",
                value=unit_params["TN_in"],
                min_value=0.0
            )
            unit_params["TN_out"] = st.number_input(
                "出水TN(mg/L)",
                value=unit_params["TN_out"],
                min_value=0.0
            )
            unit_params["COD_in"] = st.number_input(
                "进水COD(mg/L)",
                value=unit_params["COD_in"],
                min_value=0.0
            )
            unit_params["COD_out"] = st.number_input(
                "出水COD(mg/L)",
                value=unit_params["COD_out"],
                min_value=0.0
            )
        if selected_unit == "DF系统":
            unit_params["PAC"] = st.number_input(
                "PAC投加量(kg)",
                value=unit_params["PAC"],
                min_value=0.0
            )
            st.info("次氯酸钠投加量: 100 kg/d")
        if selected_unit == "催化氧化":
            st.info("臭氧投加量: 80 kg/d")
        if selected_unit == "污泥处理车间":
            unit_params["PAM"] = st.number_input(
                "PAM投加量(kg)",
                value=unit_params["PAM"],
                min_value=0.0
            )
        st.subheader(f"{selected_unit} - 当前状态")
        st.metric("甲烷排放量", f"{unit_params['emission']:.2f} kgCO2eq")
        st.metric("运行状态", status_text)
        if "water_flow" in unit_params:
            st.metric("处理水量", f"{unit_params['water_flow']:.0f} m³")
        if "energy" in unit_params:
            st.metric("能耗", f"{unit_params['energy']:.0f} kWh")
        # 显示单元详情 - 使用可扩展区域
        if selected_unit not in st.session_state.unit_details:
            st.session_state.unit_details[selected_unit] = {
                "description": "",
                "notes": ""
            }
        with st.expander("单元详情", expanded=True):
            st.session_state.unit_details[selected_unit]["description"] = st.text_area(
                "单元描述",
                value=st.session_state.unit_details[selected_unit]["description"],
                height=100
            )
            st.session_state.unit_details[selected_unit]["notes"] = st.text_area(
                "运行笔记",
                value=st.session_state.unit_details[selected_unit]["notes"],
                height=150
            )
        # 显示单元说明
        if selected_unit == "粗格栅":
            st.info("粗格栅主要用于去除污水中的大型固体杂质，防止后续设备堵塞")
        elif selected_unit == "提升泵房":
            st.info("提升泵房将污水提升到足够高度，以便重力流通过后续处理单元")
        elif selected_unit == "厌氧池":
            st.info("厌氧池进行有机物分解和磷的释放，产生少量甲烷")
        elif selected_unit == "好氧池":
            st.info("好氧池进行有机物氧化和硝化反应，是N2O主要产生源")
        elif selected_unit == "DF系统":
            st.info("DF系统进行深度过滤，需要投加PAC等化学药剂")
        elif selected_unit == "污泥处理车间":
            st.info("污泥处理车间进行污泥浓缩和脱水，需要投加PAM等絮凝剂")
        elif selected_unit == "除臭系统":
            st.info("除臭系统处理全厂产生的臭气，减少恶臭排放")
        elif selected_unit == "消毒接触池":
            st.info("消毒接触池对处理后的水进行消毒，确保水质安全")

with tab2:
    st.header("甲烷足迹追踪与评估")
    # 初始化calculator对象
    calculator = CarbonCalculator()

    # 如果有选中的数据，进行甲烷核算计算
    if 'df_selected' in st.session_state and st.session_state.df_selected is not None:
        df_selected = st.session_state.df_selected
        try:
            df_calc = calculator.calculate_direct_emissions(df_selected)
            df_calc = calculator.calculate_indirect_emissions(df_calc)
            df_calc = calculator.calculate_unit_emissions(df_calc)
            st.session_state.df_calc = df_calc
            # 计算单元排放数据（包含除臭系统）
            st.session_state.emission_data = {
                "预处理区": df_calc['pre_CO2eq'].sum(),
                "生物处理区": df_calc['bio_CO2eq'].sum(),
                "深度处理区": df_calc['depth_CO2eq'].sum(),
                "泥处理区": df_calc['sludge_CO2eq'].sum(),
                "出水区": df_calc['effluent_CO2eq'].sum(),
                "除臭系统": df_calc['deodorization_CO2eq'].sum()  # 新增除臭系统
            }
        except Exception as e:
            st.error(f"甲烷核算计算错误: {str(e)}")
            st.stop()

    # 工艺全流程甲烷排放热力图
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("工艺全流程甲烷排放热力图")
        if st.session_state.emission_data:
            heatmap_fig = vis.create_heatmap_overlay(st.session_state.emission_data)
            st.plotly_chart(heatmap_fig)
        else:
            st.warning("请先上传运行数据")
    with col2:
        st.subheader("甲烷动态追踪图谱")
        if 'df_calc' in st.session_state and st.session_state.df_calc is not None:
            sankey_fig = vis.create_sankey_diagram(st.session_state.df_calc)
            st.plotly_chart(sankey_fig)
        else:
            st.warning("请先上传运行数据")

    # 甲烷排放效率排行榜
    if 'df_calc' in st.session_state and st.session_state.df_calc is not None:
        st.subheader("甲烷排放效率排行榜")
        eff_fig = vis.create_efficiency_ranking(st.session_state.df_calc)
        st.plotly_chart(eff_fig)

with tab3:
    st.header("甲烷账户管理")
    if 'df_calc' in st.session_state and st.session_state.df_calc is not None:
        df_calc = st.session_state.df_calc
        # 碳账户明细（包含除臭系统）
        st.subheader("甲烷账户收支明细（当月）")
        account_df = pd.DataFrame({
            "工艺单元": ["预处理区", "生物处理区", "深度处理区", "泥处理区", "出水区", "除臭系统"],
            "甲烷流入(kgCO2eq)": [
                df_calc['energy_CO2eq'].sum() * 0.3193,
                df_calc['energy_CO2eq'].sum() * 0.4453,
                df_calc['energy_CO2eq'].sum() * 0.1155 + df_calc['chemicals_CO2eq'].sum(),
                df_calc['energy_CO2eq'].sum() * 0.0507,
                df_calc['energy_CO2eq'].sum() * 0.0672,
                df_calc['energy_CO2eq'].sum() * 0.0267  # 除臭系统能耗占比
            ],
            "甲烷流出(kgCO2eq)": [
                df_calc['pre_CO2eq'].sum(),
                df_calc['bio_CO2eq'].sum(),
                df_calc['depth_CO2eq'].sum(),
                df_calc['sludge_CO2eq'].sum(),
                df_calc['effluent_CO2eq'].sum(),
                df_calc['deodorization_CO2eq'].sum()  # 除臭系统排放
            ],
            "净排放(kgCO2eq)": [
                df_calc['pre_CO2eq'].sum() - df_calc['energy_CO2eq'].sum() * 0.3193,
                df_calc['bio_CO2eq'].sum() - df_calc['energy_CO2eq'].sum() * 0.4453,
                df_calc['depth_CO2eq'].sum() - (
                        df_calc['energy_CO2eq'].sum() * 0.1155 + df_calc['chemicals_CO2eq'].sum()),
                df_calc['sludge_CO2eq'].sum() - df_calc['energy_CO2eq'].sum() * 0.0507,
                df_calc['effluent_CO2eq'].sum() - df_calc['energy_CO2eq'].sum() * 0.0672,
                df_calc['deodorization_CO2eq'].sum() - df_calc['energy_CO2eq'].sum() * 0.0267  # 除臭系统净排放
            ]
        })


        # 添加样式
        def color_negative_red(val):
            color = 'red' if val < 0 else 'green'
            return f'color: {color}'


        styled_account = account_df.style.map(color_negative_red, subset=['净排放(kgCO2eq)'])
        st.dataframe(styled_account, height=300)

        # 自定义公式计算器
        st.subheader("自定义公式计算器")
        st.markdown("""
        **使用说明**:
        1. 在下方输入公式名称和表达式
        2. 公式中可以使用以下变量（单位）:
           - 处理水量(m³): `water_flow`
           - 能耗(kWh): `energy`
           - 药耗(kg): `chemicals`
           - PAC投加量(kg): `pac`
           - PAM投加量(kg): `pam`
           - 次氯酸钠投加量(kg): `naclo`
           - 进水TN(mg/L): `tn_in`
           - 出水TN(mg/L): `tn_out`
           - 进水COD(mg/L): `cod_in`
           - 出水COD(mg/L): `cod_out`
        3. 支持数学运算和函数: `+`, `-`, `*`, `/`, `**`, `sqrt()`, `log()`, `exp()`, `sin()`, `cos()`等
        """)
        col1, col2 = st.columns([1, 1])
        with col1:
            formula_name = st.text_input("公式名称", "单位水处理甲烷排放")
            formula_expression = st.text_area("公式表达式", "energy * 0.9419 / water_flow")
            if st.button("保存公式"):
                if formula_name and formula_expression:
                    st.session_state.custom_calculations[formula_name] = formula_expression
                    st.success(f"公式 '{formula_name}' 已保存！")
                else:
                    st.warning("请填写公式名称和表达式")
        with col2:
            if st.session_state.custom_calculations:
                selected_formula = st.selectbox("选择公式", list(st.session_state.custom_calculations.keys()))
                st.code(f"{selected_formula}: {st.session_state.custom_calculations[selected_formula]}")

        # 公式计算区域
        if st.session_state.custom_calculations:
            st.subheader("公式计算")
            # 创建变量输入表
            variables = {
                "water_flow": "处理水量(m³)",
                "energy": "能耗(kWh)",
                "chemicals": "药耗总量(kg)",
                "pac": "PAC投加量(kg)",
                "pam": "PAM投加量(kg)",
                "naclo": "次氯酸钠投加量(kg)",
                "tn_in": "进水TN(mg/L)",
                "tn_out": "出水TN(mg/L)",
                "cod_in": "进水COD(mg/L)",
                "cod_out": "出水COD(mg/L)"
            }
            col1, col2, col3 = st.columns(3)
            var_values = {}
            # 动态生成变量输入
            for i, (var, label) in enumerate(variables.items()):
                if i % 3 == 0:
                    with col1:
                        var_values[var] = st.number_input(label, value=0.0, key=f"var_{var}")
                elif i % 3 == 1:
                    with col2:
                        var_values[var] = st.number_input(label, value=0.0, key=f"var_{var}")
                else:
                    with col3:
                        var_values[var] = st.number_input(label, value=0.0, key=f"var_{var}")

            # 计算按钮
            if st.button("计算公式"):
                try:
                    # 安全计算环境
                    safe_env = {
                        "__builtins__": None,
                        "math": math,
                        "sqrt": math.sqrt,
                        "log": math.log,
                        "exp": math.exp,
                        "sin": math.sin,
                        "cos": math.cos,
                        "tan": math.tan,
                        "pi": math.pi,
                        "e": math.e
                    }
                    # 添加变量值
                    safe_env.update(var_values)
                    # 获取当前公式
                    formula = st.session_state.custom_calculations[selected_formula]
                    # 计算结果
                    result = eval(formula, {"__builtins__": None}, safe_env)
                    # 保存结果
                    st.session_state.formula_results[selected_formula] = {
                        "result": result,
                        "variables": var_values.copy()
                    }
                    st.success(f"计算结果: {result:.4f}")
                except Exception as e:
                    st.error(f"计算错误: {str(e)}")

            # 显示历史计算结果
            if st.session_state.formula_results:
                st.subheader("历史计算结果")
                for formula_name, result_data in st.session_state.formula_results.items():
                    st.markdown(f"**{formula_name}**: {result_data['result']:.4f}")
                    st.json(result_data["variables"])

with tab4:
    st.header("优化与决策支持")

    # 在tab4（优化与决策）中添加工艺调整建议：
    if st.session_state.df is not None:
        # 确保calculator已初始化
        calculator = CarbonCalculator()
        # 添加工艺调整建议
        st.subheader("工艺调整建议")
        adjustments = calculator.generate_process_adjustments(st.session_state.df)

        if adjustments:
            for adj in adjustments:
                with st.expander(f"{adj['单元']}: {adj['问题']}"):
                    st.write(f"**建议**: {adj['建议']}")
                    st.write(f"**预期减排**: {adj['预期减排']}")
        else:
            st.info("当前运行状况良好，无需重大调整")

    if 'df_calc' in st.session_state and st.session_state.df_calc is not None:
        df_calc = st.session_state.df_calc
        df = st.session_state.df
        df_selected = st.session_state.df_selected

        # 异常识别与优化建议
        st.subheader("异常识别与优化建议")
        if len(df) >= 3 and 'total_CO2eq' in df_calc.columns and '处理水量(m³)' in df.columns:
            # 计算历史平均值（使用处理水量加权）
            total_water = df['处理水量(m³)'].sum()
            if total_water > 0:
                historical_mean = df_calc['total_CO2eq'].sum() / total_water
            else:
                historical_mean = 0
            current_water = df_selected['处理水量(m³)'].sum()
            if current_water > 0:
                current_total = df_calc['total_CO2eq'].sum() / current_water
            else:
                current_total = 0

            if historical_mean > 0 and current_total > 1.5 * historical_mean:
                st.warning(f"⚠️ 异常预警：当月单位水量甲烷排放（{current_total:.4f} kgCO2eq/m³）超历史均值50%！")
                # 识别主要问题区域（包含除臭系统）甲烷
                unit_emissions = {
                    "预处理区": df_calc['pre_CO2eq'].sum() / current_water,
                    "生物处理区": df_calc['bio_CO2eq'].sum() / current_water,
                    "深度处理区": df_calc['depth_CO2eq'].sum() / current_water,
                    "泥处理区": df_calc['sludge_CO2eq'].sum() / current_water,
                    "出水区": df_calc['effluent_CO2eq'].sum() / current_water,
                    "除臭系统": df_calc['deodorization_CO2eq'].sum() / current_water
                }
                max_unit = max(unit_emissions, key=unit_emissions.get)
                st.error(f"主要问题区域: {max_unit} (排放强度: {unit_emissions[max_unit]:.4f} kgCO2eq/m³)")

                # 针对性建议
                if max_unit == "生物处理区":
                    st.info("优化建议：")
                    st.write("- 检查曝气系统效率，优化曝气量")
                    st.write("- 调整污泥回流比，优化生物处理效率")
                    st.write("- 监控进水水质波动，避免冲击负荷")
                elif max_unit == "深度处理区":
                    st.info("优化建议：")
                    st.write("- 优化化学药剂投加量，避免过量投加")
                    st.write("- 检查混合反应效果，提高药剂利用率")
                    st.write("- 考虑使用更环保的替代药剂")
                elif max_unit == "预处理区":
                    st.info("优化建议：")
                    st.write("- 优化格栅运行频率，降低能耗")
                    st.write("- 检查水泵效率，考虑变频控制")
                    st.write("- 加强进水监控，避免大颗粒物进入")
                elif max_unit == "出水区" or max_unit == "除臭系统":  # 除臭系统与出水区建议类似
                    st.info("优化建议：")
                    st.write("- 优化消毒剂投加量，减少化学药剂使用")
                    st.write("- 检查消毒接触时间，提高消毒效率")
                    st.write("- 考虑紫外线消毒等低碳替代方案")
                else:
                    st.info("优化建议：")
                    st.write("- 优化污泥脱水工艺参数")
                    st.write("- 检查脱水设备运行效率")
                    st.write("- 考虑污泥资源化利用途径")
            else:
                st.success("✅ 当月甲烷排放水平正常")
        else:
            st.info("数据量不足，无法进行异常识别")

        # 工艺优化效果模拟
        st.subheader("工艺优化效果模拟")
        if not df_selected.empty:
            # 如果用户没有调整参数，使用推荐的优化场景
            if aeration_adjust == 0 and pac_adjust == 0 and sludge_ratio == 0.5:
                st.info("💡 当前显示推荐优化场景：曝气调整-15%，PAC投加-10%，请在侧边栏调整参数查看其他场景效果")
                effective_aeration_adjust = -15  # 推荐减少15%曝气
                effective_pac_adjust = -10  # 推荐减少10%PAC投加
                effective_sludge_ratio = 0.6  # 推荐提高污泥回流比
            else:
                effective_aeration_adjust = aeration_adjust
                effective_pac_adjust = pac_adjust
                effective_sludge_ratio = sludge_ratio

            # 修正优化逻辑：负值表示减少，正值表示增加
            # 曝气调整对生物处理区排放的影响（曝气减少15%，排放减少约12%）
            aeration_efficiency_factor = 1 + effective_aeration_adjust / 100 * 0.8  # 0.8是效率系数
            optimized_bio = df_calc['bio_CO2eq'].sum() * aeration_efficiency_factor

            # PAC调整对深度处理区排放的影响（PAC减少10%，排放减少8%）
            pac_efficiency_factor = 1 + effective_pac_adjust / 100 * 0.8  # 0.8是效率系数
            optimized_depth = df_calc['depth_CO2eq'].sum() * pac_efficiency_factor

            # 污泥回流比优化影响生物处理效率
            if effective_sludge_ratio > 0.5:
                sludge_optimization_factor = 1 - (effective_sludge_ratio - 0.5) * 0.2  # 回流比提高时减少排放
            else:
                sludge_optimization_factor = 1 + (0.5 - effective_sludge_ratio) * 0.3  # 回流比降低时增加排放
            optimized_bio = optimized_bio * sludge_optimization_factor

            optimized_total = (df_calc['total_CO2eq'].sum()
                               - df_calc['bio_CO2eq'].sum() + optimized_bio
                               - df_calc['depth_CO2eq'].sum() + optimized_depth)

            # 创建优化效果图表 - 所有文字改为黑色
            opt_fig = go.Figure()
            opt_fig.add_trace(go.Bar(
                x=["优化前", "优化后"],
                y=[df_calc['total_CO2eq'].sum(), optimized_total],
                marker_color=["#EF553B", "#00CC96"],
                text=[f"{emission:.1f}" for emission in [df_calc['total_CO2eq'].sum(), optimized_total]],
                textposition='auto',
                textfont=dict(color='black')  # 确保文字为黑色
            ))
            opt_fig.update_layout(
                title=f"优化效果：月度减排{(df_calc['total_CO2eq'].sum() - optimized_total):.1f} kgCO2eq",
                title_font=dict(color="black"),  # 标题文字颜色改为黑色
                yaxis_title="总甲烷排放（kgCO2eq/月）",
                yaxis_title_font=dict(color="black"),  # Y轴标题文字颜色改为黑色
                font=dict(size=14, color="black"),  # 整体文字颜色改为黑色
                plot_bgcolor="rgba(245, 245, 245, 1)",
                paper_bgcolor="rgba(245, 245, 245, 1)",
                height=400,
                # 确保坐标轴标签颜色为黑色
                xaxis=dict(
                    tickfont=dict(color="black"),
                    title_font=dict(color="black")
                ),
                yaxis=dict(
                    tickfont=dict(color="black"),
                    title_font=dict(color="black")
                )
            )
            # 添加减排量标注 - 文字颜色改为黑色
            opt_fig.add_annotation(
                x=1, y=optimized_total,
                text=f"减排: {df_calc['total_CO2eq'].sum() - optimized_total:.1f} kg",
                showarrow=True,
                arrowhead=1,
                ax=0,
                ay=-40,
                font=dict(color="black")  # 标注文字颜色改为黑色
            )
            st.plotly_chart(opt_fig)

            # 显示优化细节
            st.subheader("优化措施详情")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("曝气时间调整", f"{effective_aeration_adjust:+}%",
                          delta=f"生物处理区减排: {df_calc['bio_CO2eq'].sum() - optimized_bio:.1f} kgCO2eq",
                          delta_color="inverse")
            with col2:
                st.metric("PAC投加量调整", f"{effective_pac_adjust:+}%",
                          delta=f"深度处理区减排: {df_calc['depth_CO2eq'].sum() - optimized_depth:.1f} kgCO2eq",
                          delta_color="inverse")
        else:
            st.warning("没有选中数据，无法进行优化模拟")
    else:
        st.warning("请先上传运行数据")

with tab5:
    st.header("甲烷排放趋势预测")

    # 第一部分：加载预训练模型
    st.subheader("1. 模型管理")
    load_col1, load_col2 = st.columns([1, 3])
    with load_col1:
        # 在tab5中的"加载预训练模型"按钮逻辑
        if st.button("加载预训练模型", key="load_model_btn"):
            try:
                # 初始化LSTM预测器
                if st.session_state.lstm_predictor is None:
                    st.session_state.lstm_predictor = CarbonLSTMPredictor()

                # 获取当前文件所在目录的绝对路径
                current_dir = os.path.dirname(os.path.abspath(__file__))
                # 构建模型文件的绝对路径
                models_dir = os.path.join(current_dir, "models")

                # 确保目录存在
                os.makedirs(models_dir, exist_ok=True)

                # 尝试多种可能的模型文件路径（使用绝对路径）
                possible_model_paths = [
                    os.path.join(models_dir, "carbon_lstm_model.keras"),
                    os.path.join(models_dir, "carbon_lstm_model.h5"),
                    os.path.join(models_dir, "carbon_lstm.keras"),
                    os.path.join(models_dir, "carbon_lstm.h5")
                ]

                model_loaded = False
                loaded_path = None

                # 尝试按优先级顺序加载模型
                for model_path in possible_model_paths:
                    if os.path.exists(model_path):
                        try:
                            st.session_state.lstm_predictor.load_model(model_path)
                            if st.session_state.lstm_predictor.model is not None:
                                model_loaded = True
                                loaded_path = model_path
                                break
                        except Exception as e:
                            st.warning(f"尝试加载模型 {model_path} 失败: {str(e)}")
                            continue

                # 如果模型文件不存在，尝试从GitHub项目结构加载
                if not model_loaded:
                    # 尝试从GitHub项目结构加载模型
                    github_model_paths = [
                        os.path.join(current_dir, "甲烷足迹追踪系统", "models", "carbon_lstm_model.keras"),
                        os.path.join(current_dir, "甲烷足迹追踪系统", "models", "carbon_lstm_model.h5"),
                        os.path.join(current_dir, "甲烷足迹追踪系统", "models", "carbon_lstm.keras"),
                        os.path.join(current_dir, "甲烷足迹追踪系统", "models", "carbon_lstm.h5")
                    ]

                    for model_path in github_model_paths:
                        if os.path.exists(model_path):
                            try:
                                st.session_state.lstm_predictor.load_model(model_path)
                                if st.session_state.lstm_predictor.model is not None:
                                    model_loaded = True
                                    loaded_path = model_path
                                    break
                            except Exception as e:
                                st.warning(f"尝试加载模型 {model_path} 失败: {str(e)}")
                                continue

                if model_loaded:
                    st.success(f"✅ 预训练模型加载成功！从 {loaded_path} 加载")
                else:
                    # 如果直接加载失败，尝试使用create_pretrained_model.py创建默认模型
                    try:
                        from create_pretrained_model import create_pretrained_model

                        with st.spinner("未找到预训练模型，正在创建默认模型..."):
                            create_pretrained_model()
                            # 尝试加载新创建的模型
                            model_path = os.path.join(models_dir, "carbon_lstm_model.keras")
                            st.session_state.lstm_predictor.load_model(model_path)
                            if st.session_state.lstm_predictor.model is not None:
                                st.success("✅ 已创建并加载默认预训练模型！")
                            else:
                                st.warning("⚠️ 创建默认模型失败，请先训练模型")
                    except Exception as e:
                        st.warning(f"⚠️ 未找到预训练模型，请先训练模型: {str(e)}")
            except Exception as e:
                st.error(f"加载模型失败: {str(e)}")
                # 确保预测器状态为未加载
                st.session_state.lstm_predictor.model = None

    with load_col2:
        st.info("加载已训练好的LSTM模型进行预测。如果模型不存在，将创建一个新的未训练模型。")

    # 第二部分：训练新模型
    st.subheader("2. 模型训练")
    train_col1, train_col2 = st.columns([1, 3])
    with train_col1:
        if st.button("训练新模型", key="train_model_btn"):
            if st.session_state.df is not None and len(st.session_state.df) >= 30:
                with st.spinner("正在训练新模型，这可能需要几分钟..."):
                    try:
                        # 确保数据已计算甲烷排放
                        calculator = CarbonCalculator()
                        df_with_emissions = calculator.calculate_direct_emissions(st.session_state.df)
                        df_with_emissions = calculator.calculate_indirect_emissions(df_with_emissions)
                        df_with_emissions = calculator.calculate_unit_emissions(df_with_emissions)

                        # 初始化预测器并训练
                        if st.session_state.lstm_predictor is None:
                            st.session_state.lstm_predictor = CarbonLSTMPredictor()

                        # 获取当前文件所在目录的绝对路径
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        models_dir = os.path.join(current_dir, "models")
                        save_path = os.path.join(models_dir, "carbon_lstm_model.keras")

                        # 训练模型 - 使用新的保存路径
                        training_history = st.session_state.lstm_predictor.train(
                            df_with_emissions,
                            'total_CO2eq',
                            epochs=50,
                            validation_split=0.2,
                            save_path=save_path  # 使用绝对路径
                        )

                        st.success("✅ 模型训练完成并已保存！")

                    except Exception as e:
                        st.error(f"模型训练失败: {str(e)}")
                        st.error("详细错误信息: " + str(e))
            else:
                st.warning("请先上传足够的数据（至少30天记录）")

    with train_col2:
        st.info("使用当前数据训练新的LSTM模型。需要先上传数据并确保数据包含足够的日期记录。")

    # 在预测按钮代码块后添加以下内容（确保不在任何列内）
    if st.session_state.get('training_history') is not None:
        st.subheader("训练历史")
        history_fig = vis.create_training_history_chart(st.session_state.training_history)
        st.plotly_chart(history_fig, use_container_width=True)

    # 添加模型状态检查
    if st.session_state.lstm_predictor is not None and st.session_state.lstm_predictor.model is not None:
        # 检查模型输入形状是否与特征数量匹配
        expected_features = len(st.session_state.lstm_predictor.feature_columns)
        actual_input_shape = st.session_state.lstm_predictor.model.input_shape
        if actual_input_shape[2] != expected_features:
            st.warning(
                f"⚠️ 模型输入形状不匹配: 预期 {expected_features} 个特征，但模型有 {actual_input_shape[2]} 个输入特征")
            st.info("建议重新训练模型以确保输入形状正确")

    # 第三部分：进行预测
    st.subheader("3. 预测设置")
    predict_col1, predict_col2 = st.columns([1, 3])

    with predict_col1:
        # 动态预测月份选择 - 支持12/24/36个月
        prediction_months = st.selectbox(
            "选择预测时长",
            options=[12, 24, 36],
            index=0,
            help="选择要预测的未来月份数"
        )

        # 基于历史数据计算预测日期范围
        # 历史数据为2018-2026年，预测从2027年1月开始
        last_historical_date = pd.Timestamp('2026-12-31')

        # 计算预测起始日期（2027年1月）
        forecast_start = pd.Timestamp('2027-01-01')
        # 计算预测结束日期
        forecast_end = forecast_start + pd.DateOffset(months=prediction_months - 1)

        st.info(
            f"预测范围: {forecast_start.strftime('%Y年%m月')} 至 {forecast_end.strftime('%Y年%m月')}（{prediction_months}个月）")
        st.caption(f"基于历史数据（2018年1月-2026年12月）进行预测")

        # 定义预测天数
        prediction_days = prediction_months * 30

    # 进行预测
    if st.button("进行预测", key="predict_btn"):
        # 确保预测器已初始化
        if st.session_state.lstm_predictor is None:
            st.session_state.lstm_predictor = CarbonLSTMPredictor()

        # 尝试加载模型
        model_loaded = False
        if st.session_state.lstm_predictor.model is None:
            try:
                # 尝试加载预训练模型 - 修复路径问题
                current_dir = os.path.dirname(os.path.abspath(__file__))

                # 检查是否在GitHub项目结构下
                github_project_dir = os.path.join(current_dir, "甲烷足迹追踪系统")
                if os.path.exists(github_project_dir):
                    current_dir = github_project_dir

                models_dir = os.path.join(current_dir, "models")
                model_path = os.path.join(models_dir, "carbon_lstm_model.keras")

                # 确保目录存在
                os.makedirs(models_dir, exist_ok=True)

                # 如果模型文件不存在，尝试创建默认模型
                if not os.path.exists(model_path):
                    st.info("未找到预训练模型，正在创建默认模型...")
                    try:
                        from create_pretrained_model import create_pretrained_model

                        create_pretrained_model()
                        st.success("默认模型创建成功！")
                    except Exception as e:
                        st.error(f"创建默认模型失败: {str(e)}")
                        st.warning("将使用简单预测方法")

                # 尝试加载模型
                model_loaded = st.session_state.lstm_predictor.load_model(model_path)
                if model_loaded:
                    st.success("✅ 预训练模型加载成功！")
                    st.info("🤖 使用LSTM深度学习模型进行预测")
                else:
                    st.warning("⚠️ 预训练模型加载失败，将使用简单预测方法")
            except Exception as e:
                st.error(f"模型加载失败: {str(e)}")
                st.info("将使用简单预测方法")

        with st.spinner(f"正在进行未来{prediction_months}个月预测..."):
            try:
                if st.session_state.df is not None:
                    # 确保数据已计算碳排放
                    calculator = CarbonCalculator()
                    df_with_emissions = calculator.calculate_direct_emissions(st.session_state.df)
                    df_with_emissions = calculator.calculate_indirect_emissions(df_with_emissions)
                    df_with_emissions = calculator.calculate_unit_emissions(df_with_emissions)

                    # 验证数据有效性
                    if df_with_emissions.empty or 'total_CO2eq' not in df_with_emissions.columns:
                        st.error("数据无效，无法进行预测")
                        st.stop()

                    # 检查模型是否加载成功
                    prediction_df = None
                    prediction_method = "未知"

                    if st.session_state.lstm_predictor.model is not None:
                        try:
                            # 使用LSTM模型进行预测
                            prediction_df = st.session_state.lstm_predictor.predict(
                                df_with_emissions,
                                'total_CO2eq',
                                steps=prediction_months
                            )
                            prediction_method = "LSTM深度学习模型"
                            st.info(f"✅ 使用{prediction_method}完成预测")
                        except Exception as e:
                            st.warning(f"LSTM模型预测失败: {str(e)}")
                            prediction_df = None

                    # 如果LSTM预测失败，使用简单预测方法
                    if prediction_df is None or prediction_df.empty:
                        prediction_df = calculator._simple_emission_prediction(
                            st.session_state.df, prediction_days
                        )
                        prediction_method = "基于历史数据的统计预测"
                        st.warning(f"使用{prediction_method}生成数据")

                        # 将日预测数据转换为月预测数据
                        if '日期' in prediction_df.columns:
                            prediction_df['日期'] = pd.to_datetime(prediction_df['日期'])
                            prediction_df.set_index('日期', inplace=True)

                            # 按月聚合 - 使用平均值
                            prediction_df = prediction_df.resample('ME').agg({
                                'predicted_CO2eq': 'mean',
                                'lower_bound': 'mean',
                                'upper_bound': 'mean'
                            }).reset_index()

                    # 确保有日期列 - 预测从2026年1月开始
                    if '日期' not in prediction_df.columns:
                        # 固定从2026年1月开始生成预测日期
                        prediction_dates = []
                        for i in range(prediction_months):
                            next_month = pd.Timestamp('2026-01-01') + pd.DateOffset(months=i)
                            month_end = pd.Timestamp(year=next_month.year, month=next_month.month,
                                                     day=1) + pd.offsets.MonthEnd(1)
                            prediction_dates.append(month_end)
                        prediction_df['日期'] = prediction_dates[:len(prediction_df)]

                    # 添加年月列用于显示
                    prediction_df['年月'] = prediction_df['日期'].dt.strftime('%Y年%m月')

                    # 验证预测结果并进行数据质量检查
                    if prediction_df.empty:
                        st.error("预测结果为空，请检查输入数据")
                        st.stop()

                    if 'predicted_CO2eq' not in prediction_df.columns:
                        st.error("预测结果缺少必要的列")
                        st.stop()

                    # 数据合理性检查
                    avg_prediction = prediction_df['predicted_CO2eq'].mean()
                    if avg_prediction <= 0:
                        st.warning("预测结果异常，使用备用计算方法")
                        # 基于历史平均值生成合理的预测数据
                        historical_avg = df_with_emissions['total_CO2eq'].mean()
                        prediction_df['predicted_CO2eq'] = historical_avg * (
                                1 + np.random.normal(0, 0.1, len(prediction_df)))
                        prediction_df['lower_bound'] = prediction_df['predicted_CO2eq'] * 0.8
                        prediction_df['upper_bound'] = prediction_df['predicted_CO2eq'] * 1.2

                    # 存储结果
                    st.session_state.prediction_data = prediction_df
                    st.session_state.historical_data = df_with_emissions
                    st.session_state.prediction_made = True
                    st.session_state.prediction_method = prediction_method  # 记录预测方法

                    st.success(f"✅ 预测完成！使用方法：{prediction_method}")
                    st.info(f"📊 生成了{len(prediction_df)}个月的预测数据")

            except Exception as e:
                st.error(f"预测过程发生错误: {str(e)}")
                # 最终备用方案
                try:
                    calculator = CarbonCalculator()
                    df_calc = calculator.calculate_direct_emissions(st.session_state.df)
                    df_calc = calculator.calculate_indirect_emissions(df_calc)
                    df_calc = calculator.calculate_unit_emissions(df_calc)

                    # 基于历史数据生成简单预测
                    historical_avg = df_calc['total_CO2eq'].mean()

                    # 固定从2026年1月开始生成预测日期
                    prediction_dates = []
                    for i in range(prediction_months):
                        next_month = pd.Timestamp('2026-01-01') + pd.DateOffset(months=i)
                        month_end = pd.Timestamp(year=next_month.year, month=next_month.month,
                                                 day=1) + pd.offsets.MonthEnd(1)
                        prediction_dates.append(month_end)

                    # 确保预测值不为0
                    min_prediction = max(100, historical_avg * 0.5)

                    # 修复：生成有显著差异的预测值 - 增强版
                    base_seed = int(pd.Timestamp.now().timestamp()) % 10000
                    predictions = []
                    lower_bounds = []
                    upper_bounds = []

                    # 计算历史标准差用于生成合理的波动
                    historical_std = df_calc[
                        'total_CO2eq'].std() if 'total_CO2eq' in df_calc.columns else historical_avg * 0.1

                    for i in range(prediction_months):
                        # 计算月份索引（0-11）
                        month_idx = i % 12

                        # 1. 季节性波动 - 不同月份有不同的基准
                        seasonal_factor = 1 + 0.12 * np.sin(2 * np.pi * i / 12 - np.pi / 2)

                        # 2. 轻微年度趋势
                        trend_factor = 1 + (i * 0.001 * np.random.choice([-1, 1]))

                        # 3. 月份特异性噪声 - 确保每个月的值都不同
                        np.random.seed(base_seed + i * 1000 + month_idx * 100)
                        # 使用历史标准差的一部分作为噪声幅度
                        noise_magnitude = historical_std * (0.1 + 0.03 * np.random.random())
                        random_noise = np.random.normal(0,
                                                        noise_magnitude / historical_avg if historical_avg > 0 else 0.05)

                        # 4. 添加月份特异性偏移 - 确保相邻月份有明显差异
                        month_offset = (month_idx - 5.5) * 0.03  # 根据月份添加偏移

                        # 5. 复合波动 - 多种频率叠加
                        compound_variation = (0.08 * np.sin(2 * np.pi * i / 12) +
                                              0.04 * np.sin(4 * np.pi * i / 12 + np.pi / 3))

                        # 组合所有成分
                        pred = historical_avg * seasonal_factor * trend_factor * (
                                    1 + random_noise + month_offset) + compound_variation * historical_avg
                        pred = max(min_prediction, pred)
                        predictions.append(pred)

                        # 置信区间随时间增加
                        uncertainty = 0.1 + 0.02 * i
                        lower_bounds.append(max(min_prediction * 0.8, pred * (1 - uncertainty)))
                        upper_bounds.append(pred * (1 + uncertainty))

                    fallback_prediction = pd.DataFrame({
                        '日期': prediction_dates,
                        'predicted_CO2eq': predictions,
                        'lower_bound': lower_bounds,
                        'upper_bound': upper_bounds,
                        '年月': [date.strftime('%Y年%m月') for date in prediction_dates]
                    })

                    st.session_state.prediction_data = fallback_prediction
                    st.session_state.historical_data = df_calc
                    st.session_state.prediction_made = True
                    st.session_state.prediction_method = "备用统计方法"
                    st.warning("使用备用方法生成预测数据")
                except Exception as final_error:
                    st.error(f"所有预测方法均失败: {str(final_error)}")
                    st.session_state.prediction_made = False

    with predict_col2:
        current_year = pd.Timestamp.now().year
        st.info(f"基于历史数据，动态预测未来{prediction_months}个月的甲烷排放趋势。使用LSTM深度学习模型进行智能预测。")

    # 第四部分：预测结果显示
    if st.session_state.get('prediction_made', False):
        st.subheader("预测结果")

        # 添加年份选择器
        col1, col2 = st.columns([1, 3])
        with col1:
            available_years = sorted(st.session_state.historical_data['日期'].dt.year.unique())
            selected_year = st.selectbox("选择年份查看历史趋势", available_years,
                                         index=len(available_years) - 1 if available_years else 0)

        # 显示历史年度趋势图
        yearly_trend_fig = vis.create_historical_trend_chart(st.session_state.historical_data)
        st.plotly_chart(yearly_trend_fig, use_container_width=True)

        # 显示指定年份的月度趋势
        monthly_trend_fig = vis.create_monthly_trend_chart(st.session_state.historical_data, selected_year)
        st.plotly_chart(monthly_trend_fig, use_container_width=True)

        # 显示预测图表
        forecast_fig = vis.create_forecast_chart(
            st.session_state.historical_data,
            st.session_state.prediction_data
        )
        st.plotly_chart(forecast_fig, use_container_width=True)

        # 显示预测数值
        st.subheader("预测数值详情")
        if not st.session_state.prediction_data.empty:
            display_df = st.session_state.prediction_data.copy()
            if '日期' in display_df.columns:
                display_df = display_df[['日期', 'predicted_CO2eq', 'lower_bound', 'upper_bound']]
                display_df = display_df.rename(columns={
                    'predicted_CO2eq': '预测甲烷排放(kgCO2eq)',
                    'lower_bound': '预测下限(kgCO2eq)',
                    'upper_bound': '预测上限(kgCO2eq)'
                })

                # 格式化数值
                for col in ['预测甲烷排放(kgCO2eq)', '预测下限(kgCO2eq)', '预测上限(kgCO2eq)']:
                    display_df[col] = display_df[col].round(1)

                st.dataframe(display_df, height=300)

                # 计算平均预测值
                avg_prediction = display_df['预测甲烷排放(kgCO2eq)'].mean()

                # 初始化change变量，确保在所有情况下都有定义
                change = 0

                # 计算并显示变化趋势 - 科学修正版本
                change = 0

                if (hasattr(st.session_state, 'prediction_data') and
                        not st.session_state.prediction_data.empty and
                        hasattr(st.session_state, 'historical_data') and
                        not st.session_state.historical_data.empty and
                        'total_CO2eq' in st.session_state.historical_data.columns):

                    try:
                        historical_data = st.session_state.historical_data.copy()
                        prediction_data = st.session_state.prediction_data.copy()

                        # 确保日期列为datetime类型
                        if '日期' in historical_data.columns:
                            historical_data['日期'] = pd.to_datetime(historical_data['日期'])

                        # 科学的趋势计算：基于历史数据预测未来变化
                        # 统一数据处理逻辑：都按日均值×30标准化处理
                        historical_data['年月'] = historical_data['日期'].dt.to_period('M')

                        # 无论原始数据是什么格式，都统一按日均值处理
                        historical_monthly_raw = historical_data.groupby('年月')['total_CO2eq'].mean()
                        # 标准化为月度表示（日均值×30）
                        historical_monthly = historical_monthly_raw * 30

                        # 计算历史基准（最近24个月作为基准更科学）
                        if len(historical_monthly) >= 24:
                            # 使用最近24个月作为基准
                            recent_historical_avg = historical_monthly.tail(24).mean()
                            calculation_base = "最近24个月历史数据"
                        elif len(historical_monthly) >= 12:
                            # 至少使用最近12个月作为基准
                            recent_historical_avg = historical_monthly.tail(12).mean()
                            calculation_base = "最近12个月历史数据"
                        else:
                            # 数据不足时使用全部历史数据
                            recent_historical_avg = historical_monthly.mean()
                            calculation_base = f"全部{len(historical_monthly)}个月历史数据"

                        # 处理预测数据（未来期间）
                        if 'predicted_CO2eq' in prediction_data.columns:
                            # 预测数据已经是标准化的月度值
                            predicted_monthly_avg = prediction_data['predicted_CO2eq'].mean()

                            # 计算预测期相对于历史基准的变化趋势
                            if recent_historical_avg > 0 and predicted_monthly_avg > 0:
                                change = ((predicted_monthly_avg - recent_historical_avg) / recent_historical_avg) * 100

                                # 合理性检查：年际变化通常在±50%以内
                                if abs(change) > 100:
                                    st.warning(f"检测到较大变化率 {change:.1f}%，请检查数据质量")
                                    # 限制在合理范围内
                                    change = np.clip(change, -50, 50)

                                # 科学解释变化趋势
                                trend_explanation = ""
                                if change > 10:
                                    trend_explanation = "预测未来期间甲烷排放将显著上升，建议加强节能减排措施"
                                elif change > 5:
                                    trend_explanation = "预测未来期间甲烷排放将适度上升"
                                elif change > -5:
                                    trend_explanation = "预测未来期间甲烷排放将保持相对稳定"
                                elif change > -10:
                                    trend_explanation = "预测未来期间甲烷排放将适度下降"
                                else:
                                    trend_explanation = "预测未来期间甲烷排放将显著下降，减排效果良好"

                                # 获取预测期间说明
                                forecast_start_str = prediction_data['日期'].min().strftime(
                                    '%Y年%m月') if '日期' in prediction_data.columns else '未来'
                                forecast_end_str = prediction_data['日期'].max().strftime(
                                    '%Y年%m月') if '日期' in prediction_data.columns else '期间'

                                # 记录详细计算信息
                                calculation_details = {
                                    'historical_avg': recent_historical_avg,
                                    'predicted_avg': predicted_monthly_avg,
                                    'change_rate': change,
                                    'calculation_base': calculation_base,
                                    'data_processing': '日均值×30天标准化处理',
                                    'historical_data_points': len(historical_monthly),
                                    'prediction_method': st.session_state.get('prediction_method', '未知方法'),
                                    'trend_explanation': trend_explanation,
                                    'data_range': f"{historical_data['日期'].min().strftime('%Y-%m')} 到 {historical_data['日期'].max().strftime('%Y-%m')}",
                                    'forecast_range': f"{forecast_start_str} 至 {forecast_end_str}"
                                }
                                st.session_state.trend_calculation = calculation_details

                                # 显示科学的趋势解释
                                with st.expander("趋势计算科学解释", expanded=False):
                                    st.markdown(f"""
                                    **趋势计算说明**：
                                    - **历史基准期**: {calculation_details['data_range']}
                                    - **预测目标期**: {calculation_details['forecast_range']}
                                    - **历史月均值**: {recent_historical_avg:.1f} kgCO2eq/月
                                    - **预测月均值**: {predicted_monthly_avg:.1f} kgCO2eq/月
                                    - **变化趋势**: {change:+.1f}% ({trend_explanation})
                                    - **数据处理**: {calculation_details['data_processing']}
                                    - **基准数据**: {calculation_base}
                                    """)

                            else:
                                st.warning("历史数据或预测数据存在异常值，无法计算准确的变化趋势")
                                change = 0
                        else:
                            st.warning("预测数据格式异常，缺少'predicted_CO2eq'列")
                            change = 0

                    except Exception as e:
                        st.error(f"计算变化趋势时发生错误: {str(e)}")
                        change = 0
                else:
                    if not hasattr(st.session_state, 'prediction_data') or st.session_state.prediction_data.empty:
                        st.info("请先进行预测以查看趋势变化")
                    elif not hasattr(st.session_state, 'historical_data') or st.session_state.historical_data.empty:
                        st.info("请先上传历史数据以进行趋势对比")
                    change = 0

                # 存储变化率供后续使用
                st.session_state.change_percent = change

                col1, col2, col3 = st.columns(3)
                with col1:
                    # 修复：使用display_df而不是未定义的prediction_df
                    unit_label = "月均" if len(display_df) <= 12 else "日均"
                    st.metric("平均预测值", f"{avg_prediction:.1f} kgCO2eq/{unit_label}")
                with col2:
                    # 使用预测数据的上下界来计算区间
                    avg_lower = display_df['预测下限(kgCO2eq)'].mean()
                    avg_upper = display_df['预测上限(kgCO2eq)'].mean()
                    st.metric("预测区间", f"{avg_lower:.1f} - {avg_upper:.1f} kgCO2eq/{unit_label}")
                with col3:
                    # 显示变化趋势，包含预测方法信息
                    trend_direction = "↗️" if change > 0 else "↘️" if change < 0 else "➡️"
                    prediction_method = st.session_state.get('prediction_method', '未知方法')

                    st.metric(
                        "变化趋势",
                        f"{change:+.1f}% {trend_direction}",
                        delta=f"{change:.1f}%",
                        delta_color="inverse" if change > 0 else "normal"
                    )
                    st.caption(f"基于{prediction_method}")

        # 添加前瞻性运行指导建议
        st.subheader("前瞻性运行指导建议")

        if not st.session_state.prediction_data.empty and not st.session_state.historical_data.empty:
            # 直接使用前面计算的变化百分比
            change_percent = st.session_state.get('change_percent', 0)
            trend = "上升" if change_percent > 0 else "下降"

            # 分析趋势强度
            trend_strength = "显著" if abs(change_percent) > 15 else "轻微" if abs(change_percent) > 5 else "平稳"

            # 分析季节性模式
            historical_monthly = st.session_state.historical_data.copy()
            historical_monthly['月份'] = historical_monthly['日期'].dt.month
            monthly_avg = historical_monthly.groupby('月份')['total_CO2eq'].mean()

            if len(monthly_avg) >= 6:  # 至少有半年数据
                seasonal_variation = monthly_avg.max() - monthly_avg.min()
                has_seasonal_pattern = seasonal_variation > monthly_avg.mean() * 0.2  # 变化超过20%认为有季节性
            else:
                has_seasonal_pattern = False

            # 根据详细分析提供建议
            if trend == "上升":
                if trend_strength == "显著":
                    st.error(
                        f"⚠️ 预警：预测显示未来甲烷排放将{trend}{change_percent:.1f}%，{trend_strength}{trend}趋势！")
                    st.info("""
                    **紧急措施建议：**
                    - 立即检查曝气系统运行效率，优化DO控制（目标1.5-2.5mg/L）
                    - 全面评估化学药剂投加量，减少PAC/PAM过量使用
                    - 加强进水水质监控，预防冲击负荷影响生化系统
                    - 考虑实施变频控制改造，降低水泵/风机能耗
                    - 检查污泥脱水系统运行，优化脱水剂投加
                    """)
                else:
                    st.warning(f"⚠️ 预测显示未来甲烷排放将{trend}{change_percent:.1f}%，{trend_strength}{trend}趋势")
                    st.info("""
                    **优化建议：**
                    - 检查曝气系统效率，优化曝气量控制
                    - 评估化学药剂投加量，避免过量使用
                    - 加强进水水质监控，预防冲击负荷
                    - 考虑实施节能技术改造
                    """)
            else:
                if trend_strength == "显著":
                    st.success(
                        f"✅ 良好：预测显示未来甲烷排放将{trend}{change_percent:.1f}%，{trend_strength}{trend}趋势！")
                    st.info("""
                    **巩固措施：**
                    - 继续保持当前优化运行参数
                    - 定期校准在线监测仪表，确保数据准确性
                    - 记录并分析成功经验，形成标准化操作程序
                    - 探索进一步优化空间，如精准加药控制系统
                    """)
                else:
                    st.success(f"✅ 预测显示未来甲烷排放将{trend}{change_percent:.1f}%，{trend_strength}{trend}趋势")
                    st.info("""
                    **保持措施：**
                    - 维持当前优化运行参数
                    - 继续监控关键工艺指标
                    - 定期维护设备确保高效运行
                    """)

            # 添加季节性建议
            if has_seasonal_pattern:
                peak_month = monthly_avg.idxmax()
                st.info(f"📈 检测到季节性模式：甲烷排放通常在{peak_month}月达到峰值，建议提前制定应对措施")

            # 添加技术投资建议（基于预测趋势动态推荐）
            st.subheader("减排技术投资建议")

            if not st.session_state.prediction_data.empty:
                # 根据预测趋势推荐技术
                current_avg = st.session_state.historical_data['total_CO2eq'].mean()
                predicted_avg = st.session_state.prediction_data['predicted_CO2eq'].mean()
                trend = predicted_avg > current_avg  # True表示上升趋势

                if trend:  # 碳排放上升趋势，推荐高效减排技术
                    tech_recommendations = {
                        "高效曝气系统": {
                            "减排潜力": "15-25%",
                            "投资回收期": "2-4年",
                            "适用性": "高",
                            "推荐理由": "直接降低能耗最大的曝气系统电耗，应对上升趋势最有效"
                        },
                        "光伏发电": {
                            "减排潜力": "20-30%",
                            "投资回收期": "5-8年",
                            "适用性": "中",
                            "推荐理由": "利用厂区空间发电，抵消外购电力碳排放，长期效益好"
                        },
                        "智能加药系统": {
                            "减排潜力": "10-20%",
                            "投资回收期": "3-5年",
                            "适用性": "高",
                            "推荐理由": "精准控制药剂投加，减少化学药剂相关碳排放"
                        }
                    }
                else:  # 碳排放下降趋势，推荐维持性技术
                    tech_recommendations = {
                        "设备能效提升": {
                            "减排潜力": "5-15%",
                            "投资回收期": "1-3年",
                            "适用性": "高",
                            "推荐理由": "更换高效水泵/风机，持续优化能耗表现"
                        },
                        "污泥厌氧消化": {
                            "减排潜力": "10-20%",
                            "投资回收期": "3-5年",
                            "适用性": "中高",
                            "推荐理由": "利用污泥产沼发电，实现能源回收"
                        },
                        "过程控制系统": {
                            "减排潜力": "8-12%",
                            "投资回收期": "2-4年",
                            "适用性": "中",
                            "推荐理由": "优化全厂运行参数，稳定保持低碳排放水平"
                        }
                    }

                tech_df = pd.DataFrame(tech_recommendations).T
                st.dataframe(tech_df)

                # 添加投资优先级建议
                st.info(
                    "💡 投资优先级建议：根据投资回收期和减排潜力综合评估，建议优先考虑投资回收期短、减排潜力大的技术")

    # 显示模型状态
    st.subheader("模型状态")
    if st.session_state.lstm_predictor is not None and st.session_state.lstm_predictor.model is not None:
        st.success("✅ 模型已加载，可以进行预测")
    elif st.session_state.lstm_predictor is not None and st.session_state.lstm_predictor.model is None:
        st.warning("⚠️ 模型未加载，请先加载或训练模型")
    else:
        st.warning("⚠️ 请先加载或训练模型")

    # 显示模型基本信息
    if st.session_state.lstm_predictor is not None and st.session_state.lstm_predictor.model is not None:
        model = st.session_state.lstm_predictor.model
        if hasattr(model, 'summary'):
            import io
            import contextlib

            string_buffer = io.StringIO()
            with contextlib.redirect_stdout(string_buffer):
                model.summary()
            model_summary = string_buffer.getvalue()

            with st.expander("查看模型架构"):
                st.text(model_summary)

    # 添加简单预测方法作为备选
    if st.session_state.df is not None and st.session_state.lstm_predictor is None:
        st.info("也可以使用简单预测方法（基于历史平均值）")
        if st.button("使用简单预测", key="simple_predict_btn"):
            with st.spinner("正在进行简单预测..."):
                calculator = CarbonCalculator()
                simple_prediction = calculator._simple_emission_prediction(st.session_state.df, prediction_days)

                # 显示预测图表
                df_with_emissions = calculator.calculate_direct_emissions(st.session_state.df)
                df_with_emissions = calculator.calculate_indirect_emissions(df_with_emissions)
                df_with_emissions = calculator.calculate_unit_emissions(df_with_emissions)

                historical_data = df_with_emissions[['日期', 'total_CO2eq']].tail(30)
                fig = vis.create_carbon_trend_chart(historical_data, simple_prediction)
                st.plotly_chart(fig, use_container_width=True)

                st.info("这是基于历史平均值的简单预测，精度较低")

with tab6:
    st.header("甲烷减排技术对比分析")

    # 技术选择
    selected_techs = st.multiselect(
        "选择对比技术",
        ["厌氧消化产沼", "光伏发电", "高效曝气", "热泵技术", "污泥干化", "沼气发电"],
        default=["厌氧消化产沼", "光伏发电", "高效曝气"]
    )

    # 始终显示技术说明
    st.subheader("可选减排技术说明")
    tech_descriptions = {
        "厌氧消化产沼": "利用污泥厌氧消化产生沼气发电，减少外购电力碳排放",
        "光伏发电": "在厂区屋顶安装光伏板，利用太阳能发电抵消部分电力碳排放",
        "高效曝气": "采用微孔曝气、变频控制等技术，降低生物处理单元能耗",
        "热泵技术": "利用污水余热进行加热，减少辅助加热设备能耗",
        "污泥干化": "污泥干化后资源化利用，减少污泥处置碳排放",
        "沼气发电": "收集处理过程中产生的沼气进行发电，实现能源回收"
    }

    for tech, desc in tech_descriptions.items():
        st.write(f"**{tech}**: {desc}")

    st.subheader("技术对比分析")
    if st.button("运行技术对比分析"):
        with st.spinner("正在进行技术对比分析..."):
            try:
                calculator = CarbonCalculator()
                comparison_results = calculator.compare_carbon_techs(
                    selected_techs,
                    st.session_state.df_selected if 'df_selected' in st.session_state else None
                )
                st.session_state.tech_comparison_results = comparison_results

                # 显示技术对比图表
                tech_fig = vis.create_technology_comparison(comparison_results)
                st.plotly_chart(tech_fig, key="carbon")

                # 显示详细对比表格
                st.subheader("技术经济性分析")
                st.dataframe(comparison_results)

                st.success("✅ 技术对比分析完成！")

            except Exception as e:
                st.error(f"技术对比分析失败: {str(e)}")
                # 显示默认对比数据
                st.info("显示默认技术对比数据")
                default_comparison = pd.DataFrame({
                    '技术名称': selected_techs,
                    '减排量_kgCO2eq': [15000, 8000, 6000, 4500, 3000, 12000][:len(selected_techs)],
                    '投资成本_万元': [500, 300, 200, 150, 100, 400][:len(selected_techs)],
                    '回收期_年': [5, 8, 4, 6, 7, 5][:len(selected_techs)],
                    '适用性': ['高', '中', '高', '中', '低', '高'][:len(selected_techs)]
                })
                st.dataframe(default_comparison)

    # 显示历史对比结果（如果存在）
    if hasattr(st.session_state,
               'tech_comparison_results') and st.session_state.tech_comparison_results is not None:
        st.subheader("历史对比结果")
        tech_fig = vis.create_technology_comparison(st.session_state.tech_comparison_results)
        st.plotly_chart(tech_fig, key="carbon-b")

        # 技术详情表格
        st.subheader("减排技术详情")
        st.dataframe(st.session_state.tech_comparison_results)
    else:
        st.info("💡 请点击'运行技术对比分析'按钮，基于当前工厂数据生成技术对比分析")

    # 技术适用性分析
    st.subheader("技术适用性分析")
    selected_tech = st.selectbox(
        "选择技术查看详情",
        ["厌氧消化产沼", "光伏发电", "高效曝气", "热泵技术", "污泥干化", "沼气发电"]
    )

    # 技术详细信息
    tech_details = {
        "厌氧消化产沼": {
            "预计年减排量": "15000 kgCO2eq",
            "投资成本": "500 万元",
            "投资回收期": "5 年",
            "适用性": "高",
            "甲烷减排贡献率": "25%",
            "能源中和率": "30%"
        },
        "光伏发电": {
            "预计年减排量": "8000 kgCO2eq",
            "投资成本": "300 万元",
            "投资回收期": "8 年",
            "适用性": "中",
            "甲烷减排贡献率": "15%",
            "能源中和率": "40%"
        },
        "高效曝气": {
            "预计年减排量": "6000 kgCO2eq",
            "投资成本": "200 万元",
            "投资回收期": "4 年",
            "适用性": "高",
            "甲烷减排贡献率": "20%",
            "能源中和率": "10%"
        },
        "热泵技术": {
            "预计年减排量": "4500 kgCO2eq",
            "投资成本": "150 万元",
            "投资回收期": "6 年",
            "适用性": "中",
            "甲烷减排贡献率": "12%",
            "能源中和率": "15%"
        },
        "污泥干化": {
            "预计年减排量": "3000 kgCO2eq",
            "投资成本": "100 万元",
            "投资回收期": "7 年",
            "适用性": "低",
            "甲烷减排贡献率": "8%",
            "能源中和率": "5%"
        },
        "沼气发电": {
            "预计年减排量": "12000 kgCO2eq",
            "投资成本": "400 万元",
            "投资回收期": "5 年",
            "适用性": "高",
            "甲烷减排贡献率": "20%",
            "能源中和率": "35%"
        }
    }

    if selected_tech in tech_details:
        tech_detail = tech_details[selected_tech]
        st.write(f"**{selected_tech}**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("预计年减排量", tech_detail["预计年减排量"])
            st.metric("投资成本", tech_detail["投资成本"])
        with col2:
            st.metric("投资回收期", tech_detail["投资回收期"])
            st.metric("适用性", tech_detail["适用性"])
        with col3:
            st.metric("甲烷减排贡献率", tech_detail["甲烷减排贡献率"])
            st.metric("能源中和率", tech_detail["能源中和率"])

    # 甲烷抵消计算
    st.subheader("甲烷抵消计算")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        biogas = st.number_input("沼气发电量(kWh)", value=1000, min_value=0)
        st.session_state.carbon_offset_data["沼气发电"] = biogas * 2.5
    with col2:
        solar = st.number_input("光伏发电量(kWh)", value=500, min_value=0)
        st.session_state.carbon_offset_data["光伏发电"] = solar * 0.85
    with col3:
        heatpump = st.number_input("热泵技术节能量(kWh)", value=300, min_value=0)
        st.session_state.carbon_offset_data["热泵技术"] = heatpump * 1.2
    with col4:
        sludge = st.number_input("污泥资源化量(kgDS)", value=200, min_value=0)
        st.session_state.carbon_offset_data["污泥资源化"] = sludge * 0.3

    total_offset = sum(st.session_state.carbon_offset_data.values())
    st.metric("总甲烷抵消量", f"{total_offset:.2f} kgCO2eq")

# 新增选项卡：因子库管理
with tab7:
    st.header("甲烷排放因子库管理")

    # 检查是否是回退模式
    fallback_mode = hasattr(st.session_state.factor_db,
                            'is_fallback') and st.session_state.factor_db.is_fallback
    if fallback_mode:
        st.warning("⚠️ 当前处于回退模式，使用默认因子值。某些功能可能受限。")

    # 显示当前因子
    st.subheader("当前甲烷排放因子（权威来源）")

    # 定义默认因子数据
    default_factors_data = {
        '因子类型': ['电力', 'PAC', 'PAM', 'N2O', 'CH4', '次氯酸钠', '臭氧', '沼气发电', '光伏发电', '热泵技术',
                     '污泥资源化'],
        '因子值': [0.5366, 1.62, 1.5, 273, 27.9, 0.92, 0.8, 2.5, 0.85, 1.2, 0.3],
        '单位': ['kgCO2/kWh', 'kgCO2/kg', 'kgCO2/kg', 'kgCO2/kgN2O', 'kgCO2/kgCH4', 'kgCO2/kg', 'kgCO2/kg',
                 'kgCO2eq/kWh', 'kgCO2eq/kWh', 'kgCO2eq/kWh', 'kgCO2eq/kgDS'],
        '地区': ['中国', '通用', '通用', '通用', '通用', '通用', '通用', '通用', '通用', '通用', '通用'],
        '数据来源': ['生态环境部公告2024年第12号', 'T/CAEPI 49-2022', 'T/CAEPI 49-2022', 'IPCC AR6', 'IPCC AR6',
                     'T/CAEPI 49-2022', '研究文献', '研究文献', '研究文献', '研究文献', '研究文献'],
        '生效日期': ['2021-01-01', '2020-01-01', '2020-01-01', '2020-01-01', '2020-01-01', '2020-01-01',
                     '2020-01-01', '2020-01-01', '2020-01-01', '2020-01-01', '2020-01-01'],
        '描述': ['2021年全国电力平均二氧化碳排放因子', '聚合氯化铝排放因子', '聚丙烯酰胺排放因子',
                 '氧化亚氮全球变暖潜能值(GWP)', '甲烷全球变暖潜能值(GWP)', '次氯酸钠排放因子', '臭氧排放因子',
                 '沼气发电甲烷抵消因子', '光伏发电甲烷抵消因子', '热泵技术甲烷抵消因子', '污泥资源化甲烷抵消因子']
    }

    try:
        # 尝试从数据库获取因子
        if not fallback_mode:
            factors_df = st.session_state.factor_db.export_factors("temp_factors.csv", format="csv")
        else:
            factors_df = pd.DataFrame()

        if not factors_df.empty:
            # 高亮显示关键因子
            def highlight_key_factors(row):
                if row['factor_type'] in ['电力', 'N2O', 'CH4']:
                    return ['background-color: #e6f3ff'] * len(row)
                else:
                    return [''] * len(row)


            styled_df = factors_df.style.apply(highlight_key_factors, axis=1)
            st.dataframe(styled_df, height=400)
            st.caption("注：高亮因子来源于中国生态环境部官方文件或IPCC第六次评估报告(AR6)。")
        else:
            # 显示默认数据
            if fallback_mode:
                st.info("📄 显示默认因子数据")
            else:
                st.warning("📊 因子数据库为空，显示默认因子数据")

            default_df = pd.DataFrame(default_factors_data)


            # 高亮显示关键因子
            def highlight_key_factors_default(row):
                if row['因子类型'] in ['电力', 'N2O', 'CH4']:
                    return ['background-color: #e6f3ff'] * len(row)
                else:
                    return [''] * len(row)


            styled_default_df = default_df.style.apply(highlight_key_factors_default, axis=1)
            st.dataframe(styled_default_df, height=400)
            st.caption("注：高亮因子来源于中国生态环境部官方文件或IPCC第六次评估报告(AR6)。")

    except Exception as e:
        st.error(f"获取因子数据失败: {e}")
        # 显示备用数据
        st.info("📄 显示备用因子数据")
        default_df = pd.DataFrame(default_factors_data)
        st.dataframe(default_df, height=400)

    # 因子更新界面
    st.subheader("更新甲烷排放因子")

    # 在回退模式下禁用更新功能
    if fallback_mode:
        st.info("🔒 回退模式下无法更新因子。请检查数据库连接。")

        # 显示模拟的更新界面（仅供演示）
        st.markdown("**演示模式 - 因子更新界面**")
        col1, col2, col3 = st.columns(3)
        with col1:
            factor_type = st.selectbox("因子类型", ["电力", "PAC", "PAM", "次氯酸钠", "臭氧", "N2O", "CH4"])
        with col2:
            factor_value = st.number_input("因子值", value=0.0, step=0.01)
        with col3:
            factor_year = st.selectbox("生效年份", list(range(2020, 2026)))

        if st.button("更新因子（演示）"):
            st.info(f"📝 演示模式：将更新{factor_type} {factor_year}年排放因子为: {factor_value}")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            factor_type = st.selectbox("因子类型", ["电力", "PAC", "PAM", "次氯酸钠", "臭氧", "N2O", "CH4"])
        with col2:
            factor_value = st.number_input("因子值", value=0.0, step=0.01)
        with col3:
            factor_year = st.selectbox("生效年份", list(range(2020, 2026)))

        if st.button("更新因子"):
            try:
                # 根据因子类型确定单位
                unit_mapping = {
                    "电力": "kgCO2/kWh",
                    "PAC": "kgCO2/kg",
                    "PAM": "kgCO2/kg",
                    "次氯酸钠": "kgCO2/kg",
                    "臭氧": "kgCO2/kg",
                    "N2O": "kgCO2/kgN2O",
                    "CH4": "kgCO2/kgCH4"
                }
                unit = unit_mapping.get(factor_type, "kgCO2/kg")

                st.session_state.factor_db.update_factor(
                    factor_type, factor_value, unit, "中国",
                    f"{factor_year}-01-01", f"{factor_year}-12-31",
                    "用户更新", f"{factor_year}年{factor_type}排放因子", "手动更新"
                )
                st.success(f"✅ 已更新{factor_type} {factor_year}年排放因子: {factor_value} {unit}")

                # 刷新页面显示
                st.experimental_rerun()

            except Exception as e:
                st.error(f"❌ 更新因子失败: {e}")

            # 因子历史趋势
            st.subheader("电力排放因子历史趋势")
            try:
                if not fallback_mode:
                    electricity_history = st.session_state.factor_db.get_factor_history("电力", "中国")
                else:
                    # 回退模式下显示模拟历史数据
                    electricity_history = pd.DataFrame({
                        'effective_date': ['2020-01-01', '2021-01-01', '2022-01-01', '2023-01-01', '2024-01-01'],
                        'factor_value': [0.5703, 0.5366, 0.5568, 0.5456, 0.5320],
                        'data_source': ['官方数据', '官方数据', '官方数据', '预测值', '预测值']
                    })
                    electricity_history['effective_date'] = pd.to_datetime(electricity_history['effective_date'])

                if not electricity_history.empty:
                    fig = px.line(
                        electricity_history, x="effective_date", y="factor_value",
                        title="电力排放因子历史变化", markers=True,
                        hover_data=['data_source'] if 'data_source' in electricity_history.columns else None
                    )
                    fig.update_layout(
                        xaxis_title="生效日期",
                        yaxis_title="排放因子 (kgCO2/kWh)",
                        font=dict(size=14, color="black"),
                        plot_bgcolor="rgba(245, 245, 245, 1)",
                        paper_bgcolor="rgba(245, 245, 245, 1)",
                        height=400,
                        xaxis=dict(tickfont=dict(color="black"), title_font=dict(color="black")),
                        yaxis=dict(tickfont=dict(color="black"), title_font=dict(color="black"))
                    )
                    fig.update_traces(line=dict(width=3), marker=dict(size=8))
                    st.plotly_chart(fig, use_container_width=True)

                    if fallback_mode:
                        st.caption("📊 显示模拟历史数据用于演示")
                else:
                    st.info("📈 暂无电力排放因子历史数据")

            except Exception as e:
                st.error(f"❌ 获取电力因子历史失败: {e}")

            # 因子数据导出功能
            st.subheader("数据导出")
            col1, col2 = st.columns(2)
            with col1:
                export_format = st.selectbox("选择导出格式", ["CSV", "Excel"])
            with col2:
                if st.button("导出因子数据"):
                    try:
                        if not fallback_mode:
                            if export_format == "CSV":
                                factors_df = st.session_state.factor_db.export_factors("carbon_factors.csv",
                                                                                       format="csv")
                                st.success("✅ 因子数据已导出为 carbon_factors.csv")
                            else:
                                factors_df = st.session_state.factor_db.export_factors("carbon_factors.xlsx",
                                                                                       format="excel")
                                st.success("✅ 因子数据已导出为 carbon_factors.xlsx")

                            st.dataframe(factors_df.head(), caption="导出数据预览")
                        else:
                            # 回退模式下导出默认数据
                            default_df = pd.DataFrame(default_factors_data)
                            if export_format == "CSV":
                                csv = default_df.to_csv(index=False)
                                st.download_button(
                                    label="📥 下载CSV文件",
                                    data=csv,
                                    file_name="default_carbon_factors.csv",
                                    mime="text/csv"
                                )
                            else:
                                # Excel下载按钮
                                st.download_button(
                                    label="📥 下载Excel文件",
                                    data=default_df.to_csv(index=False),
                                    file_name="default_carbon_factors.xlsx",
                                    mime="application/vnd.ms-excel"
                                )
                            st.dataframe(default_df, caption="默认数据预览")

                    except Exception as e:
                        st.error(f"❌ 导出失败: {e}")

            # 系统状态信息
            st.subheader("系统状态")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("运行模式", "回退模式" if fallback_mode else "正常模式")
            with col2:
                try:
                    if not fallback_mode:
                        total_factors = len(st.session_state.factor_db.export_factors("temp.csv", format="csv"))
                    else:
                        total_factors = len(default_factors_data['因子类型'])
                    st.metric("因子总数", f"{total_factors} 个")
                except:
                    st.metric("因子总数", "11 个")
            with col3:
                st.metric("数据来源", "官方+研究文献")


        # 添加页面卸载时的清理函数
        def cleanup():
            """清理资源"""
            if 'factor_db' in st.session_state:
                # 调用数据库清理方法
                try:
                    st.session_state.factor_db.__del__()
                except:
                    pass


        # 注册清理函数
        import atexit

        atexit.register(cleanup)

# ============== 数字人助手标签页 ==============
with tab8:
    # 调用数字人助手模块
    try:
        render_digital_human_tab()
    except Exception as e:
        st.error(f"数字人助手加载失败: {e}")
        st.info("请确保digital_human_agent.py和coze_api.py文件存在且正确")

        # 显示简单的备用界面
        st.header("🤖 数字人助手")
        st.warning("数字人助手暂时不可用，请检查文件配置")

        col1, col2 = st.columns(2)
        with col1:
            st.info("📁 需要检查的文件：")
            st.write("- digital_human_agent.py")
            st.write("- coze_api.py")
            st.write("- assets/digital_human.jpg")
        with col2:
            st.info("🔧 配置说明：")
            st.write("1. 确保卡通形象图片已放置到assets目录")
            st.write("2. 检查Python依赖是否完整")
            st.write("3. 查看控制台错误信息")

# ============== AI实验室·污水处理闯关小游戏标签页 ==============
with tab9:
    # 调用污水处理闯关小游戏模块
    if WATER_GAME_AVAILABLE:
        try:
            render_water_treatment_game()
        except Exception as e:
            st.error(f"污水处理闯关小游戏加载失败: {e}")
            st.info("请检查water_treatment_game.py文件是否存在且正确")

            # 显示简单的备用界面
            st.header("🎮 AI实验室·污水处理闯关小游戏")
            st.warning("游戏暂时不可用，请检查文件配置")

            col1, col2 = st.columns(2)
            with col1:
                st.info("📁 需要检查的文件：")
                st.write("- water_treatment_game.py")
            with col2:
                st.info("🔧 配置说明：")
                st.write("1. 确保water_treatment_game.py文件存在")
                st.write("2. 检查Python依赖是否完整")
                st.write("3. 查看控制台错误信息")
    else:
        # 游戏模块不可用时的备用界面
        st.header("🎮 AI实验室·污水处理闯关小游戏")
        st.warning("游戏模块未加载，请检查water_treatment_game.py文件是否存在")

        st.markdown("""
        ### 🎯 游戏简介

        这是一款互动式污水处理工艺学习游戏，通过闯关的方式帮助您掌握污水处理的核心工艺流程。

        ### 📋 游戏特点

        - **3个精心设计的关卡**：预处理、生物处理、深度处理
        - **互动式学习**：拖拽工艺模块，按正确顺序排列
        - **实时反馈**：即时检查答案，提供详细解析
        - **科普知识**：丰富的污水处理小知识

        ### 🔧 故障排除

        如果游戏无法正常加载，请检查：
        1. water_treatment_game.py 文件是否存在于项目目录
        2. 文件是否包含正确的Python代码
        3. 依赖包是否完整安装

        请联系系统管理员解决此问题。
        """)

# 运行应用
if __name__ == "__main__":
    # 在开发环境中，Streamlit会自动运行这个文件
    pass
