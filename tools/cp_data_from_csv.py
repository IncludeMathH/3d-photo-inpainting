import glob
import pandas as pd
import os
import shutil

def get_reference_timestamps(csv_dir):
    # 获取所有CSV文件
    files = glob.glob(csv_dir)

    # 初始化一个空列表来保存所有的参考图像时间戳
    reference_timestamps = {}

    # 遍历所有的CSV文件
    for file in files:
        # 读取CSV文件
        data = pd.read_csv(file)
        # 添加参考图像时间戳到列表
        reference_timestamps[os.path.basename(file).split('.')[0]] = data['Reference Timestamp'].tolist()

    return reference_timestamps

def convert_filename(filename):
    # 分割文件名
    parts = filename.split('/')
    # 组合新的文件名
    new_filename = f"{parts[2]}-{parts[4]}-{parts[-1].split('.')[0]}"
    return new_filename

timestamps = get_reference_timestamps('work_dirs/sample_euroc/*.csv')
left_images = []
right_images = []
dataset_dir = 'data/EuRoC'
dest_dir = 'data/EuRoC/sampled'
for folder_name, stamps in timestamps.items():
    for stamp in stamps:
        left_img_dir = os.path.join(dataset_dir, folder_name, 'mav0/cam0/data', f'{stamp}.png')
        left_img_newname = convert_filename(left_img_dir) + '.png'
        shutil.copy(left_img_dir, os.path.join(dest_dir, left_img_newname))