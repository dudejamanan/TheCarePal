"""Fit an interpretable pairwise ranker using simulated preferences."""

from math import exp, log
from random import Random

from data import generate
from matching import WEIGHTS, distance_km, eligible, features

# Separate generators provide independent historical and holdout request contexts
# for the canonical nurse pool. The live demo uses a third request stream.
SIMULATOR_COEFFICIENTS = (2.4, 3.2, 1.3, 2.9)


def probability(value):
    return 1 / (1 + exp(-value))


def feedback(nurses, seeds):
    for seed in seeds:
        _, requests = generate(seed)
        rng = Random(seed + 1000)
        for request in requests:
            candidates = [
                features(request, nurse, distance_km(request, nurse))
                for nurse in nurses if eligible(request, nurse)
            ]
            if len(candidates) < 2:
                continue
            for _ in range(20):
                a, b = rng.sample(candidates, 2)
                delta = tuple(left - right for left, right in zip(a, b))
                preference = probability(sum(x * w for x, w in zip(delta, SIMULATOR_COEFFICIENTS)))
                yield delta, int(rng.random() < preference)


def train(nurses):
    pairs = list(feedback(nurses, (101, 102, 103, 104)))
    coefficients = [0.0] * len(WEIGHTS)
    for _ in range(18):
        for delta, preferred in pairs:
            error = preferred - probability(sum(x * w for x, w in zip(delta, coefficients)))
            coefficients = [max(0, w + .035 * (error * x - .0003 * w))
                            for x, w in zip(delta, coefficients)]
    scaled = [round(100 * w / sum(coefficients), 2) for w in coefficients]
    scaled[-1] = round(100 - sum(scaled[:-1]), 2)
    return dict(zip(WEIGHTS, scaled))


def held_out_metrics(pairs, weights):
    correct = 0.0
    loss = 0.0
    for delta, preferred in pairs:
        prediction = probability(sum(x * w for x, w in zip(delta, weights.values())) / 10)
        if prediction == .5:
            correct += .5
        else:
            correct += (prediction > .5) == preferred
        loss -= log(prediction if preferred else 1 - prediction)
    return {"pair_accuracy": round(correct / len(pairs), 4),
            "log_loss": round(loss / len(pairs), 4)}


if __name__ == "__main__":
    nurses, _ = generate()
    learned = train(nurses)
    holdout = list(feedback(nurses, (201, 202)))
    print(f"Held-out comparisons: {len(holdout)}")
    print(f"Default: {WEIGHTS} | {held_out_metrics(holdout, WEIGHTS)}")
    print(f"Learned: {learned} | {held_out_metrics(holdout, learned)}")
