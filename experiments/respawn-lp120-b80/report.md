# Respawn rule comparison

Seeds: `1..100`; policies: discovery, nearest, situational.
Selected non-all conditions use b feed=80, a count=23, b count=9, C count=None, c/C sword uses=None, and LP max=120 when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| all | 1 | discovery | 0.120 | 0.360 | {'won': 12, 'lp_depleted': 84, 'turn_limit': 4} |
| all | 1 | nearest | 0.330 | 0.300 | {'won': 33, 'lp_depleted': 65, 'turn_limit': 2} |
| all | 1 | situational | 0.230 | 0.310 | {'lp_depleted': 71, 'turn_limit': 6, 'won': 23} |
| all | 2 | discovery | 0.020 | 0.280 | {'lp_depleted': 96, 'turn_limit': 2, 'won': 2} |
| all | 2 | nearest | 0.080 | 0.220 | {'lp_depleted': 91, 'won': 8, 'turn_limit': 1} |
| all | 2 | situational | 0.050 | 0.230 | {'lp_depleted': 93, 'won': 5, 'turn_limit': 2} |
| no-core | 1 | discovery | 0.330 | 0.090 | {'lp_depleted': 67, 'won': 33} |
| no-core | 1 | nearest | 0.410 | 0.060 | {'won': 41, 'lp_depleted': 59} |
| no-core | 1 | situational | 0.380 | 0.050 | {'won': 38, 'turn_limit': 3, 'lp_depleted': 59} |
| no-core | 2 | discovery | 0.100 | 0.080 | {'lp_depleted': 90, 'won': 10} |
| no-core | 2 | nearest | 0.070 | 0.060 | {'lp_depleted': 93, 'won': 7} |
| no-core | 2 | situational | 0.090 | 0.050 | {'lp_depleted': 91, 'won': 9} |
