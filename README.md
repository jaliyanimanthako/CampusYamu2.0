# CampusYamu agents

This repository contains focused components for the larger CampusYamu agentic
system.

## Z-score agent

The deterministic Z-score agent accepts:

- applicant district
- course of study
- student Z-score

It retrieves every available academic year for that course and district from
the read-only SQLite database. Results are grouped by institution and analyzed
with ordinary Python statistics.

### Use from Python

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

### Run from the command line

```bash
python -m zscore_agent.cli \
  --district Gampaha \
  --course Medicine \
  --z-score 2.10
```

Add `--json` for the complete structured response.

The database currently has no syllabus column. If a future dataset contains old
and new syllabus cutoffs, add syllabus as an explicit fourth input rather than
guessing it.

## Career-trends agent

The career-trends agent collects current occupational evidence relevant to a
student's study stream. It uses Firecrawl's v2 scrape endpoint to extract a
fixed JSON schema from a curated source registry. Python then merges independent
sources, detects disagreement, ranks trend direction, and preserves a URL for
every claim.

```python
from career_trends_agent import CareerTrendRequest, CareerTrendsAgent

agent = CareerTrendsAgent()
result = agent.research(
    CareerTrendRequest(
        study_stream="Physical Science",
        subjects=("Combined Mathematics", "Physics", "Chemistry"),
        region="Sri Lanka",
    )
)
```

Set `FIRECRAWL_API_KEY` before creating the live agent. Successful extraction is
cached in memory for 24 hours, and sources are fetched concurrently. Pass
`refresh=True` to bypass the cache.

The default registry uses authoritative global sources from the World Economic
Forum, ILO, and OECD. Regional additions include the U.S. Bureau of Labor
Statistics or Sri Lanka's Department of Census and Statistics and TVEC. It does
not perform unrestricted crawling or use news headlines as career evidence.

AI exposure is kept separate from employment direction. Exposure can mean that
tasks change; it does not prove that an occupation will disappear. Results are
evidence inputs for a student decision, not guarantees or automatic course
recommendations.

## Structure

- `zscore_agent/`: read-only historical cutoff analysis
- `career_trends_agent/`: Firecrawl collection and career-signal aggregation
- `tests/`: one end-to-end behavior test for each agent

## Test

```bash
python -m unittest discover -s tests -v
```
