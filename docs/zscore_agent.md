# Z-score agent

The deterministic Z-score agent accepts:

- applicant district
- course of study
- student Z-score

It retrieves every available academic year for that course and district from
the read-only SQLite database. Results are grouped by institution and analyzed
with ordinary Python statistics.

### Use from Python

```python
from campusyamu.agents.zscore import ZScoreAgent

agent = ZScoreAgent()
result = agent.analyze(
    district="Gampaha",
    course="Medicine",
    z_score=2.10,
)
```

The response contains all numeric and NQC history, statistical summaries,
`historical_alignment`, and `evidence_confidence`. Historical alignment is a
comparison with calibrated historical cutoffs, not an admission probability.

### Run from the command line

```bash
uv run python -m campusyamu.agents.zscore.cli \
  --district Gampaha \
  --course Medicine \
  --z-score 2.10
```

Add `--json` for the complete structured response.

The database currently has no syllabus column. If a future dataset contains old
and new syllabus cutoffs, add syllabus as an explicit fourth input rather than
guessing it.
