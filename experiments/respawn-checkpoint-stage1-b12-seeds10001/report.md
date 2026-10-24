# Respawn rule comparison

Seeds: `10001..11000`; policies: discovery, nearest, situational.
Selected non-all conditions use a feed=10, b feed=60, a count=25, b count=12, C count=None, c/C sword uses=None, and LP max=None when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| checkpoint | 1 | discovery | 0.263 | 0.097 | {'lp_depleted': 737, 'won': 263} |
| checkpoint | 1 | nearest | 0.363 | 0.055 | {'won': 363, 'lp_depleted': 635, 'turn_limit': 2} |
| checkpoint | 1 | situational | 0.344 | 0.057 | {'lp_depleted': 655, 'won': 344, 'turn_limit': 1} |
