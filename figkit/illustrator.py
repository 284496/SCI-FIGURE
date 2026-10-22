# -*- coding: utf-8 -*-
"""illustrator.py —— Illustrator COM 通道：建文档、跑 JSX、存 .ai、导出 PNG。

要点：
- 一律「应用脚本接口」后台执行，不碰鼠标键盘、不抢前台
- 存盘用新文件名，避免弹出「是否覆盖」把自动化卡死
- 导出 PNG 是权威验收依据（huatu 的规矩：以 AI 实际导出为准）
"""
import os

_APP = None


def app():
    global _APP
    if _APP is None:
        import win32com.client as win32
        _APP = win32.Dispatch("Illustrator.Application")
        try:
            _APP.UserInteractionLevel = 1  # DONTDISPLAYALERTS
        except Exception:
            pass
    return _APP


def version():
    return str(app().Version)


def close_all(save=False):
    """清空当前打开的文档，保证每次从干净状态开始。"""
    a = app()
    try:
        while a.Documents.Count > 0:
            d = a.Documents[0]
            d.Close(2 if not save else 1)   # 2 = 不保存
    except Exception:
        pass


def run(jsx):
    return app().DoJavaScript(jsx)


def draw(spec, ai_path, png_path=None, close_existing=True):
    """按 spec 生成 .ai；可选同时导出 PNG 预览。"""
    from .jsx import compile_spec

    a = app()
    if close_existing:
        close_all()
    c = spec["canvas"]
    run("app.documents.add(DocumentColorSpace.RGB, %d, %d);" % (c["w"], c["h"]))
    run(compile_spec(spec))

    ai_path = os.path.abspath(ai_path)
    run(_save_jsx(ai_path))
    out = {"ai": ai_path, "objects": counts()}
    if png_path:
        png_path = os.path.abspath(png_path)
        run(_export_jsx(png_path))
        out["png"] = png_path
    return out


def _js(p):
    return '"' + os.path.abspath(p).replace("\\", "/") + '"'


def _save_jsx(path):
    return ("(function(){var o=new IllustratorSaveOptions();o.pdfCompatible=true;"
            "app.activeDocument.saveAs(new File(%s),o);return 'saved';})();" % _js(path))


def _export_jsx(path):
    return ("(function(){var o=new ExportOptionsPNG24();o.antiAliasing=true;"
            "o.artBoardClipping=true;o.horizontalScale=100;o.verticalScale=100;"
            "app.activeDocument.exportFile(new File(%s),ExportType.PNG24,o);"
            "return 'exported';})();" % _js(path))


def counts():
    """对象统计：用于「原生可编辑性」验收（huatu 要求统计文本/竖排/曲线）。"""
    js = """
    (function(){
      var d=app.activeDocument, tf=d.textFrames.length, vt=0, pt=0, ctr=0;
      for (var i=0;i<d.textFrames.length;i++){
        var f=d.textFrames[i];
        try{ if(f.orientation==TextOrientation.VERTICAL) vt++; }catch(e){}
        try{ if(f.kind==TextType.PATHTEXT) pt++; }catch(e){}
        try{ if(f.paragraphs[0].justification==Justification.CENTER) ctr++; }catch(e){}
      }
      return [tf, vt, pt, ctr, d.pathItems.length, d.groupItems.length, d.placedItems.length].join(',');
    })();
    """
    try:
        raw = str(run(js)).split(",")
        keys = ["text", "vertical", "pathtext", "centered", "paths", "groups", "images"]
        return dict(zip(keys, [int(x) for x in raw]))
    except Exception as e:
        return {"error": str(e)}


def close(save=False):
    try:
        app().ActiveDocument.Close(1 if save else 2)
    except Exception:
        pass
