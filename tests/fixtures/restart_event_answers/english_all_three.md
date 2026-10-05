# Event That Restarts the Game

## Answer

**Event Number: 9**

Located in the "Restart" group of the Game event sheet.

## What Must Be True to Fire

Two conditions must both be true for this event to trigger:

1. **System: Coin.Count = 0** — All coins have been collected (there are zero coins left in the layout)
2. **System: Trigger once** — Ensures the event fires only once per frame (prevents repeated execution)

## What Happens When It Fires

When both conditions are met, the event executes these three actions in order:

1. **System: Set beat to (beat + 1) % tokencount(ROUND_COINS, ",")** — Increments to the next round (with wraparound based on the number of rounds defined in ROUND_COINS)
2. **System: Wait 1 seconds (use time scale: True)** — Pauses for 1 second
3. **System: Restart layout** — Restarts the layout, which triggers the Setup group (event 2) to empty the score and deal the next round's coins

## Context

This event is part of the "Restart" group, which handles transitioning between rounds. When all coins in a round are collected (Coin.Count = 0), the game waits 1 second, then restarts the layout to begin the next round with a new set of coins determined by the ROUND_COINS constant.

---

## Commands run

```bash
cd "<run>/project" && find . -name "*.json" -path "*/eventSheets/*" -type f | head -20
python ".agents/skills/construct3-agent-plugin/scripts/print_sheet.py" Game
mkdir -p "<run>/outputs"
```
