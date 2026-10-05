## Event that restarts the game

**Event 9** in the **Game** event sheet (under group *Restart*).

### What it does

1. System: Set beat to (beat + 1) % tokencount(ROUND_COINS, ",") — advance to the next round
2. System: Wait 1 seconds (use timescale: True) — pause one game-second
3. **System: Restart layout** — reloads the current layout

### Conditions that must be true for it to fire

Both of these conditions must be simultaneously satisfied:

| # | Condition object | Condition type | What it checks |
|---|------------------|----------------|----------------|
| 1 | **System** | Compare two values | Coin.Count = 0 — zero Coin instances alive on the layout. |
| 2 | **System** | Trigger once (while true) | Fires exactly once when condition 1 first becomes true, then ignores further ticks while it remains true. Re-triggers next time Coin.Count goes to 0 on a fresh layout. |

### In plain language

The event fires **the tick after every last Coin instance is destroyed** in a round. That is all that must be true: no coins left on screen. Once that happens, it advances the beat counter, waits one game-second, and calls Restart layout, which reloads the scene so Setup (event 2) runs again to deal fresh coins for the next round.

## Commands run

1. python .agents/skills/construct3-agent-plugin/scripts/print_sheet.py Game --events 1-200 — print all events in the Game sheet
2. python .agents/skills/construct3-agent-plugin/scripts/print_sheet.py Game --show 9 — show event 9 as JSON (ACE lookup)
3. python .agents/skills/construct3-agent-plugin/scripts/print_sheet.py Game --outline — print all event numbers for context
4. python .agents/skills/construct3-agent-plugin/scripts/print_sheet.py Game --events 9-9 — confirm conditions + actions of event 9
