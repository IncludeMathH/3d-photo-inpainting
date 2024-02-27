import pandas as pd
import random
import os

file_names = ['data/EuRoC/MH01_GT.txt', 'data/EuRoC/MH02_GT.txt', 'data/EuRoC/MH03_GT.txt', 'data/EuRoC/MH04_GT.txt', 'data/EuRoC/MH05_GT.txt',
              'data/EuRoC/V101_GT.txt', 'data/EuRoC/V102_GT.txt', 'data/EuRoC/V103_GT.txt', 
              'data/EuRoC/V201_GT.txt', 'data/EuRoC/V202_GT.txt', 'data/EuRoC/V203_GT.txt']
num_sequences = 2

dtype = {
    '#timestamp [ns]': str,
    'px': float,
    'py': float,
    'pz': float,
    'qw': float,
    'qx': float,
    'qy': float,
    'qz': float,
}

# 读取文件
for file_name in file_names:
    data = pd.read_csv(file_name, dtype=dtype)  # .astype({'#timestamp [ns]': 'int'}) # 如果是空格分隔，使用sep=" "
    print(data.head())
    # 将'#timestamp [ns]'列转换为整数
    data['#timestamp [ns]'] = data['#timestamp [ns]'].astype(float).astype(int)
    print(data.head())

    # 确保我们有足够的行来选择
    assert len(data) > 20, "File doesn't have enough lines."

    # 随机选择两个不同的索引
    indices = random.sample(range(len(data) - 10), num_sequences)

    # 记录选择的行和对应的第十行
    selected_lines = [(data.iloc[i]['#timestamp [ns]'], data.iloc[i+10]['#timestamp [ns]']) for i in indices]
    print(f'{file_name} has {len(data)} lines, and we selected {selected_lines}.')
    # breakpoint()

    # 创建一个新的DataFrame来保存结果
    result = pd.DataFrame(selected_lines, columns=['Reference Timestamp', 'Target Timestamp'], dtype=int)

    # 保存到新的CSV文件
    prefix = os.path.basename(file_name).split('_')[0]
    result.to_csv(f'work_dirs/sample_euroc/{prefix}.csv', index=False)

    # # 打印结果
    # for ref, target in selected_lines:
    #     print(f'Reference image timestamp: {ref}')
    #     print(f'Target image timestamp: {target}')
