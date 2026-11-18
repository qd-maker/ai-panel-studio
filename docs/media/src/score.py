#!/usr/bin/env python3
"""score.py — the demo film's sound, placed from the comp's own window.__events() (so a retimed beat takes its sound with it).

  python score.py [--skill <onetake dir>] [--out sfx.wav]

Synthesised only (onetake scripts/sfx_palette.py: air, glass, wood, sub, bubble, one shared room). No music, no
recorded samples, so nothing here needs a licence. Material per event kind:
  key/type   wood, quiet, one in two or three          enter/land/dropcap  sub + wood, the felt contacts
  seat       glass, one note per seat as the split lands   hop        a short air that travels with the light (panned)
  stretch    a long air breath to the right             avatar     small wood knocks       mark   the last sub, then silence
"""
import argparse, asyncio, json, os, pathlib, sys
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--skill", default=os.path.expanduser("~/.claude/skills/onetake"))
ap.add_argument("--out", default=str(HERE / "sfx.wav"))
a = ap.parse_args()
sys.path.insert(0, os.path.join(a.skill, "scripts"))
from sfx_palette import Score, air, glass, wood, sub, bubble  # noqa: E402


async def events():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 1920, "height": 1080})
        await pg.goto("file://" + str(HERE / "comp.html")); await pg.evaluate("window.__ready")
        ev = await pg.evaluate("window.__events()"); await b.close(); return ev


E = asyncio.run(events())
json.dump(E, open(HERE / "events.json", "w"), indent=0)
rng = np.random.default_rng(11)
s = Score(dur=E["T"], T60=1.3)
pan = lambda e: float(np.clip(e["pan"] * 0.6, -0.7, 0.7))
SEAT_NOTES = iter([587, 659, 784, 880])        # D5 E5 G5 A5: the split lands as one rising figure
n_type = 0
for e in E["events"]:
    t, k, v = e["t"], e["kind"], e["v"]
    if k == "key":
        if rng.uniform() < 0.45: continue
        s.place(wood(175 + rng.uniform(-25, 25), 0.08), t, 0.11 * v, pan(e), 0.15)
    elif k == "type":
        n_type += 1
        if n_type % 2: continue
        s.place(wood(260 + rng.uniform(-30, 30), 0.06), t, 0.05 * v, pan(e), 0.12)
    elif k == "enter":
        s.place(wood(240, 0.08), t, 0.30, pan(e), 0.2); s.place(wood(190, 0.07), t + 0.06, 0.2, pan(e), 0.2)
    elif k == "lift":
        s.place(air(0.42, 300, 2600, 1.3, 0.55), t - 0.05, 0.22, pan(e), 0.45, pan_to=0.0)
    elif k == "land":
        s.place(sub(64, 0.7), t, 0.34, pan(e), 0.35); s.place(glass(523, 1.0, 0.6), t + 0.01, 0.12, pan(e), 0.55)
    elif k == "seat":
        s.place(glass(next(SEAT_NOTES), 0.8, 0.7), t, 0.11, pan(e), 0.5)
    elif k == "panels":
        s.place(air(0.6, 2200, 300, 1.2, 0.3), t - 0.1, 0.14, 0.0, 0.5)
    elif k == "hop":
        s.place(air(0.34, 260, 3000, 1.5, 0.6), t - 0.02, 0.28 * v, pan(e), 0.4)
    elif k == "hopland":
        s.place(bubble(430 + 40 * v, 0.2), t, 0.20 * v, pan(e), 0.3)
        if v >= 1: s.place(sub(58, 0.8), t, 0.26, pan(e), 0.4)
    elif k == "drop":
        s.place(air(0.26, 1800, 400, 1.4, 0.3), t, 0.07, pan(e), 0.35)
    elif k == "stretch":
        s.place(air(1.1, 180, 2400, 1.1, 0.45), t, 0.34, -0.2, 0.6, pan_to=0.55)
    elif k == "tick":
        s.place(glass(1046, 0.9, 0.4), t, 0.08, pan(e), 0.6)
    elif k == "avatar":
        s.place(wood(300 + rng.uniform(-30, 30), 0.07), t, 0.13 * v, pan(e), 0.2)
    elif k == "travel":
        s.place(air(1.2, 2600, 220, 1.1, 0.4), t, 0.30, 0.5, 0.6, pan_to=-0.4)
    elif k == "dropcap":
        s.place(sub(56, 1.0), t, 0.40, pan(e), 0.45); s.place(wood(150, 0.1), t, 0.18, pan(e), 0.3)
    elif k == "rise":
        s.place(air(0.7, 240, 2200, 1.2, 0.6), t, 0.16, pan(e), 0.55, pan_to=0.0)
    elif k == "mark":
        s.place(sub(48, 1.4), t, 0.46, 0.0, 0.5); s.place(glass(392, 1.4, 0.3), t + 0.02, 0.06, 0.0, 0.7)
    elif k == "letter":
        s.place(wood(210 + rng.uniform(-20, 20), 0.06), t, 0.05, pan(e), 0.2)
s.write(a.out)
