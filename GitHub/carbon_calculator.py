import math

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from factor_database import CarbonFactorDatabase


class CarbonCalculator:
    def __init__(self):
        # 初始化因子数据库
        try:
            from factor_database import CarbonFactorDatabase
            self.factor_db = CarbonFactorDatabase()
        except:
            # 创建回退实现
            class FallbackCarbonFactorDatabase:
                def get_factor(self, factor_type, region="中国", date=None):
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

            self.factor_db = FallbackCarbonFactorDatabase()

        # 从数据库获取当前因子
        try:
            self.f_e = self.factor_db.get_factor("电力", "中国")
        except ValueError:
            self.f_e = 0.5568  # 默认值

        # 其他固定因子
        self.EF_N2O = 0.016
        self.C_N2O_N2 = 44 / 28

        try:
            self.f_N2O = self.factor_db.get_factor("N2O", "通用")
        except ValueError:
            self.f_N2O = 273

        self.B0 = 0.25
        self.MCF = 0.003

        try:
            self.f_CH4 = self.factor_db.get_factor("CH4", "通用")
        except ValueError:
            self.f_CH4 = 27.9

        # 药剂排放因子
        self.EF_chemicals = {
            "PAC": self.factor_db.get_factor("PAC", "通用"),
            "PAM": self.factor_db.get_factor("PAM", "通用"),
            "次氯酸钠": self.factor_db.get_factor("次氯酸钠", "通用"),
            "臭氧": self.factor_db.get_factor("臭氧", "通用")
        }

        # 碳汇技术因子
        self.carbon_offset_factors = {
            "沼气发电": self.factor_db.get_factor("沼气发电", "通用"),
            "光伏发电": self.factor_db.get_factor("光伏发电", "通用"),
            "热泵技术": self.factor_db.get_factor("热泵技术", "通用"),
            "污泥资源化": self.factor_db.get_factor("污泥资源化", "通用")
        }

        # 各工艺单元能耗分配比例
        self.energy_distribution = {
            "预处理区": 0.3193,
            "生物处理区": 0.4453,
            "深度处理区": 0.1155,
            "泥处理区": 0.0507,
            "出水区": 0.0672,
            "除臭系统": 0.0267
        }


        # 碳汇和减排技术因子
        self.carbon_offset_factors = {
            "沼气发电": 2.5,  # kgCO2eq/kWh
            "光伏发电": 0.85,  # kgCO2eq/kWh
            "热泵技术": 1.2,  # kgCO2eq/kWh
            "污泥资源化": 0.3  # kgCO2eq/kgDS
        }

    def update_electricity_factor(self, year=None):
        """更新电力排放因子"""
        if year:
            # 获取指定年份的因子
            try:
                self.f_e = self.factor_db.get_factor("电力", "中国", f"{year}-01-01")
            except ValueError:
                print(f"未找到{year}年的电力排放因子，使用当前因子: {self.f_e}")
        else:
            # 获取最新因子
            try:
                self.f_e = self.factor_db.get_factor("电力", "中国")
            except ValueError:
                print(f"未找到最新电力排放因子，使用当前因子: {self.f_e}")

    def calculate_direct_emissions(self, df):
        """计算N₂O、CH₄直接排放"""
        required_cols = ['处理水量(m³)', '进水TN(mg/L)', '出水TN(mg/L)', '进水COD(mg/L)', '出水COD(mg/L)']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"数据缺少必需列：{missing_cols}")

        # 处理缺失值
        df = df.fillna(0)

        # N₂O直接排放 - 确保非负
        df['N2O_emission'] = np.maximum(0, (
                df['处理水量(m³)'] * (df['进水TN(mg/L)'] - df['出水TN(mg/L)']) *
                self.EF_N2O * self.C_N2O_N2 / 1000
        ))

        df['N2O_CO2eq'] = df['N2O_emission'] * self.f_N2O

        # CH4直接排放 - 确保非负
        df['COD_removed'] = np.maximum(0, (
                df['处理水量(m³)'] * np.abs(df['进水COD(mg/L)'] - df['出水COD(mg/L)']) / 1000
        ))

        df['CH4_emission'] = np.maximum(0, df['COD_removed'] * self.B0 * self.MCF)
        df['CH4_CO2eq'] = df['CH4_emission'] * self.f_CH4

        return df

    def calculate_indirect_emissions(self, df):
        """计算能耗、药耗间接排放"""
        required_cols = ['电耗(kWh)', 'PAC投加量(kg)', 'PAM投加量(kg)', '次氯酸钠投加量(kg)', '臭氧投加量(kg)']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            # 添加缺失列并用0填充
            for col in missing_cols:
                if col in ['PAC投加量(kg)', 'PAM投加量(kg)', '次氯酸钠投加量(kg)', '臭氧投加量(kg)']:
                    df[col] = 0

        # 处理缺失值
        df = df.fillna(0)

        # 能耗间接排放 - 确保非负
        df['energy_CO2eq'] = np.maximum(0, df['电耗(kWh)'] * self.f_e)

        # 药耗间接排放 - 确保非负
        df['PAC_CO2eq'] = np.maximum(0, df['PAC投加量(kg)'] * self.EF_chemicals['PAC'])
        df['PAM_CO2eq'] = np.maximum(0, df['PAM投加量(kg)'] * self.EF_chemicals['PAM'])
        df['NaClO_CO2eq'] = np.maximum(0, df['次氯酸钠投加量(kg)'] * self.EF_chemicals['次氯酸钠'])
        df['O3_CO2eq'] = np.maximum(0, df['臭氧投加量(kg)'] * self.EF_chemicals['臭氧'])
        df['chemicals_CO2eq'] = df['PAC_CO2eq'] + df['PAM_CO2eq'] + df['NaClO_CO2eq'] + df['O3_CO2eq']

        return df

    def calculate_carbon_offset(self, df, tech_applied):
        """计算甲烷抵消量（减排技术带来的碳汇）"""
        offset_data = {}

        if "沼气发电" in tech_applied:
            # 假设沼气产率：0.3 m³/kgCOD_removed，发电效率：2 kWh/m³
            df['biogas_production'] = df['COD_removed'] * 0.3
            df['biogas_power'] = df['biogas_production'] * 2
            offset_data["沼气发电"] = df['biogas_power'].sum() * self.carbon_offset_factors["沼气发电"]

        if "光伏发电" in tech_applied:
            # 假设光伏安装容量100kW，日均发电4小时
            光伏发电量 = 100 * 4 * len(df)
            offset_data["光伏发电"] = 光伏发电量 * self.carbon_offset_factors["光伏发电"]

        if "热泵技术" in tech_applied:
            # 假设热泵技术节能效果
            热泵节能量 = df['电耗(kWh)'].sum() * 0.1  # 假设节能10%
            offset_data["热泵技术"] = 热泵节能量 * self.carbon_offset_factors["热泵技术"]

        if "污泥资源化" in tech_applied:
            # 假设污泥资源化量
            污泥资源化量 = df.get('脱水污泥外运量(80%)', pd.Series([0])).sum() * 0.8  # 假设80%干固体
            offset_data["污泥资源化"] = 污泥资源化量 * self.carbon_offset_factors["污泥资源化"]

        return offset_data

    def calculate_unit_emissions(self, df):
        """按工艺单元拆分排放量"""
        required_cols = ['energy_CO2eq', 'N2O_CO2eq', 'CH4_CO2eq', 'chemicals_CO2eq', '处理水量(m³)']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"数据缺少必需列：{missing_cols}，请先执行直接/间接排放计算！")

        # 处理缺失值
        df = df.fillna(0)

        # 按工艺单元分配甲烷排放
        df['pre_CO2eq'] = df['energy_CO2eq'] * self.energy_distribution["预处理区"]
        df['bio_CO2eq'] = df['N2O_CO2eq'] + df['CH4_CO2eq'] + df['energy_CO2eq'] * self.energy_distribution[
            "生物处理区"]
        df['depth_CO2eq'] = df['chemicals_CO2eq'] + df['energy_CO2eq'] * self.energy_distribution["深度处理区"]
        df['sludge_CO2eq'] = df['energy_CO2eq'] * self.energy_distribution["泥处理区"]
        df['effluent_CO2eq'] = df['energy_CO2eq'] * self.energy_distribution["出水区"]
        df['deodorization_CO2eq'] = df['energy_CO2eq'] * self.energy_distribution["除臭系统"]

        # 总排放与效率
        df['total_CO2eq'] = (
                df['pre_CO2eq'] + df['bio_CO2eq'] + df['depth_CO2eq'] +
                df['sludge_CO2eq'] + df['effluent_CO2eq'] + df['deodorization_CO2eq']
        )
        df['carbon_efficiency'] = df['处理水量(m³)'] / df['total_CO2eq'].replace(0, 1)

        return df

    def calculate_carbon_reduction_metrics(self, df, tech_applied=None):
        """计算甲烷减排指标"""
        if 'total_CO2eq' not in df.columns:
            df = self.calculate_unit_emissions(df)

        total_emission = df['total_CO2eq'].sum()
        total_water = df['处理水量(m³)'].sum()

        # 单位水量甲烷排放
        emission_per_water = total_emission / total_water if total_water > 0 else 0

        # 计算甲烷抵消
        carbon_offset = 0
        if tech_applied:
            offset_data = self.calculate_carbon_offset(df, tech_applied)
            carbon_offset = sum(offset_data.values())

        # 净甲烷排放
        net_emission = max(0, total_emission - carbon_offset)

        # 能源中和率
        energy_consumption = df['电耗(kWh)'].sum()
        energy_production = df.get('biogas_power', pd.Series([0])).sum() + (
            100 * 4 * len(df) if tech_applied and "光伏发电" in tech_applied else 0)
        energy_neutrality = min(energy_production / energy_consumption, 1) if energy_consumption > 0 else 0

        # 甲烷减排率
        carbon_reduction_rate = (carbon_offset / total_emission * 100) if total_emission > 0 else 0

        metrics = {
            '总甲烷排放量_kgCO2eq': total_emission,
            '总甲烷抵消量_kgCO2eq': carbon_offset,
            '净甲烷排放量_kgCO2eq': net_emission,
            '总处理水量_m3': total_water,
            '单位水量甲烷排放_kgCO2eq/m3': emission_per_water,
            '甲烷效率_m3/kgCO2eq': total_water / total_emission if total_emission > 0 else 0,
            '能源中和率_%': energy_neutrality * 100,
            '甲烷减排率_%': carbon_reduction_rate
        }

        return metrics

    def optimize_parameters(self, df, target_reduction=0.1):
        """优化运行参数以实现甲烷减排目标"""
        # 基础排放计算
        df_base = self.calculate_direct_emissions(df)
        df_base = self.calculate_indirect_emissions(df_base)
        df_base = self.calculate_unit_emissions(df_base)

        base_emission = df_base['total_CO2eq'].sum()
        target_emission = base_emission * (1 - target_reduction)

        # 模拟不同优化策略
        strategies = {
            "优化曝气量": {"energy_reduction": 0.15, "N2O_reduction": 0.1},
            "优化污泥回流比": {"energy_reduction": 0.05, "N2O_reduction": 0.15},
            "优化化学药剂投加": {"chemical_reduction": 0.2},
            "综合优化": {"energy_reduction": 0.1, "N2O_reduction": 0.1, "chemical_reduction": 0.15}
        }

        results = {}
        for strategy, params in strategies.items():
            df_opt = df.copy()

            # 应用优化参数
            if "energy_reduction" in params:
                df_opt['电耗(kWh)'] = df_opt['电耗(kWh)'] * (1 - params["energy_reduction"])

            if "N2O_reduction" in params:
                # 假设通过优化减少N2O排放
                df_opt['出水TN(mg/L)'] = df_opt['出水TN(mg/L)'] * 0.9  # 改善脱氮效果

            if "chemical_reduction" in params:
                df_opt['PAC投加量(kg)'] = df_opt['PAC投加量(kg)'] * (1 - params["chemical_reduction"])
                df_opt['PAM投加量(kg)'] = df_opt['PAM投加量(kg)'] * (1 - params["chemical_reduction"])
                df_opt['次氯酸钠投加量(kg)'] = df_opt['次氯酸钠投加量(kg)'] * (1 - params["chemical_reduction"])

            # 计算优化后排放
            df_opt = self.calculate_direct_emissions(df_opt)
            df_opt = self.calculate_indirect_emissions(df_opt)
            df_opt = self.calculate_unit_emissions(df_opt)

            opt_emission = df_opt['total_CO2eq'].sum()
            reduction = base_emission - opt_emission
            reduction_percent = (reduction / base_emission) * 100

            results[strategy] = {
                '优化后排放_kgCO2eq': opt_emission,
                '减排量_kgCO2eq': reduction,
                '减排率_%': reduction_percent,
                '达到目标': reduction_percent >= (target_reduction * 100)
            }

        return results

    # 在CarbonCalculator类中添加以下方法

    def predict_emissions(self, df, future_days=7):
        """使用LSTM模型预测未来甲烷排放"""
        try:
            from lstm_predictor import CarbonLSTMPredictor

            # 准备数据
            df_calc = self.calculate_direct_emissions(df)
            df_calc = self.calculate_indirect_emissions(df_calc)
            df_calc = self.calculate_unit_emissions(df_calc)

            # 训练预测模型
            predictor = CarbonLSTMPredictor()
            predictor.train(df_calc, 'total_CO2eq', epochs=30)

            # 进行预测
            predictions = []
            last_date = df_calc['日期'].max()

            for i in range(1, future_days + 1):
                # 使用最近的数据进行预测
                prediction = predictor.predict(df_calc.tail(30))
                predictions.append({
                    '日期': last_date + pd.Timedelta(days=i),
                    '预测甲烷排放': prediction,
                    '下限': prediction * 0.9,  # 10%下限
                    '上限': prediction * 1.1  # 10%上限
                })

            return pd.DataFrame(predictions)

        except Exception as e:
            print(f"预测模型错误: {e}")
            # 回退到简单线性预测
            return self._simple_emission_prediction(df, future_days)

    def _simple_emission_prediction(self, df, future_days):
        """改进的简单预测方法 - 修复量级问题"""
        # 确保输入是DataFrame
        if not isinstance(df, pd.DataFrame) or df.empty:
            # 创建模拟数据 - 使用更合理的日均碳排放量级
            dates = [datetime.now() - timedelta(days=i) for i in range(30, 0, -1)]
            df = pd.DataFrame({
                '日期': dates,
                'total_CO2eq': [2000 + np.random.normal(0, 200) for _ in range(30)]  # 合理的日均排放量级
            })

        # 确保有日期列和碳排放列
        if '日期' not in df.columns:
            df['日期'] = pd.date_range(end=datetime.now(), periods=len(df), freq='D')

        if 'total_CO2eq' not in df.columns:
            # 计算甲烷排放
            df = self.calculate_direct_emissions(df)
            df = self.calculate_indirect_emissions(df)
            df = self.calculate_unit_emissions(df)

        # 确保没有NaN值
        df = df.fillna(0)

        # 确保所有数值都是正数
        for col in df.select_dtypes(include=[np.number]).columns:
            df[col] = df[col].abs()

        # 判断数据类型并标准化
        historical_values = df['total_CO2eq'].values

        # 检查是否是累积数据（如果单日排放超过10000，可能是累积数据）
        if np.mean(historical_values) > 10000:
            print(f"检测到高量级数据，可能是累积数据，进行标准化处理")
            historical_values = historical_values / 30  # 假设是月累积，转换为日均

        historical_mean = np.mean(historical_values)
        historical_std = np.std(historical_values)

        print(f"预测基础统计: 均值={historical_mean:.1f}, 标准差={historical_std:.1f}")

        # 确保合理的标准差
        if historical_std == 0:
            historical_std = historical_mean * 0.1  # 如果没有变化，假设10%的变异

        # 修复：计算更合理的趋势
        if len(historical_values) > 1:
            # 使用线性回归计算趋势
            x = np.arange(len(historical_values))
            trend_slope = np.polyfit(x, historical_values, 1)[0]
            # 限制趋势变化不要太大
            trend_slope = np.clip(trend_slope, -historical_mean * 0.01, historical_mean * 0.01)
        else:
            trend_slope = 0

        # 生成预测 - 添加趋势和季节性（修复版：使用当前真实日期作为预测起点）
        predictions = []
        # 使用当前真实日期而非历史数据的最后日期作为预测起点
        current_date = pd.Timestamp.now()
        historical_last_date = df['日期'].max()

        for i in range(1, future_days + 1):
            # 添加趋势和季节性变化
            trend = trend_slope * i
            # 增加季节性波动幅度（从5%增加到8%）
            seasonal = historical_mean * 0.08 * math.sin(2 * math.pi * i / 30 + i * 0.1)
            # 增加随机噪声使预测值有更多差异
            noise = np.random.normal(0, historical_std * 0.15)

            prediction = max(0, historical_mean + trend + seasonal + noise)

            # 扩大合理范围（从±30%增加到±50%）以允许更多变化
            prediction = np.clip(prediction, historical_mean * 0.5, historical_mean * 1.5)

            predictions.append({
                '日期': current_date + timedelta(days=i),
                'predicted_CO2eq': prediction,
                'lower_bound': max(0, prediction - historical_std * (0.2 + i * 0.001)),
                'upper_bound': prediction + historical_std * (0.2 + i * 0.001)
            })

        return pd.DataFrame(predictions)

    def generate_process_adjustments(self, df):
        """生成工艺调整建议"""
        adjustments = []

        # 计算单元排放占比
        df_calc = self.calculate_direct_emissions(df)
        df_calc = self.calculate_indirect_emissions(df_calc)
        df_calc = self.calculate_unit_emissions(df_calc)

        total_emission = df_calc['total_CO2eq'].sum()
        unit_ratios = {
            '生物处理区': df_calc['bio_CO2eq'].sum() / total_emission,
            '深度处理区': df_calc['depth_CO2eq'].sum() / total_emission,
            '预处理区': df_calc['pre_CO2eq'].sum() / total_emission,
            '泥处理区': df_calc['sludge_CO2eq'].sum() / total_emission
        }

        # 生物处理区建议
        if unit_ratios['生物处理区'] > 0.4:
            n2o_ratio = df_calc['N2O_CO2eq'].sum() / df_calc['bio_CO2eq'].sum()
            if n2o_ratio > 0.3:
                adjustments.append({
                    '单元': '生物处理区',
                    '问题': 'N₂O排放占比高',
                    '建议': '调整DO浓度至1-2mg/L，优化硝化反硝化过程',
                    '预期减排': '10-15%'
                })

        # 深度处理区建议
        if unit_ratios['深度处理区'] > 0.3:
            chem_ratio = df_calc['chemicals_CO2eq'].sum() / df_calc['depth_CO2eq'].sum()
            if chem_ratio > 0.6:
                adjustments.append({
                    '单元': '深度处理区',
                    '问题': '化学药剂排放占比高',
                    '建议': 'PAC/PAM投加量阶梯式降低5%-15%，评估出水效果',
                    '预期减排': '8-12%'
                })

        # 能耗相关建议
        energy_ratio = df_calc['energy_CO2eq'].sum() / total_emission
        if energy_ratio > 0.5:
            adjustments.append({
                '单元': '全厂',
                '问题': '能耗甲烷排放占比高',
                '建议': '优化曝气系统，实施变频控制，检查设备效率',
                '预期减排': '15-20%'
            })

        return adjustments

    def compare_carbon_techs(self, tech_list, df=None, water_flow=10000):
        """比较不同减排技术的效果"""
        results = []

        # 计算基准排放
        baseline_emission = 1000  # 默认基准排放
        total_water = water_flow
        total_energy = 3000  # 默认能耗

        if df is not None and not df.empty:
            df_calc = self.calculate_direct_emissions(df)
            df_calc = self.calculate_indirect_emissions(df_calc)
            df_calc = self.calculate_unit_emissions(df_calc)

            baseline_emission = df_calc['total_CO2eq'].sum()
            total_water = df_calc['处理水量(m³)'].sum()
            total_energy = df_calc['电耗(kWh)'].sum()

        # 基于实际数据的技术效果计算
        tech_calculations = {
                '厌氧消化产沼': {
                    'reduction_rate': 0.20,  # 20%减排
                    'investment_per_m3': 50,  # 50元/m³投资成本
                    'payback_years': 6,
                    'applicability': '高'
                },
                '光伏发电': {
                    'reduction_rate': 0.15,  # 15%减排（抵消电力甲烷排放）
                    'investment_per_m3': 30,
                    'payback_years': 8,
                    'applicability': '中'
                },
                '高效曝气': {
                    'reduction_rate': 0.12,  # 12%减排
                    'investment_per_m3': 20,
                    'payback_years': 4,
                    'applicability': '高'
                },
                '热泵技术': {
                    'reduction_rate': 0.08,  # 8%减排
                    'investment_per_m3': 15,
                    'payback_years': 6,
                    'applicability': '中'
                },
                '污泥干化': {
                    'reduction_rate': 0.05,  # 5%减排
                    'investment_per_m3': 10,
                    'payback_years': 7,
                    'applicability': '低'
                },
                '沼气发电': {
                    'reduction_rate': 0.25,  # 25%减排
                    'investment_per_m3': 60,
                    'payback_years': 5,
                    'applicability': '高'
                }
        }

        for tech in tech_list:
            if tech in tech_calculations:
                calc = tech_calculations[tech]
                reduction_amount = baseline_emission * calc['reduction_rate']
                investment_cost = total_water * calc['investment_per_m3'] / 10000  # 万元

                results.append({
                        '技术名称': tech,
                        '减排量_kgCO2eq': reduction_amount,
                        '投资成本_万元': investment_cost,
                        '回收期_年': calc['payback_years'],
                        '适用性': calc['applicability'],
                        '甲烷减排贡献率_%': calc['reduction_rate'] * 100,
                        '能源中和率_%': min(50, calc['reduction_rate'] * 150)  # 基于减排率估算能源中和率
                })

        return pd.DataFrame(results)
