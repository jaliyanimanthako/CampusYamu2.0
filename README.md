# CampusSelection Z-score agent

This package is a deterministic component for a larger agentic system. Its
complete input is:

- applicant district
- course of study
- student Z-score

It retrieves every available academic year for that course and district from
the read-only SQLite database. Results are grouped by institution and analyzed
with ordinary Python statistics.

## Use from Python

```python
from zscore_agent import ZScoreAgent

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

## Run from the command line

```bash
python -m zscore_agent.cli \
  --district Gampaha \
  --course Medicine \
  --z-score 2.10
```

Add `--json` for the complete structured response.

## Modules

- `agent.py`: three-input public interface
- `repository.py`: read-only SQLite retrieval
- `analysis.py`: workflow orchestration
- `statistics.py`: descriptive and robust statistics
- `forecasting.py`: pooled backtests and calibrated uncertainty
- `assessment.py`: alignment and evidence-confidence rules
- `reporting.py`: institution-level output construction
- `models.py`: request and internal data models
- `cli.py`: command-line adapter

The database currently has no syllabus column. If a future dataset contains old
and new syllabus cutoffs, add syllabus as an explicit fourth input rather than
guessing it.

## Test

The project keeps one end-to-end test script that checks the public output:

```bash
python -m unittest tests/test_zscore_agent.py -v
```
