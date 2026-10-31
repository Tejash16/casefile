# Eval: planted cases

6 cases x 3 runs; run 1 live, later runs from the Crustdata cache (`--offline`). A case passes only if all 3 runs are correct. Total 948 s.

| Case | Fakes caught (per run) | Honest businesses turned away | Allegations correct | Precision | Citation validity | Unsubstantiated rate | Log verifies | Wall time (s) | Credits | Result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| career_overlap | 1/1, 1/1, 1/1 | 0 | 3/3 | 50% | 100% | 43% | 3/3 | 53.8 | 6.74 | **pass 3/3** |
| clean_controls | 0/0, 0/0, 0/0 | 0 | 0/0 | n/a | 100% | 62% | 3/3 | 51.6 | 2.68 | **pass 3/3** |
| duplicate_billing | 1/1, 1/1, 1/1 | 0 | 3/3 | 100% | 100% | 68% | 3/3 | 49.0 | 0 | **pass 3/3** |
| false_lead | 0/0, 0/0, 0/0 | 0 | 3/3 | n/a | 100% | 57% | 3/3 | 50.2 | 0 | **pass 3/3** |
| shared_office_honest | 0/0, 0/0, 0/0 | 0 | 0/0 | n/a | 100% | 65% | 3/3 | 50.8 | 4.06 | **pass 3/3** |
| shell_vendor | 1/1, 1/1, 1/1 | 0 | 3/3 | 33% | 100% | 48% | 3/3 | 58.8 | 0 | **pass 3/3** |

**Fakes caught**: planted Substantiated allegations found Substantiated, per run. **Honest businesses turned away**: must-clear vendors with any Substantiated finding (target 0). **Precision**: Substantiated findings that match a planted allegation. **Citation validity**: share of cited sentences whose evidence ids resolve, whose payload hash verifies and whose quote is literally in the payload.
