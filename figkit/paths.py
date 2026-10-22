# -*- coding: utf-8 -*-
"""paths.py —— 统一的工作区位置。

默认全部落在 E:\\科研图，可用环境变量 SCI_FIGURE_HOME 覆盖。

目录约定：
  inbox/    放原始素材（截图、图片、参考图）
  specs/    放 FigureSpec（json），可纳入版本管理
  out/      最终交付（.ai / .png / 预览）
  preview/  中间预览与调参截图，可随时清空
  archive/  归档旧稿
"""
import os

DEFAULT_HOME = r"E:\科研图"


def home():
    return os.environ.get("SCI_FIGURE_HOME", DEFAULT_HOME)


def sub(name):
    p = os.path.join(home(), name)
    os.makedirs(p, exist_ok=True)
    return p


def inbox():
    return sub("inbox")


def specs():
    return sub("specs")


def out():
    return sub("out")


def preview():
    return sub("preview")


def archive():
    return sub("archive")


def ensure_all():
    for f in (inbox, specs, out, preview, archive):
        f()
    return home()


def out_path(name, ext=None):
    """给一个名字，返回 out/ 下的完整路径（自动补扩展名）。"""
    if ext and not name.lower().endswith(ext.lower()):
        name += ext
    return os.path.join(out(), os.path.basename(name))
