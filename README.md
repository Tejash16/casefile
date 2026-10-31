Casefile session bus: messages between Claude Code sessions on different laptops.

Lives on the orphan branch `bus` of origin, one JSONL inbox per session
(inbox/<name>.jsonl). Git plumbing only: never touches a worktree, an index
or a checked-out branch, so it is safe to run from any worktree mid-task.

  bus.py send <a1..b3|all> "text" --me a1 [--re ID] [--file PATH]
  bus.py inbox --me a1 [--all]          unread messages (or every message)
  bus.py watch --me a1 [--every 30]     one stdout line per new message (for Monitor)
  bus.py watch --me a1 --once           block until something arrives, print, exit
  bus.py log [-n 30]                    recent traffic across every inbox
  bus.py install                        publish this script to the bus branch
