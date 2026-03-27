# create_pretrained_model.py
import pandas as pd
from carbon_calculator import CarbonCalculator
from lstm_predictor import CarbonLSTMPredictor
from data_simulator import DataSimulator
import os


def create_pretrained_model():
    """创建月度预训练模型"""
    # 确保目录存在
    os.makedirs("models", exist_ok=True)

    # 生成模拟数据
    simulator = DataSimulator()
    daily_data = simulator.generate_simulated_data()

    # 计算甲烷排放
    calculator = CarbonCalculator()
    daily_data_with_emissions = calculator.calculate_direct_emissions(daily_data)
    daily_data_with_emissions = calculator.calculate_indirect_emissions(daily_data_with_emissions)
    daily_data_with_emissions = calculator.calculate_unit_emissions(daily_data_with_emissions)

    # 初始化月度预测器并转换为月度数据
    predictor = CarbonLSTMPredictor()
    monthly_data = predictor._convert_to_monthly(daily_data_with_emissions)

    # 确保所有必需的特征列都存在
    for col in predictor.feature_columns:
        if col not in monthly_data.columns:
            if col == '处理水量(m³)':
                monthly_data[col] = 10000
            elif col == '电耗(kWh)':
                monthly_data[col] = 3000
            elif col in ['PAC投加量(kg)', 'PAM投加量(kg)', '次氯酸钠投加量(kg)']:
                monthly_data[col] = 0
            elif col in ['进水COD(mg/L)', '出水COD(mg/L)', '进水TN(mg/L)', '出水TN(mg/L)']:
                if col == '进水COD(mg/L)':
                    monthly_data[col] = 200
                elif col == '出水COD(mg/L)':
                    monthly_data[col] = 50
                elif col == '进水TN(mg/L)':
                    monthly_data[col] = 40
                elif col == '出水TN(mg/L)':
                    monthly_data[col] = 15

    # 获取当前文件所在目录的绝对路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(current_dir, "models")
    save_path = os.path.join(models_dir, "carbon_lstm_model.keras")

    # 训练月度模型 - 使用更长的训练轮次因为月度数据较少
    predictor = CarbonLSTMPredictor()
    history = predictor.train(
        monthly_data,
        'total_CO2eq',
        epochs=100,  # 增加训练轮次
        batch_size=8,  # 减小批次大小适应月度数据
        save_path=save_path
    )

    print("月度预训练模型已创建并保存到 models/carbon_lstm_model.keras")

if __name__ == "__main__":
    create_pretrained_model()
