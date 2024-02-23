from  moviepy.editor import *
import glob, argparse, os

def parse_args():
    parser = argparse.ArgumentParser(description='generate stereo video')

    parser.add_argument('--input', default='video/IGEV', help='the dir of mono video')

    args = parser.parse_args()
    return args

def main():
    args = parse_args()
    for left in glob.glob(os.path.join(args.input, '*_left_*.mp4')):
        right = left.replace('_left_', '_right_')
        clips = [VideoFileClip(left), VideoFileClip(right)]
        video = clips_array([clips])
        video.write_videofile(left.replace('_left_', '_'))

if __name__=='__main__':
    main()
    