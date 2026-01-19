import time
import json
import os
import sys
import logging
import argparse
import shutil
import subprocess
import datetime

try:
    import mss
    from PIL import Image, ImageOps, ImageFilter
    import pytesseract
    import numpy as np
except Exception:
    print("Missing Python dependencies. Please run: python -m pip install -r requirements.txt")
    raise

try:
    import win32gui
except Exception:
    win32gui = None

try:
    from win10toast import ToastNotifier
    toaster = ToastNotifier()
except Exception:
    toaster = None

import ctypes
try:
    import winsound
except Exception:
    winsound = None

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")


def load_config(path="config.json"):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_python_version():
    if sys.version_info < (3, 6):
        raise RuntimeError("Python 3.6+ is required. You're running: %s" % sys.version)


def check_tesseract(cfg):
    cmd = cfg.get("tesseract_cmd")
    if cmd:
        if not os.path.exists(cmd):
            logging.warning("Configured tesseract_cmd does not exist: %s", cmd)
        else:
            logging.info("Using tesseract binary: %s", cmd)
            pytesseract.pytesseract.tesseract_cmd = cmd
            return True

    # Try discovering tesseract on PATH
    found = shutil.which("tesseract")
    if found:
        logging.info("Found tesseract on PATH: %s", found)
        pytesseract.pytesseract.tesseract_cmd = found
        return True

    # Try running `tesseract -v` to be sure
    try:
        out = subprocess.run([cmd or "tesseract", "-v"], capture_output=True, text=True)
        if out.returncode == 0 or out.stderr:
            logging.info("Tesseract appears available")
            return True
    except Exception:
        pass

    logging.warning("Tesseract binary not found. OCR will likely fail until Tesseract is installed or `tesseract_cmd` is set in config.json.")
    return False


def find_window_rect(title_substring: str):
    if not win32gui:
        return None

    found = []

    def enum(hwnd, lparam):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and title_substring.lower() in title.lower():
                rect = win32gui.GetWindowRect(hwnd)
                found.append(rect)

    win32gui.EnumWindows(enum, None)
    if found:
        left, top, right, bottom = found[0]
        return {"left": left, "top": top, "width": right - left, "height": bottom - top}
    return None


def capture_region(region):
    with mss.mss() as sct:
        shot = sct.grab(region)
        # `shot.rgb` contains RGB bytes; create an RGB image directly
        img = Image.frombytes("RGB", shot.size, shot.rgb)
        return img


def preprocess_for_ocr(img: Image.Image, scale=2):
    gray = ImageOps.grayscale(img)
    w, h = gray.size
    gray = gray.resize((w * scale, h * scale), Image.LANCZOS)
    gray = gray.filter(ImageFilter.SHARPEN)
    return gray


def ocr_image(img: Image.Image, ocr_lang="eng", tesseract_cmd=None, tesseract_config='--psm 6'):
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    try:
        text = pytesseract.image_to_string(img, lang=ocr_lang, config=tesseract_config)
    except Exception:
        logging.exception("Tesseract OCR failed")
        text = ""
    return text
    

def notify(title, message):
    # Avoid win10toast threaded callbacks (can trigger WNDPROC conversion errors).
    try:
        if os.name == 'nt':
            try:
                ctypes.windll.user32.MessageBoxW(0, message, title, 0x1000)
            except Exception as e:
                logging.exception("MessageBox failed: %s", e)
                # fallback to toast if MessageBox fails
                if toaster:
                    try:
                        toaster.show_toast(title, message, duration=6, threaded=False)
                    except Exception:
                        logging.exception("Toast fallback failed")
        else:
            logging.info("Notification: %s - %s", title, message)
    except Exception:
        logging.exception("Notification failed")

    try:
        if winsound:
            winsound.Beep(750, 400)
    except Exception:
        logging.exception("Beep failed")


