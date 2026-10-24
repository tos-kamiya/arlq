# Respawn rule comparison

Seeds: `1..100`; policies: discovery, nearest, situational.
Selected non-all conditions use b feed=80, a count=None, b count=None, C count=None, c/C sword uses=None, and LP max=None when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| all | 1 | discovery | 0.120 | 0.360 | {'won': 12, 'lp_depleted': 85, 'turn_limit': 3} |
| all | 1 | nearest | 0.340 | 0.300 | {'won': 34, 'lp_depleted': 65, 'turn_limit': 1} |
| all | 1 | situational | 0.230 | 0.310 | {'lp_depleted': 71, 'turn_limit': 6, 'won': 23} |
| all | 2 | discovery | 0.020 | 0.280 | {'lp_depleted': 96, 'turn_limit': 2, 'won': 2} |
| all | 2 | nearest | 0.080 | 0.220 | {'lp_depleted': 91, 'won': 8, 'turn_limit': 1} |
| all | 2 | situational | 0.050 | 0.230 | {'lp_depleted': 93, 'won': 5, 'turn_limit': 2} |
| no-core | 1 | discovery | 0.060 | 0.400 | {'won': 6, 'lp_depleted': 94} |
| no-core | 1 | nearest | 0.030 | 0.330 | {'lp_depleted': 97, 'won': 3} |
| no-core | 1 | situational | 0.040 | 0.330 | {'lp_depleted': 96, 'won': 4} |
| no-core | 2 | discovery | 0.000 | 0.270 | {'lp_depleted': 100} |
| no-core | 2 | nearest | 0.000 | 0.250 | {'lp_depleted': 100} |
| no-core | 2 | situational | 0.000 | 0.250 | {'lp_depleted': 100} |
