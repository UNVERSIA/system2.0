import numpy as np
import pandas as pd
from scipy.optimize import minimize


class OptimizationEngine:
    def __init__(self, carbon_calculator):
        self.calculator = carbon_calculator

    def calculate_emissions(self, params, baseline_data):
        """计算给定参数下的甲烷排放"""
        # 复制基线数据
        data = baseline_data.copy()

        # 应用参数调整
        # 参数格式: {参数名: 调整比例}
        for param_name, adjustment in params.items():
            if param_name in data.columns:
                data[param_name] = data[param_name] * (1 + adjustment)

        # 计算甲烷排放
        data = self.calculator.calculate_direct_emissions(data)
        data = self.calculator.calculate_indirect_emissions(data)
        data = self.calculator.calculate_unit_emissions(data)

        return data['total_CO2eq'].sum()

    def objective_function(self, params, baseline_data, baseline_emission):
        """优化目标函数：最小化甲烷排放"""
        # 将参数从数组转换为字典
        param_dict = {
            '电耗(kWh)': params[0],
            'PAC投加量(kg)': params[1],
            'PAM投加量(kg)': params[2],
            '次氯酸钠投加量(kg)': params[3]
        }

        # 计算新排放
        new_emission = self.calculate_emissions(param_dict, baseline_data)

        # 返回排放减少量（负值表示减少）
        return new_emission - baseline_emission

    def constraints(self, params):
        """约束条件：参数调整范围"""
        # 参数调整范围限制
        # 电耗: -20% 到 +10%
        # PAC: -30% 到 +10%
        # PAM: -30% 到 +10%
        # 次氯酸钠: -30% 到 +10%
        constraints = []
        constraints.append({'type': 'ineq', 'fun': lambda x: x[0] + 0.2})  # 电耗不低于-20%
        constraints.append({'type': 'ineq', 'fun': lambda x: 0.1 - x[0]})  # 电耗不高于+10%
        constraints.append({'type': 'ineq', 'fun': lambda x: x[1] + 0.3})  # PAC不低于-30%
        constraints.append({'type': 'ineq', 'fun': lambda x: 0.1 - x[1]})  # PAC不高于+10%
        constraints.append({'type': 'ineq', 'fun': lambda x: x[2] + 0.3})  # PAM不低于-30%
        constraints.append({'type': 'ineq', 'fun': lambda x: 0.1 - x[2]})  # PAM不高于+10%
        constraints.append({'type': 'ineq', 'fun': lambda x: x[3] + 0.3})  # 次氯酸钠不低于-30%
        constraints.append({'type': 'ineq', 'fun': lambda x: 0.1 - x[3]})  # 次氯酸钠不高于+10%

        return constraints

    def optimize_parameters(self, baseline_data, initial_params=None):
        """优化运行参数"""
        # 计算基线排放
        baseline_data_calc = self.calculator.calculate_direct_emissions(baseline_data)
        baseline_data_calc = self.calculator.calculate_indirect_emissions(baseline_data_calc)
        baseline_data_calc = self.calculator.calculate_unit_emissions(baseline_data_calc)
        baseline_emission = baseline_data_calc['total_CO2eq'].sum()

        # 设置初始参数（无调整）
        if initial_params is None:
            initial_params = [0, 0, 0, 0]  # 电耗, PAC, PAM, 次氯酸钠

        # 定义优化问题
        result = minimize(
            fun=self.objective_function,
            x0=initial_params,
            args=(baseline_data, baseline_emission),
            constraints=self.constraints(initial_params),
            method='SLSQP',
            options={'maxiter': 100, 'ftol': 1e-6}
        )

        # 解析优化结果
        optimized_params = {
            '电耗(kWh)': result.x[0],
            'PAC投加量(kg)': result.x[1],
            'PAM投加量(kg)': result.x[2],
            '次氯酸钠投加量(kg)': result.x[3]
        }

        # 计算优化后的排放
        optimized_emission = self.calculate_emissions(optimized_params, baseline_data)
        reduction = baseline_emission - optimized_emission
        reduction_percent = (reduction / baseline_emission) * 100

        return {
            'optimized_params': optimized_params,
            'baseline_emission': baseline_emission,
            'optimized_emission': optimized_emission,
            'reduction': reduction,
            'reduction_percent': reduction_percent,
            'success': result.success,
            'message': result.message
        }

    def simulate_scenario(self, baseline_data, scenario_params):
        """模拟特定场景下的甲烷排放"""
        # 计算基线排放
        baseline_data_calc = self.calculator.calculate_direct_emissions(baseline_data)
        baseline_data_calc = self.calculator.calculate_indirect_emissions(baseline_data_calc)
        baseline_data_calc = self.calculator.calculate_unit_emissions(baseline_data_calc)
        baseline_emission = baseline_data_calc['total_CO2eq'].sum()

        # 计算场景排放
        scenario_emission = self.calculate_emissions(scenario_params, baseline_data)
        reduction = baseline_emission - scenario_emission
        reduction_percent = (reduction / baseline_emission) * 100

        return {
            'scenario_emission': scenario_emission,
            'baseline_emission': baseline_emission,
            'reduction': reduction,
            'reduction_percent': reduction_percent
        }

    def sensitivity_analysis(self, baseline_data, param_name, range_min=-0.3, range_max=0.1, steps=10):
        """参数敏感性分析"""
        results = []
        step_size = (range_max - range_min) / steps

        for i in range(steps + 1):
            adjustment = range_min + i * step_size
            params = {param_name: adjustment}

            emission = self.calculate_emissions(params, baseline_data)
            baseline_emission = self.calculate_emissions({}, baseline_data)
            reduction = baseline_emission - emission
            reduction_percent = (reduction / baseline_emission) * 100

            results.append({
                'adjustment': adjustment,
                'adjustment_percent': adjustment * 100,
                'emission': emission,
                'reduction': reduction,
                'reduction_percent': reduction_percent
            })

        return pd.DataFrame(results)

    # 在OptimizationEngine类中添加以下方法

    def predict_emissions(self, historical_data, future_days=7):
        """预测未来甲烷排放趋势"""
        from carbon_calculator import CarbonCalculator

        calculator = CarbonCalculator()
        return calculator.predict_emissions(historical_data, future_days)

    def reinforcement_learning_optimization(self, baseline_data, target_reduction=0.1):
        """使用强化学习优化运行参数"""
        # 简化版的强化学习优化
        # 实际应用中应使用PPO等算法

        best_params = None
        best_emission = float('inf')
        best_reduction = 0

        # 参数搜索空间
        param_ranges = {
            'aeration_adjust': np.linspace(-30, 10, 9),  # 曝气调整 -30% 到 +10%
            'pac_adjust': np.linspace(-30, 0, 7),  # PAC调整 -30% 到 0%
            'sludge_ratio': np.linspace(0.3, 0.8, 6)  # 污泥回流比 0.3-0.8
        }

        # 简化搜索（实际应使用更高效的算法）
        for aeration in param_ranges['aeration_adjust']:
            for pac in param_ranges['pac_adjust']:
                for sludge in param_ranges['sludge_ratio']:
                    # 应用参数
                    adjusted_data = baseline_data.copy()
                    adjusted_data['电耗(kWh)'] = adjusted_data['电耗(kWh)'] * (1 + aeration / 100)
                    adjusted_data['PAC投加量(kg)'] = adjusted_data['PAC投加量(kg)'] * (1 + pac / 100)

                    # 计算排放
                    emission = self.calculate_emissions({
                        '电耗(kWh)': aeration / 100,
                        'PAC投加量(kg)': pac / 100,
                        'sludge_ratio': sludge
                    }, baseline_data)

                    # 检查是否是最优解
                    baseline_emission = self.calculate_emissions({}, baseline_data)
                    reduction = (baseline_emission - emission) / baseline_emission

                    if reduction >= target_reduction and emission < best_emission:
                        best_emission = emission
                        best_reduction = reduction
                        best_params = {
                            'aeration_adjust': aeration,
                            'pac_adjust': pac,
                            'sludge_ratio': sludge
                        }

        return best_params, best_emission, best_reduction

    def multi_parameter_sensitivity(self, baseline_data, params_list, ranges):
        """多参数敏感性分析"""
        results = []

        for param in params_list:
            sensitivity_df = self.sensitivity_analysis(baseline_data, param,
                                                       ranges[param][0], ranges[param][1])
            results.append({
                'parameter': param,
                'data': sensitivity_df
            })

        return results

    def map_to_engineering_measures(self, optimized_params):
        """将优化参数映射为具体工程措施"""
        measures = []

        if 'aeration_adjust' in optimized_params:
            adjust = optimized_params['aeration_adjust']
            if adjust < 0:
                freq = max(30, 50 + adjust * 0.67)  # 计算风机频率
                measures.append(f"调整曝气风机频率至 {freq:.1f}Hz (降低{-adjust:.1f}%)")

        if 'pac_adjust' in optimized_params:
            adjust = optimized_params['pac_adjust']
            if adjust < 0:
                measures.append(f"减少PAC投加量 {-adjust:.1f}%，加强混凝效果监测")

        if 'sludge_ratio' in optimized_params:
            ratio = optimized_params['sludge_ratio']
            measures.append(f"调整污泥回流比至 {ratio:.2f}，优化生物处理效果")

        return measures


# 使用示例
if __name__ == "__main__":
    # 加载数据
    data = pd.read_csv("data/simulated_data.csv")
    data['日期'] = pd.to_datetime(data['日期'])

    # 选择最近一个月的数据作为基线
    recent_data = data.tail(30).copy()

    # 初始化甲烷计算器和优化引擎
    calculator = CarbonCalculator()
    optimizer = OptimizationEngine(calculator)

    # 运行优化
    result = optimizer.optimize_parameters(recent_data)

    print("优化结果:")
    print(f"基线排放: {result['baseline_emission']:.2f} kgCO2eq")
    print(f"优化后排放: {result['optimized_emission']:.2f} kgCO2eq")
    print(f"减排量: {result['reduction']:.2f} kgCO2eq ({result['reduction_percent']:.2f}%)")
    print("优化参数调整:")
    for param, adjustment in result['optimized_params'].items():
        print(f"  {param}: {adjustment * 100:+.2f}%")
