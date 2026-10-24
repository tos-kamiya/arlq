# Respawn rule comparison

Seeds: `1..100`; policies: discovery, nearest, situational.
Selected non-all conditions use b feed=66, a count=26, b count=11, C count=None, c/C sword uses=None, and LP max=None when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| checkpoint | 1 | discovery | 0.240 | 0.110 | {'won': 24, 'lp_depleted': 76} |
| checkpoint | 1 | nearest | 0.320 | 0.100 | {'won': 32, 'lp_depleted': 68} |
| checkpoint | 1 | situational | 0.280 | 0.100 | {'won': 28, 'lp_depleted': 72} |
| checkpoint | 2 | discovery | 0.090 | 0.150 | {'lp_depleted': 91, 'won': 9} |
| checkpoint | 2 | nearest | 0.060 | 0.100 | {'lp_depleted': 94, 'won': 6} |
| checkpoint | 2 | situational | 0.120 | 0.110 | {'won': 12, 'lp_depleted': 88} |
| no-core | 1 | discovery | 0.360 | 0.000 | {'won': 36, 'lp_depleted': 64} |
| no-core | 1 | nearest | 0.420 | 0.000 | {'won': 42, 'lp_depleted': 58} |
| no-core | 1 | situational | 0.380 | 0.000 | {'won': 38, 'lp_depleted': 62} |
| no-core | 2 | discovery | 0.050 | 0.020 | {'lp_depleted': 95, 'won': 5} |
| no-core | 2 | nearest | 0.090 | 0.010 | {'lp_depleted': 91, 'won': 9} |
| no-core | 2 | situational | 0.070 | 0.010 | {'lp_depleted': 93, 'won': 7} |
