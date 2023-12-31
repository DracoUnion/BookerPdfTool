import fitz
import subprocess as subp
import sys
from os import path
from pyquery import PyQuery as pq
import re
import os
import shutil
import copy
import tempfile
import uuid
import platform
import traceback
from PIL import Image, ImageFile
from multiprocessing import Pool
from imgyaso import pngquant_bts, adathres_bts
import img2pdf
from img2jb2pdf import img2jb2pdf
from io import BytesIO
from .util import *

def comp_pdf(args):
    fname = args.fname
    if not fname.endswith('.pdf'):
        print('请提供 PDF 文件')
        return
    print(f'file: {fname}')
    doc = fitz.open("pdf", open(fname, 'rb').read())
    for i, p in enumerate(doc):
        print(f'page: {i+1}')
        imgs = p.get_images()
        for ii, info in enumerate(imgs):
            xref = info[0]
            print(f'image: {ii+1}, xref: {xref}')
            img = fitz.Pixmap(doc, xref)
            data = img.pil_tobytes(format="JPEG", quality=100)
            data = adathres_bts(data)
            p.replace_image(xref, stream=data)
    doc.save(fname, clean=True, garbage=4, deflate=True, linear=True)
    doc.close()

def ext_pdf(args):
    if path.isdir(args.fname):
        ext_pdf_dir(args)
    else:
        ext_pdf_file(args)

def ext_pdf_dir(args):
    dir = args.fname
    for fname in os.listdir(dir):
        try:
            ffname = path.join(dir, fname)
            args.fname = ffname
            ext_pdf_file(args)
        except: traceback.print_exc()

def ext_pdf_file(args):
    fname, dir = args.fname, args.dir
    if not fname.endswith('.pdf'):
        print('请提供 PDF 文件')
        return
    print(f'file: {fname}')
    title = path.basename(fname)[:-4]

    doc = fitz.open(fname)
    lp = len(str(len(doc)))
    for ip, p in enumerate(doc):
        print(f'page: {ip + 1}')
        
        # 判断是否整页截图
        if args.whole:
            img = p.get_pixmap(dpi=400)
            imgname = path.join(dir, f'{title}_{ip+1:0{lp}d}.png')
            print(f'save: {imgname}')
            img.save(imgname)
            continue
        
        imgs = p.get_images()
        limg = len(str(len(imgs)))
        for ii, info in enumerate(imgs):
            xref = info[0]
            print(f'img: {ii + 1}, xref: {xref}')
            img = fitz.Pixmap(doc, xref)
            imgname = path.join(dir, f'{title}_{ip+1:0{lp}d}_{ii+1:0{limg}d}.png')
            print(f'save: {imgname}')
            img.save(imgname)
    
    doc.close()

def get_scale_by_width(wid):
    if wid < 800:
        return 4
    elif wid < 900:
        return 3.5
    elif wid < 1000:
        return 3
    elif wid < 1200:
        return 2.5
    elif wid < 1600:
        return 2
    elif wid < 2000:
        return 1.5
    elif wid < 3200:
        return 1
    elif wid < 4200:
        return 0.75
    else:
        return 0.5

def pack_pdf(args):
    dir, rgx = args.dir, args.regex
    if dir.endswith('/') or \
        dir.endswith('\\'):
        dir = dir[:-1]
    
    fnames = filter(is_pic, os.listdir(dir))
    if not rgx:
        fnames = [path.join(dir, f) for f in fnames]
        if args.jb2:
            pdf = img2jb2pdf(fnames)
        else:
            pdf = img2pdf.convert(fnames)
        fname = dir + '.pdf'
        print(fname)
        open(fname, 'wb').write(pdf)
        return
        
    d = {}
    for fname in fnames:
        m = re.search(rgx, fname)
        if not m: continue
        kw = m.group(0)
        d.setdefault(kw, [])
        d[kw].append(fname)
        
    for kw, fnames in d.items():
        fnames = [path.join(dir, f) for f in fnames]
        if args.jb2:
            pdf = img2jb2pdf(fnames)
        else:
            pdf = img2pdf.convert(fnames)
        fname = path.join(dir, kw + '.pdf')
        print(fname)
        open(fname, 'wb').write(pdf)

# @safe()
def anime4k_auto_file(args):
    fname = args.fname
    if not is_pic(fname):
        print('请提供图像')
        return
    print(fname)
    try: img = Image.open(fname)
    except: 
        print('文件无法打开')
        return
    width = min(img.size[0], img.size[1])
    scale = get_scale_by_width(width)
    img.close()
    cmd = [
        'Anime4KCPP_CLI', 
        '-t', str(args.threads),
        '-z', str(scale),
        '-i', fname,
        '-o', fname,
        "-w", "-H",
        "-L", "3",
    ]
    if args.gpu: cmd.append('-q')
    print(f'cmd: {cmd}')
    r = subp.Popen(
        cmd, 
        shell=True,
        stdout=subp.PIPE,
        stderr=subp.PIPE,
        cwd=find_cmd_path('Anime4KCPP_CLI'),
    ).communicate()
    open(fname, 'ab').close() # touch
    print(r[0].decode('utf8', 'ignore') or 
        r[1].decode('utf8', 'ignore'))
        
