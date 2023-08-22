from .util import *
import os
import shutil
from os import path

def pdg2pic(args):
    dir = args.dir
    if dir.endswith('/') or \
        dir.endswith('\\'):
        dir = dir[:-1]
    odir = args.output_dir or dir
    safe_mkdir(odir)
    
    fnames = filter(lambda s: s.endswith('.pdg', os.listdir(dir))
    prefs = {
        'cov': 0,
        'bok': 1,
        'leg': 2,
        'fow': 3,
        '!00': 4,
        '000': 5,
    }
    sort_key = lambda s: \
        (prefs.get(s[:3], 999), int(s[3:])
    fnames.sort(key=sort_key)
    if 'cov002.pdg' in fnames:
        idx = fnames.index('cov002.pdg')
        del fnames[idx]
        fnames.append('cov002.pdg')
    
    fnames = [path.join(dir, f) for f in fnames]
    npad = len(str(len(fnames)))
    for i, f in enumerate(fnames):
        print(f)
        img_fname = path.join(odir, str(i).zfill(npad) + '.png')
        shutil.copy(f, img_fname)
