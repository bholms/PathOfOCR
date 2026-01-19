"""Simple full-screen click-drag region picker using tkinter.

Usage:
  python tools\list_windows.py            # prints coords to stdout
  python tools\region_picker.py --output config.json   # writes `monitor_region` into config.json

Click-drag to select a rectangle. Press Esc to cancel. After releasing mouse, coordinates
are printed as JSON: {"left":..., "top":..., "width":..., "height":...}
"""
import json
import argparse
import tkinter as tk
import sys
import os


class RegionPicker:
    def __init__(self, write_path=None):
        self.write_path = write_path
        self.root = tk.Tk()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.canvas = tk.Canvas(self.root, cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        self._bind()

    def _bind(self):
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Escape>", lambda e: self.cancel())

    def on_button_press(self, event):
        self.start_x = event.x_root
        self.start_y = event.y_root
        # create rectangle if not yet
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)

    def on_move(self, event):
        if not self.rect:
            return
        cur_x = event.x_root
        cur_y = event.y_root
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_release(self, event):
        end_x = event.x_root
        end_y = event.y_root
        left = min(self.start_x, end_x)
        top = min(self.start_y, end_y)
        width = abs(end_x - self.start_x)
        height = abs(end_y - self.start_y)
        region = {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}
        print(json.dumps(region))
        sys.stdout.flush()
        if self.write_path:
            try:
                self._write_to_config(region)
                print(f"Wrote monitor_region to {self.write_path}")
            except Exception as e:
                print(f"Failed to write config: {e}", file=sys.stderr)
        self.root.destroy()

    def _write_to_config(self, region):
        if not os.path.exists(self.write_path):
            raise FileNotFoundError(self.write_path)
        with open(self.write_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        cfg['monitor_region'] = region
        # clear window_crop to avoid confusion when monitor_region is set
        cfg.pop('window_crop', None)
        with open(self.write_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)

    def cancel(self):
        print("Canceled")
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', '-o', help='Path to config.json to write monitor_region into')
    args = parser.parse_args()
    picker = RegionPicker(write_path=args.output)
    picker.run()


if __name__ == '__main__':
    main()
