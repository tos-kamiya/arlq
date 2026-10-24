# Respawn rule comparison

Seeds: `1001..1100`; policies: discovery, nearest, situational.
Selected non-all conditions use a feed=12, b feed=60, a count=25, b count=10, C count=None, c/C sword uses=None, and LP max=None when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| checkpoint | 1 | discovery | 0.290 | 0.070 | {'lp_depleted': 71, 'won': 29} |
| checkpoint | 1 | nearest | 0.320 | 0.030 | {'lp_depleted': 67, 'won': 32, 'turn_limit': 1} |
| checkpoint | 1 | situational | 0.320 | 0.040 | {'lp_depleted': 67, 'won': 32, 'turn_limit': 1} |
| checkpoint | 2 | discovery | 0.110 | 0.100 | {'lp_depleted': 89, 'won': 11} |
| checkpoint | 2 | nearest | 0.100 | 0.080 | {'lp_depleted': 90, 'won': 10} |
| checkpoint | 2 | situational | 0.070 | 0.090 | {'lp_depleted': 93, 'won': 7} |
