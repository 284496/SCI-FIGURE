# -*- coding: utf-8 -*-
"""trace2spec.py —— 截图/位图 → FigureSpec（可编辑原生对象），而不是死路径。

和「纯描摹」的关键差别：
- 矩形轮廓优先还原成 **矩形对象**（能改圆角、改填充、改大小），不是 4 个点的路径
- 圆形轮廓还原成 **椭圆对象**
- 复杂形状才退化成多边形
- 文字还原成 **文本对象**，并在其下方垫一块同色矩形做「抹字」（矢量抹除，不伤原图）
- 照片区域单独裁切，落成 **置入图**（PowerPoint/Illustrator 里可换图）

这样出来的 .ai 是可编辑的版式，而不是一张能缩放的截图。
"""
import os
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None


def _read(path, max_w=4000):
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise IOError("读不到图片：%s" % path)
    h, w = img.shape[:2]
    if w > max_w:
        r = max_w / float(w)
        img = cv2.resize(img, (max_w, int(h * r)), interpolation=cv2.INTER_AREA)
    return img


def _hex(c):
    return "#%02X%02X%02X" % (int(c[2]), int(c[1]), int(c[0]))


def _quantize(img, k, sample=300000, chunk=200000):
    Z = img.reshape(-1, 3).astype(np.float32)
    n = len(Z)
    if len(np.unique(Z, axis=0)) <= k:
        return img
    rng = np.random.default_rng(20261022)
    sub = Z[rng.choice(n, size=min(sample, n), replace=False)] if n > sample else Z
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, _, centers = cv2.kmeans(sub, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    centers = centers.astype(np.float32)
    out = np.empty(n, np.int32)
    for s in range(0, n, chunk):
        blk = Z[s:s + chunk]
        d = ((blk[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        out[s:s + chunk] = d.argmin(axis=1)
    return np.uint8(centers)[out].reshape(img.shape)


def _bg_color(q):
    """背景 = 图像四边边框的主导色（不能用全图众数，否则大片彩色面板会被当底色）。"""
    ring = np.concatenate([q[0:3, :].reshape(-1, 3), q[-3:, :].reshape(-1, 3),
                           q[:, 0:3].reshape(-1, 3), q[:, -3:].reshape(-1, 3)])
    v, c = np.unique(ring, axis=0, return_counts=True)
    return v[c.argmax()]


def _photo_blocks(img):
    """照片区：实心大块 + 颜色多 + 纹理连续（扁平色少）+ 不是整页容器。"""
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ink = (gray < 250).astype(np.uint8) * 255
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    g = gray.astype(np.float32)
    m, m2 = cv2.blur(g, (5, 5)), cv2.blur(g * g, (5, 5))
    sd = np.sqrt(np.clip(m2 - m * m, 0, None))
    blocks = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if w < 60 or h < 60 or area < 4000:
            continue
        if w > 0.85 * W and h > 0.85 * H:
            continue
        if area / float(w * h) < 0.78:
            continue
        if len(np.unique(img[y:y + h, x:x + w].reshape(-1, 3), axis=0)) < 220:
            continue
        if float((sd[y:y + h, x:x + w] < 3.0).mean()) > 0.55:
            continue
        blocks.append((int(x), int(y), int(w), int(h)))
    return blocks


def _fit(mask, eps):
    """轮廓 → 矩形/椭圆/多边形对象列表。"""
    cnts, _ = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        a = abs(cv2.contourArea(c))
        if a < 12:
            continue
        x, y, w, h = cv2.boundingRect(c)
        bx, by, bw, bh = x, y, w, h
        ap = cv2.approxPolyDP(c, eps, True)
        fill = a / float(max(1, bw * bh))
        peri = cv2.arcLength(c, True)
        # 矩形：顶点少、填充率高
        if fill > 0.90 and len(ap) <= 8 and peri < 2.6 * (bw + bh):
            out.append({"type": "rect", "x": int(bx), "y": int(by),
                        "w": int(bw), "h": int(bh)})
            continue
        # 椭圆：只在「接近正圆 + 面积与内切圆吻合」时才认，否则一律多边形
        if (0.75 < bw / float(bh) < 1.33 and fill > 0.70
                and abs(a - np.pi * bw * bh / 4.0) < 0.12 * a):
            out.append({"type": "ellipse", "cx": int(bx + bw / 2), "cy": int(by + bh / 2),
                        "rx": int(bw / 2), "ry": int(bh / 2)})
            continue
        pts = [[int(p[0][0]), int(p[0][1])] for p in ap]
        if len(pts) >= 3:
            out.append({"type": "polygon", "points": pts})
    return out


def to_spec(image, out_dir, colors=32, eps=0.8, scale=2.0, max_w=2200,
            use_ocr=True, font="Arial"):
    img0 = _read(image, max_w)
    h0, w0 = img0.shape[:2]
    img = cv2.resize(img0, (w0 * int(scale), h0 * int(scale)),
                     interpolation=cv2.INTER_CUBIC) if scale != 1 else img0
    s = img.shape[1] / float(w0)

    blocks = _photo_blocks(img)
    work = img.copy()
    for (x, y, w, h) in blocks:          # 照片区不参与矢量化
        work[y:y + h, x:x + w] = 255
    q = _quantize(work, colors)
    bg = _bg_color(q)
    bg_hex = _hex(bg)

    # 颜色层 → 图元；按覆盖面积排序（大色块在下）
    layers = {}
    for col in np.unique(q.reshape(-1, 3), axis=0):
        if np.array_equal(col, bg):
            continue
        mask = (np.all(q == col, axis=2)).astype(np.uint8) * 255
        if mask.sum() == 0:
            continue
        area = int(mask.sum() // 255)
        objs = _fit(mask, eps * s)
        if not objs:
            continue
        hx = _hex(col)
        for o in objs:
            o["fill"] = hx
        layers.setdefault(hx, {"area": area, "objs": objs})["area"] = area

    order = sorted(layers.items(), key=lambda kv: -kv[1]["area"])
    objects = []
    for hx, item in order:
        for o in item["objs"]:
            if o["type"] == "rect":
                o["x"] = int(o["x"] / s)
                o["y"] = int(o["y"] / s)
                o["w"] = max(1, int(o["w"] / s))
                o["h"] = max(1, int(o["h"] / s))
            elif o["type"] == "ellipse":
                o["cx"] = int(o["cx"] / s)
                o["cy"] = int(o["cy"] / s)
                o["rx"] = max(1, int(o["rx"] / s))
                o["ry"] = max(1, int(o["ry"] / s))
            else:
                o["points"] = [[int(p[0] / s), int(p[1] / s)] for p in o["points"]]
            objects.append(o)

    # 照片 → 置入图
    if blocks:
        pdir = os.path.join(out_dir, "assets")
        os.makedirs(pdir, exist_ok=True)
        for i, (x, y, w, h) in enumerate(blocks):
            fn = os.path.join(pdir, "photo_%d.png" % (i + 1))
            cv2.imwrite(fn, work[y:y + h, x:x + w])
            objects.append({"type": "image", "path": fn,
                            "x": int(x / s), "y": int(y / s),
                            "w": max(1, int(w / s)), "h": max(1, int(h / s))})

    # 文字 → 文本对象（下面垫同色矩形，做矢量抹除）
    if use_ocr:
        objects.extend(_text_objects(img, s, font, bg_hex))

    return {"canvas": {"w": w0, "h": h0, "bg": bg_hex},
            "_base": os.path.abspath(out_dir),
            "layers": [{"name": "shapes", "objects": objects}]}



def _local_bg(img, x0, y0, x1, y1):
    """取文字框外圈一圈像素的众数色，作为该文字的背景色（比全局背景准）。"""
    H, W = img.shape[:2]
    x0, y0 = max(0, int(x0) - 3), max(0, int(y0) - 3)
    x1, y1 = min(W, int(x1) + 3), min(H, int(y1) + 3)
    ring = np.concatenate([
        img[y0:y0 + 2, x0:x1].reshape(-1, 3), img[max(y0, y1 - 2):y1, x0:x1].reshape(-1, 3),
        img[y0:y1, x0:x0 + 2].reshape(-1, 3), img[y0:y1, max(x0, x1 - 2):x1].reshape(-1, 3),
    ]) if x1 > x0 and y1 > y0 else img[y0:y1, x0:x1].reshape(-1, 3)
    if len(ring) == 0:
        return "#FFFFFF"
    v, c = np.unique(ring.astype(np.uint8), axis=0, return_counts=True)
    return _hex(v[c.argmax()])
def _text_objects(img, s, font, bg_hex):
    """OCR 重建文字；每条文字带一个背景矩形盖住原字形。"""
    try:
        from rapidocr_onnxruntime import RapidOCR
    except Exception:
        try:
            from rapidocr import RapidOCR
        except Exception:
            return []
    try:
        engine = RapidOCR()
        res, _ = engine(img)
    except Exception:
        return []
    out = []
    for item in (res or []):
        box, txt, score = item[0], item[1], item[2]
        if score < 0.55 or not txt.strip():
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        w, h = (x1 - x0) / s, (y1 - y0) / s
        n = max(1, len(txt))
        size = max(4.0, min(h * 0.78, w / (n * 0.62)))
        vertical = h > 1.5 * w
        # 竖排文字保持「描摹字形」，不重建成文本：
        # 竖排的 OCR 框通常比字宽得多，垫背景会盖住底色，重建字又必然溢出。
        # 用户已明确「字体不需要复现」，所以这里保留矢量字形是最优解。
        if vertical:
            continue
        out.append({"type": "rect", "x": int(x0 / s), "y": int(y0 / s),
                    "w": max(1, int(w)), "h": max(1, int(h)),
                    "fill": _local_bg(img, x0, y0, x1, y1)})
        out.append({"type": "text", "x": int((x0 + x1) / 2 / s),
                    "y": int((y0 + y1) / 2 / s), "text": txt, "size": round(size, 1),
                    "color": "#111111", "vertical": vertical, "font": font})
    return out




