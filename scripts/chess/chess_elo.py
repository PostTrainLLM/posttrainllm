#!/usr/bin/env python3
"""Dependency-free internal Elo fitting for the Character Chess ladder."""

from __future__ import annotations

import math
import random
from typing import Sequence

ELO_SCALE = 400.0
LOWER_BOUND = -1000.0
UPPER_BOUND = 4000.0


def expected_score(rating: float, opponent_rating: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((opponent_rating - rating) / ELO_SCALE))


def rating_from_score(score: float, opponent_rating: float) -> float:
    if score <= 0:
        return LOWER_BOUND
    if score >= 1:
        return UPPER_BOUND
    return opponent_rating + ELO_SCALE * math.log10(score / (1.0 - score))


def fit_single_rating(observations: Sequence[tuple[float, float]]) -> tuple[float, str]:
    """Fit one rating against fixed opponent ratings by logistic MLE."""
    if not observations:
        raise ValueError("rating fit requires observations")
    score_sum = sum(score for _, score in observations)
    if score_sum == 0:
        return LOWER_BOUND, "left-censored"
    if score_sum == len(observations):
        return UPPER_BOUND, "right-censored"
    low, high = LOWER_BOUND, UPPER_BOUND
    for _ in range(100):
        middle = (low + high) / 2
        residual = sum(score - expected_score(middle, opponent) for opponent, score in observations)
        if residual > 0:
            low = middle
        else:
            high = middle
    return (low + high) / 2, "finite"


def bootstrap_single_rating(
    observations: Sequence[tuple[float, float]],
    *,
    samples: int,
    confidence: float,
    seed: int,
) -> list[float]:
    if samples < 100:
        raise ValueError("rating bootstrap requires at least 100 samples")
    rng = random.Random(seed)
    estimates = []
    for _ in range(samples):
        sample = [rng.choice(observations) for _ in observations]
        estimate, _ = fit_single_rating(sample)
        estimates.append(estimate)
    estimates.sort()
    tail = (1.0 - confidence) / 2.0
    low_index = max(0, min(samples - 1, int(math.floor(tail * samples))))
    high_index = max(0, min(samples - 1, int(math.ceil((1.0 - tail) * samples)) - 1))
    return [estimates[low_index], estimates[high_index]]


def fit_connected_pool(
    policy_ids: Sequence[str],
    matches: Sequence[tuple[str, str, float]],
    *,
    anchor_id: str,
    anchor_rating: float,
    prior_sd: float = 800.0,
) -> dict[str, float]:
    """Fit a regularized Bradley-Terry pool with one disclosed fixed anchor."""
    ids = list(policy_ids)
    if anchor_id not in ids:
        raise ValueError("rating anchor is not in the policy pool")
    if len(ids) != len(set(ids)):
        raise ValueError("policy ids must be unique")
    variables = [policy_id for policy_id in ids if policy_id != anchor_id]
    ratings = {policy_id: float(anchor_rating) for policy_id in ids}
    scale = math.log(10.0) / ELO_SCALE
    prior_precision = 1.0 / (prior_sd * prior_sd)

    def solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
        n = len(vector)
        augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
        for column in range(n):
            pivot = max(range(column, n), key=lambda row: abs(augmented[row][column]))
            if abs(augmented[pivot][column]) < 1e-12:
                raise ValueError("rating pool is not numerically connected")
            augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
            divisor = augmented[column][column]
            augmented[column] = [value / divisor for value in augmented[column]]
            for row in range(n):
                if row == column:
                    continue
                factor = augmented[row][column]
                augmented[row] = [
                    current - factor * pivot_value
                    for current, pivot_value in zip(augmented[row], augmented[column], strict=True)
                ]
        return [augmented[index][-1] for index in range(n)]

    index = {policy_id: offset for offset, policy_id in enumerate(variables)}
    for _ in range(100):
        gradient = [0.0] * len(variables)
        information = [[0.0] * len(variables) for _ in variables]
        for first, second, first_score in matches:
            probability = expected_score(ratings[first], ratings[second])
            residual = scale * (first_score - probability)
            weight = scale * scale * probability * (1.0 - probability)
            if first != anchor_id:
                i = index[first]
                gradient[i] += residual
                information[i][i] += weight
            if second != anchor_id:
                j = index[second]
                gradient[j] -= residual
                information[j][j] += weight
            if first != anchor_id and second != anchor_id:
                i, j = index[first], index[second]
                information[i][j] -= weight
                information[j][i] -= weight
        for policy_id in variables:
            i = index[policy_id]
            gradient[i] -= (ratings[policy_id] - anchor_rating) * prior_precision
            information[i][i] += prior_precision
        delta = solve(information, gradient)
        largest = max((abs(value) for value in delta), default=0.0)
        for policy_id, change in zip(variables, delta, strict=True):
            ratings[policy_id] += max(-200.0, min(200.0, change))
        ratings[anchor_id] = float(anchor_rating)
        if largest < 1e-7:
            break
    return ratings
