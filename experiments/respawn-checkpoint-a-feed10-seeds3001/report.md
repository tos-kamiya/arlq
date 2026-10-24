# Respawn rule comparison

Seeds: `3001..3100`; policies: discovery, nearest, situational.
Selected non-all conditions use a feed=10, b feed=60, a count=25, b count=10, C count=None, c/C sword uses=None, and LP max=None when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| checkpoint | 1 | discovery | 0.370 | 0.080 | {'lp_depleted': 63, 'won': 37} |
| checkpoint | 1 | nearest | 0.390 | 0.050 | {'lp_depleted': 60, 'won': 39, 'turn_limit': 1} |
| checkpoint | 1 | situational | 0.420 | 0.050 | {'won': 42, 'lp_depleted': 58} |
| checkpoint | 2 | discovery | 0.060 | 0.120 | {'lp_depleted': 94, 'won': 6} |
| checkpoint | 2 | nearest | 0.080 | 0.040 | {'won': 8, 'lp_depleted': 92} |
| checkpoint | 2 | situational | 0.070 | 0.050 | {'won': 7, 'lp_depleted': 93} |
