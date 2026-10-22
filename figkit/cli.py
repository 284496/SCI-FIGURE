# -*- coding: utf-8 -*-
"""cli.py —— sci-figure 命令行入口。

  draw   spec.json  [-o 名字]        文字/规格 → Illustrator 原生图
  trace  shot.png   [-o 名字]        截图 → 可编辑原生图
  qa     原图.png   复现.png          差分验收：IoU / SSIM / diff
  probe  spec.json                   只校验 + 版式预览，不碰 Illustrator

不写 --ai 时，产物默认落到 E:\\科研图\\out。
"""
import argparse
import json
import os
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sci-figure")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("draw", help="规格 → .ai")
    d.add_argument("spec")
    d.add_argument("-o", "--out", help="输出名或路径；默认 <spec名>.ai 落到工作区 out/")
    d.add_argument("--ai", help="显式指定 .ai 路径（优先级高于 -o）")
    d.add_argument("--png", help="同时导出 PNG 预览")

    t = sub.add_parser("trace", help="截图 → .ai")
    t.add_argument("image")
    t.add_argument("-o", "--out", help="输出名或路径；默认 <图名>.ai 落到工作区 out/")
    t.add_argument("--ai")
    t.add_argument("--png")
    t.add_argument("--colors", type=int, default=32)
    t.add_argument("--eps", type=float, default=0.8)
    t.add_argument("--scale", type=float, default=2.0)
    t.add_argument("--max-w", type=int, default=2200)
    t.add_argument("--no-ocr", action="store_true")
    t.add_argument("--save-spec", nargs="?", const="__auto__",
                   help="把推导出的 spec 存到 specs/，便于手改后再 draw")

    q = sub.add_parser("qa", help="差分验收")
    q.add_argument("ref")
    q.add_argument("out")
    q.add_argument("--dir", default=None)

    p = sub.add_parser("probe", help="校验 spec 并打印版式预览")
    p.add_argument("spec")

    w = sub.add_parser("where", help="打印工作区位置与目录内容")
    w.add_argument("--open", action="store_true", help="在资源管理器中打开")

    a = ap.parse_args(argv)
    from . import paths, spec as spec_mod

    if a.cmd == "where":
        h = paths.ensure_all()
        print("工作区：", h)
        for name in ("inbox", "specs", "out", "preview", "archive"):
            p = os.path.join(h, name)
            n = len([f for f in os.listdir(p)]) if os.path.isdir(p) else 0
            print("  %-8s %s  (%d 项)" % (name, p, n))
        if a.open:
            os.startfile(h)
        return 0

    if a.cmd == "probe":
        s = spec_mod.load(a.spec)
        print(spec_mod.preview_ascii(s))
        print(json.dumps({"canvas": s["canvas"], "objects": spec_mod.stats(s)},
                         ensure_ascii=False, indent=1))
        return 0

    if a.cmd == "draw":
        from . import illustrator
        s = spec_mod.load(a.spec)
        ai = a.ai or paths.out_path(a.out or (os.path.splitext(os.path.basename(a.spec))[0] + ".ai"))
        png = a.png or (os.path.splitext(ai)[0] + ".png")
        out = illustrator.draw(s, ai, png)
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    if a.cmd == "trace":
        from . import trace2spec, illustrator
        ai = a.ai or paths.out_path(
            a.out or (os.path.splitext(os.path.basename(a.image))[0] + ".ai"))
        png = a.png or (os.path.splitext(ai)[0] + ".png")
        s = trace2spec.to_spec(a.image, os.path.dirname(os.path.abspath(ai)),
                               colors=a.colors, eps=a.eps, scale=a.scale,
                               max_w=a.max_w, use_ocr=not a.no_ocr)
        if a.save_spec:
            sp = (paths.specs() if a.save_spec == "__auto__"
                  else os.path.dirname(os.path.abspath(a.save_spec)))
            os.makedirs(sp, exist_ok=True)
            name = os.path.splitext(os.path.basename(ai))[0] + ".json"
            fp = os.path.join(sp, name)
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(s, f, ensure_ascii=False, indent=1)
            print("spec ->", fp)
        spec_mod.validate(s)
        out = illustrator.draw(s, ai, png)
        out["spec_objects"] = spec_mod.stats(s)
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    if a.cmd == "qa":
        from . import qa
        out_dir = a.dir or os.path.join(
            paths.preview(), os.path.splitext(os.path.basename(a.out))[0] + "_qa")
        rep = qa.compare(a.ref, a.out, out_dir)
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        print("qa   ->", out_dir)
        return 0 if rep["ink_iou"] >= 0.65 else 2

    return 1


if __name__ == "__main__":
    sys.exit(main())
