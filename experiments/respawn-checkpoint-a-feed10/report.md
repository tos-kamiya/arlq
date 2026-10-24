# Respawn rule comparison

Seeds: `1..100`; policies: discovery, nearest, situational.
Selected non-all conditions use a feed=10, b feed=60, a count=25, b count=10, C count=None, c/C sword uses=None, and LP max=None when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| checkpoint | 1 | discovery | 0.220 | 0.100 | {'lp_depleted': 78, 'won': 22} |
| checkpoint | 1 | nearest | 0.300 | 0.070 | {'lp_depleted': 70, 'won': 30} |
| checkpoint | 1 | situational | 0.330 | 0.070 | {'lp_depleted': 67, 'won': 33} |
| checkpoint | 2 | discovery | 0.050 | 0.150 | {'lp_depleted': 95, 'won': 5} |
| checkpoint | 2 | nearest | 0.030 | 0.100 | {'lp_depleted': 96, 'turn_limit': 1, 'won': 3} |
| checkpoint | 2 | situational | 0.090 | 0.090 | {'lp_depleted': 91, 'won': 9} |
