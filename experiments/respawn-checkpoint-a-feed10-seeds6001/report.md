# Respawn rule comparison

Seeds: `6001..6100`; policies: discovery, nearest, situational.
Selected non-all conditions use a feed=10, b feed=60, a count=25, b count=10, C count=None, c/C sword uses=None, and LP max=None when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| checkpoint | 1 | discovery | 0.230 | 0.090 | {'lp_depleted': 77, 'won': 23} |
| checkpoint | 1 | nearest | 0.360 | 0.060 | {'lp_depleted': 64, 'won': 36} |
| checkpoint | 1 | situational | 0.330 | 0.060 | {'lp_depleted': 67, 'won': 33} |
| checkpoint | 2 | discovery | 0.060 | 0.140 | {'lp_depleted': 94, 'won': 6} |
| checkpoint | 2 | nearest | 0.070 | 0.090 | {'lp_depleted': 93, 'won': 7} |
| checkpoint | 2 | situational | 0.040 | 0.100 | {'lp_depleted': 96, 'won': 4} |
