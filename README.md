# contribution-mirror

Mirrors commit timestamps from local work repos as empty commits, so they appear on your personal GitHub contribution graph.
The mirror repo must already exist locally and be connected to your personal GitHub remote.

## Usage

```bash
python main.py \
    --work-dir ~/dev/work \
    --mirror-dir ~/dev/contribution-mirror \
    --email you@company.com \
    --message "work"
```

## Options

```bash
--work-dir   Path to directory containing your work repos
--mirror-dir Path to the local mirror repo
--email      Your work git commit email
--message    Commit message for mirror commits
--dry-run    Preview commits without writing anything
--no-push    Commit locally but skip the push
```
