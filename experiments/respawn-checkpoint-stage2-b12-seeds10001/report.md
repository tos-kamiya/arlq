# Respawn rule comparison

Seeds: `10001..11000`; policies: discovery, nearest, situational.
Selected non-all conditions use a feed=10, b feed=60, a count=25, b count=12, C count=None, c/C sword uses=None, and LP max=None when specified.
All conditions use the same seeds. `all` keeps the current respawn rule; the other conditions disable respawn for the named weak monsters. Companions remain unchanged.

| Condition | Stage | Policy | Clear rate | Early starvation | End reasons |
| --- | ---: | --- | ---: | ---: | --- |
| checkpoint | 2 | discovery | 0.067 | 0.127 | {'lp_depleted': 931, 'won': 67, 'turn_limit': 2} |
| checkpoint | 2 | nearest | 0.085 | 0.076 | {'lp_depleted': 913, 'won': 85, 'turn_limit': 2} |
| checkpoint | 2 | situational | 0.081 | 0.076 | {'lp_depleted': 918, 'won': 81, 'turn_limit': 1} |
