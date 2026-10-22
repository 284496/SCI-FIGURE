# -*- coding: utf-8 -*-
"""qa.py —— 验收闭环（zyipeng 与 huatu 的 QA 思路）。

不看"像不像"，看三个数：
- ink IoU   ：前景覆盖重合率（形状位置是否对得上）
- SSIM      ：结构相似度（纹理与灰度层次）
- 差分图     ：青色=原图独有，洋红=复现独有，深色=重合

输出：report.json + diff.png + side_by_side.png
"""
import json
import os

import numpy as np


def _load(path, size=None):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if size:
        im = im.resize(size, Image.LANCZOS)
    return np.array(im)


def ink_mask(a, thr=245):
    g = a.mean(axis=2)
    return (g < thr)


def compare(ref_path, out_path, out_dir):
    a = _load(ref_path)
    b = _load(out_path, (a.shape[1], a.shape[0]))
    ma, mb = ink_mask(a), ink_mask(b)

    inter = np.logical_and(ma, mb).sum()
    union = np.logical_or(ma, mb).sum()
    iou = float(inter) / float(union) if union else 1.0

    try:
        from skimage.metrics import structural_similarity as ssim
        s = float(ssim(a, b, channel_axis=2, data_range=255))
    except Exception:
        s = float("nan")

    diff = np.zeros_like(a)
    only_a = np.logical_and(ma, ~mb)
    only_b = np.logical_and(mb, ~ma)
    both = np.logical_and(ma, mb)
    diff[both] = (40, 40, 40)
    diff[only_a] = (0, 200, 220)
    diff[only_b] = (230, 0, 200)
    diff[~ma & ~mb] = (255, 255, 255)

    os.makedirs(out_dir, exist_ok=True)
    from PIL import Image
    Image.fromarray(diff).save(os.path.join(out_dir, "diff.png"))

    h = a.shape[0]
    gap = np.full((h, 12, 3), 255, np.uint8)
    side = np.concatenate([a, gap, b], axis=1)
    Image.fromarray(side).save(os.path.join(out_dir, "side_by_side.png"))

    rep = {"ink_iou": round(iou, 4), "ssim": round(s, 4) if s == s else None,
           "ink_missing_px": int(only_a.sum()), "ink_extra_px": int(only_b.sum()),
           "ink_total_px": int(union),
           "verdict": _verdict(iou, s)}
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    return rep


def _verdict(iou, s):
    if iou >= 0.90 and (s != s or s >= 0.85):
        return "高保真"
    if iou >= 0.80:
        return "可用，建议局部修"
    if iou >= 0.65:
        return "结构在，细节需重画"
    return "不达标，换参数或改走重画路线"
