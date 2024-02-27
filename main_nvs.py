import numpy as np
import argparse
import glob
import os
from functools import partial
import vispy
import scipy.misc as misc
from tqdm import tqdm
import yaml
import time
import sys
from mesh import write_ply, read_ply, output_3d_photo, output_novel_view
from utils import get_MiDaS_samples, read_MiDaS_depth
import torch
import cv2
from skimage.transform import resize
import imageio
import copy
from networks import Inpaint_Color_Net, Inpaint_Depth_Net, Inpaint_Edge_Net
from MiDaS.run import run_depth
from boostmonodepth_utils import run_boostmonodepth
from MiDaS.monodepth_net import MonoDepthNet
import MiDaS.MiDaS_utils as MiDaS_utils
from bilateral_filtering import sparse_bilateral_filtering
import pandas as pd

def read_quaternions_from_csv(file_path):
    dtype = {
    '#timestamp [ns]': str,
    'q_RS_w []': float,
    'q_RS_x []': float,
    'q_RS_y []': float,
    'q_RS_z []': float,
    'p_RS_R_x [m]': float,
    'p_RS_R_y [m]': float,
    'p_RS_R_z [m]': float,
    }
    df = pd.read_csv(file_path, dtype=dtype)
    df['#timestamp [ns]'] = df['#timestamp [ns]'].astype(float).astype(int)
    quaternions = df[['#timestamp [ns]', 'q_RS_w []', 'q_RS_x []', 'q_RS_y []', 'q_RS_z []', 'p_RS_R_x [m]', 'p_RS_R_y [m]', 'p_RS_R_z [m]']]
    return quaternions

def get_quaternion_by_timestamp(quaternions, timestamp):
    quaternion = quaternions[quaternions['#timestamp [ns]'] == timestamp]
    return quaternion

def quaternion_to_rotation_matrix(quaternion_df):
    quaternion = quaternion_df[['q_RS_w []', 'q_RS_x []', 'q_RS_y []', 'q_RS_z []']].values[0]
    w, x, y, z = quaternion
    Nq = w*w + x*x + y*y + z*z
    if Nq < np.finfo(float).eps:
        return np.identity(3)
    s = 2.0/Nq
    X = x*s; Y = y*s; Z = z*s
    wX = w*X; wY = w*Y; wZ = w*Z
    xX = x*X; xY = x*Y; xZ = x*Z
    yY = y*Y; yZ = y*Z; zZ = z*Z
    return np.array(
           [[ 1.0-(yY+zZ), xY-wZ, xZ+wY ],
            [ xY+wZ, 1.0-(xX+zZ), yZ-wX ],
            [ xZ-wY, yZ+wX, 1.0-(xX+yY) ]])

def quaternion_to_position(quaternion_df):
    position = quaternion_df[['p_RS_R_x [m]', 'p_RS_R_y [m]', 'p_RS_R_z [m]']].values[0]
    return position

def get_pose_matrix(rotation_matrix, x, y, z):
    pose_matrix = np.eye(4)
    pose_matrix[:3, :3] = rotation_matrix
    pose_matrix[:3, 3] = [x, y, z]
    return pose_matrix

def timestamp_to_pose_matrix(quaternions, timestamp):
    quaternion = get_quaternion_by_timestamp(quaternions, timestamp)
    rotation_matrix = quaternion_to_rotation_matrix(quaternion)
    x, y, z = quaternion_to_position(quaternion)
    pose_matrix = get_pose_matrix(rotation_matrix, x, y, z)
    return pose_matrix

parser = argparse.ArgumentParser()
parser.add_argument('--config', type=str, default='argument_euroc.yml',help='Configure of post processing')
args = parser.parse_args()
config = yaml.full_load(open(args.config, 'r'))
if config['offscreen_rendering'] is True:
    vispy.use(app='egl')
os.makedirs(config['mesh_folder'], exist_ok=True)
os.makedirs(config['video_folder'], exist_ok=True)
os.makedirs(config['depth_folder'], exist_ok=True)
sample_list = get_MiDaS_samples(config['src_folder'], config['depth_folder'], config, config['specific'])
normal_canvas, all_canvas = None, None

if isinstance(config["gpu_ids"], int) and (config["gpu_ids"] >= 0):
    device = config["gpu_ids"]
else:
    device = "cpu"

print(f"running on device {device}")

