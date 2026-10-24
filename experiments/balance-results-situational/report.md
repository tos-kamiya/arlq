# ARLQ static balance tuning report

The policies use mapped terrain and observed entities. `discovery` means the order in which the player first saw each monster; it is not internal spawn order. Unknown monster stats are not read by a policy.

Evaluated 12960 plays in 2886.6 seconds. Candidates are proposals; no game constants were modified.

Finite policies, seeds, and budgets do not prove optimality. Spawn changes also change random-number consumption, so equal seeds do not guarantee identical layouts.

## Final candidates

### 1. `99f09367c007`

Change distance: 46.0

```json
{
  "feed": {
    "b": 65
  },
  "spawn": {
    "1": {
      "a": 22,
      "b": 10
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
| stage1:discovery | 0.245 | 0.065 | 597.0 | 59.0 |
| stage1:nearest | 0.315 | 0.035 | 560.0 | 56.0 |
| stage1:situational | 0.320 | 0.035 | 593.0 | 50.0 |
| stage2:discovery | 0.025 | 0.110 | 753.0 | 16.0 |
| stage2:nearest | 0.025 | 0.075 | 647.0 | 47.0 |
| stage2:situational | 0.045 | 0.075 | 732.0 | 31.0 |

Paired clear-rate differences:

- `stage1:nearest-discovery`: +0.070, 95% paired bootstrap [+0.010, +0.130] (200 seeds)
- `stage1:situational-discovery`: +0.075, 95% paired bootstrap [+0.010, +0.140] (200 seeds)
- `stage2:nearest-discovery`: +0.000, 95% paired bootstrap [-0.025, +0.020] (200 seeds)
- `stage2:situational-discovery`: +0.020, 95% paired bootstrap [-0.005, +0.050] (200 seeds)

### 2. `49c32b2ffbe5`

Change distance: 44.0

```json
{
  "feed": {
    "b": 65
  },
  "spawn": {
    "1": {
      "a": 18,
      "b": 12
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
| stage1:discovery | 0.230 | 0.140 | 610.0 | 52.0 |
| stage1:nearest | 0.285 | 0.070 | 558.0 | 60.0 |
| stage1:situational | 0.270 | 0.075 | 601.0 | 65.0 |
| stage2:discovery | 0.025 | 0.110 | 753.0 | 16.0 |
| stage2:nearest | 0.025 | 0.075 | 647.0 | 47.0 |
| stage2:situational | 0.045 | 0.075 | 732.0 | 31.0 |

Paired clear-rate differences:

- `stage1:nearest-discovery`: +0.055, 95% paired bootstrap [-0.010, +0.125] (200 seeds)
- `stage1:situational-discovery`: +0.040, 95% paired bootstrap [-0.025, +0.110] (200 seeds)
- `stage2:nearest-discovery`: +0.000, 95% paired bootstrap [-0.025, +0.020] (200 seeds)
- `stage2:situational-discovery`: +0.020, 95% paired bootstrap [-0.005, +0.050] (200 seeds)

### 3. `fb119d166930`

Change distance: 38.0

```json
{
  "feed": {
    "b": 55
  },
  "spawn": {
    "1": {
      "a": 24,
      "b": 10
    },
    "2": {
      "a": 20,
      "b": 11
    }
  }
}
```

| Policy and stage | Clear rate | Early starvation | Win steps (median) | Win LP (median) |
| --- | ---: | ---: | ---: | ---: |
| stage1:discovery | 0.265 | 0.055 | 582.0 | 44.0 |
| stage1:nearest | 0.340 | 0.010 | 601.0 | 38.0 |
| stage1:situational | 0.280 | 0.010 | 583.0 | 47.0 |
| stage2:discovery | 0.035 | 0.130 | 557.0 | 31.0 |
| stage2:nearest | 0.060 | 0.065 | 555.0 | 37.0 |
| stage2:situational | 0.025 | 0.065 | 619.0 | 25.0 |

Paired clear-rate differences:

- `stage1:nearest-discovery`: +0.075, 95% paired bootstrap [+0.010, +0.135] (200 seeds)
- `stage1:situational-discovery`: +0.015, 95% paired bootstrap [-0.055, +0.080] (200 seeds)
- `stage2:nearest-discovery`: +0.025, 95% paired bootstrap [-0.005, +0.055] (200 seeds)
- `stage2:situational-discovery`: -0.010, 95% paired bootstrap [-0.035, +0.015] (200 seeds)
