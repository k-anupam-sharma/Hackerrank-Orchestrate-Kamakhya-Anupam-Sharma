# Protected-expense analysis

## Scope

This analysis uses the 21 uncapped public sample cases only. An uncapped label gives an indirect constraint: the benchmark minimum baseline would be the profile floor plus the expected safe amount. It does not reveal the benchmark's individual event schedule.

## Observations

Nineteen cases have production safe capacity above the benchmark and two have production capacity below it:

| direction | cases | total absolute error | mean absolute error |
|---|---:|---:|---:|
| production too high | 19 | 7,708,292.49 | 405,699.60 |
| production too low | 2 | 1,077.14 | 538.57 |

The 19 high cases commonly have historical activity in one or more protected variable categories: groceries, transport, or healthcare. The fixed-only protected profiles (for example housing/utilities/education) also occur, so protected-variable activity is an association rather than a proof of a benchmark rule.

The two low cases prevent a simple “reserve more protected spending” policy:

- request_15 already reaches a EUR 713.25 production baseline minimum, below its EUR 1,200 floor, while the label implies EUR 1,283.05.
- request_19 is INR 994.09 below the label, despite having a blank image-backed historical grocery row.

## Candidate policy experiment

All candidates were analysis-only. They use the existing source-backed baseline and never inspect expected labels while generating a reserve. Metrics compare the final independently calculated capacity to the labels afterwards.

| model | rule | exact / 21 | MAE | median absolute error | max absolute error |
|---|---|---:|---:|---:|---:|
| A | current recurring-stream baseline | 0 | 367,112.84 | 4,268.49 | 4,291,200.00 |
| B | add latest historical non-recurring protected-category amount on days 30 and 60 | 0 | 365,866.39 | 4,268.49 | 4,291,200.00 |
| C | add median historical non-recurring protected-category amount on days 30 and 60 | 0 | 365,620.56 | 2,765.43 | 4,291,200.00 |
| D | add average historical non-recurring protected-category amount on days 30 and 60 | 0 | 365,647.79 | 2,765.43 | 4,291,200.00 |
| E | current model plus confirmed future protected expenses | 0 | 367,112.84 | 4,268.49 | 4,291,200.00 |

Model E is identical to the current forecast because confirmed future protected expenses are already included by the normalized scheduled/pending event treatment.

## Conclusion

The candidate reserves slightly reduce mean error but produce no new exact matches and cannot explain the two under-estimated cases. They also make an unsupported assumption about both amount and date for historical variable spending. The evidence does not support changing production to any candidate model.

The general policy currently supported by the challenge data is therefore: reserve explicit recurring commitments, scheduled obligations, and pending debits; do not fabricate a monthly budget from historical variable purchases. A future change would need a challenge-authoritative variable-essential-spending rule or complete image evidence.
