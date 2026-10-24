# Respawn rule comparison

Seeds: `1..100`; policies: discovery, nearest, situational.
Selected non-all conditions use b feed=60, a count=14, b count=7, C count=None, c/C sword uses=None, and LP max=None when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| checkpoint | 1 | discovery | 0.020 | 0.600 | {'lp_depleted': 98, 'won': 2} |
| checkpoint | 1 | nearest | 0.040 | 0.540 | {'lp_depleted': 96, 'won': 4} |
| checkpoint | 1 | situational | 0.020 | 0.540 | {'lp_depleted': 98, 'won': 2} |
| checkpoint | 2 | discovery | 0.020 | 0.650 | {'won': 2, 'lp_depleted': 98} |
| checkpoint | 2 | nearest | 0.010 | 0.600 | {'lp_depleted': 99, 'won': 1} |
| checkpoint | 2 | situational | 0.010 | 0.600 | {'lp_depleted': 99, 'won': 1} |
