# TheCarePal Nurse to Patient Matching

AI-05 internship worklet. Care Match ranks available synthetic nurses for home-care requests in Pune, Mumbai and Delhi. The demo opens with a sample request and shows the shortlist, a score breakdown for each nurse, and a schematic map.

## Run locally

Install Python 3.10 or later. From the repository root, run:

```sh
python app.py
```

Open [Care Match](http://127.0.0.1:8015). Pick a sample, click **Find matches**, and expand **Why this match?** to inspect the points. **View JSON response** opens the same result the UI used. On Windows, use `py -3` if that is how Python is installed.

No package installation, API keys, accounts or internet connection are required. The server binds to localhost. To change the port, set the `PORT` environment variable before starting the server. `.env.example` shows the variable and its default. The demo reads the shell environment directly.

```sh
python data.py
python evaluate.py
python learning.py
```

The first command exports 200 nurse profiles and 100 care requests to `generated/`. The second runs the hand-checked cases, fairness replay, and held-out preference evaluation. The third prints the fitted weights and preference metrics. The exported sample data matches the service's seeded dataset. All profiles, requests, coordinates, ratings, and feedback are synthetic.

## Design decisions

- Apply eligibility filters before scoring so a high score cannot compensate for a missing skill, language, or shift.
- Restrict matches to the requested city as an explicit service-area assumption.
- Use four normalized, additive factors so operations staff can inspect the contribution of distance, rating, experience, and continuity.
- Cap experience at 12 years and reduce distance points to zero at 25 km. These are configurable scoring assumptions in the code.
- Keep default and learned weights selectable so the learned model can be compared against a reproducible baseline.
- Use Python's standard library and a small browser interface to make local setup a single command with zero runtime API costs.
- Measure first-place exposure separately from assignment workload. The current demo recommends nurses, and a future booking system would track actual shifts and hours.

## API

| Method and path | Purpose |
| --- | --- |
| `GET /api/requests` | List the 100 sample requests |
| `GET /api/matches/R001` | Rank nurses for a saved request |
| `POST /api/matches` | Rank nurses for a custom synthetic request |

```sh
curl http://127.0.0.1:8015/api/matches/R001
curl "http://127.0.0.1:8015/api/matches/R001?ranking=learned"
```

PowerShell example for a custom request:

```powershell
$body = @{
    city = "Pune"
    lat = 18.52
    lon = 73.86
    skill = "Dementia care"
    language = "Marathi"
    shift = "Morning"
    previous_nurse_id = $null
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8015/api/matches" -Method Post -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 8
```

The response contains the normalized request, `eligible_count`, and zero to five ranked `matches`. Each match contains the profile, Haversine distance, score, reasons and points by factor, and the requirements it satisfied. An empty shortlist returns HTTP 200 with `matches: []`. Invalid inputs return 400, an unknown saved request returns 404, a body over 4 KB returns 413, and the wrong content type returns 415.

## Ranking

Use **Ranking method** in the browser to switch between default and learned weights. Both match endpoints accept `?ranking=learned`; their JSON also identifies the mode and weights used. The method applies after the same eligibility filter in both modes.

First filter by exact required skill, requested language, shift availability, and same city. Then score each eligible nurse:

| Factor | Maximum | Calculation |
| --- | ---: | --- |
| Distance | 40 | `40 × max(0, 1 − distance_km / 25)` |
| Rating | 27 | `27 × rating / 5` |
| Experience | 18 | `18 × min(years / 12, 1)` |
| Continuity | 15 | 15 points when the eligible nurse previously cared for this patient |

Sort by score rounded to two decimals, then by distance rounded to two decimals, then by nurse ID. Each result displays the component points rounded individually, so adding the displayed components may differ from the displayed score by a cent or two. The weights are hand-set: proximity carries the most weight, the experience cap limits the benefit of seniority, and a returning nurse can move up if eligible. Scores are points, with no probability interpretation.

A request describes one recurring shift category. Each request is evaluated independently and the app makes no bookings. The coordinates are synthetic points near the city center, and the map plots relative positions without an external basemap. Haversine distance approximates proximity while actual travel time could change the ordering.

## Evaluation

**Learned weights.** A simulator samples pairs of eligible nurses for historical requests and randomly chooses a preferred candidate using a logistic probability. The simulator assigns its own coefficients to the four features. A nonnegative pairwise logistic model learns from the resulting choices using stochastic gradient descent. Its coefficients are normalized into points that sum to 100, so each recommendation retains a factor-by-factor explanation. Training uses four seeded request streams; evaluation uses two separate streams with the same nurse pool. The demo requests use a third set of seeds.

| Ranking method | Distance | Rating | Experience | Continuity | Holdout accuracy | Log loss |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Default | 40 | 27 | 18 | 15 | 65.52% | 0.6384 |
| Learned | 26.43 | 35.42 | 14.98 | 23.17 | 66.07% | 0.6172 |

Accuracy measures agreement with 4,000 held-out simulated choices, with half credit for ties. Log loss uses the sigmoid of the point difference divided by ten for both modes. These figures measure how closely each mode reproduces the simulator's preferences. The learned mode has no clinical validation.

`evaluate.py` runs nine hand-checked fixtures covering independent eligibility failures, empty results, distance, rating, experience, continuity, stable ties, the top-five limit and a capped exposure adjustment.

The fairness replay treats each first-place recommendation as one exposure. It compares the default API with an experiment that subtracts two points per first place in the preceding 20 matched requests, capped at eight points. The API supports default and learned weights and keeps no exposure history.

| Metric | Default API | Exposure experiment |
| --- | ---: | ---: |
| Requests with at least one match | 100 | 100 |
| Nurses eligible at least once | 192 | 192 |
| Distinct first-ranked nurses | 64 | 67 |
| Distinct shortlisted nurses | 150 | 150 |
| Largest share of first placements | 4% | 4% |
| Nurses ranked first every time they were eligible, with at least five opportunities | 0 | 0 |
| Mean unadjusted score for the first-ranked nurse | 76.05 | 76.02 |

The adjustment spread first places across three additional nurses in this replay while the maximum concentration stayed at 4%. This measures exposure on one synthetic dataset. Fair shift allocation would also need booked hours, eligibility opportunity, cancellations, preferences, and repeated-request stress tests.

The learned mode ranked 66 distinct nurses first and shortlisted 142 across the same 100 requests. Its largest first-place share was 5%. In a stress test of 30 copies of the same request, the default score always returned the same first-ranked nurse. The experimental exposure adjustment spread first place across eight nurses and reduced the largest share to 20%. The adjustment remains a replay experiment because a real dispatch flow needs a durable history of assignments and a clear definition of when to count an exposure.

## Tools and costs

| Tool | Use | Local runtime cost |
| --- | --- | --- |
| Python standard library | Dataset, scoring, evaluation, and HTTP service | Free |
| Browser HTML, CSS, JavaScript and Canvas | Responsive demo and schematic map | Free |
| OpenAI Codex | Interpreted the worklet, drafted and reviewed code and documentation, and ran verification | No model calls or model API charges when running this project |

## What I would build next

1. Model dated shifts, capacity and travel-time buffers, and reserve shifts transactionally after an operations reviewer confirms a match.
2. Collect acceptance, completion and family feedback with consent. Use chronological holdouts to test whether weights trained on observed outcomes improve ranking while preserving eligibility rules.
3. Audit first-place exposure and booked hours relative to each nurse's eligible opportunities. Check coverage by city, skill and language before enabling any exposure adjustment.
4. Add authentication and role-based access for a deployed service. Return only coarse location information to clients so nurse home coordinates remain private.

## Code guide

- `data.py` creates the reproducible dataset.
- `matching.py` filters, scores, ranks and explains each match.
- `learning.py` simulates historical preferences, fits a pairwise ranker, and evaluates held-out comparisons.
- `app.py` serves the local API and demo.
- `evaluate.py` verifies hand-checked cases and measures exposure.
- `web/` contains the responsive interface and map.
