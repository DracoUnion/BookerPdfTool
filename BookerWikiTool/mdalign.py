import re
import sys
from os import path
import yaml
import json
import os

PREF_IND = r'(\x20{4}|\t)'
PREF_OL = r'\d+\.\x20{2}'
PREF_UL = r'[\*\+\-]\x20{3}'
PREF_H1 = r'#\x20+'
PREF_H2 = r'#{2}\x20+'
PREF_H3 = r'#{3}\x20+'
PREF_H4 = r'#{4}\x20+'
PREF_H5 = r'#{5}\x20+'
PREF_H6 = r'#{6}\x20+'
PREF_BQ = r'>\x20'
PREF_TB = r'\|\x20+'
SUFF_TB = r'\x20+\|'

PREF_MAP = {
    'PREF_IND': PREF_IND, 
    'PREF_OL': PREF_OL, 
    'PREF_UL': PREF_UL, 
    'PREF_H1': PREF_H1, 
    'PREF_H2': PREF_H2, 
    'PREF_H3': PREF_H3, 
    'PREF_H4': PREF_H4, 
    'PREF_H5': PREF_H5, 
    'PREF_H6': PREF_H6, 
    'PREF_BQ': PREF_BQ
}


RE_PRE = r'(`{3,})[\s\S]+?\1'

def match_one_pref(line):
    for tp, rgx in PREF_MAP.items():
        # print(tp, rgx, line)
        m = re.search('^' + rgx, line, re.M)
        if not m: continue
        l = len(m.group())
        line = line[l:]
        return tp, line
    return None, line
        

def ext_prefs(line):
    prefs = []
    while True:
        pref, line = match_one_pref(line)
        if not pref: break
        prefs.append(pref)
    return {
        'prefs': prefs,
        'line': line.strip(),
    }

def proc_md(md):
    lines = md.split('\n')
    lines = [l.strip() for l in lines]
    lines = list(filter(None, lines))
    
    res = [ext_prefs(l) for l in lines]
    return res
    
def find_next_pref(r, st, p):
    for i in range(st, len(r)):
        if r[i]['prefs'] == p:
            return i
    return len(r)
    
def make_align(md1, md2):
    r1, r2 = proc_md(md1), proc_md(md2)
    idx1, idx2 = 0, 0
    res = []
    while idx1 < len(r1) and idx2 < len(r2):
        l1, l2 = r1[idx1], r2[idx2]
        p1, p2 = l1['prefs'], l2['prefs']
        if p1 == p2:
            res.append({
                'en': l1['line'],
                'zh': l2['line'],
                'pref': p1,
            })
            idx1 += 1
            idx2 += 1
            continue
        idx1n = find_next_pref(r1, idx1 + 1, p2)
        idx2n = find_next_pref(r2, idx2 + 1, p1)
        if idx1n - idx1 < idx2n - idx2:
            while idx1 < idx1n:
                res.append({
                    'en': r1[idx1]['line'],
                    'zh': '',
                    'pref': r1[idx1]['prefs'],
                })
                idx1 += 1
        else:
            while idx2 < idx2n:
                res.append({
                    'en': '',
                    'zh': r2[idx2]['line'],
                    'pref': r2[idx2]['prefs'],
                })
                idx2 += 1
            
    while idx1 < len(r1):
        res.append({
            'en': r1[idx1]['line'],
            'zh': '',
            'pref': r1[idx1]['prefs'],
        })
        idx1 += 1
    while idx2 < len(r2):
        res.append({
            'en': '',
            'zh': r2[idx2]['line'],
            'pref': r2[idx2]['prefs'],
        })
        idx2 += 1
    return res
    
def extreact_pre(md):
    pres = []
    def repl_func(m):
        s = m.group()
        pres.append(s)
        idx = len(pres) - 1
        return f'[PRE{idx}]'
    md = re.sub(RE_PRE, repl_func, md)
    return md, pres
    
def recover_pre(md, pres):
    for i, pre in enumerate(pres):
        md = md.replace(f'[PRE{i}]', pre)
    return md
    
def extract_pre_handler(args):
    fname = args.fname
    if not fname.endswith('.md'):
        print('请提供MD文件')
        return
    json_fname = fname + '.json'
    if path.isfile(json_fname):
        print('文件中的代码段已提取')
        return
    md = open(fname, encoding='utf8').read()
    md, pres = extreact_pre(md)
    open(fname, 'w', encoding='utf8').write(md)
    open(json_fname, 'w', encoding='utf8').write(json.dumps(pres))
    
def recover_pre_handler(args):
    fname = args.fname
    if not fname.endswith('.md'):
        print('请提供MD文件')
        return
    json_fname = fname + '.json'
    if not path.isfile(json_fname):
        print('找不到已提取的代码段')
        return
    md = open(fname, encoding='utf8').read()
    pres = json.loads(open(json_fname, encoding='utf8').read())
    md = recover_pre(md, pres)
    open(fname, 'w', encoding='utf8').write(md)
    os.unlink(json_fname)
    
def md_align_handler(args):
    fname1 = args.en
    fname2 = args.zh
    if not fname1.endswith('.md') or \
       not fname2.endswith('.md'):
       raise ValueError('请提供两个 MD 文件！')
    md1 = open(fname1, encoding='utf8').read()
    md2 = open(fname2, encoding='utf8').read()
    res = make_align(md1, md2)
    ofname = path.basename(fname1) + '_' + path.basename(fname2) + '.yaml'
    open(ofname, 'w', encoding='utf8').write(
        yaml.safe_dump(res, allow_unicode=True))
    
