# -*- coding: utf-8 -*-
"""jsx.py —— 把 FigureSpec 编译成 Illustrator ExtendScript。

踩过的坑都固化在这里：
1. `new RGBColor(r,g,b)` 不吃构造参数 → 必须逐属性赋值（否则整张图全黑）
2. `StrokeCap.ROUND` 不存在 → 是 `StrokeCap.ROUNDENDCAP`
3. 文本 `position` 是左上角 → 想按中心放置，必须创建后按实际宽高回正
4. 竖排只能用 `TextOrientation.VERTICAL`，不能用旋转
5. 段落居中必须显式 `paragraphs[0].justification = Justification.CENTER`
"""
import json
import math

HELPER = (
    "function C(hex){"
    "var c=new RGBColor();"
    "c.red=parseInt(hex.substr(1,2),16);"
    "c.green=parseInt(hex.substr(3,2),16);"
    "c.blue=parseInt(hex.substr(5,2),16);"
    "return c;}"
)


class Builder(object):
    def __init__(self, spec):
        self.s = spec
        self.H = spec["canvas"]["h"]
        self.ops = []
        self._n = 0

    # ---------- 基础 ----------
    def _emit(self, js):
        self.ops.append(js)

    def _var(self, base):
        self._n += 1
        return "%s%d" % (base, self._n)

    def _y(self, y):
        return self.H - y

    def _fill(self, v, o):
        v = self._var("p")
        self._emit("var %s=doc.pathItems.add();" % v)
        return v

    # ---------- 图元 ----------
    def rect(self, o):
        v = self._var("p")
        if o.get("radius"):
            r = o["radius"]
            self._emit("var %s=doc.pathItems.roundedRectangle(%s,%s,%s,%s,%s,%s);"
                       % (v, self._y(o["y"]), o["x"], o["w"], o["h"], r, r))
        else:
            self._emit("var %s=doc.pathItems.rectangle(%s,%s,%s,%s);"
                       % (v, self._y(o["y"]), o["x"], o["w"], o["h"]))
        if o.get("fill"):
            self._emit("%s.filled=true;%s.fillColor=C('%s');" % (v, v, o["fill"]))
        else:
            self._emit("%s.filled=false;" % v)
        if o.get("stroke"):
            self._emit("%s.stroked=true;%s.strokeWidth=%s;%s.strokeColor=C('%s');"
                       % (v, v, o.get("sw", 1), v, o["stroke"]))
        if o.get("opacity") is not None:
            self._emit("%s.opacity=%s;" % (v, o["opacity"]))

    def ellipse(self, o):
        v = self._var("p")
        self._emit("var %s=doc.pathItems.ellipse(%s,%s,%s,%s);"
                   % (v, self._y(o["cy"]) + o["ry"], o["cx"] - o["rx"],
                      o["rx"] * 2, o["ry"] * 2))
        if o.get("fill"):
            self._emit("%s.filled=true;%s.fillColor=C('%s');" % (v, v, o["fill"]))
        else:
            self._emit("%s.filled=false;" % v)
        if o.get("stroke"):
            self._emit("%s.stroked=true;%s.strokeWidth=%s;%s.strokeColor=C('%s');"
                       % (v, v, o.get("sw", 1), v, o["stroke"]))

    def polygon(self, o):
        v = self._var("p")
        pts = ",".join("[%s,%s]" % (p[0], self._y(p[1])) for p in o["points"])
        self._emit("var %s=doc.pathItems.add();%s.setEntirePath([%s]);%s.closed=true;"
                   % (v, v, pts, v))
        if o.get("fill"):
            self._emit("%s.filled=true;%s.fillColor=C('%s');" % (v, v, o["fill"]))
        else:
            self._emit("%s.filled=false;" % v)
        if o.get("stroke"):
            self._emit("%s.stroked=true;%s.strokeWidth=%s;%s.strokeColor=C('%s');"
                       % (v, v, o.get("sw", 1), v, o["stroke"]))

    def line(self, o):
        v = self._var("l")
        self._emit("var %s=doc.pathItems.add();%s.setEntirePath([[%s,%s],[%s,%s]]);"
                   % (v, v, o["x1"], self._y(o["y1"]), o["x2"], self._y(o["y2"])))
        self._emit("%s.stroked=true;%s.filled=false;%s.strokeWidth=%s;"
                   "%s.strokeColor=C('%s');" % (v, v, v, o.get("sw", 1.5), v,
                                                o.get("color", "#1A1A1A")))
        if o.get("dash"):
            self._emit("%s.strokeDashed=true;" % v)

    def arrow(self, o):
        color = o.get("color", "#E87D1E")
        w = o.get("sw", 4)
        head = o.get("head", 13)
        x1, y1 = o["x1"], self._y(o["y1"])
        x2, y2 = o["x2"], self._y(o["y2"])
        ang = math.atan2(y2 - y1, x2 - x1)
        bx, by = x2 - head * math.cos(ang), y2 - head * math.sin(ang)
        v = self._var("a")
        self._emit("var %s=doc.pathItems.add();%s.setEntirePath([[%s,%s],[%s,%s]]);"
                   % (v, v, x1, y1, bx, by))
        self._emit("%s.stroked=true;%s.filled=false;%s.strokeWidth=%s;"
                   "%s.strokeColor=C('%s');%s.strokeCap=StrokeCap.ROUNDENDCAP;"
                   % (v, v, v, w, v, color, v))
        h = self._var("h")
        p2 = (bx - head * 0.45 * math.sin(ang), by + head * 0.45 * math.cos(ang))
        p3 = (bx + head * 0.45 * math.sin(ang), by - head * 0.45 * math.cos(ang))
        self._emit("var %s=doc.pathItems.add();"
                   "%s.setEntirePath([[%s,%s],[%s,%s],[%s,%s]]);%s.closed=true;"
                   "%s.filled=true;%s.fillColor=C('%s');"
                   % (h, h, x2, y2, p2[0], p2[1], p3[0], p3[1], h, h, h, color))

    def text(self, o):
        v = self._var("t")
        self._emit("var %s=doc.textFrames.add();%s.contents=%s;"
                   % (v, v, json.dumps(o["text"], ensure_ascii=False)))
        self._emit("%s.textRange.characterAttributes.size=%s;" % (v, o.get("size", 12)))
        self._emit("%s.textRange.characterAttributes.fillColor=C('%s');"
                   % (v, o.get("color", "#1A1A1A")))
        if o.get("bold"):
            self._emit("%s.textRange.characterAttributes.bold=true;" % v)
        if o.get("font"):
            # 字体名在不同机器上不一定存在（如 Arial 常被本地化成 ArialMT），
            # 缺失时保持默认字体，不能让整张图报错中断
            self._emit("try{%s.textRange.characterAttributes.textFont="
                       "app.textFonts.getByName('%s');}catch(e){}" % (v, o["font"]))
        if o.get("vertical"):
            self._emit("%s.orientation=TextOrientation.VERTICAL;" % v)
        self._emit("%s.paragraphs[0].justification=Justification.CENTER;"
                   % v)
        # 按实际宽高，把「左上角锚点」回正到「中心锚点」
        self._emit("%s.position=[%s-%s.width/2,%s+%s.height/2];"
                   % (v, o["x"], v, self._y(o["y"]), v))

    def image(self, o):
        v = self._var("pi")
        self._emit("var %s=doc.placedItems.add();" % v)
        self._emit("%s.file=new File('%s');" % (v, o["path"].replace("\\", "/")))
        self._emit("%s.position=[%s,%s];" % (v, o["x"], self._y(o["y"] + o["h"])))
        self._emit("%s.width=%s;%s.height=%s;" % (v, o["w"], v, o["h"]))
        if o.get("opacity") is not None:
            self._emit("%s.opacity=%s;" % (v, o["opacity"]))

    # ---------- 编译 ----------
    def build(self):
        c = self.s["canvas"]
        self._emit("doc.artboards[0].artboardRect=[0,%s,%s,0];" % (c["h"], c["w"]))
        for layer in self.s["layers"]:
            lv = self._var("L")
            self._emit("var %s=doc.layers.add();%s.name=%s;"
                       % (lv, lv, json.dumps(layer["name"], ensure_ascii=False)))
            self._emit("doc.activeLayer=%s;" % lv)
            for ob in layer["objects"]:
                getattr(self, ob["type"])(ob)
        return "(function(){\nvar doc=app.activeDocument;\n" + HELPER + "\n" + \
               "\n".join(self.ops) + "\nreturn 'ok';\n})();"


def compile_spec(spec):
    return Builder(spec).build()
