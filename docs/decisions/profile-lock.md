# One Run at a Time Holds a Browser Profile

Date: 2026-10-16

## Problem

`open_in_editor.py` drives the machine's browser on a profile kept between
runs, `.tmp/editor-<browser>` of the project. A warm profile opens the
editor in seconds, a cold one in tens of seconds. Every script that drives
the browser does so through the same `Browser` class. A second browser
process started on a profile hands its request to the first and exits, so
a run that finds a browser on the profile takes it over through the
`DevToolsActivePort` file. That is how a stopped run's browser is reused.

The takeover does not tell a dead run's browser from a live run's. The user
runs several agent sessions in worktrees of one game at once, so two runs
on one profile are an ordinary event: one session previews while another
plays a plan. The second run takes the first run's browser over. The first
run's close then ends that browser under the second. `Browser.__init__`
also deletes every staged `project-*.c3p` on the profile, the other run's
among them.

## Evidence

Two `open_in_editor.py` processes, started 0.5 seconds apart on one
project, Edge headless on Windows, the profile warm. Without the lock, the
first run prints `opened` and exits 0. The second fails with
`Target.closeTarget: No target with given id found`, then prints "the
editor did not load for any project. Check the network connection and
--release" and exits 2. That is the exit code and the advice of a real
network failure, so an agent reading it retries or asks the user about the
connection. With the lock, the first run prints `opened` and exits 0 as
before, and the second prints one line and exits 5:

```
another run holds the browser profile <project>/.tmp/editor-msedge (pid 48532, open_in_editor.py,
since 2026-10-16 03:28:02): wait for it to end, or pass --profile FOLDER to run on a profile of this run's own
```

The second run is refused before it starts or takes over anything. Two
projects opened in one run with `--jobs 2` share its one lock and both
open.

## Options

- A lock on the profile for the life of the run, taken without waiting, so
  that the second run fails at once with the holder named. The OS releases
  the lock when the process ends, however it ends, so a stopped run leaves
  no stale lock and the takeover of its browser still works.
- A queue: the second run waits for the lock, then runs. A run holds the
  profile for seconds to minutes, a preview plan for as long as its steps
  take, and a harness waiting on a silent process cannot tell a queue from
  a hang. The agent can wait itself once it knows who holds the profile.
- A profile per run. Every run would load the editor cold, 20 to 40 seconds
  against 4 to 7, and `export_project.py` keeps the user's login in its
  profile, which a profile per run would lose.

## Decision

The first. `Browser.__init__` takes a non-blocking OS lock on `run.lock` in
the profile, `msvcrt.locking` on Windows and `flock` elsewhere, before it
reads the port file or deletes a staged project. The holder writes its pid,
its script and its start time into the file below the locked byte, so that
a refused run can read the line while the byte stays locked. The lock is
released at `close()`, and by the OS when the process ends. The file stays
in the profile; the lock, not the file, says whether a run holds it.

A refused run prints one line with the holder and what to do, and exits
with code 5, which no other exit of the skill's scripts means. Every
script that constructs a `Browser` or calls `drive()` catches
`ProfileBusy` in its `main()` and exits so. A script with `--profile`
offers it as the second way out; a script without it says to run again
when the holder has ended. `--jobs` opens several projects inside one run,
in one browser, under one lock.

The test holds the lock from a child process and runs the script against a
browser path that does not exist. A refusal with exit 5 and the child's pid
shows that the lock is checked before the browser. Once the child has
ended, the same command reaches the browser and fails on the path, which
shows that the lock went with the process.

## Re-evaluate when

- A run is observed waiting on a profile for longer than the editor takes
  to load cold: then a second profile per worktree, warmed once, may serve
  the user better than the wait, and `--profile` could default to one.
- The browser gains a way to tell a live DevTools client from a dead one,
  so that the takeover itself could refuse a live run.
