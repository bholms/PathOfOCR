"""List top-level windows and their rectangles (Windows only).

Run from the repo root with:
  python tools\list_windows.py
"""
import sys
try:
    import win32gui
except Exception:
    print("win32gui not available. Run this script with a Windows Python that has pywin32 installed.")
    sys.exit(1)

def enum_windows():
    results = []
    def enum(hwnd, lparam):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            results.append((hwnd, title, rect))
    win32gui.EnumWindows(enum, None)
    return results

if __name__ == '__main__':
    wins = enum_windows()
    for hwnd, title, rect in wins:
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        print(f"HWND={hwnd} | {title!r} | left={left} top={top} width={width} height={height}")