for idx in tqdm(range(len(sample_list))):
    depth = None
    sample = sample_list[idx]
    print("Current Source ==> ", sample['src_pair_name'])
    mesh_fi = os.path.join(config['mesh_folder'], sample['src_pair_name'] +'.ply')
    image = imageio.imread(sample['ref_img_fi'])

    print(f"Running depth extraction at {time.time()}")
    if config['use_boostmonodepth'] is True:
        run_boostmonodepth(sample['ref_img_fi'], config['src_folder'], config['depth_folder'])
    elif config['require_midas'] is True:
        run_depth([sample['ref_img_fi']], config['src_folder'], config['depth_folder'],
                  config['MiDaS_model_ckpt'], MonoDepthNet, MiDaS_utils, target_w=640)

    if 'npy' in config['depth_format']:
        config['output_h'], config['output_w'] = np.load(sample['depth_fi']).shape[:2]
    else:
        config['output_h'], config['output_w'] = imageio.imread(sample['depth_fi']).shape[:2]
    frac = config['longer_side_len'] / max(config['output_h'], config['output_w'])
    config['output_h'], config['output_w'] = int(config['output_h'] * frac), int(config['output_w'] * frac)
    config['original_h'], config['original_w'] = config['output_h'], config['output_w']
    if image.ndim == 2:
        image = image[..., None].repeat(3, -1)
    if np.sum(np.abs(image[..., 0] - image[..., 1])) == 0 and np.sum(np.abs(image[..., 1] - image[..., 2])) == 0:
        config['gray_image'] = True
    else:
        config['gray_image'] = False
    image = cv2.resize(image, (config['output_w'], config['output_h']), interpolation=cv2.INTER_AREA)
    depth = read_MiDaS_depth(sample['depth_fi'], 3.0, config['output_h'], config['output_w'])
    mean_loc_depth = depth[depth.shape[0]//2, depth.shape[1]//2]
    if not(config['load_ply'] is True and os.path.exists(mesh_fi)):
        vis_photos, vis_depths = sparse_bilateral_filtering(depth.copy(), image.copy(), config, num_iter=config['sparse_iter'], spdb=False)
        depth = vis_depths[-1]
        model = None
        torch.cuda.empty_cache()
        print("Start Running 3D_Photo ...")
        print(f"Loading edge model at {time.time()}")
        depth_edge_model = Inpaint_Edge_Net(init_weights=True)
        depth_edge_weight = torch.load(config['depth_edge_model_ckpt'],
                                       map_location=torch.device(device))
        depth_edge_model.load_state_dict(depth_edge_weight)
        depth_edge_model = depth_edge_model.to(device)
        depth_edge_model.eval()

        print(f"Loading depth model at {time.time()}")
        depth_feat_model = Inpaint_Depth_Net()
        depth_feat_weight = torch.load(config['depth_feat_model_ckpt'],
                                       map_location=torch.device(device))
        depth_feat_model.load_state_dict(depth_feat_weight, strict=True)
        depth_feat_model = depth_feat_model.to(device)
        depth_feat_model.eval()
        depth_feat_model = depth_feat_model.to(device)
        print(f"Loading rgb model at {time.time()}")
        rgb_model = Inpaint_Color_Net()
        rgb_feat_weight = torch.load(config['rgb_feat_model_ckpt'],
                                     map_location=torch.device(device))
        rgb_model.load_state_dict(rgb_feat_weight)
        rgb_model.eval()
        rgb_model = rgb_model.to(device)
        graph = None


        print(f"Writing depth ply (and basically doing everything) at {time.time()}")
        rt_info = write_ply(image,
                              depth,
                              sample['int_mtx'],
                              mesh_fi,
                              config,
                              rgb_model,
                              depth_edge_model,
                              depth_edge_model,
                              depth_feat_model)

        if rt_info is False:
            continue
        rgb_model = None
        color_feat_model = None
        depth_edge_model = None
        depth_feat_model = None
        torch.cuda.empty_cache()
    if config['save_ply'] is True or config['load_ply'] is True:
        verts, colors, faces, Height, Width, hFov, vFov = read_ply(mesh_fi)
    else:
        verts, colors, faces, Height, Width, hFov, vFov = rt_info


    print(f"Making video at {time.time()}")
    videos_poses, video_basename = copy.deepcopy(sample['tgts_poses']), sample['tgt_name']
    top = (config.get('original_h') // 2 - sample['int_mtx'][1, 2] * config['output_h'])
    left = (config.get('original_w') // 2 - sample['int_mtx'][0, 2] * config['output_w'])
    down, right = top + config['output_h'], left + config['output_w']
    border = [int(xx) for xx in [top, down, left, right]]

    scene_name = sample['src_pair_name'].split('-')[0]
    quaternions = read_quaternions_from_csv(f'data/EuRoC/{scene_name}_GT.txt')
    ref_timestamp = int(sample['src_pair_name'].split('-')[-1])

    # get target timestamp
    map_csv = pd.read_csv(os.path.join('work_dirs/sample_euroc', scene_name + '.csv'))
    tgt_timestamp = int(map_csv[map_csv['Reference Timestamp']==ref_timestamp]['Target Timestamp'].values)

    ref_pose = timestamp_to_pose_matrix(quaternions, ref_timestamp)
    tgt_pose = timestamp_to_pose_matrix(quaternions, tgt_timestamp)

    # scale
    factor = 0.1
    ref_pose[:3, 3] *= factor
    tgt_pose[:3, 3] *= factor

    novel_view = output_novel_view(verts.copy(), colors.copy(), faces.copy(), copy.deepcopy(Height), copy.deepcopy(Width), copy.deepcopy(hFov), copy.deepcopy(vFov),
                            copy.deepcopy(sample['tgt_pose']), sample['video_postfix'], ref_pose, copy.deepcopy(config['video_folder']),
                            image.copy(), copy.deepcopy(sample['int_mtx']), config, image,
                            videos_poses, video_basename, config.get('original_h'), config.get('original_w'), border=border, depth=depth, normal_canvas=normal_canvas, all_canvas=all_canvas,
                            mean_loc_depth=mean_loc_depth, tgt_pose=tgt_pose)
    
    pred_name = sample['src_pair_name']
    cv2.imwrite(os.path.join(config['video_folder'], f'{pred_name}_novel_view.png'), novel_view)
