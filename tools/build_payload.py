"""Build payload.json from ArtifactData out_dir dumps: python3 tools/build_payload.py <dbdir> payload.json"""
import json, sys, glob, os
d = sys.argv[1]
def body(p):
    j = json.load(open(p))
    return j.get("data", j)
cfg = body(os.path.join(d, "config", "budget.json"))
months = {os.path.basename(p)[:-5]: body(p) for p in glob.glob(os.path.join(d, "months", "*.json"))}
json.dump({"config": cfg, "months": months}, open(sys.argv[2], "w"))
print("months:", sorted(months))
