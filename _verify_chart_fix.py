"""Quick verification script for Chart.js race-condition fix."""
from pathlib import Path

t = (Path(__file__).resolve().parent / "templates" / "profile.html").read_text(encoding="utf-8")

checks = [
    ("window._chartJsReady = new Promise" in t, "Promise loader exists"),
    ("s.addEventListener('load'" in t, "Primary CDN resolves on load"),
    ("fb.addEventListener('load'" in t, "Fallback CDN resolves on load"),
    ("fb.addEventListener('error'" in t, "Fallback CDN rejects on error"),
    ("s.remove()" in t, "Failed primary script removed"),
    ("function initCharts()" in t, "initCharts function exists"),
    ("window._chartJsReady.then(initCharts)" in t, "Charts gated behind Promise"),
    ("window._chartJsReady.then(initCharts).catch" in t, "Graceful catch handler"),
    ("typeof Chart !== 'undefined'" not in t, "No old typeof Chart guard"),
    ("document.head.appendChild(chartScript)" not in t, "No old fire-and-forget append"),
    ("})();" not in t.split("// ── Chart")[0] if "// ── Chart" in t else True, "No IIFE invocation in chart section"),
]

all_pass = True
for result, desc in checks:
    status = "PASS" if result else "FAIL"
    if not result:
        all_pass = False
    print(f"  {status}: {desc}")

print("\nALL PASSED" if all_pass else "\nSOME CHECKS FAILED")