def anime4k_auto_dir(args):
    dir = args.fname
    fnames = os.listdir(dir)
    for f in fnames:
        ff = path.join(dir, f)
        args.fname = ff
        anime4k_auto_file(args)

def anime4k_auto_handle(args):
    # 检查 waifu2x
    if not find_cmd_path('Anime4KCPP_CLI'): 
        print('Anime4KCPP_CLI 未找到，请下载并将其目录添加到系统变量 PATH 中')
        return
    if path.isdir(args.fname):
        anime4k_auto_dir(args)
    else:
        anime4k_auto_file(args)

# @safe()
def pdf_auto_file(args):
    fname = args.fname
    threads = args.threads
    if not fname.endswith('.pdf'):
        print('请提供 PDF 文件')
        return
    print(f'file: {fname}')
    tmpdir = path.join(tempfile.gettempdir(), uuid.uuid4().hex)
    safe_mkdir(tmpdir)
    
    cmds = [
        ['pdf-tool', 'ext', '-d', tmpdir, fname],
        ['pdf-tool', 'tog-bw', '-t', str(threads), tmpdir],
        ['pdf-tool', 'anime4k-auto', '-t', str(threads), tmpdir],
        ['imgyaso', '-m', 'thres', '-t', str(threads), tmpdir],
        ['pdf-tool', 'pack', tmpdir, '--jb2'],
    ]
    if args.gpu: cmds[2].append('-G')
    if args.whole: cmds[0].append('-w')
    for cmd in cmds:
        print(f'cmd: {cmd}')
        subp.Popen(cmd, shell=True).communicate()
    if path.isfile(fname + '.bak'): os.unlink(fname + '.bak')
    shutil.move(fname, fname + '.bak')
    shutil.move(path.abspath(tmpdir) + '.pdf', fname)
    
    safe_rmdir(tmpdir)
    
def pdf_auto_dir(args):
    dir = args.fname
    fnames = os.listdir(dir)
    for f in fnames:
        ff = path.join(dir, f)
        args.fname = ff
        pdf_auto_file(args)


def pdf_auto_handle(args):
    if path.isdir(args.fname):
        pdf_auto_dir(args)
    else:
        pdf_auto_file(args)

def pg_all_imgs_area(pg):
    rects = [
        pg.get_image_rects(info[0])
        for info in pg.get_images()
    ]
    rects = [r[0] for r in rects if r]
    return sum([(r[2] - r[0]) * (r[3] - r[1]) for r in rects])

def pg_area(pg):
    return (pg.rect[2] - pg.rect[0]) * (pg.rect[3] - pg.rect[1])

def is_scanned_pdf(fname, imgs_area_rate=0.8, scanned_pg_rate=0.8):
    doc = fitz.open("pdf", open(fname, 'rb').read())
    rate = sum([
        pg_all_imgs_area(pg) >= pg_area(pg) * imgs_area_rate
        for pg in doc
    ]) / len(doc)
    return rate >= scanned_pg_rate
    
# @safe()
def tr_pick_scanned_pdf(fname, odirs, imgs_area_rate, scanned_pg_rate):
    scanned = is_scanned_pdf(
        fname, 
        imgs_area_rate=imgs_area_rate, 
        scanned_pg_rate=scanned_pg_rate,
    )
    rtext = '扫描版' if scanned else '文字版'
    print(f'{fname}：{rtext}')
    if scanned:
        shutil.move(fname, path.join(odirs[0], path.basename(fname)))
    else:
        shutil.move(fname, path.join(odirs[1], path.basename(fname)))
    
def pick_scanned_pdf(args):
    dir = args.dir
    if not path.isdir(dir):
        print('请提供目录')
        return
    odir0 = path.join(dir, '扫描版')
    odir1 = path.join(dir, '文字版')
    safe_mkdir(odir0)
    safe_mkdir(odir1)
    pool = Pool(args.threads)
    for f in os.listdir(dir):
        if not f.endswith('.pdf'):
            continue
        ff = path.join(dir, f)
        pool.apply_async(
            tr_pick_scanned_pdf, 
            [
                ff, [odir0, odir1], 
                args.imgs_area_rate, 
                args.scanned_pg_rate
            ]
        )
    pool.close()
    pool.join()
        
