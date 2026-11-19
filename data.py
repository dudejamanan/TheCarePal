"""Reproducible, entirely synthetic home-care profiles and requests."""

import json
import random
from pathlib import Path

CITIES = {
    "Pune": (18.5204, 73.8567),
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.6139, 77.2090),
}
SKILLS = ("Elderly care", "Dementia care", "Baby care", "Post-surgery care",
          "Physiotherapy support")
LANGUAGES = ("Hindi", "English", "Marathi", "Punjabi")
SHIFTS = ("Morning", "Afternoon", "Overnight")
CITY_LANGUAGES = {
    "Pune": ("Marathi", "Hindi", "English"),
    "Mumbai": ("Hindi", "Marathi", "English"),
    "Delhi": ("Hindi", "Punjabi", "English"),
}


def generate(seed=42):
    rng = random.Random(seed)

    def location(city):
        latitude, longitude = CITIES[city]
        return {
            "lat": round(latitude + rng.uniform(-0.095, 0.095), 5),
            "lon": round(longitude + rng.uniform(-0.095, 0.095), 5),
        }

    nurses = []
    for index in range(200):
        city = tuple(CITIES)[index % len(CITIES)]
        nurses.append({
            "id": f"N{index + 1:03}",
            "city": city,
            **location(city),
            "skills": rng.sample(SKILLS, rng.choices([1, 2, 3], [2, 5, 2])[0]),
            "languages": rng.sample(CITY_LANGUAGES[city], rng.choice([1, 2, 2, 3])),
            "availability": rng.sample(SHIFTS, rng.choice([1, 2, 2, 3])),
            "years": rng.randint(1, 19),
            "rating": round(rng.triangular(3.4, 5, 4.8), 1),
        })

    requests = []
    for index in range(100):
        city = rng.choice(tuple(CITIES))
        skill = rng.choice(SKILLS)
        language = rng.choice(CITY_LANGUAGES[city])
        shift = rng.choice(SHIFTS)
        previous_candidates = [
            nurse["id"] for nurse in nurses
            if nurse["city"] == city and skill in nurse["skills"]
            and language in nurse["languages"] and shift in nurse["availability"]
        ]
        previous = rng.choice(previous_candidates) if previous_candidates and rng.random() < .32 else None
        requests.append({
            "id": f"R{index + 1:03}",
            "city": city,
            **location(city),
            "skill": skill,
            "language": language,
            "shift": shift,
            "previous_nurse_id": previous,
        })
    return nurses, requests


if __name__ == "__main__":
    output = Path("generated")
    output.mkdir(exist_ok=True)
    nurses, requests = generate()
    for name, records in (("nurses", nurses), ("requests", requests)):
        (output / f"{name}.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(nurses)} nurses and {len(requests)} care requests to {output}/")
