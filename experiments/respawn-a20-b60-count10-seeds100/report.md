# Respawn rule comparison

Seeds: `1..100`; policies: discovery, nearest, situational.
The no-a-b condition uses b feed=60, a count=20, and b count=10 when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| all | 1 | discovery | 0.120 | 0.360 | {'won': 12, 'lp_depleted': 85, 'turn_limit': 3} |
| all | 1 | nearest | 0.340 | 0.300 | {'won': 34, 'lp_depleted': 65, 'turn_limit': 1} |
| all | 1 | situational | 0.230 | 0.310 | {'lp_depleted': 71, 'turn_limit': 6, 'won': 23} |
| all | 2 | discovery | 0.030 | 0.280 | {'lp_depleted': 96, 'won': 3, 'turn_limit': 1} |
| all | 2 | nearest | 0.080 | 0.220 | {'lp_depleted': 91, 'won': 8, 'turn_limit': 1} |
| all | 2 | situational | 0.050 | 0.230 | {'lp_depleted': 93, 'won': 5, 'turn_limit': 2} |
| no-a-b | 1 | discovery | 0.320 | 0.100 | {'lp_depleted': 68, 'won': 32} |
| no-a-b | 1 | nearest | 0.350 | 0.060 | {'lp_depleted': 65, 'won': 35} |
| no-a-b | 1 | situational | 0.300 | 0.060 | {'lp_depleted': 68, 'won': 30, 'turn_limit': 2} |
| no-a-b | 2 | discovery | 0.030 | 0.090 | {'lp_depleted': 97, 'won': 3} |
| no-a-b | 2 | nearest | 0.080 | 0.060 | {'won': 8, 'lp_depleted': 92} |
| no-a-b | 2 | situational | 0.110 | 0.040 | {'lp_depleted': 89, 'won': 11} |
