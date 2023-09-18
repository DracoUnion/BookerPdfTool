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

code_fonts = ['Courier', 'Mocano', 'Consolas', 'Monospace', 'Menlo']

def process_el_code(rt):
    el_spans = rt('span')
    for el in el_spans:
        el = pq(el)
        # 如果 SPAN 的字体是等宽字体之一，就认为是内联代码
        style = el.attr('style') or ''
        is_code = any([
            f.lower() in style.lower() 
            for f in code_fonts
        ])
        if not is_code: continue
        el_code = rt('<code></code>')
        el_code.text(el.text())
        el_code.attr('style', el.attr('style'))
        el.replace_with(el_code)

def process_el_pre(rt):
    el_paras = rt('p')
    for el in el_paras:
        el = pq(el)
        # 如果段落只包含内联代码，就认为是代码块
        is_pre = all([pq(ch).is_('code') for ch in el.children()])
        if not is_pre: continue
        el_pre = rt('<pre></pre>')
        # 移除里面的所有 CODE 标签但保留内容
        for el_code in el.children():
            el_code = pq(el_code)
            el_span = rt('<span></span>')
            el_span.text(el_code.text() or '')
            el_code.replace_with(el_span)
        el_pre.text(el.text().replace('\n', ''))
        el_pre.attr('style', el.attr('style'))
        el.replace_with(el_pre)

def process_el_heading(rt):
    def get_font_size(el):
        style = el.attr('style') or ''
        m = re.search(r'font-size:\s*(\d+\.\d+)', style)
        if not m: return 0
        else: return float(m.group(1))
    el_paras = rt('p')
    for el in el_paras:
        el = pq(el)
        # 如果字体大于等于 16，则认为它是标题
        el_spans = el.find('span')
        is_heading = (
            get_font_size(el) >= 16 or
            any([get_font_size(pq(el)) >= 16 for el in el_spans])
        )
        if not is_heading: continue
        el_h2 = rt('<h2></h2>')
        el_h2.html(el.html() or '')
        el_h2.attr('style', el.attr('style'))
        el.replace_with(el_h2)

def process_pre_indent(rt):
    def get_indent(el):
        style = el.attr('style') or ''
        m = re.search(r'left:\s*(\d+\.\d+)', style)
        if not m: return 0
        else: return float(m.group(1))
    inds = [get_indent(pq(el)) for el in rt('pre')]
    inds_uni = list({x for x in inds if x != 0})
    inds_uni.sort()
    if len(inds_uni) <= 1: return
    # 计算基址和偏移，转换为空格数
    diff = inds_uni[1] - inds_uni[0]
    base = inds_uni[0]
    for i, el in enumerate(rt('pre')):
        if inds[i] == 0: continue
        nspace = int((inds[i] - base) // diff) * 4
        el = pq(el)
        el.text(' ' * nspace + (el.text() or ''))


def process_html_code(html):
    rt = pq(html)
    process_el_code(rt)
    # process_el_pre(rt)
    process_pre_indent(rt)
    process_el_heading(rt)
    # 处理缩进
    html = rt('body').html() if rt('body') else str(rt)
    # 合并连续的 PRE
    # html = re.sub(r'</pre>\s*<pre[^>]*>', '\n', html)
    # 合并段落内的换行
    # html = re.sub(r'(?<![\.\?!:])</p>\s*<p [^>]*>', ' ', html)
    # html = re.sub(r'</?span[^>]*>', '' ,html)
    # html = re.sub(r'style=".+?"', '' ,html)
    return html

def pdf2html_file(args):
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
        html = process_html_code(p.get_text("html"))
        # html = (p.get_text("html"))
        html_fname = path.join(dir, f'{title}_{ip+1:0{lp}d}.html')
        print(f'save: {html_fname}')
        open(html_fname, 'w', encoding='utf8').write(html)

    doc.close()

def pdf2html_dir(args):
    dir = args.fname
    for fname in os.listdir(dir):
        try:
            ffname = path.join(dir, fname)
            args.fname = ffname
            pdf2html_file(args)
        except: traceback.print_exc()

def pdf2html(args):
    if path.isdir(args.fname):
        pdf2html_dir(args)
    else:
        pdf2html_file(args)