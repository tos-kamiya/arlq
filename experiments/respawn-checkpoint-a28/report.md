# Respawn rule comparison

Seeds: `1..100`; policies: discovery, nearest, situational.
Selected non-all conditions use b feed=60, a count=28, b count=7, C count=None, c/C sword uses=None, and LP max=None when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| checkpoint | 1 | discovery | 0.150 | 0.100 | {'lp_depleted': 85, 'won': 15} |
| checkpoint | 1 | nearest | 0.320 | 0.070 | {'lp_depleted': 68, 'won': 32} |
| checkpoint | 1 | situational | 0.250 | 0.070 | {'lp_depleted': 75, 'won': 25} |
| checkpoint | 2 | discovery | 0.010 | 0.220 | {'lp_depleted': 99, 'won': 1} |
| checkpoint | 2 | nearest | 0.040 | 0.140 | {'lp_depleted': 96, 'won': 4} |
| checkpoint | 2 | situational | 0.030 | 0.180 | {'lp_depleted': 97, 'won': 3} |
