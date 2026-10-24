# Respawn rule comparison

Seeds: `1..50`; policies: discovery, nearest, situational.
The no-a-b condition uses b feed=60 and a count=20 when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| all | 1 | discovery | 0.140 | 0.300 | {'won': 7, 'lp_depleted': 40, 'turn_limit': 3} |
| all | 1 | nearest | 0.420 | 0.260 | {'won': 21, 'lp_depleted': 29} |
| all | 1 | situational | 0.280 | 0.260 | {'lp_depleted': 31, 'turn_limit': 5, 'won': 14} |
| all | 2 | discovery | 0.040 | 0.240 | {'lp_depleted': 47, 'turn_limit': 1, 'won': 2} |
| all | 2 | nearest | 0.120 | 0.180 | {'lp_depleted': 44, 'won': 6} |
| all | 2 | situational | 0.060 | 0.200 | {'lp_depleted': 46, 'won': 3, 'turn_limit': 1} |
| no-a-b | 1 | discovery | 0.140 | 0.120 | {'lp_depleted': 43, 'won': 7} |
| no-a-b | 1 | nearest | 0.240 | 0.060 | {'lp_depleted': 38, 'won': 12} |
| no-a-b | 1 | situational | 0.120 | 0.060 | {'lp_depleted': 44, 'won': 6} |
| no-a-b | 2 | discovery | 0.080 | 0.140 | {'lp_depleted': 46, 'won': 4} |
| no-a-b | 2 | nearest | 0.040 | 0.100 | {'lp_depleted': 48, 'won': 2} |
| no-a-b | 2 | situational | 0.040 | 0.080 | {'lp_depleted': 48, 'won': 2} |
