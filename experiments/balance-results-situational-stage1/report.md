# ARLQ static balance tuning report

The policies use mapped terrain and observed entities. `discovery` means the order in which the player first saw each monster; it is not internal spawn order. Unknown monster stats are not read by a policy.

Evaluated 9720 plays in 1952.4 seconds. Candidates are proposals; no game constants were modified.

Finite policies, seeds, and budgets do not prove optimality. Spawn changes also change random-number consumption, so equal seeds do not guarantee identical layouts.

## Final candidates

### 1. `a96ae122f970`

Change distance: 49.0

```json
{
  "feed": {
    "b": 66
  },
  "spawn": {
    "1": {
      "a": 23,
      "b": 9
    },
    "2": {
      "a": 24,
      "b": 9
    }
  }
}
```

| Policy and stage | Clear rate | Early starvation | Win steps (median) | Win LP (median) |
| --- | ---: | ---: | ---: | ---: |
| stage1:discovery | 0.207 | 0.060 | 558.0 | 35.0 |
| stage1:nearest | 0.300 | 0.033 | 562.0 | 49.0 |
| stage1:situational | 0.307 | 0.040 | 556.0 | 46.0 |

Paired clear-rate differences:

- `stage1:nearest-discovery`: +0.093, 95% paired bootstrap [+0.040, +0.147] (300 seeds)
- `stage1:situational-discovery`: +0.100, 95% paired bootstrap [+0.047, +0.150] (300 seeds)

### 2. `01168b0d14b2`

Change distance: 45.0

```json
{
  "feed": {
    "b": 62
  },
  "spawn": {
    "1": {
      "a": 23,
      "b": 9
    },
    "2": {
      "a": 24,
      "b": 9
    }
  }
}
```

| Policy and stage | Clear rate | Early starvation | Win steps (median) | Win LP (median) |
| --- | ---: | ---: | ---: | ---: |
| stage1:discovery | 0.200 | 0.060 | 571.0 | 38.0 |
| stage1:nearest | 0.293 | 0.033 | 562.0 | 53.0 |
| stage1:situational | 0.297 | 0.040 | 556.0 | 46.0 |

Paired clear-rate differences:

- `stage1:nearest-discovery`: +0.093, 95% paired bootstrap [+0.043, +0.147] (300 seeds)
- `stage1:situational-discovery`: +0.097, 95% paired bootstrap [+0.047, +0.147] (300 seeds)

### 3. `c48b9b19567d`

Change distance: 51.0

```json
{
  "feed": {
    "b": 68
  },
  "spawn": {
    "1": {
      "a": 23,
      "b": 9
    },
    "2": {
      "a": 24,
      "b": 9
    }
  }
}
```

| Policy and stage | Clear rate | Early starvation | Win steps (median) | Win LP (median) |
| --- | ---: | ---: | ---: | ---: |
| stage1:discovery | 0.207 | 0.060 | 558.0 | 38.0 |
| stage1:nearest | 0.300 | 0.033 | 562.0 | 49.0 |
| stage1:situational | 0.303 | 0.040 | 551.0 | 46.0 |

Paired clear-rate differences:

- `stage1:nearest-discovery`: +0.093, 95% paired bootstrap [+0.043, +0.147] (300 seeds)
- `stage1:situational-discovery`: +0.097, 95% paired bootstrap [+0.047, +0.147] (300 seeds)
