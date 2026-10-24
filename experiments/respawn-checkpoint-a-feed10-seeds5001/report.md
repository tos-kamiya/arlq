# Respawn rule comparison

Seeds: `5001..5100`; policies: discovery, nearest, situational.
Selected non-all conditions use a feed=10, b feed=60, a count=25, b count=10, C count=None, c/C sword uses=None, and LP max=None when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| checkpoint | 1 | discovery | 0.320 | 0.070 | {'lp_depleted': 68, 'won': 32} |
| checkpoint | 1 | nearest | 0.380 | 0.020 | {'lp_depleted': 62, 'won': 38} |
| checkpoint | 1 | situational | 0.360 | 0.020 | {'lp_depleted': 64, 'won': 36} |
| checkpoint | 2 | discovery | 0.030 | 0.160 | {'lp_depleted': 97, 'won': 3} |
| checkpoint | 2 | nearest | 0.080 | 0.090 | {'lp_depleted': 92, 'won': 8} |
| checkpoint | 2 | situational | 0.070 | 0.080 | {'lp_depleted': 93, 'won': 7} |
