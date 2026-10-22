# -*- coding: utf-8 -*-
"""spec.py —— 图形描述文件（FigureSpec）的读取、校验与坐标换算。

设计原则（吸收四家之长）：
- 一切以「原生对象」为单位，不用位图凑数（LY / huatu）
- 坐标统一用图像习惯（左上原点，y 向下），落盘到 Illustrator 时再翻转
- 严格校验，错误早报（scientific-illustrator-agent 的 Pydantic 思路，但不引依赖）
"""
import json
import os

KINDS = {
    "rect": {"req": ("x", "y", "w", "h"), "opt": ("fill", "stroke", "sw", "radius", "opacity")},
    "ellipse": {"req": ("cx", "cy", "rx", "ry"), "opt": ("fill", "stroke", "sw", "opacity")},
    "polygon": {"req": ("points",), "opt": ("fill", "stroke", "sw", "opacity")},
    "line": {"req": ("x1", "y1", "x2", "y2"), "opt": ("color", "sw", "dash")},
    "arrow": {"req": ("x1", "y1", "x2", "y2"), "opt": ("color", "sw", "head")},
    "text": {"req": ("x", "y", "text"), "opt": ("size", "color", "bold", "vertical",
                                                "align", "font")},
    "image": {"req": ("path", "x", "y", "w", "h"), "opt": ("opacity",)},
}


class SpecError(ValueError):
    pass


def load(path):
    with open(path, encoding="utf-8") as f:
        return validate(json.load(f))


def validate(s):
    if "canvas" not in s:
        raise SpecError("缺少 canvas（画板尺寸与背景色）")
    c = s["canvas"]
    for k in ("w", "h"):
        if k not in c:
            raise SpecError("canvas 缺少 %s" % k)
    c.setdefault("bg", "#FFFFFF")
    s.setdefault("layers", [])
    if not s["layers"]:
        raise SpecError("layers 为空，至少要有一层")

    seen = set()
    for li, layer in enumerate(s["layers"]):
        layer.setdefault("name", "layer-%d" % (li + 1))
        if layer["name"] in seen:
            raise SpecError("图层重名：%s" % layer["name"])
        seen.add(layer["name"])
        layer.setdefault("objects", [])
        for oi, ob in enumerate(layer["objects"]):
            t = ob.get("type")
            if t not in KINDS:
                raise SpecError("第 %d 层第 %d 个对象类型未知：%r" % (li, oi, t))
            for k in KINDS[t]["req"]:
                if k not in ob:
                    raise SpecError("%s 缺少字段 %s（第 %d 层第 %d 个）" % (t, k, li, oi))
            if t == "image":
                p = ob["path"]
                if not os.path.isabs(p):
                    p = os.path.join(s.get("_base", "."), p)
                if not os.path.exists(p):
                    raise SpecError("图片不存在：%s" % ob["path"])
    return s


def stats(s):
    from collections import Counter
    c = Counter()
    for layer in s["layers"]:
        for ob in layer["objects"]:
            c[ob["type"]] += 1
    return dict(c)


def preview_ascii(s, cols=60):
    """极简版式预览，帮助在没有 Illustrator 时先判断布局。"""
    w, h = s["canvas"]["w"], s["canvas"]["h"]
    rows, rr = 18, max(1, cols / float(w))
    grid = [[" "] * cols for _ in range(rows)]
    for layer in s["layers"]:
        for ob in layer["objects"]:
            t = ob["type"]
            if t in ("rect", "image"):
                x, y, ww, hh = ob["x"], ob["y"], ob["w"], ob["h"]
            elif t == "ellipse":
                x, y = ob["cx"] - ob["rx"], ob["cy"] - ob["ry"]
                ww, hh = ob["rx"] * 2, ob["ry"] * 2
            elif t in ("line", "arrow"):
                x, y = min(ob["x1"], ob["x2"]), min(ob["y1"], ob["y2"])
                ww = abs(ob["x2"] - ob["x1"]) or 2
                hh = abs(ob["y2"] - ob["y1"]) or 2
            elif t == "polygon":
                xs = [p[0] for p in ob["points"]]
                ys = [p[1] for p in ob["points"]]
                x, y, ww, hh = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
            elif t == "text":
                x, y = ob["x"] - len(ob["text"]) * ob.get("size", 12) * 0.3, ob["y"]
                ww, hh = len(ob["text"]) * ob.get("size", 12) * 0.6, ob.get("size", 12)
            else:
                continue
            ch = {"rect": "#", "image": "I", "ellipse": "o", "line": "-",
                  "arrow": ">", "polygon": "^", "text": "T"}[t]
            x0, x1 = int(x * rr), max(int(x * rr) + 1, int((x + ww) * rr))
            y0, y1 = int(y * rows / float(h)), max(int(y * rows / float(h)) + 1,
                                                   int((y + hh) * rows / float(h)))
            for yy in range(max(0, y0), min(rows, y1)):
                for xx in range(max(0, x0), min(cols, x1)):
                    grid[yy][xx] = ch
    return "\n".join("".join(r) for r in grid)
