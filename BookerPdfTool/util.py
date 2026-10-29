import tempfile
import uuid
import subprocess as subp
import re
import os
import sys
import shutil
import json
import traceback
import fitz
import hashlib
import ctypes
import yaml
from functools import reduce
from typing import Any, List, Optional, Type, Tuple
from pydantic import BaseModel, parse_obj_as, ValidationError
from urllib.parse import quote_plus
from PIL import ImageFile
from os import path
from pyquery import PyQuery as pq
from datetime import datetime
from collections import OrderedDict
import imgyaso

ImageFile.LOAD_TRUNCATED_IMAGES = True
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
fitz.Document.is_image = fitz.Document.xref_is_image

RE_YAML_META = r'<!--yml([\s\S]+?)-->'
RE_TITLE = r'^#+ (.+?)$'
RE_SOURCE = r'原文：<(.+?)>'
RE_SRC_TITLE = r'[\w\-]{15,}'
RE_CODE_BLOCK = r'```[\s\S]+?```'
RE_IMG = r'!\[.*?\]\(.*?\)'
# Word 字数统计标准：
# 一个汉字或中文标点算一个字
# 一个连续的英文字母、标点和数字序列算一个字
RE_ZH_WORD = r'[\u2018-\u201d\u3001-\u301c\u4e00-\u9fff\uff01-\uff65]'
RE_EN_WORD = r'[\x21-\x7e]+'
RE_IFRAME = r'<iframe[^>]*src="(.+?)"[^>]*>'
RE_IFRAME_ALL = r'</?iframe[^>]*>'
RE_IFRAME_REPL = r'<br/><br/><a href="\1">\1</a><br/><br/>'

DIR = path.dirname(path.abspath(__file__))

default_hdrs = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36',
}

headers = {
    'User-Agent': 'PostmanRuntime/7.26.8',
    'Referer': 'https://www.bilibili.com/',
}


def d(name):
    return path.join(DIR, name)

def asset(name=''):
    return path.join(DIR, 'assets', name)

def opti_img(img, mode, colors):
    if mode == 'quant':
        return imgyaso.pngquant_bts(img, colors)
    elif mode == 'grid':
        return imgyaso.grid_bts(img)
    elif mode == 'trunc':
        return imgyaso.trunc_bts(img, colors)
    elif mode == 'thres':
        return imgyaso.adathres_bts(img)
    else:
        return img

def tomd(html):
    # 处理 IFRAME
    html = re.sub(RE_IFRAME, RE_IFRAME_REPL, html)
    html = re.sub(RE_IFRAME_ALL, '', html)
    js_fname = d('tomd.js')
    html_fname = path.join(tempfile.gettempdir(), uuid.uuid4().hex + '.html')
    open(html_fname, 'w', encoding='utf8').write(html)
    subp.Popen(
        ["node", js_fname, html_fname],
        shell=True,
    ).communicate()
    md_fname = re.sub(r'\.html$', '', html_fname) + '.md'
    md = open(md_fname, encoding='utf8').read()
    os.remove(html_fname)
    return md

def fname_escape(name):
    return name.replace('\\', '＼') \
               .replace('/', '／') \
               .replace(':', '：') \
               .replace('*', '＊') \
               .replace('?', '？') \
               .replace('"', '＂') \
               .replace('<', '＜') \
               .replace('>', '＞') \
               .replace('|', '｜')
               
def account_words(cont):
    # 去掉代码块和图片
    cont = re.sub(RE_CODE_BLOCK, '', cont)
    cont = re.sub(RE_IMG, '', cont)
    zh_count = len(re.findall(RE_ZH_WORD, cont))
    en_count = len(re.findall(RE_EN_WORD, cont))
    total = zh_count + en_count
    return (total, zh_count, en_count)
    
def safe_mkdir(dir):
    try: os.makedirs(dir)
    except: pass
    
def safe_rmdir(dir):
    try: shutil.rmtree(dir)
    except: pass

def is_c_style_code(fname):
    ext = [
        'c', 'cpp', 'cxx', 'h', 'hpp',
        'java', 'kt', 'scala', 
        'cs', 'js', 'json', 'ts', 
        'php', 'go', 'rust', 'swift',
    ]
    m = re.search(r'\.(\w+)$', fname)
    return bool(m and m.group(1) in ext)

