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

# 准备月度数据
if '年月' not in df.columns:
    df = predictor._convert_to_monthly(df)
df = df.sort_values('日期').reset_index(drop=True)
df = predictor._enhanced_data_preprocessing(df)

historical_values = df['total_CO2eq'].values
historical_mean = np.mean(historical_values)
historical_std = np.std(historical_values)

print(f'历史均值: {historical_mean:.2f}')
print(f'历史标准差: {historical_std:.2f}')

# 准备特征数据
X = predictor._prepare_features_for_prediction(df.tail(12))
current_sequence = X[-1:].copy()

# 使用独立的RandomState
rng = np.random.RandomState(42)

# 模拟5次预测迭代
print('\n=== 模拟预测循环 ===')
predictions = []
for i in range(5):
    # LSTM预测
    pred_scaled = predictor.model.predict(current_sequence, verbose=0)[0][0]
    pred_original = pred_scaled
    
    # 添加扰动
    month_index = i % 12
    month_noise = rng.normal(0, 0.08)
    pred_scaled = pred_scaled + month_noise
    
    # 逆变换
    try:
        pred = predictor.target_scaler.inverse_transform([[pred_scaled]])[0][0]
    except:
        pred = historical_mean * pred_scaled
    
    pred_before_forced = pred
    
    # 添加强制扰动
    forced_variation = rng.normal(0, historical_std * 0.15)
    pred = pred + forced_variation
    
    print(f'步骤{i}: LSTM输出={pred_original:.6f}, 加噪声后={pred_scaled:.6f}, 逆变换后={pred_before_forced:.2f}, 最终={pred:.2f}')
    
    predictions.append(pred)
    
    # 更新序列
    current_sequence = predictor._update_prediction_sequence(current_sequence, pred_scaled, historical_mean, i)

print(f'\n预测值: {predictions}')
print(f'标准差: {np.std(predictions):.2f}')
