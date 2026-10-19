"""Rebuild the add-only archive from the repository's historical news.json revisions."""
import json
import subprocess
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
def normalize(url):
    p = urlsplit(str(url).strip())
    if p.scheme.lower() not in ("http", "https") or not p.netloc or p.username or p.password:
        return ""
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if not k.lower().startswith(("utm_", "fbclid", "gclid", "mc_cid", "mc_eid"))]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/") or "/", urlencode(q), ""))

def merge_archiv(existing, additions, stand):
    result, seen = [], set()
    for item in list(existing.get("meldungen", [])) + list(additions or []):
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k].strip()
                for k in ("titel", "zusammenfassung", "quelle", "url", "datum")):
            continue
        try:
            datetime.strptime(item["datum"], "%Y-%m-%d")
        except ValueError:
            continue
        key = normalize(item["url"])
        if not key or key in seen:
            continue
        item = dict(item); item["url"] = key
        item.setdefault("erstmals_angezeigt", item["datum"])
        seen.add(key); result.append(item)
    result.sort(key=lambda x: x.get("datum", ""), reverse=True)
    return {"stand": stand, "meldungen": result}

def main():
    commits = subprocess.check_output(
        ["git", "log", "HEAD", "--format=%H", "--", "news.json"], cwd=ROOT, text=True,
        encoding="utf-8", errors="strict"
    ).splitlines()
    data = {"meldungen": []}
    for commit in reversed(commits):
        try:
            raw = subprocess.check_output(["git", "show", f"{commit}:news.json"], cwd=ROOT,
                                          text=True, encoding="utf-8", errors="strict")
            obj = json.loads(raw)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        data = merge_archiv(data, obj.get("meldungen", []), obj.get("stand") or "1970-01-01")
    data["stand"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (ROOT / "news-archiv.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(data['meldungen'])} historische Meldungen archiviert")

if __name__ == "__main__":
    main()
