"""Encrypt budget data for the phone app.
Usage: python3 tools/encrypt.py payload.json data.enc.json
payload.json = {"config": <config/budget doc>, "months": {"YYYY-MM": <months doc>, ...}}
Passphrase from env BUDGET_PASS. AES-256-GCM, key = PBKDF2-SHA256(pass, salt, 250000).
"""
import json, os, sys, base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
src, dst = sys.argv[1], sys.argv[2]
pw = os.environ["BUDGET_PASS"].encode()
data = json.dumps(json.load(open(src)), separators=(",", ":")).encode()
salt, iv = os.urandom(16), os.urandom(12)
key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=250000).derive(pw)
ct = AESGCM(key).encrypt(iv, data, None)
b = lambda x: base64.b64encode(x).decode()
json.dump({"v": 1, "iter": 250000, "salt": b(salt), "iv": b(iv), "ct": b(ct)}, open(dst, "w"))
print("wrote", dst, len(ct), "bytes")
