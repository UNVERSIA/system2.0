import pandas as pd
import numpy as np
import logging
logging.basicConfig(level=logging.DEBUG)

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

# 加载预测器
predictor = CarbonLSTMPredictor()
loaded = predictor.load_model('models/carbon_lstm_model.keras')
print(f'模型加载: {loaded}, model为None: {predictor.model is None}')

# 准备月度数据
if '年月' not in df.columns:
    df = predictor._convert_to_monthly(df)
df = df.sort_values('日期').reset_index(drop=True)
df = predictor._enhanced_data_preprocessing(df)

print(f'月度数据形状: {df.shape}')
print(f'历史数据均值: {df["total_CO2eq"].mean():.2f}')
print(f'历史数据标准差: {df["total_CO2eq"].std():.2f}')

# 准备特征数据
X = predictor._prepare_features_for_prediction(df.tail(12))
print(f'特征数据形状: {X.shape}')
print(f'特征数据样本: {X[0, -1, :3]}')  # 最后一个时间步的前3个特征

# 使用模型预测几次，看输出是否变化
if predictor.model is not None:
    print('\n=== 测试LSTM模型输出 ===')
    preds = []
    for i in range(5):
        # 添加一些小的扰动到输入
        X_test = X.copy()
        X_test[0, -1, :] = X_test[0, -1, :] * np.random.uniform(0.95, 1.05, size=X_test.shape[2])
        pred_scaled = predictor.model.predict(X_test, verbose=0)[0][0]
        preds.append(pred_scaled)
        print(f'预测 {i+1}: {pred_scaled:.6f}')
    print(f'预测值标准差: {np.std(preds):.8f}')

# 进行完整预测
print('\n=== 进行完整预测 ===')
pred_df = predictor.predict(df, 'total_CO2eq', steps=12)
print('\n预测结果:')
for idx, row in pred_df.iterrows():
    print(f"{row['年月']}: {row['predicted_CO2eq']:.2f}")

print(f'\n预测值统计:')
print(pred_df['predicted_CO2eq'].describe())
