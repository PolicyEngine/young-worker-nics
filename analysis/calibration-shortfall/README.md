# Step 8 misses its own calibration target

The targeted variant (Step 8, `--lfs-path`) restricts the relief to employed
21-24-year-olds who were NEET within the past year. It imputes each
employee's chance of being such a recent entrant, then scales those chances
so their weighted mean equals the entrant share measured in the LFS panels.
The published results miss that share.

## What the published results show

`published_shortfall.py` reads `data/young_worker_nics_results.json` and
nothing else ([output](published_shortfall_output.json)).

| | Published | Target | Gap |
| --- | ---: | ---: | ---: |
| Share of employed 21-24s | 12.18% | 12.74% | -4.3% |
| Targeted employees | 235,627 | 246,338 | 10,712 |

The target is `targeted.entrant_share` (12.736%) times the 1,934,192
employed 21-24-year-olds in `reform.static`. Hitting it takes 4.5% more
targeted employees than the results publish.

## Why

Step 8 (`neet.py` as of 30f5b65, unchanged until this PR) passes a float 0/1 target, `was_neet_recently`, to
microimpute's `autoimpute(..., models=[QRF])`. For a 0/1 target, microimpute
fits a random-forest classifier and writes each receiver's predicted class,
0 or 1, into `receiver_data`; this call returns no probabilities. `_calibrate` then
scales those values by `target / mean` and clips them at 1. Whenever the
share of 1s falls short of the target, the factor exceeds 1, the clip returns
every 1 to 1, and the share stays where the labels left it: 12.18% in the
published run.

An earlier run (e015103, 2026-06-12, before 6b579b4 added the Microcosm
backend) made the same call and hit its target to within 3e-17. Its labels
overshot the target, so the factor fell below 1 and nothing clipped. That run
still counted a discrete subsample (every employee labelled 1, each at the
same fraction), where the methods text describes a probability for each
employee.

## What the fix changes

- **Probabilities.** `_classifier_neet_probabilities` fits Microcosm's
  `CategoricalClassifier` (microcosm-fit) and takes each employee's
  probability of being an entrant from `predict_proba`.
- **Calibration.** `_calibrate` finds the one factor `f` for which the
  weighted mean of `min(f * p, 1)` equals the target. When nothing clips, `f`
  is the plain ratio and the output matches the published formula bit for
  bit. When the target exceeds the most any factor can reach (the weighted
  share of employees with a nonzero probability), it raises instead of
  publishing a shortfall. On 0/1 labels below the target it therefore
  refuses, which is why rescaling alone can't repair the published run.
- **Weights.** The classifier fits on donor weights normalised to mean 1.
  Its boosted half divides weighted gradient sums by weighted hessian sums
  plus a fixed L2 penalty, so without normalising, the penalty's pull, and
  the probabilities, depend on the weights' arbitrary scale.

`tests/test_calibration.py` states the calibration's invariants and checks
them with Hypothesis: bounds, hitting a reachable target, one factor, order,
weight-scale invariance, idempotence, monotonicity in the target, and the
bit-for-bit match with the published formula where nothing clips.

## How the published figures move

The target fixes only the targeted count in advance: 246,338. The cost depends on
which employees the probabilities pick out, so it takes a rerun with the
licensed panels. These scenarios show the range the published outputs
already imply (static cost, £bn):

| Scenario | Cost |
| --- | ---: |
| Published | 0.773 |
| Same targeted mix, scaled up to the target count | 0.809 |
| Missing 10,712 spread evenly over the employees the labels left at 0 | 0.811 |
| Published earnings-banded sensitivity | 0.719 |
| Every employed 21-24-year-old at the entrant share | 0.849 |

The first two scenarios hold the mix fixed; a rerun won't. The published
breakdowns by age, gender, country and region count only the employees the
classifier labelled 1, so they move too. Every Step 8 figure (pass-through,
employment and the public-sector split) scales from the same probabilities.

## Synthetic demonstration

`synthetic_demo.py` builds LFS-like donors and FRS-like receivers with a
known entrant probability, then runs the published path and the fix
([output](synthetic_demo_output.json)). No survey record enters it.

| | Published path (microimpute 3.1.1) | Fix |
| --- | ---: | ---: |
| Distinct values among treated employees | 2 (0 and 1) | 1,043 |
| Share after calibration | 2.70% | 5.98% |
| Target | 5.98% | 5.98% |

The solved calibration refuses the published path's labels: only 2.70% of
treated weight holds a nonzero value, below the 5.98% target. The synthetic
entrants are rarer than the LFS ones, so the synthetic shortfall (55%) runs
far larger than the published one (4.3%).

On the weights:

- Scaling every donor weight 1,000-fold moves the classifier's probabilities
  by up to 0.008 on raw weights, and by 3e-16 after normalising.
- Over five fresh draws, normalising recovers the true probabilities at least
  as well: root-mean-square error 0.0154 (sd 0.0013) against 0.0161 (sd 0.0017)
  on raw weights.

microimpute 1.15.1 also returns only 0 and 1 for this call
(`synthetic_demo_output_microimpute_1.15.1.json`), with a label share of
3.06% against 2.70% under 3.1.1. Releases before 2.0.3 resample the donors by
weight and fit the forest unweighted, while later ones pass the weights to the
forest, so the two label sets differ. Also, microimpute 3.1.1 reports
`microimpute.__version__` as 1.1.2, so read its version from the package
metadata.

## Reproduce

```bash
python analysis/calibration-shortfall/published_shortfall.py
uv pip install -e ".[lfs,dev]" "microimpute==3.1.1"
python analysis/calibration-shortfall/synthetic_demo.py

# Part A under microimpute 1.15.1, installed alone ahead of the environment
uv pip install --target "$TMPDIR/mi-1.15.1" --no-deps "microimpute==1.15.1"
PYTHONPATH="$TMPDIR/mi-1.15.1" python analysis/calibration-shortfall/synthetic_demo.py
```

The demo's output came from Python 3.14 with microimpute 3.1.1,
scikit-learn 1.8.0, quantile-forest 1.4.2 and microcosm-fit at dc00d158. uv
installed the PyPI packages with `--exclude-newer 2026-06-22`, two days after
the 2026-06-20 run (6b579b4) behind the published targeted count. The 1.15.1
output came from the same environment with only microimpute swapped; every
section that doesn't call microimpute matches the 3.1.1 output exactly.
