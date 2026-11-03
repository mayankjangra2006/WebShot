#!/usr/bin/env python3
"""
webshot.py - Bulk web screenshot tool (EyeWitness / Aquatone alternative)

Reads a list of URLs/hosts from a text file, visits each one with headless
Chromium (Playwright), saves a screenshot, and builds an HTML + CSV + JSON report.

Setup:
    pip install playwright
    playwright install chromium :- if this won't work then use above command
sudo python -m playwright install-deps chromium

Usage:
    python webshot.py -i urls.txt
    python webshot.py -i urls.txt -o results -c 10 --full-page --timeout 20
"""
print(r"""
██╗    ██╗███████╗██████╗ ███████╗██╗  ██╗ ██████╗ ████████╗
██║    ██║██╔════╝██╔══██╗██╔════╝██║  ██║██╔═══██╗╚══██╔══╝
██║ █╗ ██║█████╗  ██████╔╝███████╗███████║██║   ██║   ██║   
██║███╗██║██╔══╝  ██╔══██╗╚════██║██╔══██║██║   ██║   ██║   
╚███╔███╔╝███████╗██████╔╝███████║██║  ██║╚██████╔╝   ██║   
 ╚══╝╚══╝ ╚══════╝╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝    ╚═╝   

        Bulk Web Screenshot Tool
        Author : @Hacker_Mayank
""")


import argparse
import asyncio
import csv
import hashlib
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    from playwright.async_api import async_playwright
except ImportError:
    sys.exit("[!] Playwright not installed. Run:\n"
             "    pip install playwright\n    playwright install chromium")


# --------------------------------------------------------------------------- #
# Input handling
# --------------------------------------------------------------------------- #
def load_targets(path: Path):
    """Read targets, skip blanks/comments, de-duplicate, keep order."""
    seen, targets = set(), []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line not in seen:
            seen.add(line)
            targets.append(line)
    return targets


def candidates(target: str):
    """If no scheme is given, try https first, then fall back to http."""
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", target):
        return [target]
    return [f"https://{target}", f"http://{target}"]


def shot_name(url: str) -> str:
    p = urlparse(url)
    base = re.sub(r"[^A-Za-z0-9.-]+", "_", f"{p.scheme}_{p.netloc}{p.path}").strip("_")[:80]
    digest = hashlib.md5(url.encode()).hexdigest()[:6]
    return f"{base}_{digest}.png"


# --------------------------------------------------------------------------- #
# Capture logic
# --------------------------------------------------------------------------- #
async def capture(context, target, args, shots_dir):
    result = {"input": target, "url": None, "final_url": None, "status": None,
              "title": "", "server": "", "screenshot": None, "error": None}

    for url in candidates(target):
        page = await context.new_page()
        page.on("dialog", lambda d: asyncio.ensure_future(d.dismiss()))
        try:
            resp = await page.goto(url, wait_until="domcontentloaded",
                                   timeout=args.timeout * 1000)
            # Give JS-heavy pages a chance to settle, but don't hang on them
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            if args.delay:
                await page.wait_for_timeout(int(args.delay * 1000))

            fname = shot_name(url)
            await page.screenshot(path=str(shots_dir / fname),
                                  full_page=args.full_page, type="png")

            result.update(
                url=url,
                final_url=page.url,
                status=resp.status if resp else None,
                title=(await page.title()).strip(),
                server=(resp.headers.get("server", "") if resp else ""),
                screenshot=f"screenshots/{fname}",
                error=None,
            )
            await page.close()
            return result
        except Exception as e:
            result["url"] = url
            result["error"] = str(e).splitlines()[0][:200]
            try:
                await page.close()
            except Exception:
                pass
    return result


