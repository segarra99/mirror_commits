import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path


# ── DB ────────────────────────────────────────────────────────────────────────

def open_db(mirror_dir: Path) -> sqlite3.Connection:
    db = sqlite3.connect(mirror_dir / ".mirrored.db")
    db.execute("CREATE TABLE IF NOT EXISTS seen (hash TEXT PRIMARY KEY)")
    db.commit()
    return db


def is_seen(db: sqlite3.Connection, hash: str) -> bool:
    return db.execute("SELECT 1 FROM seen WHERE hash=?", (hash,)).fetchone() is not None


def mark_seen(db: sqlite3.Connection, hash: str):
    db.execute("INSERT OR IGNORE INTO seen VALUES (?)", (hash,))
    db.commit()


# ── GIT HELPERS ───────────────────────────────────────────────────────────────

def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> str:
    result = subprocess.run(
        cmd, cwd=cwd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def find_repos(root: Path) -> list[Path]:
    """Return all git repo roots under `root`."""
    return [p.parent for p in root.rglob(".git/HEAD")]


def get_commits(repo: Path, email: str) -> list[tuple[str, str]]:
    """Return list of (hash, iso-timestamp) for commits by email in repo."""
    try:
        out = run(
            ["git", "log", f"--author={email}", "--format=%H|%aI", "--no-merges"],
            cwd=repo
        )
    except RuntimeError:
        return []
    results = []
    for line in out.splitlines():
        if "|" in line:
            h, ts = line.split("|", 1)
            results.append((h.strip(), ts.strip()))
    return results


def empty_commit(mirror_dir: Path, timestamp: str, message: str):
    """Create a backdated empty commit in the mirror repo."""
    env = {
        **__import__("os").environ,
        "GIT_AUTHOR_DATE": timestamp,
        "GIT_COMMITTER_DATE": timestamp,
    }
    run(
        ["git", "commit", "--allow-empty", "--message", "{message}", "--quiet"],
        cwd=mirror_dir, env=env
    )


def push(mirror_dir: Path):
    run(["git", "push", "origin", "HEAD"], cwd=mirror_dir)


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Mirror work commits to personal GitHub graph.")
    parser.add_argument("--work-dir",   required=True,  type=Path, help="Root dir of your work repos")
    parser.add_argument("--mirror-dir", required=True,  type=Path, help="Local clone of your personal mirror repo")
    parser.add_argument("--email",      required=True,  type=str,  help="Your work git commit email")
    parser.add_argument("--message",    required=True,  type=str,  help="Mirror commit message")
    parser.add_argument("--dry-run",    action="store_true",       help="Scan only, do not commit or push")
    parser.add_argument("--no-push",    action="store_true",       help="Commit locally but do not push")
    args = parser.parse_args()

    work_dir   = args.work_dir.expanduser().resolve()
    mirror_dir = args.mirror_dir.expanduser().resolve()
    email = args.email
    message = args.message

    if not work_dir.is_dir():
        sys.exit(f"[✗] Work directory not found: {work_dir}")
    if not mirror_dir.is_dir():
        sys.exit(f"[✗] Mirror repo not found: {mirror_dir}")

    db = open_db(mirror_dir)

    # Collect all new commits across all repos
    print(f"[→] Scanning repos under {work_dir} for {email} ...")
    new_commits: list[tuple[str, str]] = []  # (timestamp, hash)

    for repo in find_repos(work_dir):
        commits = get_commits(repo, email)
        for hash, timestamp in commits:
            if not is_seen(db, hash):
                new_commits.append((timestamp, hash))
        if commits:
            print(f"    {repo.name}: {len(commits)} commit(s) found")

    if not new_commits:
        print("[✓] No new commits to mirror.")
        return

    # Sort chronologically so the graph fills in order
    new_commits.sort()
    print(f"[→] {len(new_commits)} new commit(s) to mirror.")

    if args.dry_run:
        print("[i] Dry run — nothing written.")
        for ts, h in new_commits:
            print(f"    {ts}  {h}")
        return

    # Create empty commits
    for i, (timestamp, hash) in enumerate(new_commits, 1):
        print(f"    [{i}/{len(new_commits)}] {timestamp}", end="\r")
        empty_commit(mirror_dir, timestamp, message)
        mark_seen(db, hash)

    print(f"\n[✓] Mirrored {len(new_commits)} commit(s).")

    if not args.no_push:
        print("[→] Pushing to personal GitHub...")
        push(mirror_dir)
        print("[✓] Done! Your contribution graph will update shortly.")
    else:
        print("[i] Skipped push (--no-push).")


if __name__ == "__main__":
    main()
