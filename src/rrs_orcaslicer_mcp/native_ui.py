"""Version-sensitive native GUI controls with semantic locators, never caller coordinates."""

import io
import math
import re
import subprocess
import sys
import time
from pathlib import Path

from .desktop import Desktop
from .storage import atomic_bytes


def tokens(text):
    return re.findall(r"[\w]+", text.casefold())


class NativeControls:
    def __init__(self, desktop: Desktop, evidence: Path):
        self.desktop, self.evidence = desktop, evidence

    def bounds(self):
        # Also checks the owning process, including native Orca dialogs.
        self.desktop._api()
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            rectangle = wintypes.RECT()
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rectangle))
            return rectangle.left, rectangle.top, rectangle.right, rectangle.bottom
        if sys.platform == "darwin":
            raw = subprocess.check_output(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to tell first application process whose frontmost is true to get {position, size} of front window',
                ],
                text=True,
            )
            x, y, width, height = [int(x) for x in re.findall(r"-?\d+", raw)]
            return x, y, x + width, y + height
        raw = subprocess.check_output(
            ["xdotool", "getactivewindow", "getwindowgeometry", "--shell"], text=True
        )
        data = dict(s.split("=", 1) for s in raw.splitlines() if "=" in s)
        x, y, width, height = [int(data[k]) for k in ("X", "Y", "WIDTH", "HEIGHT")]
        return x, y, x + width, y + height

    def words(self):
        import pytesseract

        api = self.desktop._api()
        left, top, right, bottom = self.bounds()
        image = api.screenshot()
        left, top = max(left, 0), max(top, 0)
        right, bottom = min(right, image.width), min(bottom, image.height)
        crop = image.crop((left, top, right, bottom)).convert("RGB")
        data = pytesseract.image_to_data(
            crop.resize((crop.width * 2, crop.height * 2)),
            config="--psm 11",
            output_type=pytesseract.Output.DICT,
        )
        result = []
        for n, text in enumerate(data["text"]):
            if tokens(text):
                result.append(
                    {
                        "text": text,
                        "tokens": tokens(text),
                        "x": left + data["left"][n] / 2,
                        "y": top + data["top"][n] / 2,
                        "w": data["width"][n] / 2,
                        "h": data["height"][n] / 2,
                    }
                )
        return result

    @staticmethod
    def locate(words, phrase, region=None, all_matches=False):
        desired = tokens(phrase)
        candidates = []
        for first in words:
            if region and not (
                region[0] <= first["x"] <= region[2] and region[1] <= first["y"] <= region[3]
            ):
                continue
            row = sorted(
                (
                    w
                    for w in words
                    if abs((w["y"] + w["h"] / 2) - (first["y"] + first["h"] / 2)) <= 8
                ),
                key=lambda w: w["x"],
            )
            start = row.index(first)
            found, chosen = [], []
            for item in row[start:]:
                found.extend(item["tokens"])
                chosen.append(item)
                if found == desired:
                    candidates.append(
                        {
                            "x": first["x"],
                            "y": min(w["y"] for w in chosen),
                            "w": chosen[-1]["x"] + chosen[-1]["w"] - first["x"],
                            "h": max(w["h"] for w in chosen),
                        }
                    )
                    break
                if desired[: len(found)] != found:
                    break
        if all_matches:
            return candidates
        if len(candidates) != 1:
            raise ValueError(
                f"Native control {phrase!r} missing or ambiguous ({len(candidates)} matches)"
            )
        return candidates[0]

    def label(self, phrase, region=None):
        return self.locate(self.words(), phrase, region)

    def click(self, phrase, region=None):
        box = self.label(phrase, region)
        self.desktop._api().click(box["x"] + box["w"] / 2, box["y"] + box["h"] / 2)
        time.sleep(0.3)

    def key(self, *keys):
        self.desktop._api().hotkey(*keys)
        time.sleep(0.2)

    def paste(self, value):
        api = self.desktop._api()
        import pyperclip

        previous = pyperclip.paste()
        try:
            pyperclip.copy(str(value))
            api.hotkey("command" if sys.platform == "darwin" else "ctrl", "v")
            time.sleep(0.15)
        finally:
            pyperclip.copy(previous)

    def numeric(
        self,
        label,
        value=None,
        delta=None,
        region=None,
        index=0,
        columns=None,
        commit="tab",
        required_unit=None,
    ):
        words = self.words()
        rows = []
        for anchor in self.locate(words, label, region, all_matches=True):
            mid = anchor["y"] + anchor["h"] / 2
            numbers = sorted(
                [
                    w
                    for w in words
                    if w["x"] > anchor["x"] + anchor["w"] + 5
                    and abs(w["y"] + w["h"] / 2 - mid) <= 10
                    and re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?(?:%|mm|°)?", w["text"])
                ],
                key=lambda w: w["x"],
            )
            if required_unit and not any(
                w["text"] == required_unit and abs(w["y"] + w["h"] / 2 - mid) <= 10 for w in words
            ):
                continue
            if len(numbers) > index and (columns is None or len(numbers) == columns):
                rows.append(numbers)
        if len(rows) != 1:
            raise ValueError(f"Numeric row next to {label!r} missing or ambiguous")
        box = rows[0][index]
        old = float(re.sub(r"[^0-9.,+-]", "", box["text"]).replace(",", "."))
        target = old + delta if delta is not None else value
        if type(target) not in (int, float) or not math.isfinite(target):
            raise ValueError("Native numeric value must be finite")
        self.desktop._api().click(box["x"] + box["w"] / 2, box["y"] + box["h"] / 2)
        self.key("command" if sys.platform == "darwin" else "ctrl", "a")
        self.paste(format(target, ".10g"))
        self.key(commit)
        time.sleep(0.3)
        return {"before": old, "requested": target}

    def capture(self, phase):
        self.evidence.mkdir(parents=True, exist_ok=True)
        image = self.desktop._api().screenshot()
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        destination = self.evidence / (phase + ".png")
        atomic_bytes(destination, stream.getvalue())
        return str(destination)

    def main(self):
        left, top, right, _ = self.bounds()
        # Dialogs/bridge panels do not satisfy the native MainFrame toolbar check.
        self.label("Slice plate", (left, top, right, top + 110))
        return left, top, right

    def canvas(self):
        left, top, right = self.main()
        self.click("Prepare", (left, top + 25, right, top + 110))
        # The supported Prepare layout places the viewport below the right toolbar.
        # Focus it before shortcuts so Ctrl+A/Z cannot target a settings text box.
        self.desktop._api().click(right - 100, top + 160)
        time.sleep(0.2)
