"""Expenses run, Part 8: update the phone app payload with this run's month doc(s) and print the Necessities block.

Usage (BUDGET_PASS in env):
  python3 tools/month_push.py NEW_DOC.json [NEW_DOC2.json ...] [--config CONFIG.json] [--base data.enc.json] [--dry-run]

- Decrypts --base (default data.enc.json), which holds LAST run's month docs and config/budget.
- Replaces months[doc.month] with each NEW_DOC (and config if --config is given), re-encrypts into data.enc.json
  unless --dry-run. Commit and push are left to the caller.
- Prints the Necessities block for the newest NEW_DOC: last run vs this run (Spent, Left, Delta), what moved the
  Delta, and the per-line spend change, computed the way index.html does (needCalc + gapPct + weightedFrac).
"""
import json, os, sys, base64, argparse, datetime as dt, calendar, subprocess
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def key(pw, salt, it):
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=it).derive(pw)


def decrypt(path, pw):
    e = json.load(open(path)); b = base64.b64decode
    return json.loads(AESGCM(key(pw, b(e["salt"]), e["iter"])).decrypt(b(e["iv"]), b(e["ct"]), None))


def wfrac(ym, day, w):
    y, m = map(int, ym.split("-")); n = calendar.monthrange(y, m)[1]
    done = alls = 0
    for i in range(1, n + 1):
        k = float(w.get(DOW[dt.date(y, m, i).weekday()], 0)) if w else 1
        alls += k; done += k if i <= day else 0
    return min(1, done / alls) if alls > 0 else min(1, day / n)


def need(doc, cfg):
    ym = doc["month"]; y, m = map(int, ym.split("-")); n = calendar.monthrange(y, m)[1]
    a = dt.date.fromisoformat(doc["asOf"]); day = a.day if (a.year, a.month) == (y, m) else n
    sp = doc.get("spend", {}); pc = cfg.get("pace", {})
    lines = []
    for l in cfg["necessities"]:
        s = sum(float(sp.get(c, 0)) for c in l["cats"]) if l.get("cats") else float(sp.get(l["cat"], 0))
        if l["mode"] == "fixed":
            e = l["budget"]
        else:
            f = wfrac(ym, day, pc.get("byDay")) if l["cat"] in pc.get("cats", []) else min(1, day / n)
            e = l["budget"] * f
        lines.append((l, s, e))
    B = sum(l["budget"] for l, _, _ in lines); S = sum(s for _, s, _ in lines)
    pace = [(l, s, e) for l, s, e in lines if l["mode"] != "fixed"]
    PE = sum(e for _, _, e in pace); PS = sum(s for _, s, _ in pace)
    delta = (B - S) if day >= n else (PE - PS)
    return {"B": B, "S": S, "left": B - S, "delta": delta, "PE": PE, "PS": PS, "day": day, "days": n, "lines": lines}


def money(x, sign=False):
    r = round(x); s = ("+" if r > 0 else "-" if r < 0 else "") if sign else ("-" if r < 0 else "")
    return f"{s}${abs(r):,}"


def block(old, new, cfg):
    o, n = need(old, cfg), need(new, cfg)
    out = []
    if old["month"] != new["month"]:
        out.append(f"{old['month']} closed with {money(o['left'])} left.")
        o = {**o, "S": 0, "left": n["B"], "delta": 0, "PE": 0, "PS": 0}
        old = {**old, "asOf": "start"}
    out += ["| | Spent | Left | Delta |", "|---|---|---|---|",
            f"| Last run ({old['asOf']}) | {money(o['S'])} | {money(o['left'])} | {money(o['delta'], True)} |",
            f"| This run ({new['asOf']}) | {money(n['S'])} | **{money(n['left'])}** | {money(n['delta'], True)} |", ""]
    dd = n["delta"] - o["delta"]
    out.append(f"Delta moved {money(dd, True)}: {money(n['PE'] - o['PE'])} of budget added since last run, "
               f"{money(n['PS'] - o['PS'], True)} of spend on the pace lines.")
    ch = []
    for (l, s1, _), (_, s0, _) in zip(n["lines"], o["lines"]):
        if round(s1 - s0):
            ch.append(f"{l['cat']} {money(s1 - s0, True)}")
    out.append(f"Net {money(n['S'] - o['S'], True)} by line: " + (", ".join(ch) or "no change"))
    over = [f"{l['cat']} ({money(s)} vs {money(l['budget'])})" for l, s, _ in n["lines"] if s > l["budget"]]
    if over:
        out.append("Over own budget: " + ", ".join(over))
    out.append(f"Left for the remaining {n['days'] - n['day']} days: {money(n['left'])}")
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("docs", nargs="+")
    ap.add_argument("--config")
    ap.add_argument("--base", default="data.enc.json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    pw = os.environ["BUDGET_PASS"].encode()
    p = decrypt(a.base, pw)
    docs = [json.load(open(f)) for f in a.docs]
    newest = max(docs, key=lambda x: x["month"])
    old = p["months"].get(newest["month"]) or p["months"][max(p["months"])]
    if a.config:
        p["config"] = json.load(open(a.config))
    for d in docs:
        p["months"][d["month"]] = d
    print(block(old, newest, p["config"]))
    if not a.dry_run:
        json.dump(p, open("/tmp/payload.json", "w"))
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "encrypt.py"), "/tmp/payload.json", "data.enc.json"], check=True)
