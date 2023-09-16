import numpy as np
import fitz
from io import BytesIO
import re
import tempfile
from .util import *

def norm_l2(arr, axis=-1):
    l2 = (arr ** 2).sum(axis, keepdims=True) ** 0.5
    return arr / l2

def read_pdf_text_n(pdf, n=500):
    res = ''
    for l in read_pdf_lines(data):
        if len(res) >= n: break
        res += re.sub(r'\s', '', l)
    return res[:n]

def read_pdf_lines(pdf):
    # 全部读进来转成内存流避免锁文件
    if isinstance(pdf, str):
        pdf = open(pdf, 'rb').read()
    doc: fitz.Document = fitz.open(BytesIO(pdf))
    for pg in doc:
        for block in pg.get_text_blocks():
            yield block[4].strip()
    
def ngram_hash_freq(text, ngram=3, nbucket=1000):
    # 创建形状为 [nbucket] 的数组储存结果
    vec = np.zeros([nbucket], dtype=np.int32)
    # 将文本切分为 ngram，然后对于每个子串计算哈希值，映射到 nbucket 个桶中
    hashs = [
        hash(text[i:i+ngram]) % nbucket 
        for i in range(0, len(text) - ngram + 1)
    ]
    # 将哈希计数保存到数组中
    for h in hashs:
        vec[h] += 1
    # 将哈希计数变成哈希频率
    return vec / vec.sum()

def dedup(fvecs, his_vecs=None, thres=0.9):
    if his_vecs is None:
        his_vecs = np.zeros([0, 1000])
    for it in fvecs:
        fname, fvec = it['name'], it['vec'][None]
        if len(his_vecs) == 0:
            his_vecs = np.vstack([his_vecs, fvec])
            continue
        sims = norm_l2(fvec) @ norm_l2(his_vecs).T
        maxsim = np.max(sims)
        print(f'文件名: {fname}, 相似度: {maxsim}')
        # 如果最大相似度小于阈值，判定不重复
        if maxsim < thres:
            # 将当前文档添加到历史向量及结果中
            his_vecs = np.vstack([his_vecs, fvec])
        else:
            # 将当前文档移动到重复目录
            dupdir = path.join(path.dirname(fname), 'dup')
            safe_mkdir(dupdir)
            nfname = path.join(dupdir, path.basename(fname))
            os.rename(fname, nfname)
    # 返回新的历史向量库
    # 添加了当前一批非重复文件向量
    return his_vecs



def dedup_handle(args):
    # 获取文件名列表
    pdf_path = args.fname
    if path.isfile(pdf_path):
        if not fnames.endswith('.pdf'):
            print('请提供 PDF')
            return
        fnames = [pdf_path]
    else:
        fnames = os.listdir(pdf_path)
        fnames = [
            path.join(pdf_path, f) 
            for f in fnames 
            path_if f.endswith('.pdf')
        ]
    # 读取每个文件，转成哈希频率
    fvecs = [
        {
            'name': f,
            'vec': ngram_hash_freq(
                   read_pdf_text_n(
                   open(f, 'rb').read())),
        }
        for f in fnames
    ]
    # 加载历史库
    db_fname = args.db or \
        path.join(tempfile.gettempdir(), 'dedup.npy')
    if not db_fname.endswith('.npy'):
        print('数据库必须是 NPY 文件')
        return
    # 如果不存在，初始化这个文件
    if not path.isfile(db_fname):
        np.save(db_fname, np.zeros([0, 1000]))
    his_vecs = np.load(db_fname)
    assert isinstance(his_vecs, np.array) \ 
           and his_vecs.ndim == 2 \
           and his_vecs.shape[1] == 1000
    # 去重
    his_vecs = dedup(fvec, his_vecs, args.thres)
    # 保存历史向量库
    np.save(db_fname, his_vecs)
    