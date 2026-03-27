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

print(f'=== TensorFlow可用: {TENSORFLOW_AVAILABLE} ===')

# 计算碳排放
calc = CarbonCalculator()
df = calc.calculate_direct_emissions(test_data)
df = calc.calculate_indirect_emissions(df)
df = calc.calculate_unit_emissions(df)

print(f'数据形状: {df.shape}')
print(f'包含total_CO2eq: {"total_CO2eq" in df.columns}')

# 加载预测器
predictor = CarbonLSTMPredictor()
print(f'初始化后模型为None: {predictor.model is None}')

# 加载模型
loaded = predictor.load_model('models/carbon_lstm_model.keras')
print(f'模型加载结果: {loaded}')
print(f'加载后模型为None: {predictor.model is None}')

# 进行预测
if predictor.model is not None:
    print('\n=== 尝试使用LSTM进行预测 ===')
    try:
        pred = predictor.predict(df, 'total_CO2eq', steps=12)
        print(f'预测成功！结果行数: {len(pred)}')
        print(f'预测列: {list(pred.columns)}')
        print('\n前3个月预测值:')
        print(pred[['年月', 'predicted_CO2eq']].head(3))
        print('\n预测值是否有变化:')
        print(pred['predicted_CO2eq'].describe())
    except Exception as e:
        print(f'预测出错: {e}')
        import traceback
        traceback.print_exc()
else:
    print('\n=== 使用备用预测模式 ===')
    pred = predictor.predict(df, 'total_CO2eq', steps=12)
    print(f'预测成功！结果行数: {len(pred)}')
    print(f'预测列: {list(pred.columns)}')
    print('\n前3个月预测值:')
    print(pred[['年月', 'predicted_CO2eq']].head(3))
    print('\n预测值是否有变化:')
    print(pred['predicted_CO2eq'].describe())
