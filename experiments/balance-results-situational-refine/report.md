# ARLQ static balance tuning report

The policies use mapped terrain and observed entities. `discovery` means the order in which the player first saw each monster; it is not internal spawn order. Unknown monster stats are not read by a policy.

Evaluated 12960 plays in 2887.5 seconds. Candidates are proposals; no game constants were modified.

Finite policies, seeds, and budgets do not prove optimality. Spawn changes also change random-number consumption, so equal seeds do not guarantee identical layouts.

## Final candidates

### 1. `07566e2a0be9`

Change distance: 43.0

```json
{
  "feed": {
    "b": 60
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
| stage1:discovery | 0.195 | 0.065 | 582.0 | 37.0 |
| stage1:nearest | 0.315 | 0.030 | 560.0 | 49.0 |
| stage1:situational | 0.300 | 0.035 | 570.0 | 46.0 |
| stage2:discovery | 0.040 | 0.045 | 646.0 | 19.0 |
| stage2:nearest | 0.060 | 0.035 | 589.0 | 31.0 |
| stage2:situational | 0.085 | 0.040 | 542.0 | 38.0 |

Paired clear-rate differences:

- `stage1:nearest-discovery`: +0.120, 95% paired bootstrap [+0.055, +0.185] (200 seeds)
- `stage1:situational-discovery`: +0.105, 95% paired bootstrap [+0.040, +0.170] (200 seeds)
- `stage2:nearest-discovery`: +0.020, 95% paired bootstrap [-0.015, +0.055] (200 seeds)
- `stage2:situational-discovery`: +0.045, 95% paired bootstrap [+0.010, +0.080] (200 seeds)

### 2. `f212ec76dc38`

Change distance: 47.0

```json
{
  "feed": {
    "b": 66
  },
  "spawn": {
    "1": {
      "a": 24,
      "b": 10
    },
    "2": {
      "a": 20,
      "b": 9
    }
  }
}
```

| Policy and stage | Clear rate | Early starvation | Win steps (median) | Win LP (median) |
| --- | ---: | ---: | ---: | ---: |
| stage1:discovery | 0.265 | 0.055 | 582.0 | 47.0 |
| stage1:nearest | 0.350 | 0.010 | 601.0 | 40.0 |
| stage1:situational | 0.290 | 0.010 | 566.0 | 47.0 |
| stage2:discovery | 0.035 | 0.105 | 461.0 | 71.0 |
| stage2:nearest | 0.045 | 0.045 | 440.0 | 31.0 |
| stage2:situational | 0.070 | 0.055 | 558.0 | 35.0 |

Paired clear-rate differences:

- `stage1:nearest-discovery`: +0.085, 95% paired bootstrap [+0.020, +0.150] (200 seeds)
- `stage1:situational-discovery`: +0.025, 95% paired bootstrap [-0.045, +0.095] (200 seeds)
- `stage2:nearest-discovery`: +0.010, 95% paired bootstrap [-0.015, +0.035] (200 seeds)
- `stage2:situational-discovery`: +0.035, 95% paired bootstrap [+0.000, +0.075] (200 seeds)

### 3. `e4cdb07bc9bf`

Change distance: 43.0

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
      "a": 22,
      "b": 9
    }
  }
}
```

| Policy and stage | Clear rate | Early starvation | Win steps (median) | Win LP (median) |
| --- | ---: | ---: | ---: | ---: |
| stage1:discovery | 0.195 | 0.065 | 582.0 | 38.0 |
| stage1:nearest | 0.315 | 0.030 | 560.0 | 49.0 |
| stage1:situational | 0.295 | 0.035 | 569.0 | 43.0 |
| stage2:discovery | 0.025 | 0.110 | 753.0 | 13.0 |
| stage2:nearest | 0.025 | 0.075 | 647.0 | 47.0 |
| stage2:situational | 0.045 | 0.075 | 732.0 | 31.0 |

Paired clear-rate differences:

- `stage1:nearest-discovery`: +0.120, 95% paired bootstrap [+0.055, +0.185] (200 seeds)
- `stage1:situational-discovery`: +0.100, 95% paired bootstrap [+0.035, +0.165] (200 seeds)
- `stage2:nearest-discovery`: +0.000, 95% paired bootstrap [-0.025, +0.020] (200 seeds)
- `stage2:situational-discovery`: +0.020, 95% paired bootstrap [-0.005, +0.050] (200 seeds)
