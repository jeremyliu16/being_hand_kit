"""Apply the Windows/platform patches onto hand 0.13.5 (Mini/macOS copy).

Same three patches as the Windows run, path parameterised:
  P1  vision_ocr._capture_screenshot  -> cross-platform capture
  P2  mcp_server.hand_see_vlm         -> default returns the frame itself
  P3  vision_ocr._vision_recognize    -> honest "OCR unavailable" on non-darwin
  P4  router.route_screenshot         -> with_data honoured on the screen branch

Both machines get the same file contents so the two installs stay one source.
"""
import ast
import io
import json
import os
import sys

KIT = os.path.expanduser("~/.heart-portal/kits/hand")


def read(p):
    with io.open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def sub_once(text, old, new, label):
    if old not in text:
        raise SystemExit("ANCHOR MISSING: " + label)
    if text.count(old) != 1:
        raise SystemExit("ANCHOR AMBIGUOUS (%d): %s" % (text.count(old), label))
    return text.replace(old, new)


# ---------------- P1 + P3 ----------------
vo = os.path.join(KIT, "hand", "perception", "vision_ocr.py")
src = read(vo)

OLD_CAP = '''def _capture_screenshot(path: Optional[str] = None) -> str:
    """Take a screenshot, return path."""
    if path is None:
        path = os.path.join(tempfile.gettempdir(), "hand_screenshot.png")
    result = subprocess.run(
        ["screencapture", "-x", path],
        capture_output=True, text=True, timeout=5
    )
    if result.returncode != 0:
        raise RuntimeError(f"screencapture failed: {result.stderr}")
    return path
'''

NEW_CAP = '''def _capture_screenshot(path: Optional[str] = None) -> str:
    """Take a screenshot of the whole screen, return the PNG path.

    Cross-platform (Judy, 2026-10-28): hand_see_vlm returns the frame itself,
    so capture is not a rare fallback any more -- it is how a being looks.
    A macOS-only backend made that explode on Windows with [WinError 2],
    which reads like a bug in the caller instead of an absent platform hook.
    """
    if path is None:
        path = os.path.join(tempfile.gettempdir(), "hand_screenshot.png")

    if sys.platform.startswith("win"):
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
            "$b=[System.Windows.Forms.SystemInformation]::VirtualScreen;"
            "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
            "$g=[System.Drawing.Graphics]::FromImage($bmp);"
            "$g.CopyFromScreen($b.Left,$b.Top,0,0,$bmp.Size);"
            "$bmp.Save('" + path.replace("'", "''") + "',"
            "[System.Drawing.Imaging.ImageFormat]::Png);"
            "$g.Dispose();$bmp.Dispose()"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=25)
        if result.returncode != 0 or not os.path.exists(path):
            raise RuntimeError(
                "powershell screen capture failed: "
                + (result.stderr or "no file produced"))
        return path

    result = subprocess.run(
        ["screencapture", "-x", path],
        capture_output=True, text=True, timeout=5
    )
    if result.returncode != 0:
        raise RuntimeError(f"screencapture failed: {result.stderr}")
    return path
'''
src = sub_once(src, OLD_CAP, NEW_CAP, "P1 _capture_screenshot")

OLD_REC = '''    warnings = []
    if not os.path.exists(VISION_OCR_BIN):
        # Fallback: compile on the fly
        _compile_vision_bin()
'''
NEW_REC = '''    warnings = []
    if sys.platform != "darwin":
        # The OCR backend is a compiled Swift binary linked against Apple's
        # Vision framework. There is no Windows/Linux equivalent in this kit,
        # so say that instead of letting subprocess raise [WinError 193]
        # ("%1 is not a valid Win32 application") -- an error that names
        # neither the platform nor the missing capability.
        return {"lines": [],
                "warnings": ["vision OCR unavailable on " + sys.platform
                             + ": the backend is a macOS-only Swift binary "
                               "(Apple Vision framework). Use hand_see_vlm "
                               "for pixels, or cdp_see kind=a11y for text "
                               "from a browser page."],
                "unsupported_platform": sys.platform}
    if not os.path.exists(VISION_OCR_BIN):
        # Fallback: compile on the fly
        _compile_vision_bin()
'''
src = sub_once(src, OLD_REC, NEW_REC, "P3 platform guard")
if "\nimport sys\n" not in src:
    src = sub_once(src, "\nimport subprocess\n",
                   "\nimport subprocess\nimport sys\n", "P3 import sys")
