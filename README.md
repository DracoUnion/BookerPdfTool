# BookerPdfTool

iBooker/DracoUnion 知识库 PDF 处理工具

一套面向电子书 / 扫描版 PDF 的命令行工具，提供压缩、抽取图片、转 HTML、黑白反转纠正、AI 超分增强、打包成 PDF、扫描版甄别、PDF 去重、加密压缩包破解、PDG 转图片、Office 转 PDF 等能力。

## 安装

通过 pip（推荐）：

```
pip install BookerPdfTool
```

从源码安装：

```
pip install git+https://github.com/DracoUnion/BookerPdfTool.git
```

Python 版本要求：>= 3.6。

安装后可通过 `BookerPdfTool` 或 `pdf-tool` 两个命令调用（两者等价），也可以使用 `python -m BookerPdfTool`。

### 可选依赖

+   `anime4k-auto` / `auto` 命令需要 [Anime4KCPP_CLI](https://github.com/TianZerL/Anime4KCPP)，并将其所在目录加入系统 PATH。
+   `fm-office` 命令仅在 Windows 上可用（基于 Office COM 组件）。
+   `crack-zip` 破解 RAR 需要 `unrar` 后端程序（随附的 `assets/unrar.exe` 已内置）。

## 使用说明

```
BookerPdfTool -h    # 查看帮助
BookerPdfTool -v    # 查看版本
```

帮助中也列出了全部子命令和参数。

### fm-office：Office 转 PDF

将 DOC/XLS/PPT 转换为 PDF（Windows）。

```
BookerPdfTool fm-office <fname>
```

| 参数 | 说明 |
| --- | --- |
| `fname` | 文件或目录名 |

支持 `doc/docx/xls/xlsx/ppt/pptx`；传入目录时批量转换目录下的所有文件。

### comp：压缩 PDF

对 PDF 内嵌图片做压缩处理后写回，并清理无用数据。

```
BookerPdfTool comp <fname>
```

| 参数 | 说明 |
| --- | --- |
| `fname` | PDF 文件名 |

### ext：抽取 PDF 图片

将 PDF 每一页的内嵌图片抽出来保存为 PNG（或整页截图，需 `-w`）。

```
BookerPdfTool ext <fname> [-d 输出目录] [-w]
```

| 参数 | 说明 |
| --- | --- |
| `fname` | 文件或目录名 |
| `-d, --dir` | 输出目录，默认当前目录 |
| `-w, --whole` | 整页截图，不抽取内嵌图片 |

### 2html：PDF 转 HTML

将 PDF 每页渲染为 HTML，并识别行内代码 / 代码块 / 标题、处理缩进。

```
BookerPdfTool 2html <fname> [-d 输出目录]
```

| 参数 | 说明 |
| --- | --- |
| `fname` | 文件或目录名 |
| `-d, --dir` | 输出目录，默认当前目录 |

### anime4k-auto：Anime4K 增强图片

用 Anime4K 对图片做缩放增强，适合扫描版图片降噪提清晰度。

```
BookerPdfTool anime4k-auto <fname> [-G] [-t 线程数]
```

| 参数 | 说明 |
| --- | --- |
| `fname` | 文件或目录名 |
| `-G, --gpu` | 使用 GPU 推理 |
| `-t, --threads` | 线程数，默认 8 |

需要将 Anime4KCPP_CLI 加入系统 PATH（见「可选依赖」）。

### pack：图片打包成 PDF

把指定目录下的图片按顺序打包为 PDF；配合正则可以把按关键词命名的一组图片分别打包。

```
BookerPdfTool pack <dir> [-r 正则] [--jb2]
```

| 参数 | 说明 |
| --- | --- |
| `dir` | 图片所在目录 |
| `-r, --regex` | 按文件名匹配关键词分组，每组生成一个 PDF |
| `--jb2` | 生成 JBIG2 编码的 PDF，体积更小 |

### tog-bw：黑白反转纠正

自动检测反色的黑白扫描图（平均灰度低于阈值的图片）并反转，纠正「黑底白字」。

```
BookerPdfTool tog-bw <fname> [-t 线程数] [-s 阈值]
```

| 参数 | 说明 |
| --- | --- |
| `fname` | 文件或目录名 |
| `-t, --threads` | 线程数，默认 8 |
| `-s, --thres` | 平均灰度低于该值才视为反色并反转，默认 50 |

### crack-zip：破解加密压缩包

对加密的 ZIP / RAR 压缩包进行字典爆破，成功后解压到同名目录。

```
BookerPdfTool crack-zip <fname> [-p 密码字典] [-t 线程数]
```

| 参数 | 说明 |
| --- | --- |
| `fname` | ZIP / RAR 文件名 |
| `-p, --pw` | 密码字典文件，默认使用随附的 `assets/PwdDic.txt` |
| `-t, --threads` | 线程数，默认 8 |

### auto：一键全自动处理 PDF

一条命令完成整套流程：`ext` 抽图 → `tog-bw` 黑白纠正 → `anime4k-auto` 增强 → 二值化 → `pack` 打包回 PDF。

```
BookerPdfTool auto <fname> [-t 线程数] [-G] [-w]
```

| 参数 | 说明 |
| --- | --- |
| `fname` | PDF 文件或目录名 |
| `-t, --threads` | 线程数，默认 8 |
| `-G, --gpu` | Anime4K 使用 GPU |
| `-w, --whole` | 抽取整页截图 |

原文件会备份为 `xxx.pdf.bak`。同样需要 Anime4KCPP_CLI。

### pick-scan：甄别扫描版 PDF

根据页面图片占比判断每本 PDF 是「扫描版」还是「文字版」，并移动到对应子目录。

```
BookerPdfTool pick-scan <dir> [-i 图片面积占比] [-s 扫描页占比] [-t 线程数]
```

| 参数 | 说明 |
| --- | --- |
| `dir` | 存放 PDF 的目录 |
| `-i, --imgs-area-rate` | 页面图片面积占比高于该值则视为扫描页，默认 0.8 |
| `-s, --scanned-pg-rate` | 扫描页占比高于该值则整本视为扫描版，默认 0.8 |
| `-t, --threads` | 线程数，默认 8 |

结果分别移动到 `dir/扫描版` 与 `dir/文字版`。

### pdg2pic：PDG 转图片

按封面、卷首、正文等前缀排序，把 PDG 文件复制为顺序编号的 PNG。

```
BookerPdfTool pdg2pic <dir> [-o 输出目录]
```

| 参数 | 说明 |
| --- | --- |
| `dir` | PDG 文件所在目录 |
| `-o, --output-dir` | 输出目录，默认与输入目录相同 |

### dedup：PDF 去重

基于文本 n-gram 哈希的相似度判断，把重复的 PDF 移到 `dup` 目录，并把历史向量保存到数据库文件，供后续批次比对。

```
BookerPdfTool dedup <fname> [-t 相似度阈值] [--db 历史库文件]
```

| 参数 | 说明 |
| --- | --- |
| `fname` | PDF 文件或目录名 |
| `-t, --thres` | 相似度阈值，高于该值判定重复，默认 0.9 |
| `--db` | 保存历史向量的 `.npy` 文件，默认 `临时目录/dedup.npy` |

## 协议

本项目基于 SATA 协议发布。

您有义务为此开源项目点赞，并考虑额外给予作者适当的奖励。

## 赞助我们

![](https://home.apachecn.org/img/about/donate.jpg)

## 另见

+   [ApacheCN 学习资源](https://docs.apachecn.org/)
+   [计算机电子书](http://it-ebooks.flygon.net)
+   [布客新知](http://flygon.net/ixinzhi/)