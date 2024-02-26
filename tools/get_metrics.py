import cv2
import numpy as np
import csv
from skimage.metrics import structural_similarity as ssim
import lpips
import torch

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
        writer.writerow(["True Image", "Generated Image", "SSIM", "PSNR", "LPIPS"])

        ssim_sum, psnr_sum, lpips_sum = 0, 0, 0

        for true_image_path, generated_image_path in image_pairs:
            ssim_value, psnr_value, lpips_value = calculate_metrics(true_image_path, generated_image_path)
            writer.writerow([true_image_path, generated_image_path, ssim_value, psnr_value, lpips_value])

            ssim_sum += ssim_value
            psnr_sum += psnr_value
            lpips_sum += lpips_value

        num_pairs = len(image_pairs)
        writer.writerow(["Average", "", ssim_sum / num_pairs, psnr_sum / num_pairs, lpips_sum / num_pairs])

# 使用示例
image_pairs = [
    ('data/EuRoC/mav0/cam0/data/1403636579763555584.png', 'data/EuRoC/mav0/cam1/data/1403636579763555584.png'),
    ('data/EuRoC/mav0/cam0/data/1403636583713555456.png', 'data/EuRoC/mav0/cam1/data/1403636583713555456.png'),
    ('data/EuRoC/mav0/cam0/data/1403636591463555584.png', 'data/EuRoC/mav0/cam1/data/1403636591463555584.png'),
    # 更多图像对...
]
save_metrics_to_csv(image_pairs, 'metrics.csv')