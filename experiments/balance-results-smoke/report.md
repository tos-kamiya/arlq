# ARLQ static balance tuning report

The policies use mapped terrain and observed entities. `discovery` means the order in which the player first saw each monster; it is not internal spawn order. Unknown monster stats are not read by a policy.

Evaluated 1080 plays in 490.4 seconds. Candidates are proposals; no game constants were modified.

Finite policies, seeds, and budgets do not prove optimality. Spawn changes also change random-number consumption, so equal seeds do not guarantee identical layouts.

## Final candidates

### 1. `f934e3f30b3b`

Change distance: 7.0

```json
{
  "feed": {
    "b": 45
  },
  "spawn": {
    "1": {
      "a": 16
    },
    "2": {
      "a": 14
    }
  }
}
```

| Policy and stage | Clear rate | Early starvation | Win steps (median) | Win LP (median) |
| --- | ---: | ---: | ---: | ---: |
| stage1:discovery | 0.300 | 0.040 | 673.0 | 73.0 |
| stage1:nearest | 0.480 | 0.020 | 708.0 | 44.0 |
| stage1:situational | 0.340 | 0.020 | 581.0 | 74.0 |
| stage2:discovery | 0.040 | 0.120 | 557.0 | 27.0 |
| stage2:nearest | 0.180 | 0.080 | 655.0 | 18.0 |
| stage2:situational | 0.080 | 0.100 | 600.0 | 43.0 |

Paired clear-rate differences:

- `stage1:nearest-discovery`: +0.180, 95% paired bootstrap [+0.000, +0.340] (50 seeds)
- `stage1:situational-discovery`: +0.040, 95% paired bootstrap [-0.120, +0.180] (50 seeds)
- `stage2:nearest-discovery`: +0.140, 95% paired bootstrap [+0.020, +0.260] (50 seeds)
- `stage2:situational-discovery`: +0.040, 95% paired bootstrap [-0.040, +0.120] (50 seeds)

### 2. `3697c176129d`

Change distance: 9.0

```json
{
  "feed": {
    "b": 45
  },
  "spawn": {
    "1": {
      "a": 12
    },
    "2": {
      "a": 12
    }
  }
}
```

| Policy and stage | Clear rate | Early starvation | Win steps (median) | Win LP (median) |
| --- | ---: | ---: | ---: | ---: |
| stage1:discovery | 0.140 | 0.180 | 539.0 | 46.0 |
| stage1:nearest | 0.140 | 0.180 | 509.0 | 76.0 |
| stage1:situational | 0.100 | 0.180 | 597.0 | 76.0 |
| stage2:discovery | 0.000 | 0.200 | None | None |
| stage2:nearest | 0.160 | 0.200 | 564.0 | 71.0 |
| stage2:situational | 0.020 | 0.200 | 888.0 | 92.0 |

Paired clear-rate differences:

- `stage1:nearest-discovery`: +0.000, 95% paired bootstrap [-0.120, +0.120] (50 seeds)
- `stage1:situational-discovery`: -0.040, 95% paired bootstrap [-0.120, +0.040] (50 seeds)
- `stage2:nearest-discovery`: +0.160, 95% paired bootstrap [+0.060, +0.260] (50 seeds)
- `stage2:situational-discovery`: +0.020, 95% paired bootstrap [+0.000, +0.060] (50 seeds)
