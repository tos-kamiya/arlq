# Respawn rule comparison

Seeds: `1..100`; policies: discovery, nearest, situational.
Selected non-all conditions use b feed=66, a count=23, b count=9, C count=None, c/C sword uses=None, and LP max=None when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| checkpoint | 1 | discovery | 0.190 | 0.190 | {'won': 19, 'lp_depleted': 81} |
| checkpoint | 1 | nearest | 0.290 | 0.120 | {'won': 29, 'lp_depleted': 71} |
| checkpoint | 1 | situational | 0.260 | 0.130 | {'won': 26, 'lp_depleted': 74} |
| checkpoint | 2 | discovery | 0.020 | 0.200 | {'lp_depleted': 98, 'won': 2} |
| checkpoint | 2 | nearest | 0.020 | 0.170 | {'lp_depleted': 98, 'won': 2} |
| checkpoint | 2 | situational | 0.030 | 0.160 | {'lp_depleted': 97, 'won': 3} |
| no-core | 1 | discovery | 0.210 | 0.100 | {'lp_depleted': 79, 'won': 21} |
| no-core | 1 | nearest | 0.290 | 0.070 | {'lp_depleted': 71, 'won': 29} |
| no-core | 1 | situational | 0.290 | 0.050 | {'lp_depleted': 71, 'won': 29} |
| no-core | 2 | discovery | 0.010 | 0.080 | {'lp_depleted': 99, 'won': 1} |
| no-core | 2 | nearest | 0.030 | 0.060 | {'lp_depleted': 97, 'won': 3} |
| no-core | 2 | situational | 0.030 | 0.060 | {'lp_depleted': 97, 'won': 3} |
