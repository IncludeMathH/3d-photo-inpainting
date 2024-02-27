import cv2
import numpy as np
import csv
from skimage.metrics import structural_similarity as ssim
import lpips
import torch
import glob
import pandas as pd
import os

def calculate_metrics(true_image_path, generated_image_path):
    true_image = cv2.imread(true_image_path)
    generated_image = cv2.imread(generated_image_path)

    assert true_image.shape == generated_image.shape, "Images must have the same dimensions."

    ssim_value = ssim(true_image, generated_image, multichannel=True)

    mse = np.mean((true_image - generated_image) ** 2)
    if mse == 0:
        psnr_value = 100
    else:
        max_pixel = 255.0
        psnr_value = 20 * np.log10(max_pixel / np.sqrt(mse))

    loss_fn = lpips.LPIPS(net='vgg')
    true_image = torch.unsqueeze(torch.from_numpy(np.transpose(true_image, (2,0,1))), 0).float()
    generated_image = torch.unsqueeze(torch.from_numpy(np.transpose(generated_image, (2,0,1))), 0).float()
    lpips_value = loss_fn(true_image, generated_image)

    return ssim_value, psnr_value, lpips_value.item()

def save_metrics_to_csv(image_pairs, csv_file_path):
    with open(csv_file_path, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Target Image", "Generated Image", "SSIM", "PSNR", "LPIPS"])

        ssim_sum, psnr_sum, lpips_sum = 0, 0, 0

        for true_image_path, generated_image_path in image_pairs:
            ssim_value, psnr_value, lpips_value = calculate_metrics(true_image_path, generated_image_path)
            writer.writerow([true_image_path, generated_image_path, ssim_value, psnr_value, lpips_value])

            ssim_sum += ssim_value
            psnr_sum += psnr_value
            lpips_sum += lpips_value

        num_pairs = len(image_pairs)
        writer.writerow(["Average", "", ssim_sum / num_pairs, psnr_sum / num_pairs, lpips_sum / num_pairs])

csv_dir = 'work_dirs/sample_euroc/*.csv'
files = glob.glob(csv_dir)
dtype = {
    'Reference Timestamp': str,
    'Target Timestamp': str,
}
scene_name = os.path.basename(csv_dir).split('.')[0]

image_pairs = []
# 遍历所有的CSV文件
for file in files:
    # 读取CSV文件
    data = pd.read_csv(file, dtype=dtype)
    ref_imgs = data['Reference Timestamp'].tolist()
    tgt_imgs = data['Target Timestamp'].tolist()
    pred_list = [os.path.join('video/IGEV', scene_name + '-cam0-' + ref_stamp + '_novel_view.png') for ref_stamp in ref_imgs]
    tgt_list = [os.path.join('data/EuRoC', scene_name, 'mav0', 'cam0', 'data',  tgt_stamp + '.png') for tgt_stamp in tgt_imgs]
    image_pairs.extend(zip(tgt_list, pred_list))

save_metrics_to_csv(image_pairs, 'metrics.csv')