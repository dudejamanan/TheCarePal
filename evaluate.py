"""Hand-checked fixtures and a reproducible first-place exposure audit."""

from collections import Counter, deque
from statistics import mean

from data import generate
from learning import feedback, held_out_metrics, train
from matching import WEIGHTS, distance_km, eligible, features, recommend

RECENT_WINDOW = 20


def hand_checked():
    request = {
        "city": "Pune", "lat": 18.52, "lon": 73.86, "skill": "Dementia care",
        "language": "Marathi", "shift": "Morning",
    }
    ideal = {
        "id": "A", "city": "Pune", "lat": 18.52, "lon": 73.86,
        "skills": ["Dementia care"], "languages": ["Marathi"],
        "availability": ["Morning"], "years": 12, "rating": 5,
    }
    nearby = {**ideal, "id": "B", "lat": 18.55}

    def check(name, expected, candidates, **overrides):
        result = recommend({**request, **overrides}, candidates)
        actual = [match["nurse"]["id"] for match in result["matches"]]
        assert actual == expected, f"{name}: expected {expected}, got {actual}"
        print(f"PASS  {name}")
        return result

    invalid = [
        {**ideal, "id": "C", "skills": ["Elderly care"]},
        {**ideal, "id": "D", "languages": ["Hindi"]},
        {**ideal, "id": "E", "availability": ["Afternoon"]},
        {**ideal, "id": "F", "city": "Mumbai"},
    ]
    check("Each failed requirement independently excludes a nurse", ["A"], [ideal, *invalid])
    check("Empty pool returns no matches", [], invalid)
    base = check("Equal qualifications favor the nearer nurse", ["A", "B"], [nearby, ideal])
    assert base["matches"][0]["score"] == 85
    continuity = check("A small distance disadvantage is outweighed by continuity",
                       ["B", "A"], [nearby, ideal], previous_nurse_id="B")
    assert continuity["matches"][0]["returning_nurse"]
    check("Continuity cannot override a failed requirement", ["A"], [invalid[0], ideal],
          previous_nurse_id="C")
    check("Rating resolves equal distance and experience", ["A", "B"],
          [{**ideal, "id": "B", "rating": 4}, ideal])
    check("Experience resolves equal distance and rating", ["A", "B"],
          [{**ideal, "id": "B", "years": 5}, ideal])
    ties = [{**ideal, "id": letter} for letter in "GFEDCBA"]
    result = check("Exact ties use nurse ID and only five matches return", list("ABCDE"), ties)
    assert result["eligible_count"] == 7
    adjusted = recommend(request, [ideal, {**ideal, "id": "B"}], {"A": 10})
    assert [item["nurse"]["id"] for item in adjusted["matches"]] == ["B", "A"]
    assert adjusted["matches"][1]["score"] == 77
    print("PASS  Recent exposure breaks parity and the adjustment caps at eight points")


def replay(nurses, requests, adjust=False, *, weights=None):
    recent = deque(maxlen=RECENT_WINDOW)
    firsts = Counter()
    opportunities = Counter()
    shortlists = Counter()
    quality = []
    for request in requests:
        opportunities.update(
            nurse["id"] for nurse in nurses
            if eligible(request, nurse)
        )
        matches = recommend(request, nurses, Counter(recent) if adjust else None,
                            weights=weights)["matches"]
        if not matches:
            continue
        first = matches[0]
        first_id = first["nurse"]["id"]
        recent.append(first_id)
        firsts[first_id] += 1
        shortlists.update(match["nurse"]["id"] for match in matches)
        nurse = first["nurse"]
        values = features(request, nurse, distance_km(request, nurse))
        quality.append(sum(value * weight for value, weight in zip(values, WEIGHTS.values())))

    covered = sum(firsts.values())
    assert covered
    assert all(firsts[nurse] <= opportunities[nurse] for nurse in firsts)
    most_firsts = max(firsts.values())
    always_first_when_eligible = sorted(
        nurse for nurse, eligible in opportunities.items() if eligible >= 5 and firsts[nurse] == eligible
    )
    return {
        "requests with matches": covered,
        "nurses with eligibility": len(opportunities),
        "unique first-ranked nurses": len(firsts),
        "unique shortlisted nurses": len(shortlists),
        "most first ranks": most_firsts,
        "largest first-rank share": f"{most_firsts / covered:.1%}",
        "always first when eligible (at least 5 opportunities)": always_first_when_eligible,
        "mean default score of first-ranked nurse": round(mean(quality), 2),
    }


if __name__ == "__main__":
    hand_checked()
    nurses, requests = generate()
    assert len(nurses) == 200 and len(requests) == 100
    baseline = replay(nurses, requests, adjust=False)
    adjusted = replay(nurses, requests, adjust=True)
    learned_weights = train(nurses)
    learned = replay(nurses, requests, weights=learned_weights)
    for name, result in (("Default API ranking", baseline), ("Recent exposure adjustment", adjusted),
                         ("Learned ranking", learned)):
        print(f"\n{name}")
        for metric, value in result.items():
            print(f"  {metric}: {value}")
        assert result["most first ranks"] < result["requests with matches"]
        assert not result["always first when eligible (at least 5 opportunities)"]
    holdout = list(feedback(nurses, (201, 202)))
    print(f"\nHeld-out simulated preferences ({len(holdout)} pairs)")
    print("  Default:", held_out_metrics(holdout, WEIGHTS))
    print("  Learned:", held_out_metrics(holdout, learned_weights))

    # A stream with identical requirements tests concentration hidden by varied requests.
    repeated = [requests[0]] * 30
    print("\nRepeated request stress test (30 identical recommendations)")
    for adjust in (False, True):
        result = replay(nurses, repeated, adjust)
        print(f"  Exposure adjustment {adjust}: {result['unique first-ranked nurses']} unique "
              f"first-ranked nurses, {result['largest first-rank share']} largest share")
