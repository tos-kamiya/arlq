# Respawn rule comparison

Seeds: `1001..1100`; policies: discovery, nearest, situational.
Selected non-all conditions use a feed=10, b feed=60, a count=25, b count=10, C count=None, c/C sword uses=None, and LP max=None when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| checkpoint | 1 | discovery | 0.280 | 0.080 | {'lp_depleted': 72, 'won': 28} |
| checkpoint | 1 | nearest | 0.310 | 0.050 | {'lp_depleted': 69, 'won': 31} |
| checkpoint | 1 | situational | 0.290 | 0.050 | {'lp_depleted': 70, 'won': 29, 'turn_limit': 1} |
| checkpoint | 2 | discovery | 0.090 | 0.120 | {'lp_depleted': 91, 'won': 9} |
| checkpoint | 2 | nearest | 0.090 | 0.090 | {'lp_depleted': 91, 'won': 9} |
| checkpoint | 2 | situational | 0.050 | 0.100 | {'lp_depleted': 95, 'won': 5} |
