# Path Of OCR — Path of Exile crafting monitor

This script continuously monitors your screen (Path of Exile window) and runs OCR on the captured region to detect configured desired crafting results. When a desired outcome is detected the script shows a Windows notification and plays a beep.

## Requirements
- Windows 10/11
- Python 3.8+
- Tesseract OCR installed (external binary)

## Windows-only setup (PowerShell)
1. Install Python for Windows
2. Install Tesseract for Windows and note the path to `tesseract.exe` (e.g., `C:\Program Files\Tesseract-OCR\tesseract.exe`). Add that path to `config.json` as `tesseract_cmd` if needed.
3. From PowerShell, create and activate a virtual environment and install dependencies:

```powershell
cd '<your-path>\PathofOCR'
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3 -m pip install -r requirements.txt
```

## Configuration
### Monitor region and debugging
- `monitor_region` (absolute screen coordinates) controls exactly which rectangle the monitor captures for OCR. This should be an object with `left`, `top`, `width`, and `height` keys. Example entry in `config.json`:

```json
"monitor_region": { "left": 100, "top": 200, "width": 800, "height": 120 }
```

- Use `tools/region_picker.py` on Windows to interactively select a rectangle. To write directly into `config.json` run:

```powershell
py -3 tools\region_picker.py --output config.json
```

- After selecting a region you can tune OCR speed/accuracy in `config.json`:
	- `scale`: image upscaling factor before OCR (1 = no scaling; higher may improve accuracy but is slower).
	- `poll_interval`: how often (seconds) the monitor captures the region. Lower = faster detection but higher CPU.
	- `tesseract_config`: pass custom Tesseract options (e.g., `"--psm 7 --oem 1"` for single-line OCR).

### Debug screenshots
- To help verify the area being parsed by Tesseract, enable periodic screenshots in `config.json`:

```json
"screenshot_interval": 5,
"screenshot_dir": "logs/screenshots"
```

- When enabled, the monitor saves PNG screenshots of the monitored region every `screenshot_interval` seconds and prints the saved file path to the console. Use these images to confirm the text region and fine-tune `monitor_region` or OCR settings.

## Launch

1. Start Path of Exile and open the crafting UI you want to monitor.
2. Edit `config.json` to set `window_title_substring` or set `monitor_region` with keys `left`, `top`, `width`, `height` (absolute screen coordinates), or use the `region_picker.py` tool to hand select screen region.
3. Set `desired_outcomes` to the list of strings to search for in the OCR output.
4. Run the monitor from the activated venv:

```powershell
py -3 monitor.py --config config.json
```

Notes
- If the script cannot find the Path of Exile window, provide a fixed `monitor_region` in `config.json`.
- Tweak `scale` and `poll_interval` for speed/accuracy tradeoffs.
- This tool uses simple substring matching by default; you can extend it to use regex or fuzzy matching.
