#!/usr/bin/env python3
"""
jsonl_recovery.py - Recover delta messages from .jsonl after checkpoint timestamp.

Usage:
    python3 jsonl_recovery.py recover
    python3 jsonl_recovery.py find-sessions
    python3 jsonl_recovery.py status
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CHECKPOINT_FILE = Path.home() / ".openclaw/workspace/memory/session-checkpoint.md"
MEMORY_DIR = Path.home() / ".openclaw/workspace/memory"
MAX_DELTA_BYTES = 2048
MAX_MESSAGES = 5


def find_jsonl_files() -> list[Path]:
    """Find all .jsonl session files in the memory directory."""
    return sorted(MEMORY_DIR.glob("**/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)


def get_checkpoint_timestamp() -> datetime | None:
    """Extract _last_updated timestamp from checkpoint file."""
    if not CHECKPOINT_FILE.exists():
        return None
    with open(CHECKPOINT_FILE) as f:
        for line in f:
            if "_last_updated:" in line:
                ts_str = line.split("_last_updated:")[-1].strip().rstrip("_").strip()
                try:
                    return datetime.fromisoformat(ts_str)
                except ValueError:
                    return None
    return None


def cmd_recover() -> None:
    ts = get_checkpoint_timestamp()
    if ts is None:
        print("ERROR: No _last_updated timestamp found in checkpoint.")
        sys.exit(1)

    jsonl_files = find_jsonl_files()
    if not jsonl_files:
        print("No .jsonl session files found.")
        return

    collected: list[str] = []
    total_bytes = 0

    for jf in jsonl_files:
        file_mtime = datetime.fromtimestamp(jf.stat().st_mtime, tz=timezone.utc)
        if file_mtime <= ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts:
            continue
        with open(jf) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get("role") != "assistant":
                    continue
                content = msg.get("content", "")
                if not content:
                    continue
                entry = f"**[{jf.stem}]** {content[:200]}"
                entry_bytes = len(entry.encode())
                if total_bytes + entry_bytes > MAX_DELTA_BYTES:
                    break
                collected.append(entry)
                total_bytes += entry_bytes
                if len(collected) >= MAX_MESSAGES:
                    break
        if len(collected) >= MAX_MESSAGES:
            break

    if not collected:
        print("No new delta messages found after checkpoint timestamp.")
        return

    delta_section = "\n\n### 📡 Recovered Delta\n"
    delta_section += f"_delta_since_last: {ts.isoformat()} → now_\n"
    for entry in collected:
        delta_section += f"\n{entry}\n"

    with open(CHECKPOINT_FILE, "a") as f:
        f.write(delta_section)
    print(f"Recovered {len(collected)} message(s) ({total_bytes} bytes) appended to checkpoint.")


def cmd_find_sessions() -> None:
    files = find_jsonl_files()
    if not files:
        print("No .jsonl files found.")
        return
    for f in files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime).isoformat()
        print(f"{mtime}  {f}")


def cmd_status() -> None:
    ts = get_checkpoint_timestamp()
    files = find_jsonl_files()
    print(f"checkpoint_last_updated: {ts.isoformat() if ts else 'unknown'}")
    print(f"jsonl_files_found: {len(files)}")
    if files:
        newest = datetime.fromtimestamp(files[0].stat().st_mtime).isoformat()
        print(f"newest_jsonl: {newest}  {files[0].name}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    cmd = args[0]
    if cmd == "recover":
        cmd_recover()
    elif cmd == "find-sessions":
        cmd_find_sessions()
    elif cmd == "status":
        cmd_status()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
