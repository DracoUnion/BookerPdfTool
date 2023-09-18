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

app_map = {
    'ppt': ['PowerPoint.Application', 'Presentations'],
    'pptx': ['PowerPoint.Application', 'Presentations'],
    'doc': ['Word.Application', 'Documents'],
    'docx': ['Word.Application', 'Documents'],
    'xls': ['Excel.Application', 'Workbooks'],
    'xlsx': ['Excel.Application', 'Workbooks'],
}

def office2pdf(fname, ofname):
    import win32com.client
    m = re.search(r'\.(\w+)$', fname)
    ext = m.group(1) if m else ""
    if ext not in app_map:
        raise FileError(f'{fname} 不是 DOC、XLS 或 PPT 文件')
    app = win32com.client.Dispatch(app_map[ext][0])
    ppt = getattr(app, app_map[ext][1]).Open(fname)
    ppt.SaveAs(ofname, 32)
    app.Quit()
    
def office2pdf_file(args):
    fname = args.fname
    print(fname)
    m = re.search(r'\.(\w+)$', fname)
    ext = m.group(1) if m else ""
    if ext not in app_map:
        print('请提供 DOC、XLS 或 PPT 文件')
        return
    fname = path.join(os.getcwd(), fname)
    ofname = re.sub(r'\.\w+$', '', fname) + '.pdf'
    office2pdf(fname, ofname)
    print("转换成功！")

def office2pdf_dir(args):
    dir = args.fname
    fnames = os.listdir(dir)
    for f in fnames:
        ff = path.join(dir, f)
        args.fname = ff
        try: office2pdf_file(args)
        except Exception as ex: traceback.print_exc()