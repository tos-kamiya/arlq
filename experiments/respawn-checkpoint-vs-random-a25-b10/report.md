# Respawn rule comparison

Seeds: `1..100`; policies: discovery, nearest, situational.
Selected non-all conditions use b feed=60, a count=25, b count=10, C count=None, c/C sword uses=None, and LP max=None when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| checkpoint | 1 | discovery | 0.220 | 0.120 | {'lp_depleted': 78, 'won': 22} |
| checkpoint | 1 | nearest | 0.270 | 0.090 | {'lp_depleted': 73, 'won': 27} |
| checkpoint | 1 | situational | 0.330 | 0.090 | {'lp_depleted': 67, 'won': 33} |
| checkpoint | 2 | discovery | 0.040 | 0.200 | {'lp_depleted': 96, 'won': 4} |
| checkpoint | 2 | nearest | 0.030 | 0.140 | {'lp_depleted': 97, 'won': 3} |
| checkpoint | 2 | situational | 0.090 | 0.140 | {'lp_depleted': 91, 'won': 9} |
| no-core | 1 | discovery | 0.300 | 0.040 | {'lp_depleted': 69, 'won': 30, 'turn_limit': 1} |
| no-core | 1 | nearest | 0.350 | 0.010 | {'lp_depleted': 65, 'won': 35} |
| no-core | 1 | situational | 0.310 | 0.020 | {'lp_depleted': 69, 'won': 31} |
| no-core | 2 | discovery | 0.020 | 0.060 | {'lp_depleted': 98, 'won': 2} |
| no-core | 2 | nearest | 0.050 | 0.020 | {'lp_depleted': 95, 'won': 5} |
| no-core | 2 | situational | 0.050 | 0.030 | {'lp_depleted': 95, 'won': 5} |
