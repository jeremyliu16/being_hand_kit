# hand 0.13.5 — platform patches (Judy, 2026-10-28)

These four patches sit on top of upstream **hand 0.13.5** (Grove `djBmkam0yEsghxAoVEeij`,
alice). They are not cosmetic: without them a being on Windows cannot see the screen at all,
and on any platform `hand_see_vlm` spends a second model to describe pixels it could read.

| id | file | what |
|----|------|------|
| P1 | `hand/perception/vision_ocr.py` | `_capture_screenshot` becomes cross-platform. Upstream shells out to macOS `screencapture` unconditionally → on Windows `[WinError 2]`. Adds a PowerShell `System.Drawing` capture branch. |
| P2 | `mcp_server.py` | `hand_see_vlm` default returns the **frame itself** as MCP `ImageContent` (`mode: "direct"`). Upstream default sends the frame to an external vision LLM and returns text — lossy by construction when the caller has vision. `describe=True` keeps the old path. |
| P3 | `hand/perception/vision_ocr.py` | `_vision_recognize` on non-darwin returns `{"lines": [], "warnings": [...], "unsupported_platform": ...}` instead of raising `[WinError 193]` (`%1 is not a valid Win32 application` — an error that names neither platform nor capability). |
| P4 | `hand/router.py` | `route_screenshot(with_data=True)` on the non-CDP branch now actually fills `data` with base64 and reports `emitted.image.emitted: true`. Upstream honours `with_data` on the CDP branch but silently ignores it on the screen branch — so every desktop capture returned a file path to a caller that asked for pixels, with no error. |

## Applying

```bash
cd <kit>              # e.g. ~/.heart-portal/kits/hand
git apply patches/*.patch      # or: patch -p0 < file
```

`apply_platform_patches.py` does the same thing but is anchor-checked: it fails loudly
if upstream moved the code, rather than silently shipping a half-patched kit.

## Verified

- Mini (macOS), hand 0.13.5 + P1–P4: `hand_eye_check` challenge `ZYP36E` → `pass: true`
  (pixels reached the model); `hand_see_vlm` → `mode: "direct"`, image in context.
- Windows (D5-NJ-DT-0067), hand 0.13.5 + P1–P4: `hand_see_vlm` → `mode: "direct"`,
  1920×1080 desktop image in context (`emitted.image.emitted: true`).

## Upstream status

Reported to alice (owner of `hand` on Grove). Not published as a new version by Judy —
the Grove entry is alice's asset.
