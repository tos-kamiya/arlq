# Respawn rule comparison

Seeds: `1..50`; policies: discovery, nearest, situational.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| all | 1 | discovery | 0.140 | 0.300 | {'won': 7, 'lp_depleted': 41, 'turn_limit': 2} |
| all | 1 | nearest | 0.420 | 0.260 | {'won': 21, 'lp_depleted': 29} |
| all | 1 | situational | 0.280 | 0.260 | {'lp_depleted': 31, 'turn_limit': 5, 'won': 14} |
| all | 2 | discovery | 0.040 | 0.240 | {'lp_depleted': 48, 'won': 2} |
| all | 2 | nearest | 0.120 | 0.180 | {'lp_depleted': 44, 'won': 6} |
| all | 2 | situational | 0.060 | 0.200 | {'lp_depleted': 46, 'won': 3, 'turn_limit': 1} |
| no-a | 1 | discovery | 0.120 | 0.380 | {'won': 6, 'lp_depleted': 43, 'turn_limit': 1} |
| no-a | 1 | nearest | 0.280 | 0.300 | {'lp_depleted': 34, 'won': 14, 'turn_limit': 2} |
| no-a | 1 | situational | 0.180 | 0.300 | {'lp_depleted': 38, 'turn_limit': 3, 'won': 9} |
| no-a | 2 | discovery | 0.120 | 0.260 | {'lp_depleted': 43, 'turn_limit': 1, 'won': 6} |
| no-a | 2 | nearest | 0.120 | 0.240 | {'lp_depleted': 42, 'won': 6, 'turn_limit': 2} |
| no-a | 2 | situational | 0.080 | 0.240 | {'lp_depleted': 46, 'won': 4} |
| no-b | 1 | discovery | 0.060 | 0.300 | {'lp_depleted': 47, 'won': 3} |
| no-b | 1 | nearest | 0.140 | 0.260 | {'lp_depleted': 43, 'won': 7} |
| no-b | 1 | situational | 0.120 | 0.260 | {'lp_depleted': 44, 'won': 6} |
| no-b | 2 | discovery | 0.020 | 0.220 | {'lp_depleted': 49, 'won': 1} |
| no-b | 2 | nearest | 0.040 | 0.180 | {'lp_depleted': 48, 'won': 2} |
| no-b | 2 | situational | 0.020 | 0.180 | {'lp_depleted': 49, 'won': 1} |
| no-weak | 1 | discovery | 0.040 | 0.380 | {'won': 2, 'lp_depleted': 48} |
| no-weak | 1 | nearest | 0.040 | 0.300 | {'lp_depleted': 48, 'won': 2} |
| no-weak | 1 | situational | 0.020 | 0.300 | {'lp_depleted': 49, 'won': 1} |
| no-weak | 2 | discovery | 0.020 | 0.260 | {'lp_depleted': 49, 'won': 1} |
| no-weak | 2 | nearest | 0.080 | 0.240 | {'lp_depleted': 46, 'won': 4} |
| no-weak | 2 | situational | 0.020 | 0.240 | {'lp_depleted': 49, 'won': 1} |