write(vo, src)
print("patched vision_ocr.py (P1, P3)")

# ---------------- P2 ----------------
ms = os.path.join(KIT, "mcp_server.py")
src = read(ms)
OLD_VLM = '''def hand_see_vlm(prompt: str = None, image_b64: str = None) -> dict:
    from hand.router import route_see_vlm
    _bump()
    return route_see_vlm(prompt=prompt, image_b64=image_b64)
'''
NEW_VLM = '''def hand_see_vlm(prompt: str = None, image_b64: str = None,
                 describe: bool = False):
    """Look at the screen.

    Default (describe=False): the screenshot comes back to YOU as an image and
    lands in your own multimodal context. You look at it yourself -- no external
    vision model, no lossy text summary, no second API call.

    describe=True: send the screenshot to an external vision LLM and get text
    back. Use only when the caller has no vision (text-only substrate), or when
    you explicitly want a written description you can quote or search.

    Why the default flipped (Judy, 2026-10-28): hand_eye_check already proves
    rendered pixels reach the being, so paying a second model to describe them
    is lossy by construction -- a description can only ever summarise the thing
    the caller could have looked at directly.
    """
    from hand.router import route_screenshot
    _bump()
    if describe:
        from hand.router import route_see_vlm
        return route_see_vlm(prompt=prompt, image_b64=image_b64)
    if image_b64:
        result = {"data": image_b64, "format": "png"}
    else:
        result = route_screenshot(with_data=True)
    if result.get("data"):
        from mcp.types import ImageContent
        meta = {k: v for k, v in result.items() if k != "data"}
        meta["mode"] = "direct"
        if prompt:
            meta["prompt_ignored"] = prompt
            meta["hint"] = ("default mode returns the image itself and ignores "
                            "prompt; pass describe=true for an external "
                            "vision-LLM description")
        return [ImageContent(type="image",
                             data=result["data"],
                             mimeType="image/" + str(result.get("format", "png"))),
                json.dumps(meta, ensure_ascii=False)]
    return result
'''
src = sub_once(src, OLD_VLM, NEW_VLM, "P2 hand_see_vlm")
write(ms, src)
print("patched mcp_server.py (P2)")

# ---------------- P4 ----------------
RP = os.path.join(KIT, "hand", "router.py")
src = read(RP)
OLD = '''        "emitted": emitted_block({"image": image_channel(path=path)}),
    }
'''
NEW = '''        "emitted": emitted_block({"image": image_channel(path=path)}),
    }
    # with_data on this branch (Judy, 2026-10-28): the CDP branch honours it and
    # puts base64 in `data`; this branch used to ignore it, so every caller that
    # asked for pixels on a non-browser capture got a file path back with no
    # error. Symmetric now: ask for data, get data, and the emitted block says
    # `emitted: true` because the bytes really are in this receipt.
    if with_data:
        import base64
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        out["data"] = b64
        out["data_length"] = len(b64)
        out["format"] = "png"
        out["evidence"]["data_length"] = len(b64)
        out["evidence"]["format"] = "png"
        out["emitted"] = emitted_block({
            "image": image_channel(b64=b64, fmt="png"),
        })
    return out
'''
if OLD not in src:
    raise SystemExit("ANCHOR MISSING: P4")
if src.count(OLD) != 1:
    raise SystemExit("ANCHOR AMBIGUOUS P4: %d" % src.count(OLD))
# the block above must be the tail of route_screenshot's screen branch:
src = src.replace(OLD, NEW, 1)
# rename the dict literal it belongs to from `return {` to `out = {`
needle = '''    return {
        "method": "screenshot",
        "source": "vision_ocr",
        "path": path,'''
if needle not in src:
    raise SystemExit("ANCHOR MISSING: P4 dict head")
src = src.replace(needle, '''    out = {
        "method": "screenshot",
        "source": "vision_ocr",
        "path": path,''', 1)
write(RP, src)
print("patched router.py (P4)")

for p in (vo, ms, RP):
    ast.parse(read(p))
print("syntax OK x3")
