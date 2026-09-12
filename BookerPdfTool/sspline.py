"""NumPy reimplementation of the image-resampling core identified in S-Spline.exe.

原有二进制的图像处理核心基于"可分离"（separable）的图像操作和"带裁剪的位图拷贝"。
本模块用 NumPy 将这些操作移植为可移植、向量化的版本，力求语义与原二进制一致。

整体设计：
- S-Spline 使用可分离的三次 B 样条（cubic B-spline）采样：先在水平方向重采样，
  再在垂直方向重采样，两次一维滤波等价于二维卷积，但计算量更小。
- 为每个目标像素预计算其 4 个采样源坐标（4-tap）与对应权重，形成稀疏采样矩阵，
  随后通过 np.take / 广播乘法一次性完成整幅图像的采样。
- 图像边界处使用"镜像映射"（mirror）避免下标越界，同时保留一定的对称性。

模块包含三个核心能力：
1. resize_rgb(...)    —— 基于可分离三次 B 样条的无损/高阶图像缩放
2. clipped_copy(...)  —— 带边界裁剪的行拷贝（对应 S-Spline.exe 0x459194 处逻辑）
3. resize_file(...)   —— 基于 Pillow 的文件级缩放封装，便于命令行调用
"""

from __future__ import annotations

import argparse
import math  # 保留导入；后续实现可能用到数值工具（本文件未直接使用）
from pathlib import Path
from io import BytesIO

import numpy as np
from PIL import Image


def _mirror_indices(indices: np.ndarray, length: int) -> np.ndarray:
    """在图像边界处对整数坐标做"镜像"反射，将其映射回 [0, length) 区间。

    镜像映射（clamp 与 wrap 之外的另一类边界处理）：
    - 与直接截断（clamp）相比，镜像避免了边界处权重的突变；
    - 与循环（wrap）相比，镜像不会让图像左右/上下"缝合"在一起。
    周期为 p = 2*length - 2，形如: 0,1,2,...,length-1,length-2,...,1,0,...

    参数：
        indices: 可能越界的整数坐标数组。
        length:  一维方向上的合法下标上界（即该方向上的像素数量）。

    返回：
        与 indices 同形状的合法下标数组（np.intp）。
    """
    # 长度为 1 时该方向退化为单个像素，任何坐标都应映射到 0。
    if length <= 1:
        return np.zeros_like(indices, dtype=np.intp)
    period = 2 * length - 2  # 镜像的周期。
    indices = np.mod(indices, period)  # 先折入一个周期内，去除整数倍周期偏移。
    # 周期内又分两段：前半段 [0, length) 保持原值，后半段（大于等于 length）做对称折叠。
    return np.where(indices < length, indices, period - indices).astype(np.intp)


def _cubic_bspline(distance: np.ndarray) -> np.ndarray:
    """逐元素计算"居中三次 B 样条"核函数在给定距离处的取值。

    三次 B 样条是一类光滑的插值/滤波核，用于加权邻近像素。
    影响半径取 2 个像素，因此每点需要 4 个源像素参与采样（4-tap）。
    它以分段多项式的形式定义，|x| < 2 时非零，越往中心权重越大且核本身连续光滑。

    归一化的三次 B 样条定义（经典 Mitchel-Netravali 族 / uniform cubic spline）：
        当 0 <= |x| < 1:  w = (4 - 6|x|^2 + 3|x|^3) / 6
        当 1 <= |x| < 2:  w = (2 - |x|)^3 / 6
        其余:              w = 0

    参数：
        distance: 各像素到采样中心的有符号（带符号）距离数组，元素可为任意实数。

    返回：
        与 distance 同形状的权重数组（np.float64），非负且和为 1（当距离恰落在
        半径内时；若所有距离都落在核对径之外则返回 0）。
    """
    distance = np.abs(distance)  # 核函数关于原点偶对称，只需看绝对值。
    weights = np.zeros_like(distance, dtype=np.float64)
    inner = distance < 1.0  # 中心区间：0 ~ 1。
    outer = (distance >= 1.0) & (distance < 2.0)  # 外围区间：1 ~ 2。
    weights[inner] = (4.0 - 6.0 * distance[inner] ** 2
                      + 3.0 * distance[inner] ** 3) / 6.0
    delta = 2.0 - distance[outer]
    weights[outer] = delta**3 / 6.0
    return weights


