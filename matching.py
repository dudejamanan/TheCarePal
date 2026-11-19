"""Eligibility, ranking and score explanations for care requests."""

from math import asin, cos, radians, sin, sqrt

WEIGHTS = {"distance": 40, "rating": 27, "experience": 18, "continuity": 15}
EXPOSURE_STEP = 2
EXPOSURE_CAP = 8


def distance_km(first, second):
    lat1, lat2 = radians(first["lat"]), radians(second["lat"])
    dlat = lat2 - lat1
    dlon = radians(second["lon"] - first["lon"])
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(min(1.0, a)))


def eligible(request, nurse):
    return (nurse["city"] == request["city"]
            and request["skill"] in nurse["skills"]
            and request["language"] in nurse["languages"]
            and request["shift"] in nurse["availability"])


def features(request, nurse, distance):
    return (max(0, 1 - distance / 25), nurse["rating"] / 5,
            min(nurse["years"] / 12, 1),
            int(nurse["id"] == request.get("previous_nurse_id")))


def recommend(request, nurses, first_place_history=None, *, weights=None):
    weights = WEIGHTS if weights is None else weights
    history = first_place_history or {}
    candidates = []
    for nurse in nurses:
        if not eligible(request, nurse):
            continue

        distance = distance_km(request, nurse)
        returning = nurse["id"] == request.get("previous_nurse_id")
        recent_firsts = history.get(nurse["id"], 0)
        proximity, rating, experience, continuity = features(request, nurse, distance)
        parts = [
            ("Distance", weights["distance"] * proximity,
             weights["distance"], f"{distance:.1f} km straight-line distance"),
            ("Rating", weights["rating"] * rating,
             weights["rating"], f"{nurse['rating']:.1f} out of 5"),
            ("Experience", weights["experience"] * experience,
             weights["experience"], f"{nurse['years']} years, scoring capped at 12"),
            ("Continuity", weights["continuity"] * continuity,
             weights["continuity"], "Previously cared for this patient" if returning else "New to this patient"),
            ("Recent first placements", -min(EXPOSURE_CAP, EXPOSURE_STEP * recent_firsts),
             EXPOSURE_CAP, f"Ranked first {recent_firsts} times in the recent history"),
        ]
        score = max(0, sum(part[1] for part in parts))
        candidates.append({
            "nurse": nurse,
            "distance_km": round(distance, 2),
            "score": round(score, 2),
            "returning_nurse": returning,
            "eligibility": [request["skill"], request["language"], request["shift"], request["city"]],
            "score_breakdown": [
                {"factor": label, "points": round(points, 2), "max_points": maximum, "reason": reason}
                for label, points, maximum, reason in parts
            ],
        })

    candidates.sort(key=lambda match: (
        -match["score"], match["distance_km"], match["nurse"]["id"]
    ))
    matches = candidates[:5]
    for rank, match in enumerate(matches, 1):
        match["rank"] = rank
        match["explanation"] = (
            f"Meets all requirements. Ranked #{rank} by adjusted score "
            f"({match['score']:.2f}/100). Ties use distance, then nurse ID."
        )
    return {"request": request, "eligible_count": len(candidates), "matches": matches}
