import glob, os
import numpy as np

files = glob.glob('depth/*.ppmx')
for file_name in files:
    with open(file_name, 'rb') as f:
        info = f.readline()
        shape = f.readline()
        _ = f.readline()
        data = f.read()
    f.close()
    np_data = np.frombuffer(data, dtype=np.float32)
    np_data = np_data.reshape(768, 1024)

    basename = os.path.basename(file_name).replace('.ppmx', '.npy')
    np.save('depth/' + basename, np_data)