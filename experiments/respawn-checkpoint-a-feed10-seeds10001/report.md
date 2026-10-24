# Respawn rule comparison

Seeds: `10001..11000`; policies: discovery, nearest, situational.
Selected non-all conditions use a feed=10, b feed=60, a count=25, b count=10, C count=None, c/C sword uses=None, and LP max=None when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| checkpoint | 1 | discovery | 0.249 | 0.103 | {'won': 249, 'lp_depleted': 749, 'turn_limit': 2} |
| checkpoint | 1 | nearest | 0.315 | 0.052 | {'lp_depleted': 683, 'won': 315, 'turn_limit': 2} |
| checkpoint | 1 | situational | 0.297 | 0.056 | {'won': 297, 'lp_depleted': 700, 'turn_limit': 3} |
| checkpoint | 2 | discovery | 0.044 | 0.142 | {'lp_depleted': 956, 'won': 44} |
| checkpoint | 2 | nearest | 0.066 | 0.095 | {'lp_depleted': 934, 'won': 66} |
| checkpoint | 2 | situational | 0.079 | 0.099 | {'lp_depleted': 919, 'won': 79, 'turn_limit': 2} |
