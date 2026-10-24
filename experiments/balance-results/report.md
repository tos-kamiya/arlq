# ARLQ static balance tuning report

The policies use mapped terrain and observed entities. `discovery` means the order in which the player first saw each monster; it is not internal spawn order. Unknown monster stats are not read by a policy.

Evaluated 7400 plays in 4549.0 seconds. Candidates are proposals; no game constants were modified.

Finite policies, seeds, and budgets do not prove optimality. Spawn changes also change random-number consumption, so equal seeds do not guarantee identical layouts.

## Final candidates

### 1. `6879dca3c79c`

Change distance: 38.0

```json
{
  "feed": {
    "a": 8,
    "b": 50,
    "c": 10,
    "d": 50
  },
  "spawn": {
    "1": {
      "A": 2,
      "a": 18,
      "b": 8,
      "c": 5,
      "d": 3
    },
    "2": {
      "A": 2,
      "C": 1,
      "a": 12,
      "b": 6,
      "c": 5,
      "d": 5
    }
  }
}
```

| Policy and stage | Clear rate | Early starvation | Win steps (median) | Win LP (median) |
| --- | ---: | ---: | ---: | ---: |
| stage1:discovery | 0.390 | 0.110 | 649.0 | 65.0 |
| stage1:food | 0.600 | 0.090 | 701.0 | 60.0 |
| stage1:growth | 0.560 | 0.090 | 625.0 | 70.0 |
| stage1:nearest | 0.650 | 0.080 | 630.0 | 70.0 |
| stage1:situational | 0.560 | 0.090 | 594.0 | 67.0 |
| stage2:discovery | 0.110 | 0.440 | 763.0 | 40.0 |
| stage2:food | 0.200 | 0.390 | 757.0 | 59.0 |
| stage2:growth | 0.180 | 0.400 | 699.0 | 69.0 |
| stage2:nearest | 0.310 | 0.380 | 718.0 | 68.0 |
| stage2:situational | 0.170 | 0.400 | 673.0 | 25.0 |

Paired clear-rate differences:

- `stage1:food-discovery`: +0.210, 95% paired bootstrap [+0.110, +0.310] (100 seeds)
- `stage1:growth-discovery`: +0.170, 95% paired bootstrap [+0.060, +0.270] (100 seeds)
- `stage1:nearest-discovery`: +0.260, 95% paired bootstrap [+0.150, +0.370] (100 seeds)
- `stage1:situational-discovery`: +0.170, 95% paired bootstrap [+0.060, +0.280] (100 seeds)
- `stage2:food-discovery`: +0.090, 95% paired bootstrap [+0.020, +0.160] (100 seeds)
- `stage2:growth-discovery`: +0.070, 95% paired bootstrap [+0.000, +0.160] (100 seeds)
- `stage2:nearest-discovery`: +0.200, 95% paired bootstrap [+0.110, +0.300] (100 seeds)
- `stage2:situational-discovery`: +0.060, 95% paired bootstrap [-0.010, +0.140] (100 seeds)

### 2. `18e1f37c5f10`

Change distance: 27.0

```json
{
  "feed": {
    "a": 8,
    "b": 45,
    "c": 10,
    "d": 45
  },
  "spawn": {
    "1": {
      "A": 1,
      "a": 16,
      "b": 9,
      "c": 2,
      "d": 5
    },
    "2": {
      "A": 2,
      "C": 1,
      "a": 10,
      "b": 6,
      "c": 4,
      "d": 2
    }
  }
}
```

