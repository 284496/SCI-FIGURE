# sci-figure

**科研配图工厂：文字进，可编辑矢量图出；截图进，也能变成可编辑矢量图。**

一个 Agent Skill —— 给 AI 助手装上"画论文配图"的手。两种入口共用一套引擎：

```
文字 ──► FigureSpec(JSON) ──► Illustrator 原生对象 ──► .ai + PNG ──► 量化验收
截图 ──► FigureSpec(JSON) ──┘                                      ▲
                    └────────── 改几个坐标再重跑 ───────────────────┘
```

核心主张：**交付的是"版式"，不是"能缩放的截图"**。
每个方块都能改圆角、改填充、改大小；每个字都能双击改内容。

![示例](assets/demo.png)

---

## 为什么不是"位图转矢量"

市面上多数工具做的是**描摹**：把像素轮廓抠成路径。结果是一条条碎曲线，改不动、也不能算元素。

sci-figure 做的是**还原**：

| | 描摹工具 | sci-figure |
|---|---|---|
| 矩形 | 4 个点的多边形 | **矩形对象**（改圆角、改填充） |
| 文字 | 一堆曲线 | **文本对象**（双击改字） |
| 椭圆/圆 | 几十段贝塞尔 | **椭圆对象**（改半径） |
| 照片 | 被矢量化成噪点 | **置入图**（可换可裁） |
| 改图 | 重画 | 改 JSON 里一个数，重跑 |

代价是它不会 100% 逐像素复制——换来的是"这张图以后还能改"。

---

## 安装

这是一个 [Agent Skill](https://agentskills.io/specification)，放进任意兼容 Agent 的技能目录即可。

```bash
# Codex
git clone https://github.com/<you>/sci-figure.git ~/.codex/skills/sci-figure
# Claude Code
git clone https://github.com/<you>/sci-figure.git ~/.claude/skills/sci-figure
```

Windows 上 DSH / dsh-desktop 的技能目录通常是：

```
%APPDATA%\dsh-desktop\harness\skills\sci-figure
```

依赖（Python 3.9+）：

```bash
pip install numpy opencv-python Pillow pywin32
pip install scikit-image rapidocr-onnxruntime   # 可选：SSIM 指标 / 文字重建
```

`pywin32` 只在 Windows + Adobe Illustrator 下需要。**必须装有授权的 Illustrator 并能正常打开**（本工具通过 COM + ExtendScript 驱动它）。

---

## 用法

### 一、文字 → 图

写一份 JSON（坐标左上原点、y 向下）：

```json
{
 "canvas": {"w": 900, "h": 360, "bg": "#FFFFFF"},
 "layers": [
  {"name": "流程", "objects": [
    {"type":"rect","x":60,"y":110,"w":200,"h":110,"fill":"#2F6FB0","radius":12},
    {"type":"text","x":160,"y":150,"text":"① 图像分割","size":18,"color":"#FFFFFF","bold":true},
    {"type":"arrow","x1":264,"y1":165,"x2":344,"y2":165,"color":"#E87D1E","sw":5,"head":15}
  ]}
 ]
}
```

```bash
python run.py probe my.json                          # ASCII 版式预览，不碰 Illustrator
python run.py draw  my.json --ai out.ai --png out.png
```

字段全表见 [`references/spec-reference.md`](references/spec-reference.md)。

### 二、截图 → 图

```bash
python run.py trace shot.png --ai out.ai --png out.png --save-spec tune.json
```

`--save-spec` 会把推导结果存成**可编辑的** spec。改几处坐标再 `draw`，比反复重跑可靠得多——这是把"描摹"升级成"版式"的开关。

| 参数 | 默认 | 说明 |
|---|---|---|
| `--colors` | 32 | 量化色数；40–48 更保真 |
| `--eps` | 0.8 | 轮廓简化容差；0.4 更贴合但对象翻倍 |
| `--scale` | 2 | 超采样倍数，1px 细线靠它活下来 |
| `--no-ocr` | 关 | 不重建文字，文字保留为矢量字形 |

### 三、验收（必须做）

```bash
python run.py qa 原图.png 复现.png
```

```
ink_iou : 0.8842      前景覆盖重合率
ssim    : 0.4686      结构相似度
verdict : 可用，建议局部修
```

同时产出 `diff.png`（**青=漏画，洋红=多画**）和 `side_by_side.png`。

![差分图](assets/diff.png)

---

## 实测水平

同一张架构图三条路线对比（左：原图，中：纯描摹，右：本工具）：

![对比](assets/compare.png)

| 输入 | 结果 |
|---|---|
| 文字描述 | 内容由你给，可控 ≈ 100% |
| 规整截图（方块、箭头、文字） | IoU 0.85–0.90 |
| 文字密集 + 彩色矩阵的复合图 | IoU 0.6–0.75，建议 trace 后手改 spec |
| 病理切片 / 医学影像 | 原图裁切置入，100% 保真，不可矢量化 |

**规律**：一张图里"能用一句话描述的元素"占比越高，效果越好。

---

## 已知边界（不吹）

- 不能从像素反推原始数据，也不该做
- 手绘笔触、渐变、半透明叠加只能近似
- 源图宽度低于 1600px 的密集小字，物理上救不回来
- 需要 Illustrator（Windows）；没有 Illustrator 时 `probe` 仍可用，`draw` 不行
- OCR 只对横排做文本重建；竖排保留矢量字形（实测这样最干净）

---

## 目录

```
sci-figure/
├── SKILL.md                   Agent 工作流（三模式、铁律、边界）
├── run.py                     CLI 入口
├── figkit/
│   ├── spec.py                FigureSpec 校验 + ASCII 版式预览
│   ├── jsx.py                 spec → ExtendScript（踩过的坑都在注释里）
│   ├── illustrator.py         COM 通道：建文档 / 存 .ai / 导 PNG / 对象统计
│   ├── trace2spec.py          截图 → spec（矩形还原、文字重建、照片置入）
│   └── qa.py                  IoU / SSIM / 差分图
├── references/
│   ├── spec-reference.md      字段全表
│   └── jsx-cheatsheet.md      Illustrator 脚本 API 与五个坑
└── examples/demo.json         可运行示例
```

---

## 设计取舍

这套东西的设计受几个开源项目启发，也刻意避开了它们的短板：

- **原生对象优先**：宁可少画几个细节，也不把整张图压平
- **以 Illustrator 导出为准**：浏览器渲染的 SVG 好看不代表 AI 里对
- **量化验收**：不靠肉眼"看着像"，靠 IoU 与差分图定位漏画/多画
- **spec 可落盘**：任何一次自动推导的结果都能被人工接管

---

## License

MIT