def matches_desired(text: str, desired_list):
    """Return a list of desired items that were found in the OCR text.

    Returns an empty list if no items matched.
    """
    if not text:
        return []
    t = text.lower()
    matches = []
    for item in desired_list:
        if item and item.lower() in t:
            matches.append(item)
    return matches


def main(config_path, debug=False):
    cfg = load_config(config_path)
    window_title = cfg.get("window_title_substring", "Path of Exile")
    region_cfg = cfg.get("monitor_region")
    desired = cfg.get("desired_outcomes", [])
    poll = float(cfg.get("poll_interval", 0.8))
    ocr_lang = cfg.get("ocr_lang", "eng")
    tesseract_cmd = cfg.get("tesseract_cmd")
    scale = int(cfg.get("scale", 2))
    cooldown = float(cfg.get("alert_cooldown", 1.0))

    last_alert = 0
    last_screenshot = 0

    # Screenshot debug settings
    screenshot_interval = float(cfg.get("screenshot_interval", 0))
    screenshot_dir = cfg.get("screenshot_dir", "logs/screenshots")

    if screenshot_interval and not os.path.exists(screenshot_dir):
        try:
            os.makedirs(screenshot_dir, exist_ok=True)
        except Exception:
            logging.exception("Failed to create screenshot directory: %s", screenshot_dir)

    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.info("Debug mode enabled - OCR text will be logged each poll")

    logging.info("Starting monitor for window containing: %s", window_title)
    logging.info("Desired outcomes: %s", desired)

    while True:
        region = None
        if region_cfg:
            region = region_cfg
        else:
            region = find_window_rect(window_title)

        if not region:
            logging.warning("Could not find window or region. Make sure the game is running or set a fixed region in config.json.")
            time.sleep(3.0)
            continue

        try:
            img = capture_region(region)
        except Exception as e:
            logging.exception("Capture failed: %s", e)
            time.sleep(1.0)
            continue

        # Save periodic screenshots for debugging region selection
        now = time.time()
        if screenshot_interval and (now - last_screenshot) >= screenshot_interval:
            try:
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                left = region.get("left", 0)
                top = region.get("top", 0)
                w = region.get("width", 0)
                h = region.get("height", 0)
                fname = f"screenshot_{ts}_L{left}_T{top}_W{w}_H{h}.png"
                path = os.path.join(screenshot_dir, fname)
                img.save(path)
                logging.info("Saved screenshot: %s", path)
                # Also print and append to an index file for easy discovery
                try:
                    print(path)
                    sys.stdout.flush()
                    index_file = os.path.join(screenshot_dir, "saved_files.txt")
                    with open(index_file, "a", encoding="utf-8") as idx:
                        idx.write(path + "\n")
                except Exception:
                    logging.exception("Failed to write screenshot index")
            except Exception:
                logging.exception("Failed to save screenshot")
            last_screenshot = now

        proc = preprocess_for_ocr(img, scale=scale)
        tesseract_cfg = cfg.get("tesseract_config", f"--psm 6")
        text = ocr_image(proc, ocr_lang=ocr_lang, tesseract_cmd=tesseract_cmd, tesseract_config=tesseract_cfg)

        if debug:
            logging.debug("OCR output:\n%s", text)

        matched = matches_desired(text, desired)
        if matched:
            now = time.time()
            if now - last_alert > cooldown:
                logging.info("Desired outcome detected: %s", ", ".join(matched))
                notify("PathOfOCR: Desired Craft", f"Detected: {', '.join(matched)}")
                last_alert = now
            else:
                logging.debug("Match found but still in cooldown: %s", ", ".join(matched))
        else:
            logging.debug("No desired text found")

        time.sleep(poll)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Path of Exile crafting OCR monitor")
    parser.add_argument("--config", "-c", default="config.json", help="Path to config.json")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode (log full OCR text each poll)")
    args = parser.parse_args()
    try:
        main(args.config, debug=args.debug)
    except KeyboardInterrupt:
        logging.info("Stopping monitor")
        sys.exit(0)
