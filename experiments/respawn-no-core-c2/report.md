# Respawn rule comparison

Seeds: `1..100`; policies: discovery, nearest, situational.
Selected non-all conditions use b feed=60, a count=20, and b count=10 when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| all | 1 | discovery | 0.120 | 0.280 | {'lp_depleted': 86, 'won': 12, 'turn_limit': 2} |
| all | 1 | nearest | 0.270 | 0.220 | {'lp_depleted': 71, 'won': 27, 'turn_limit': 2} |
| all | 1 | situational | 0.170 | 0.230 | {'lp_depleted': 80, 'turn_limit': 3, 'won': 17} |
| all | 2 | discovery | 0.020 | 0.280 | {'lp_depleted': 96, 'turn_limit': 2, 'won': 2} |
| all | 2 | nearest | 0.080 | 0.220 | {'lp_depleted': 91, 'won': 8, 'turn_limit': 1} |
| all | 2 | situational | 0.050 | 0.230 | {'lp_depleted': 93, 'won': 5, 'turn_limit': 2} |
| no-core | 1 | discovery | 0.150 | 0.160 | {'lp_depleted': 85, 'won': 15} |
| no-core | 1 | nearest | 0.170 | 0.070 | {'lp_depleted': 83, 'won': 17} |
| no-core | 1 | situational | 0.140 | 0.080 | {'lp_depleted': 86, 'won': 14} |
| no-core | 2 | discovery | 0.030 | 0.100 | {'lp_depleted': 97, 'won': 3} |
| no-core | 2 | nearest | 0.040 | 0.060 | {'lp_depleted': 96, 'won': 4} |
| no-core | 2 | situational | 0.030 | 0.060 | {'lp_depleted': 97, 'won': 3} |
