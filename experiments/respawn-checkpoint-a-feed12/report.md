# Respawn rule comparison

Seeds: `1..100`; policies: discovery, nearest, situational.
Selected non-all conditions use a feed=12, b feed=60, a count=25, b count=10, C count=None, c/C sword uses=None, and LP max=None when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| checkpoint | 1 | discovery | 0.240 | 0.090 | {'lp_depleted': 76, 'won': 24} |
| checkpoint | 1 | nearest | 0.350 | 0.060 | {'lp_depleted': 65, 'won': 35} |
| checkpoint | 1 | situational | 0.360 | 0.060 | {'lp_depleted': 64, 'won': 36} |
| checkpoint | 2 | discovery | 0.050 | 0.100 | {'lp_depleted': 95, 'won': 5} |
| checkpoint | 2 | nearest | 0.040 | 0.080 | {'lp_depleted': 95, 'turn_limit': 1, 'won': 4} |
| checkpoint | 2 | situational | 0.130 | 0.070 | {'lp_depleted': 87, 'won': 13} |