def _axis_weights(destination_size: int, source_size: int,
                  scale: float) -> tuple[np.ndarray, np.ndarray]:
    """为单轴构造一个"归一化的稀疏 4-tap 采样矩阵"。

    思路：对目标轴上每一个像素，找出它在源轴上参与采样的 4 个源坐标（完整、
    不裁剪），并按自定义的采样相位（pixel center 对齐）计算对应权重。

    采样相位说明：
        - 目标像素的"像素中心"位置按 (i + 0.5) 计算（i 为目标下标）；
        - 再除以缩放比 scale 得到对应的源像素中心位置；
        - 减去 0.5 得到"源像素中心到源采样点"的连续坐标，便于与整数源下标对齐。
      这样当 scale == 1 时，目标下标 i 恰好对应源的下标 i，无漂移。

    4-tap 采样：取 floor(pos) - 1 起连续 4 个源坐标，覆盖三次 B 样条 ±2 的
    影响半径；超出边界处用 _mirror_indices 做镜像反射。

    参数：
        destination_size: 目标轴长度（最终输出的宽/高）。
        source_size:      源轴长度（输入图像的宽/高）。
        scale:            缩放系数 = destination / source（大于 1 放大，小于 1 缩小）。

    返回：
        (coordinates, weights) 两个形状为 (destination_size, 4) 的数组：
        - coordinates: 每个目标像素对应的 4 个源坐标（整数下标，[0, source_size)）；
        - weights:     与 coordinates 对应的权重，未归一化（行内和为 1 由调用方保证）。
    """
    # 目标像素中心在"源坐标系"下的连续位置。
    positions = (np.arange(destination_size, dtype=np.float64) + 0.5) / scale - 0.5
    # 4-tap 的起始源下标：取 floor(pos) 的前一个位置起（左对齐的 4 邻域）。
    left = np.floor(positions).astype(np.intp) - 1
    offsets = np.arange(4, dtype=np.intp)  # 相对偏移：0,1,2,3。
    # 每个目标像素 -> 4 个源坐标（边界处镜像），形状 (destination_size, 4)。
    coordinates = _mirror_indices(left[:, None] + offsets[None, :], source_size)
    # 各源坐标到采样中心的连续距离，代入 B 样条核得到初步权重。
    weights = _cubic_bspline(positions[:, None] - (left[:, None] + offsets[None, :]))
    # 归一化：每行权重之和归一为 1，避免因裁剪/相位造成亮度偏差。
    # 除零保护：用机器精度极小值代替 0 作分母，防止空行导致 NaN/Inf。
    weights /= np.maximum(weights.sum(axis=1, keepdims=True), np.finfo(np.float64).eps)
    return coordinates, weights

def scale_rgb(pixels: np.ndarray | bytes, multiple: float):
    if isinstance(pixels, bytes):
        w, h = Image.open(BytesIO(pixels)).size
    else :
        h, w, *_ = pixels.shape
    return resize_rgb(pixels, int(w * multiple), int(h * multiple))

def resize_rgb(pixels: np.ndarray | bytes, width: int, height: int) -> np.ndarray | bytes:
    """用可分离三次 B 样条采样对 RGB/RGBA 图像做缩放。

    流程分两步（可分离性）：
        1. 水平方向：对每个目标列，沿水平轴用 `_axis_weights(width, src_w, sx)`
           采样，得到形状 (H, dest_W, C) 的中间结果；
        2. 垂直方向：对上一步结果，沿垂直轴用 `_axis_weights(height, src_h, sy)`
           再采样一次，得到最终 (dest_H, dest_W, C)。

    参数：
        pixels: 形状为 (source_height, source_width, channels) 的数组，
                通道数须为 3（RGB）或 4（RGBA）。
        width:  目标宽度（输出列数）。
        height: 目标高度（输出行数）。

    返回：
        uint8 类型的 NumPy 数组，形状为 (height, width, channels)。

    异常：
        ValueError: 输入不是合法的 (H, W, 3/4) 数组，或宽/高非正数。
    """
    is_bytes = isinstance(pixels, bytes)
    if is_bytes:
        pixels = np.asarray(Image.open(BytesIO(pixels)))
    source = np.asarray(pixels)
    if source.ndim != 3 or source.shape[2] not in (3, 4):
        raise ValueError("pixels must have shape (height, width, 3) or (height, width, 4)")
    if width < 1 or height < 1:
        raise ValueError("destination dimensions must be positive")

    source_height, source_width, _ = source.shape
    # 浮点化以便做加权求和（copy=False：仅在需要时拷贝，不改变调用方数据）。
    source = source.astype(np.float64, copy=False)
    # 分别构造水平、垂直两轴的采样矩阵（坐标 + 权重）。
    x_indices, x_weights = _axis_weights(width, source_width, width / source_width)
    y_indices, y_weights = _axis_weights(height, source_height, height / source_height)

    # ---- 水平通道： (H, W, C) -> (H, dest_W, C) ----
    # np.take 沿 axis=1 收集每个目标列对应的 4 个源列 -> 形状 (H, dest_W, 4, C)。
    horizontal = np.take(source, x_indices, axis=1)
    # 按 [None, :, :, None] 广播权重，沿 axis=2（4-tap 维度）加权求和 -> (H, dest_W, C)。
    horizontal = np.sum(horizontal * x_weights[None, :, :, None], axis=2)

    # ---- 垂直通道： (H, dest_W, C) -> (dest_H, dest_W, C) ----
    # np.take 沿 axis=0 收集每行的 4 个源行 -> 形状 (dest_H, dest_W, 4, C)。
    result = np.take(horizontal, y_indices, axis=0)
    # 按 [:, :, None, None] 广播权重，沿 axis=1（4-tap 维度）加权求和。
    result = np.sum(result * y_weights[:, :, None, None], axis=1)

    # 四舍五入并对抗裁剪到 [0, 255]，转回 uint8 输出。
    result = np.clip(np.rint(result), 0, 255).astype(np.uint8)
    
    if is_bytes:
        img = Image.fromarray(result)
        bio = BytesIO()
        img.save(bio, 'PNG')
        result = bio.getvalue()
    return result


