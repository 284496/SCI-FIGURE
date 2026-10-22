# Illustrator 脚本速查（含实战踩坑）

所有绘制都走 `app.DoJavaScript(jsx)`，**不要**用 COM 直接操作 pathItem——颜色、圆角、
竖排这些在 COM 里都没有干净的入口。

## 五个必踩的坑

### 1. `new RGBColor(r,g,b)` 不吃构造参数

```js
// ❌ 全黑，不报错
p.fillColor = new RGBColor(255,0,0);

// ✅ 逐属性赋值
function C(hex){
  var c = new RGBColor();
  c.red   = parseInt(hex.substr(1,2),16);
  c.green = parseInt(hex.substr(3,2),16);
  c.blue  = parseInt(hex.substr(5,2),16);
  return c;
}
```

### 2. 文本 `position` 是左上角

想按中心放置，必须创建后按实际尺寸回正：

```js
var t = doc.textFrames.add();
t.contents = "标题";
t.position = [cx - t.width/2, cy + t.height/2];   // AI 的 y 向上
```

### 3. 枚举名不是直觉拼写

| 想表达 | 正确写法 | 常见错写 |
|---|---|---|
| 圆头线帽 | `StrokeCap.ROUNDENDCAP` | `StrokeCap.ROUND` ❌ |
| 竖排文本 | `t.orientation = TextOrientation.VERTICAL` | 旋转文本框 ❌ |
| 段落居中 | `t.paragraphs[0].justification = Justification.CENTER` | 只设 position ❌ |
| 保存选项 | `new IllustratorSaveOptions()`，`o.pdfCompatible = true` | — |

### 4. 字体可能不存在

```js
try { t.textRange.characterAttributes.textFont =
        app.textFonts.getByName('Arial'); } catch(e) {}
```
`Arial` 在很多机器上叫 `ArialMT`。不加 try 会让整张图中断。

### 5. 位图 base64 塞进 SVG → Illustrator 静默失败

用 `<image href="data:image/png;base64,...">` 导入，Illustrator **不报错但得到空文档**。
正确做法：位图用 `doc.placedItems.add()` 单独置入。

```js
var pi = doc.placedItems.add();
pi.file = new File("/abs/path.png");
pi.position = [x, y];      // 左上角，AI 坐标
pi.width = w; pi.height = h;
```

## 常用片段

### 新建文档 + 设画板

```js
app.documents.add(DocumentColorSpace.RGB, 1036, 676);
doc.artboards[0].artboardRect = [0, 676, 1036, 0];   // [左, 上, 右, 下]
```

### 圆角矩形 / 矩形 / 椭圆 / 多边形

```js
var r = doc.pathItems.roundedRectangle(top, left, width, height, hRad, vRad);
var b = doc.pathItems.rectangle(top, left, width, height);
var e = doc.pathItems.ellipse(top, left, width, height);   // top 是椭圆外框上边
var g = doc.pathItems.add();
g.setEntirePath([[x1,y1],[x2,y2],[x3,y3]]);
g.closed = true;
```

注意所有 `top` 都是 **Illustrator 坐标**（左下原点）：`top = 画板高 - 图像 y`。

### 虚线 / 描边

```js
p.stroked = true;
p.strokeWidth = 1;
p.strokeColor = C('#9AA7B8');
p.strokeDashed = true;
```

### 导出 PNG（验收用）

```js
var o = new ExportOptionsPNG24();
o.antiAliasing = true;
o.artBoardClipping = true;
o.horizontalScale = 100; o.verticalScale = 100;
doc.exportFile(new File("/abs/out.png"), ExportType.PNG24, o);
```
**以 Illustrator 导出的 PNG 为准**，浏览器渲染的 SVG 只能做参考。

### 保存 .ai

```js
var o = new IllustratorSaveOptions();
o.pdfCompatible = true;
doc.saveAs(new File("/abs/out.ai"), o);
```

### 对象统计（验收"是否真原生可编辑"）

```js
var d = app.activeDocument;
d.textFrames.length        // 文本对象数
d.pathItems.length         // 路径数
d.placedItems.length       // 置入图数
d.groupItems.length        // 组数
```
文本数应为 0 或接近标注数量；若为 0 而图上有字，说明字被描成了曲线，不可编辑。

## COM 侧（Python）

```python
import win32com.client as win32
ai = win32.Dispatch("Illustrator.Application")
ai.UserInteractionLevel = 1      # DONTDISPLAYALERTS，避免弹窗卡死
ai.DoJavaScript(jsx_string)
```

关闭文档时 `doc.Close(2)` = 不保存，`doc.Close(1)` = 保存。
**存盘永远用新文件名**，覆盖确认弹窗会把自动化挂死。