def is_pic(fname):
    ext = [
        'jpg', 'jpeg', 'jfif', 'png', 
        'gif', 'tiff', 'webp'
    ]
    m = re.search(r'\.(\w+)$', fname)
    return bool(m and m.group(1) in ext)

def is_video(fname):
    ext = [
        'mp4', 'm4v', '3gp', 'mpg', 'flv', 'f4v', 
        'swf', 'avi', 'gif', 'wmv', 'rmvb', 'mov', 
        'mts', 'm2t', 'webm', 'ogg', 'mkv', 'mp3', 
        'aac', 'ape', 'flac', 'wav', 'wma', 'amr', 'mid',
    ]
    m = re.search(r'\.(\w+)$', fname)
    return bool(m and m.group(1) in ext)
    
def dict_get_recur(obj, keys):
    res = [obj]
    for k in keys.split('.'):
        k = k.strip()
        if k == '*':
            res = reduce(lambda x, y: x + y,res, [])
        else:
            res = [o.get(k) for o in res if k in o]
    return res
    
def safe(default=None):
    def outer(f):
        def inner(*args, **kw):
            print(123123)
            try: return f(*args, **kw)
            except KeyboardInterrupt:
                raise
            except:
                traceback.print_exc()
                return default
        return inner
    return outer


def md5(text: str):
    return hashlib.md5(text.encode('utf8')).hexdigest()


def gen_objs_md5(*args):
    args = [o if isinstance(o, str) else json_dump_model(o) for o in args]
    return '_'.join(md5(o) for o in args)


def get_md_title(text):
    m = re.search(r'^#+\x20+(.+?)$', text, flags=re.M)
    if not m:
        return None, (None, None)
    return m.group(1).strip(), m.span(1)


def to_kebab(name: str) -> str:
    s = re.sub(r"[^\w\s一-鿿\-]", "", name)
    s = re.sub(r"[\s_]+", "-", s).strip("-").lower()
    return s[:60] or "unnamed"


def extname(fname):
    m = re.search(r'\.(\w+)$', fname)
    return m.group(1) if m else ''


def render_prompt(prompt: str, **kw):
    return re.sub(r"{(\w+)}", lambda g: kw.get(g.group(1), g.group(0)), prompt)


ext_code_block = lambda s: re.search(r'```\w*([\s\S]+)```', s).group(1)
ext_cont_block = lambda s: re.search(r'\[content\]([\s\S]+)\[/content\]', s).group(1)


def malloc_trim_linux():
    if sys.platform == 'linux':
        libc = ctypes.CDLL("libc.so.6")
        libc.malloc_trim(0)


def read_text(fname: str):
    if not path.isfile(fname):
        return None
    text = open(fname, encoding='utf8').read()
    chs = set(text)
    if len(chs) == 1 and '\x00' in chs:
        text = ""
    return text


def write_text(fname: str, text: str, append: bool = False) -> None:
    parent = path.dirname(fname)
    if parent:
        os.makedirs(parent, exist_ok=True)
    open(fname, 'a' if append else 'w', encoding='utf8').write(text)


def json_dump_model(obj) -> str:
    if isinstance(obj, BaseModel):
        obj = obj.model_dump()
    elif isinstance(obj, list):
        obj = [it.dict() if isinstance(it, BaseModel) else it for it in obj]
    return json.dumps(obj, ensure_ascii=False)


def write_yaml_model(fname: str, obj: Any) -> None:
    if isinstance(obj, BaseModel):
        obj = obj.model_dump()
    elif isinstance(obj, list):
        obj = [it.dict() if isinstance(it, BaseModel) else it for it in obj]
    parent = path.dirname(fname)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(fname, 'w', encoding='utf8') as f:
        yaml.safe_dump(obj, f, allow_unicode=True, sort_keys=False)


def read_yaml_model(fname: str, model: Optional[Type[BaseModel]] = None):
    if not path.isfile(fname) or not path.getsize(fname):
        return None
    try:
        data = yaml.safe_load(open(fname, encoding='utf8').read())
        return parse_obj_as(model, data) if model else data
    except (yaml.error.YAMLError, ValidationError):
        return None
