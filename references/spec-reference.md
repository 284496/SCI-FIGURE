# FigureSpec 字段全表

本 spec 是 **sci-figure 的唯一真源**：`draw` 读它，`trace` 产出它。
改图 = 改 spec 再 draw，不要在 Illustrator 里手工挪（下次重跑就丢了）。

## 顶层

```json
{
  "canvas": {"w": 1036, "h": 676, "bg": "#FFFFFF"},
  "layers": [ {"name": "背景", "objects": [...]}, ... ]
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `canvas.w` / `canvas.h` | 是 | 画板尺寸，单位 px（导出 PNG 也是这个尺寸） |
| `canvas.bg` | 否 | 背景色，默认 `#FFFFFF` |
| `layers[].name` | 是 | 图层名，会变成 Illustrator 的图层。**不能重名** |
| `layers[].objects` | 是 | 该层对象，数组顺序 = 绘制顺序（后画的在上面） |

坐标约定：**左上原点，y 向下**，和看图一致。落盘时自动翻成 Illustrator 的左下原点。

## 图元

所有坐标单位 px，颜色用 `#RRGGBB`。

### rect 矩形

```json
{"type":"rect","x":60,"y":110,"w":200,"h":110,
 "fill":"#2F6FB0","stroke":"#1A1A1A","sw":1,"radius":12,"opacity":1}
```
`radius` 给了就是圆角矩形；不填 `fill` 则无填充；不填 `stroke` 则无描边。

### ellipse 椭圆

```json
{"type":"ellipse","cx":700,"cy":352,"rx":20,"ry":20,"fill":"#E87D1E","stroke":"#FFFFFF","sw":2.5}
```

### polygon 多边形

```json
{"type":"polygon","points":[[856,270],[912,352],[856,434]],"fill":"#5B2D8E"}
```
点序列任意，自动闭合。FC 楔形、箭头头部、自定义形状都用它。

### line 直线

```json
{"type":"line","x1":60,"y1":270,"x2":840,"y2":270,"color":"#9AA7B8","sw":1,"dash":true}
```
`dash: true` 为虚线。

### arrow 箭头

```json
{"type":"arrow","x1":264,"y1":165,"x2":344,"y2":165,"color":"#E87D1E","sw":5,"head":15}
```
线 + 三角头，自动按角度旋转。`head` 是头部长度。

### text 文本

```json
{"type":"text","x":450,"y":150,"text":"① 图像分割",
 "size":18,"color":"#FFFFFF","bold":true,"vertical":false,"font":"Source Han Sans CN"}
```

| 字段 | 说明 |
|---|---|
| `x` / `y` | **文字中心**（不是左上角）；脚本会按实际宽高回正 |
| `vertical` | 竖排，用 `TextOrientation.VERTICAL`，每个字正立 |
| `font` | 字体名；缺失时静默回退默认字体，不报错 |
| `bold` | 加粗 |

段落固定居中（`Justification.CENTER`），保证框内文字居中。

### image 置入图

```json
{"type":"image","path":"assets/photo_1.png","x":50,"y":470,"w":200,"h":150,"opacity":1}
```
`path` 相对于 spec 所在目录。用于病理切片、CT 截图这类**不该矢量化**的内容。

## 常用版式参数（照抄即可）

| 场景 | 值 |
|---|---|
| 主色 | 蓝 `#2F6FB0`、绿 `#2E9E4F`、紫 `#5B2D8E`、橙 `#E87D1E` |
| 面板底 | 浅青 `#78D2DF`、浅灰 `#F2F2F2`、浅蓝 `#F4F7FB` |
| 圆角 | 卡片 10–14，小标签 4–6 |
| 主标题 | size 20–24，bold |
| 模块名 | size 14–18，bold |
| 正文/注释 | size 10–12 |
| 箭头 | sw 4–5，head 13–16 |

## 校验规则

`probe` / `draw` 前会检查：
- canvas 有 w/h
- 每层有 name 且不重名
- 每个对象 `type` 合法、必填字段齐全
- image 的 path 真实存在

任一不过，直接报错并指出"第几层第几个对象缺什么"——不做静默降级。
