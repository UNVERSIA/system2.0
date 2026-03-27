import pandas as pd
import numpy as np
import logging
logging.basicConfig(level=logging.INFO)

# 创建测试数据
dates = pd.date_range('2024-01-01', '2025-12-31', freq='D')
np.random.seed(42)
test_data = pd.DataFrame({
    '日期': dates,
    '处理水量(m³)': np.random.normal(10000, 500, len(dates)),
    '电耗(kWh)': np.random.normal(3000, 200, len(dates)),
    'PAC投加量(kg)': np.random.normal(200, 20, len(dates)),
    'PAM投加量(kg)': np.random.normal(50, 5, len(dates)),
    '次氯酸钠投加量(kg)': np.random.normal(100, 10, len(dates)),
    '进水COD(mg/L)': np.random.normal(250, 20, len(dates)),
    '出水COD(mg/L)': np.random.normal(50, 5, len(dates)),
    '进水TN(mg/L)': np.random.normal(40, 3, len(dates)),
    '出水TN(mg/L)': np.random.normal(15, 2, len(dates))
})

from lstm_predictor import CarbonLSTMPredictor, TENSORFLOW_AVAILABLE
from carbon_calculator import CarbonCalculator

# 计算碳排放
calc = CarbonCalculator()
df = calc.calculate_direct_emissions(test_data)
df = calc.calculate_indirect_emissions(df)
df = calc.calculate_unit_emissions(df)

# 加载预测器
predictor = CarbonLSTMPredictor()
loaded = predictor.load_model('models/carbon_lstm_model.keras')

print(f'TensorFlow可用: {TENSORFLOW_AVAILABLE}')
print(f'模型加载成功: {loaded}')
print(f'模型为None: {predictor.model is None}')

# 打印目标缩放器状态
try:
    print(f'target_scaler data_min: {predictor.target_scaler.data_min_}')
    print(f'target_scaler data_max: {predictor.target_scaler.data_max_}')
    print(f'target_scaler scale: {predictor.target_scaler.scale_}')
except:
    print('target_scaler未拟合')

# 进行完整预测
print('\n=== 完整预测 ===')
pred_df = predictor.predict(df, 'total_CO2eq', steps=12)

print('\n预测结果:')
print(pred_df[['年月', 'predicted_CO2eq']])

print(f'\n预测值变化:')
print(f'最小值: {pred_df["predicted_CO2eq"].min():.2f}')
print(f'最大值: {pred_df["predicted_CO2eq"].max():.2f}')
print(f'标准差: {pred_df["predicted_CO2eq"].std():.2f}')
print(f'变异系数: {pred_df["predicted_CO2eq"].std() / pred_df["predicted_CO2eq"].mean() * 100:.2f}%')