| Policy and stage | Clear rate | Early starvation | Win steps (median) | Win LP (median) |
| --- | ---: | ---: | ---: | ---: |
| stage1:discovery | 0.370 | 0.250 | 675.0 | 72.0 |
| stage1:food | 0.510 | 0.170 | 705.0 | 72.0 |
| stage1:growth | 0.500 | 0.170 | 709.0 | 72.0 |
| stage1:nearest | 0.580 | 0.170 | 694.0 | 78.0 |
| stage1:situational | 0.480 | 0.170 | 693.0 | 77.0 |
| stage2:discovery | 0.090 | 0.510 | 633.0 | 58.0 |
| stage2:food | 0.120 | 0.470 | 649.0 | 61.0 |
| stage2:growth | 0.130 | 0.470 | 568.0 | 64.0 |
| stage2:nearest | 0.150 | 0.450 | 590.0 | 59.0 |
| stage2:situational | 0.160 | 0.480 | 643.0 | 58.0 |

Paired clear-rate differences:

- `stage1:food-discovery`: +0.140, 95% paired bootstrap [+0.030, +0.250] (100 seeds)
- `stage1:growth-discovery`: +0.130, 95% paired bootstrap [+0.020, +0.240] (100 seeds)
- `stage1:nearest-discovery`: +0.210, 95% paired bootstrap [+0.110, +0.310] (100 seeds)
- `stage1:situational-discovery`: +0.110, 95% paired bootstrap [+0.010, +0.210] (100 seeds)
- `stage2:food-discovery`: +0.030, 95% paired bootstrap [-0.030, +0.090] (100 seeds)
- `stage2:growth-discovery`: +0.040, 95% paired bootstrap [-0.010, +0.090] (100 seeds)
- `stage2:nearest-discovery`: +0.060, 95% paired bootstrap [-0.010, +0.140] (100 seeds)
- `stage2:situational-discovery`: +0.070, 95% paired bootstrap [+0.000, +0.140] (100 seeds)

### 3. `d422e25c9d45`

Change distance: 34.0

```json
{
  "feed": {
    "a": 10,
    "b": 35,
    "c": 8,
    "d": 30
  },
  "spawn": {
    "1": {
      "A": 2,
      "a": 12,
      "b": 9,
      "c": 4,
      "d": 5
    },
    "2": {
      "A": 1,
      "C": 1,
      "a": 18,
      "b": 5,
      "c": 2,
      "d": 5
    }
  }
}
```

| Policy and stage | Clear rate | Early starvation | Win steps (median) | Win LP (median) |
| --- | ---: | ---: | ---: | ---: |
| stage1:discovery | 0.240 | 0.270 | 699.0 | 68.0 |
| stage1:food | 0.460 | 0.200 | 681.0 | 79.0 |
| stage1:growth | 0.360 | 0.220 | 751.0 | 79.0 |
| stage1:nearest | 0.550 | 0.200 | 622.0 | 76.0 |
| stage1:situational | 0.330 | 0.230 | 638.0 | 75.0 |
| stage2:discovery | 0.050 | 0.140 | 701.0 | 28.0 |
| stage2:food | 0.070 | 0.140 | 734.0 | 46.0 |
| stage2:growth | 0.040 | 0.140 | 803.0 | 69.0 |
| stage2:nearest | 0.100 | 0.140 | 732.0 | 20.0 |
| stage2:situational | 0.060 | 0.140 | 569.0 | 51.0 |

Paired clear-rate differences:

- `stage1:food-discovery`: +0.220, 95% paired bootstrap [+0.110, +0.320] (100 seeds)
- `stage1:growth-discovery`: +0.120, 95% paired bootstrap [+0.030, +0.210] (100 seeds)
- `stage1:nearest-discovery`: +0.310, 95% paired bootstrap [+0.200, +0.420] (100 seeds)
- `stage1:situational-discovery`: +0.090, 95% paired bootstrap [-0.020, +0.200] (100 seeds)
- `stage2:food-discovery`: +0.020, 95% paired bootstrap [-0.050, +0.090] (100 seeds)
- `stage2:growth-discovery`: -0.010, 95% paired bootstrap [-0.070, +0.050] (100 seeds)
- `stage2:nearest-discovery`: +0.050, 95% paired bootstrap [-0.020, +0.120] (100 seeds)
- `stage2:situational-discovery`: +0.010, 95% paired bootstrap [-0.050, +0.070] (100 seeds)