def clipped_copy(src: np.ndarray, dst: np.ndarray, src_x: int, src_y: int,
                 dst_x: int, dst_y: int, width: int, height: int) -> None:
    """NumPy 版"带裁剪的行拷贝"，对应 S-Spline.exe 0x459194 处观察到的逻辑。

    该操作将 src 以 (src_x, src_y) 为左上角、宽 width、高 height 的矩形区域，
    原样拷贝到 dst 以 (dst_x, dst_y) 为左上角的对应区域。两个数组的边界都会被
    用于裁剪：任何越出 src 或 dst 的部分都会自动收窄，而不是抛出越界错误。
    支持 RGB/RGBA 或任意"尾部通道形状相同"的数组，原地修改 dst。

    参数：
        src:  源数组，至少二维，形状 (src_h, src_w[, C])。
        dst:  目标数组，原地更新，形状须与 src 通道维度一致。
        src_x, src_y: 源矩形左上角坐标。
        dst_x, dst_y: 目标矩形左上角坐标。
        width, height: 待拷贝区域的宽、高（可为负或 0，此时直接返回不做任何事）。

    异常：
        ValueError: src/dst 维度不足，或通道形状不匹配。
    """
    source = np.asarray(src)
    target = np.asarray(dst)
    if source.ndim < 2 or target.ndim < 2:
        raise ValueError("src and dst must be at least two-dimensional")
    if width <= 0 or height <= 0:
        return  # 尺寸无效，无需拷贝。
    if source.ndim != target.ndim or source.shape[2:] != target.shape[2:]:
        raise ValueError("src and dst channel shapes must match")

    # 用可变副本进行裁剪计算（保持原参数不变）。
    sx, sy, dx, dy = src_x, src_y, dst_x, dst_y

    # 1) 左上越界裁剪：若源或目标左上角为负，则同步平移起点并收窄尺寸，
    #    保证重叠区域从边界开始。例如源左上越到 0 左侧时，把目标起点右移，
    #    同时缩小拷贝宽度。
    if sx < 0:
        dx -= sx
        width += sx
        sx = 0
    if sy < 0:
        dy -= sy
        height += sy
        sy = 0
    if dx < 0:
        sx -= dx
        width += dx
        dx = 0
    if dy < 0:
        sy -= dy
        height += dy
        dy = 0

    # 2) 右下越界裁剪：取"请求宽度"与"src 剩余宽度 / dst 剩余宽度"的最小值，
    #    保证不会越过任一数组右/下边界。
    width = min(width, source.shape[1] - sx, target.shape[1] - dx)
    height = min(height, source.shape[0] - sy, target.shape[0] - dy)
    if width <= 0 or height <= 0:
        return  # 裁剪后重叠区域为空，直接返回。

    # 3) 执行真正的切片拷贝（行优先的高效 C 级拷贝）。
    #    target[dy:dy+height, dx:dx+width] = source[sy:sy+height, sx:sx+width]
    target[dy:dy + height, dx:dx + width] = source[sy:sy + height, sx:sx + width]


def sspline_resize_hdl(
    args
) -> None:
    """加载一张图片，经本模块的 NumPy 实现缩放后，再保存到目标路径。

    这是 resize_rgb 的文件级便捷封装，供命令行入口使用：
        - 通过 Pillow 读取并转换为 RGB / RGBA（按原图是否含 alpha 通道决定）；
        - 交由 resize_rgb 完成缩放；
        - 再用 Pillow 写回磁盘。

    参数：
        input_path:  输入图片路径（任意 Pillow 支持格式）。
        output_path: 输出图片路径，格式由扩展名决定（如 .png / .jpg）。
        width:       目标宽度。
        height:      目标高度。

    异常：
        RuntimeError: Pillow 未安装。提示：python -m pip install Pillow。
    """

    # 有 alpha 通道就按 RGBA 处理，否则按 RGB，避免丢失透明信息
    # 。
    img = open(args.input_path, 'rb').read()
    if args.width and args.height:
        result = resize_rgb(img, args.width, args.height)
    elif args.multiple:
        result = scale_rgb(img, args.multiple)
    else:
        raise ValueError('width & height or multiple must be set')
    open(args.output_path, 'wb').write(result)


def reg_subparser(subparsers) -> None:
    """命令行入口：python sspline_rewrite.py <输入> <输出> <宽> <高>。"""
    parser = subparsers.add_parser("sspline", help="sspline")
    parser.add_argument("input", help="input image")
    parser.add_argument("-o", "--output", help="output image")
    parser.add_argument("-iw", "--width", type=int, default=0, help="destination width in pixels")
    parser.add_argument("-ih", "--height", type=int, default=0, help="destination height in pixels")
    parser.add_argument("-x", "--multiple", type=float, default=2, help="destination multiple")
    parser.set_default(func=sspline_resize_hdl)