async def run(args):
    targets = load_targets(Path(args.input))
    if not targets:
        sys.exit("[!] No targets found in input file.")

    out_dir = Path(args.output)
    shots_dir = out_dir / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] {len(targets)} target(s) | concurrency={args.concurrency} | "
          f"timeout={args.timeout}s | output={out_dir}/")

    results, done = [], 0
    sem = asyncio.Semaphore(args.concurrency)

    async with async_playwright() as pw:
        launch_opts = {"headless": True, "args": ["--no-sandbox", "--disable-gpu"]}
        if args.proxy:
            launch_opts["proxy"] = {"server": args.proxy}
        browser = await pw.chromium.launch(**launch_opts)
        context = await browser.new_context(
            viewport={"width": args.width, "height": args.height},
            ignore_https_errors=True,
            user_agent=args.user_agent,
        )

        async def worker(t):
            nonlocal done
            async with sem:
                r = await capture(context, t, args, shots_dir)
            done += 1
            if r["error"]:
                print(f"[{done}/{len(targets)}] [FAIL] {t} -> {r['error']}")
            else:
                print(f"[{done}/{len(targets)}] [{r['status']}] {r['url']} | {r['title'][:60]}")
            return r

        results = await asyncio.gather(*(worker(t) for t in targets))
        await context.close()
        await browser.close()

    write_reports(results, out_dir)
    ok = sum(1 for r in results if not r["error"])
    print(f"\n[+] Done: {ok} captured, {len(results) - ok} failed")
    print(f"[+] Report: {(out_dir / 'report.html').resolve()}")


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def write_reports(results, out_dir: Path):
    (out_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    with open(out_dir / "results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

    cards = []
    for r in results:
        e = lambda v: html.escape(str(v or ""))
        if r["error"]:
            body = f'<div class="fail">Failed<br><small>{e(r["error"])}</small></div>'
            badge = '<span class="b err">ERR</span>'
        else:
            body = (f'<a href="{e(r["screenshot"])}" target="_blank">'
                    f'<img loading="lazy" src="{e(r["screenshot"])}"></a>')
            cls = "ok" if (r["status"] or 0) < 400 else "warn"
            badge = f'<span class="b {cls}">{e(r["status"])}</span>'
        cards.append(f"""
        <div class="card" data-s="{e((r['url'] or r['input']) + ' ' + (r['title'] or '') + ' ' + (r['server'] or '')).lower()}">
          {body}
          <div class="meta">{badge}
            <a href="{e(r['url'] or r['input'])}" target="_blank">{e(r['url'] or r['input'])}</a>
            <div class="t">{e(r['title'])}</div>
            <div class="s">{e(r['server'])}</div>
          </div>
        </div>""")

    page = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Webshot Report</title>
<style>
 body{{font-family:system-ui,sans-serif;background:#0f1115;color:#e6e6e6;margin:0;padding:20px}}
 h1{{margin:0 0 4px}} .sub{{color:#888;margin-bottom:16px}}
 input{{width:100%;max-width:420px;padding:8px 12px;border-radius:6px;border:1px solid #333;
        background:#1a1d24;color:#eee;margin-bottom:16px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px}}
 .card{{background:#1a1d24;border:1px solid #2a2e38;border-radius:8px;overflow:hidden}}
 .card img{{width:100%;height:210px;object-fit:cover;object-position:top;display:block}}
 .fail{{height:210px;display:flex;flex-direction:column;align-items:center;justify-content:center;
        color:#e66;text-align:center;padding:10px}}
 .meta{{padding:10px;font-size:13px;word-break:break-all}}
 .meta a{{color:#6cb2ff;text-decoration:none}} .t{{margin-top:4px}} .s{{color:#888;font-size:12px}}
 .b{{padding:1px 7px;border-radius:10px;font-size:11px;margin-right:6px;color:#000}}
 .ok{{background:#4caf50}} .warn{{background:#ffb300}} .err{{background:#f44336}}
</style></head><body>
<h1>Webshot Report</h1>
<div class="sub">{len(results)} targets &middot; {datetime.now():%Y-%m-%d %H:%M:%S}</div>
<input id="q" placeholder="Filter by URL, title, server...">
<div class="grid" id="g">{''.join(cards)}</div>
<script>
 document.getElementById('q').addEventListener('input', e => {{
   const v = e.target.value.toLowerCase();
   document.querySelectorAll('.card').forEach(c => c.style.display = c.dataset.s.includes(v) ? '' : 'none');
 }});
</script></body></html>"""
    (out_dir / "report.html").write_text(page, encoding="utf-8")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Bulk web screenshot tool")
    ap.add_argument("-i", "--input", required=True, help="File with URLs/hosts, one per line")
    ap.add_argument("-o", "--output", default="webshot_output", help="Output directory")
    ap.add_argument("-c", "--concurrency", type=int, default=5, help="Parallel pages (default 5)")
    ap.add_argument("-t", "--timeout", type=int, default=15, help="Page load timeout in seconds")
    ap.add_argument("-d", "--delay", type=float, default=1.0, help="Extra wait after load (sec)")
    ap.add_argument("--width", type=int, default=1366)
    ap.add_argument("--height", type=int, default=768)
    ap.add_argument("--full-page", action="store_true", help="Capture the full scrollable page")
    ap.add_argument("--proxy", help="Proxy, e.g. http://127.0.0.1:8080")
    ap.add_argument("--user-agent",
                    default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
    args = ap.parse_args()

    if not Path(args.input).is_file():
        sys.exit(f"[!] Input file not found: {args.input}")
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\n[!] Interrupted")


if __name__ == "__main__":
    main()
