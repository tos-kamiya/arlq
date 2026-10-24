# Respawn rule comparison

Seeds: `1..50`; policies: discovery, nearest, situational.
The no-a-b condition uses b feed=60, a count=20, and b count=10 when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| all | 1 | discovery | 0.140 | 0.300 | {'won': 7, 'lp_depleted': 41, 'turn_limit': 2} |
| all | 1 | nearest | 0.420 | 0.260 | {'won': 21, 'lp_depleted': 29} |
| all | 1 | situational | 0.280 | 0.260 | {'lp_depleted': 31, 'turn_limit': 5, 'won': 14} |
| all | 2 | discovery | 0.040 | 0.240 | {'lp_depleted': 48, 'won': 2} |
| all | 2 | nearest | 0.120 | 0.180 | {'lp_depleted': 44, 'won': 6} |
| all | 2 | situational | 0.060 | 0.200 | {'lp_depleted': 46, 'won': 3, 'turn_limit': 1} |
| no-a-b | 1 | discovery | 0.380 | 0.120 | {'lp_depleted': 31, 'won': 19} |
| no-a-b | 1 | nearest | 0.300 | 0.060 | {'lp_depleted': 35, 'won': 15} |
| no-a-b | 1 | situational | 0.380 | 0.060 | {'lp_depleted': 31, 'won': 19} |
| no-a-b | 2 | discovery | 0.020 | 0.080 | {'lp_depleted': 49, 'won': 1} |
| no-a-b | 2 | nearest | 0.080 | 0.060 | {'won': 4, 'lp_depleted': 46} |
| no-a-b | 2 | situational | 0.120 | 0.040 | {'lp_depleted': 44, 'won': 6} |
