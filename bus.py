"""Casefile session bus: messages between Claude Code sessions on different laptops.

Lives on the orphan branch `bus` of origin, one JSONL inbox per session
(inbox/<name>.jsonl). Git plumbing only: never touches a worktree, an index
or a checked-out branch, so it is safe to run from any worktree mid-task.

  bus.py send <a1..b3|all> "text" --me a1 [--re ID] [--file PATH]
  bus.py inbox --me a1 [--all]          unread messages (or every message)
  bus.py watch --me a1 [--every 30]     one stdout line per new message (for Monitor)
  bus.py watch --me a1 --once           block until something arrives, print, exit
  bus.py log [-n 30]                    recent traffic across every inbox
  bus.py install                        publish this script to the bus branch
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

SESSIONS = ["a1", "a2", "a3", "b1", "b2", "b3"]
BRANCH = os.environ.get("CASEFILE_BUS_BRANCH", "bus")
STATE = Path.home() / ".casefile-bus"
MAX_LINE = 1500


def run(*args: str, data: bytes | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], input=data, capture_output=True, env=env)


def git(*args: str, data: bytes | None = None, env: dict | None = None) -> bytes:
    r = run(*args, data=data, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def fetch(me: str) -> str | None:
    """Fetch the bus branch into a private ref (no lock contention between worktrees)."""
    ref = f"refs/bus/{me}"
    r = run("fetch", "-q", "origin", f"+refs/heads/{BRANCH}:{ref}")
    if r.returncode == 0:
        return ref
    err = r.stderr.decode(errors="replace")
    if "couldn't find remote ref" in err:
        return None
    raise RuntimeError(f"fetch: {err.strip()}")


def read(ref: str | None, path: str) -> bytes:
    if ref is None:
        return b""
    r = run("cat-file", "-p", f"{ref}:{path}")
    return r.stdout if r.returncode == 0 else b""


def commit_and_push(ref: str | None, files: dict[str, bytes], message: str) -> bool:
    tmp = tempfile.mkdtemp(prefix="bus-")
    env = {**os.environ, "GIT_INDEX_FILE": os.path.join(tmp, "index")}
    try:
        git("read-tree", ref, env=env) if ref else git("read-tree", "--empty", env=env)
        for path, data in files.items():
            blob = git("hash-object", "-w", "--stdin", data=data).decode().strip()
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{path}", env=env)
        tree = git("write-tree", env=env).decode().strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    parent = ["-p", git("rev-parse", ref).decode().strip()] if ref else []
    commit = git("commit-tree", tree, *parent, "-m", message).decode().strip()
    return run("push", "-q", "origin", f"{commit}:refs/heads/{BRANCH}").returncode == 0


def messages(ref: str | None, name: str) -> list[dict]:
    out = []
    for line in read(ref, f"inbox/{name}.jsonl").decode("utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def seen_path(me: str) -> Path:
    return STATE / f"seen-{BRANCH}-{me}.txt"


def load_seen(me: str) -> set[str]:
    p = seen_path(me)
    return set(p.read_text(encoding="utf-8").split()) if p.exists() else set()


def mark_seen(me: str, ids: list[str]) -> None:
    if ids:
        STATE.mkdir(parents=True, exist_ok=True)
        with seen_path(me).open("a", encoding="utf-8") as f:
            f.write("".join(i + "\n" for i in ids))


def header(m: dict) -> str:
    to = " to all" if m.get("to") == "all" else ""
    re_ = f" (re #{m['re']})" if m.get("re") else ""
    return f"#{m['id']} {m['ts'][11:16]} from {m['from']}{to}{re_}"


def cmd_send(a: argparse.Namespace) -> int:
    text = Path(a.file).read_text(encoding="utf-8") if a.file else a.text
    if text == "-":
        text = sys.stdin.read()
    if not text or not text.strip():
        sys.exit("empty message")
    if a.to != "all" and a.to not in SESSIONS:
        sys.exit(f"unknown recipient {a.to!r}; use one of {', '.join(SESSIONS)} or all")
    targets = [s for s in SESSIONS if s != a.me] if a.to == "all" else [a.to]
    stamp = datetime.now().astimezone()
    msg = {
        "id": f"{a.me}-{stamp:%H%M%S}-{random.randrange(16**3):03x}",
        "ts": stamp.isoformat(timespec="seconds"),
        "from": a.me,
        "to": a.to,
        "re": a.re,
        "text": text.strip(),
    }
    line = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
    for attempt in range(8):
        ref = fetch(a.me)
        files = {}
        for t in targets:
            cur = read(ref, f"inbox/{t}.jsonl")
            files[f"inbox/{t}.jsonl"] = cur + (b"\n" if cur and not cur.endswith(b"\n") else b"") + line
        if commit_and_push(ref, files, f"{a.me} -> {a.to}: {msg['id']}"):
            print(f"sent #{msg['id']} to {a.to}")
            return 0
        time.sleep(1 + attempt + random.random())
    sys.exit("push kept failing (someone else pushing?); try again")


def cmd_inbox(a: argparse.Namespace) -> int:
    seen = load_seen(a.me)
    msgs = messages(fetch(a.me), a.me)
    shown = msgs if a.all else [m for m in msgs if m["id"] not in seen]
    if not shown:
        print("no new messages")
    for m in shown:
        print(header(m))
        print("  " + m["text"].replace("\n", "\n  "))
        print()
    mark_seen(a.me, [m["id"] for m in shown if m["id"] not in seen])
    return 0


def cmd_watch(a: argparse.Namespace) -> int:
    seen = load_seen(a.me)
    failing = False
    while True:
        try:
            msgs = messages(fetch(a.me), a.me)
            failing = False
        except Exception as e:  # network blips must not kill the watcher
            if not failing:
                print(f"[bus] fetch failed, retrying: {e}", flush=True)
            failing = True
            time.sleep(a.every)
            continue
        new = [m for m in msgs if m["id"] not in seen]
        for m in new:
            text = " / ".join(m["text"].splitlines())
            if len(text) > MAX_LINE:
                text = text[:MAX_LINE] + " ... (truncated; run `inbox --all` for the full text)"
            print(f"[bus] {header(m)}: {text}", flush=True)
            seen.add(m["id"])
        mark_seen(a.me, [m["id"] for m in new])
        if a.once and new:
            return 0
        time.sleep(a.every)


def cmd_log(a: argparse.Namespace) -> int:
    ref = fetch("log")
    by_id: dict[str, dict] = {}
    for s in SESSIONS:
        for m in messages(ref, s):
            by_id.setdefault(m["id"], m)
    for m in sorted(by_id.values(), key=lambda m: m["ts"])[-a.n :]:
        to = m["to"]
        print(f"{m['ts'][11:16]} {m['from']} -> {to} #{m['id']}{' re #' + m['re'] if m.get('re') else ''}")
        print("  " + m["text"].replace("\n", "\n  "))
    return 0


def cmd_install(a: argparse.Namespace) -> int:
    src = Path(__file__).read_bytes()
    readme = (__doc__ or "").encode("utf-8")
    for _ in range(5):
        ref = fetch("install")
        if commit_and_push(ref, {"bus.py": src, "README.md": readme}, "install bus.py"):
            print(f"installed bus.py on origin/{BRANCH}")
            return 0
        time.sleep(1)
    sys.exit("install push failed")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    me = argparse.ArgumentParser(add_help=False)
    me.add_argument("--me", default=os.environ.get("BUS_ME"), help="your session name (a1..b3)")
    p = argparse.ArgumentParser(description="Casefile session bus")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("send", parents=[me])
    s.add_argument("to")
    s.add_argument("text", nargs="?", default="", help='message text, or "-" for stdin')
    s.add_argument("--file", help="read the message text from this file")
    s.add_argument("--re", help="id of the message you are answering")
    i = sub.add_parser("inbox", parents=[me])
    i.add_argument("--all", action="store_true")
    w = sub.add_parser("watch", parents=[me])
    w.add_argument("--every", type=float, default=30)
    w.add_argument("--once", action="store_true")
    lg = sub.add_parser("log")
    lg.add_argument("-n", type=int, default=30)
    sub.add_parser("install")
    a = p.parse_args()
    if a.cmd in ("send", "inbox", "watch") and not (a.me and re.fullmatch(r"[a-z0-9-]+", a.me)):
        sys.exit("--me <your session name> is required (a1..b3)")
    return {"send": cmd_send, "inbox": cmd_inbox, "watch": cmd_watch, "log": cmd_log, "install": cmd_install}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
