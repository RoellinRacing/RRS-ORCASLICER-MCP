"""Version-sensitive native GUI controls with semantic locators, never caller coordinates."""

import io
import csv
import os
import math
import re
import subprocess
import sys
import time
from pathlib import Path

from .desktop import Desktop
from .storage import atomic_bytes, atomic_json


def tokens(text):
    return re.findall(r"[\w]+", text.casefold())


class NativeControls:
    def __init__(self, desktop: Desktop, evidence: Path):
        self.desktop, self.evidence = desktop, evidence
        self.main_bounds = None

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

    def words(self, region=None):

        api = self.desktop._api()
        left, top, right, bottom = self.bounds()
        image = api.screenshot()
        left, top = max(left, 0), max(top, 0)
        right, bottom = min(right, image.width), min(bottom, image.height)
        if region is None and self.main_bounds == (left, top, right, bottom):
            region = (left + (right - left) * 0.36, top + 110, right, bottom)
        if region:
            left, top = max(left, int(region[0])), max(top, int(region[1]))
            right, bottom = min(right, int(region[2])), min(bottom, int(region[3]))
        crop = image.crop((left, top, right, bottom)).convert("RGB")
        stream = io.BytesIO()
        crop.resize((crop.width * 2, crop.height * 2)).save(stream, format="PNG")
        # Bound OCR wall time and use a per-child OpenMP setting. Full-screen
        # Tesseract can otherwise spend minutes on a dense GL/UI composition.
        try:
            response = subprocess.run(
                ["tesseract", "stdin", "stdout", "--psm", "11", "tsv"],
                input=stream.getvalue(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "OMP_THREAD_LIMIT": "1"},
                timeout=12,
                check=True,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            raise ValueError(
                "Native OCR did not complete; check system Tesseract and visible controls"
            ) from None
        rows = csv.DictReader(io.StringIO(response.stdout.decode("utf-8")), delimiter="\t")
        result = []
        for row in rows:
            text = row.get("text", "")
            if tokens(text):
                result.append(
                    {
                        "text": text,
                        "tokens": tokens(text),
                        "x": left + int(row["left"]) / 2,
                        "y": top + int(row["top"]) / 2,
                        "w": int(row["width"]) / 2,
                        "h": int(row["height"]) / 2,
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
        return self.locate(self.words(region), phrase, region)

    def point_click(self, box):
        api = self.desktop._api()
        # wx forwards a click according to the previous ImGui hover/capture
        # frame. Let the GL canvas observe the pointer before pressing a button.
        api.moveTo(box["x"] + box["w"] / 2, box["y"] + box["h"] / 2, duration=0.15)
        time.sleep(0.6)
        # Hold across a render frame. An instantaneous down/up can be lost by
        # ImGui on a software-rendered desktop even after the pointer is over it.
        self.desktop._api().mouseDown()
        time.sleep(0.2)
        self.desktop._api().mouseUp()
        time.sleep(0.4)

    def click(self, phrase, region=None):
        self.point_click(self.label(phrase, region))

    def window_title(self):
        if sys.platform != "linux":
            raise ValueError("Native dialog title fallback currently requires Linux X11")
        return subprocess.check_output(
            ["xdotool", "getactivewindow", "getwindowname"], text=True
        ).strip()

    def dialog_button(self, phrase, expected_title):
        title = self.window_title()
        if title != expected_title or self.bounds() == self.main_bounds:
            raise ValueError(
                f"Expected native dialog {expected_title!r} is not active; observed {title!r}"
            )
        try:
            self.click(phrase)
            return
        except ValueError:
            pass
        # Sparse OCR omits short white labels on Orca's teal primary buttons.
        # Identify button rectangles only inside this verified dialog's footer,
        # then read each inset as black text on white. Never click color alone.
        from PIL import ImageOps

        left, top, right, bottom = self.bounds()
        top = max(top, bottom - 75)
        picture = self.desktop._api().screenshot().crop((left, top, right, bottom)).convert("RGB")
        pixels = picture.load()
        colored = {}
        for x in range(picture.width):
            ys = [
                y
                for y in range(picture.height)
                if pixels[x, y][0] <= 50
                and 100 <= pixels[x, y][1] <= 190
                and 80 <= pixels[x, y][2] <= 180
            ]
            if ys:
                colored[x] = ys
        groups = []
        for x in sorted(colored):
            if not groups or x > groups[-1][-1] + 1:
                groups.append([])
            groups[-1].append(x)
        matches = []
        for group in groups:
            x0, x1 = group[0], group[-1] + 1
            ys = [y for x in group for y in colored[x]]
            y0, y1 = min(ys), max(ys) + 1
            if x1 - x0 < 50 or y1 - y0 < 20 or len(ys) < (x1 - x0) * (y1 - y0) * 0.45:
                continue
            inset = picture.crop((x0 + 5, y0 + 4, x1 - 5, y1 - 4)).convert("L")
            inset = ImageOps.expand(
                inset.point(lambda v: 0 if v > 220 else 255), border=8, fill=255
            )
            stream = io.BytesIO()
            inset.resize((inset.width * 3, inset.height * 3)).save(stream, format="PNG")
            response = subprocess.run(
                ["tesseract", "stdin", "stdout", "--psm", "7"],
                input=stream.getvalue(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=12,
                check=True,
                env={**os.environ, "OMP_THREAD_LIMIT": "1"},
            )
            if tokens(response.stdout.decode("utf-8")) == tokens(phrase):
                matches.append({"x": left + x0, "y": top + y0, "w": x1 - x0, "h": y1 - y0})
        if len(matches) != 1:
            raise ValueError(f"Native dialog button {phrase!r} missing or ambiguous")
        self.point_click(matches[0])

    def replace_emboss_text(self, value):
        # The part notification repeats the default text. Anchor the editable
        # text area above the gizmo's Style row instead of matching that name
        # anywhere in the viewport.
        style = self.label("Style")
        _, top, right, _ = self.bounds()
        editor_region = (style["x"] - 5, top + 110, right, style["y"] - 5)
        # Orca retains the previous text when opening another emboss gizmo.
        # Any glyph in this identified text area is a focus target; its content
        # is not a fixed label and need not equal the factory default.
        words = self.words(editor_region)
        if not words:
            raise ValueError("Native emboss text area could not be identified")
        self.point_click(min(words, key=lambda w: (w["y"], w["x"])))
        self.key("command" if sys.platform == "darwin" else "ctrl", "a")
        self.paste(value)

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

    def read_numeric(self, label, region=None, index=0, columns=None, required_unit=None):
        words = self.words(region)
        rows = []
        for anchor in self.locate(words, label, region, all_matches=True):
            mid = anchor["y"] + anchor["h"] / 2
            numbers = sorted(
                [
                    w
                    for w in words
                    if w["x"] > anchor["x"] + anchor["w"] + 5
                    and abs(w["y"] + w["h"] / 2 - mid) <= 10
                    and re.fullmatch(
                        r"[-+]?\d+(?:[.,]\d+)?(?:%|mm|°C?|℃|Hz|mm/s|mm[³3]/s)?",
                        w["text"],
                        re.IGNORECASE,
                    )
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
        observed = float(re.match(r"[-+]?\d+(?:[.,]\d+)?", box["text"])[0].replace(",", "."))
        return box, observed

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
        verify=False,
    ):
        box, old = self.read_numeric(label, region, index, columns, required_unit)
        # Native gizmos fit their width on the next GL frame. Hover can trigger
        # that frame, so re-locate after hover rather than clicking stale boxes.
        for _ in range(3):
            self.desktop._api().moveTo(
                box["x"] + box["w"] / 2, box["y"] + box["h"] / 2, duration=0.15
            )
            time.sleep(0.4)
            settled, current = self.read_numeric(label, region, index, columns, required_unit)
            if not math.isclose(current, old, abs_tol=1e-9):
                raise ValueError("Native field changed while acquiring its editor")
            stable = abs(settled["x"] - box["x"]) < 2 and abs(settled["y"] - box["y"]) < 2
            box = settled
            if stable:
                break
        else:
            raise ValueError("Native numeric editor layout did not settle")
        target = old + delta if delta is not None else value
        if type(target) not in (int, float) or not math.isfinite(target):
            raise ValueError("Native numeric value must be finite")
        self.point_click(box)
        evidence_name = re.sub(r"\W+", "_", label).strip("_") + f"_{index}"
        self.capture("numeric_" + evidence_name + "_focused")
        atomic_json(
            self.evidence / ("numeric_" + evidence_name + ".json"),
            {
                "box": box,
                "cursor": list(self.desktop._api().position()),
                "before": old,
                "target": target,
            },
        )
        self.key("command" if sys.platform == "darwin" else "ctrl", "a")
        # Numeric fields accept ASCII directly; this avoids clipboard ownership
        # races between X11/wx and the native ImGui canvas.
        self.desktop._api().write(format(target, ".10g"), interval=0.05)
        self.key(commit)
        time.sleep(0.3)
        self.capture("numeric_" + evidence_name + "_committed")
        result = {"before": old, "requested": target}
        if verify:
            _, observed = self.read_numeric(label, region, index, columns, required_unit)
            if not math.isclose(observed, target, rel_tol=1e-5, abs_tol=1e-5):
                raise ValueError(f"Native field {label!r} did not retain the requested value")
            result["observed"] = observed
        return result

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
        self.label("Prepare", (left, top, right, top + 110))
        self.label("Project", (left, top, right, top + 110))
        self.main_bounds = self.bounds()
        return left, top, right

    def park_bridge(self):
        api = self.desktop._api()
        _, screen_height = api.size()
        if sys.platform == "win32":
            import pygetwindow

            windows = [
                w
                for w in pygetwindow.getWindowsWithTitle("RRS MCP Bridge")
                if w.title == "RRS MCP Bridge"
            ]
            if len(windows) != 1:
                raise ValueError("Expected one modeless RRS MCP Bridge window")
            windows[0].resizeTo(350, 180)
            windows[0].moveTo(0, screen_height - 200)
        elif sys.platform == "darwin":
            raise ValueError("Native window parking on macOS needs separate acceptance")
        else:
            pid = subprocess.check_output(
                ["xdotool", "getactivewindow", "getwindowpid"], text=True
            ).strip()
            windows = subprocess.check_output(
                [
                    "xdotool",
                    "search",
                    "--all",
                    "--onlyvisible",
                    "--pid",
                    pid,
                    "--name",
                    "^RRS MCP Bridge$",
                ],
                text=True,
            ).splitlines()
            if len(windows) != 1:
                raise ValueError("Expected one modeless RRS MCP Bridge window in this Orca process")
            subprocess.run(["xdotool", "windowsize", windows[0], "350", "180"], check=True)
            subprocess.run(
                ["xdotool", "windowmove", windows[0], "0", str(screen_height - 200)], check=True
            )
        time.sleep(0.3)
        return {"title": "RRS MCP Bridge", "placement": "compact_bottom_left", "kept_running": True}

    def canvas(self):
        left, top, right = self.main()
        self.click("Prepare", (left, top + 25, right, top + 110))
        # Leave a native gizmo after any active numeric editor has lost focus.
        # Its XYZ fields occupy the top-right viewport; that is not a canvas
        # focus target. Use the supported empty lower-left viewport corridor.
        self.key("escape")
        _, _, _, bottom = self.bounds()
        self.point_click({"x": left + (right - left) * 0.48, "y": bottom - 180, "w": 0, "h": 0})
