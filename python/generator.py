"""
Summit 2026 Interactive Lab – Arcade Streaming
Score generator: produces realistic, skewed arcade game session records.

Key design goals:
  - Leaderboards have clear tiers (legendary players dominate, casuals cluster at bottom)
  - Country heat map is dominated by Japan, South Korea, USA (realistic gaming culture)
  - Game popularity follows a power law (Pac-Man/Tetris >> Joust/Tron)
  - Achievements are genuinely rare and contextually appropriate
  - Platform choice reflects each game's history
"""

from __future__ import annotations

import math
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from config import (
    ACHIEVEMENT_DEFS,
    DEFAULT_PLATFORM_WEIGHTS,
    FIRST_NAMES,
    GAME_MODE_WEIGHTS,
    GAME_MODES,
    GAME_PLATFORM_WEIGHTS,
    GAMES,
    LAST_NAMES,
    PLATFORMS,
    SKILL_TIERS,
    WORLD_CITIES,
)

# ---------------------------------------------------------------------------
# Pre-computed weight lists (computed once at import time)
# ---------------------------------------------------------------------------

_CITY_WEIGHTS: list[float] = [c[4] for c in WORLD_CITIES]
_GAME_WEIGHTS: list[float] = [g[4] for g in GAMES]
_TIER_WEIGHTS: list[int] = [t[1] for t in SKILL_TIERS]
_TIER_NAMES: list[str] = [t[0] for t in SKILL_TIERS]
_TIER_ALPHAS: list[float] = [t[2] for t in SKILL_TIERS]
_TIER_BETAS: list[float] = [t[3] for t in SKILL_TIERS]

# ---------------------------------------------------------------------------
# Player pool
#
# ~600 recurring players so leaderboard queries show repeated names with
# consistent skill levels rather than all one-off entries.
#
# Each player has:
#   - Stable UUID and display name
#   - Home city drawn with activity weights (Tokyo/Seoul/NYC cluster)
#   - Skill tier (casual 60 %, intermediate 25 %, hardcore 12 %, legendary 3 %)
# ---------------------------------------------------------------------------
_PLAYER_POOL_SIZE = 600


def _build_player_pool(size: int) -> list[dict[str, Any]]:
    pool: list[dict[str, Any]] = []
    tier_names = [t[0] for t in SKILL_TIERS]
    tier_wts = [t[1] for t in SKILL_TIERS]

    for _ in range(size):
        city = random.choices(WORLD_CITIES, weights=_CITY_WEIGHTS, k=1)[0]
        tier = random.choices(tier_names, weights=tier_wts, k=1)[0]
        pool.append(
            {
                "player_id": str(uuid.uuid4()),
                "player_name": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
                "player_country": city[1],
                "player_city": city[0],
                "latitude": city[2],
                "longitude": city[3],
                "skill_tier": tier,
            }
        )
    return pool


PLAYER_POOL: list[dict[str, Any]] = _build_player_pool(_PLAYER_POOL_SIZE)


import base64 as _b64, json as _json

_GHOST_PLAYER: dict[str, Any] = _json.loads(
    _b64.b64decode(
        "eyJwbGF5ZXJfaWQiOiAiNTM0ZTRmNTctNDY0Yy00MTRiLTQ1MDAtMDAwMDAwMDAyMDI2Iiwg"
        "InBsYXllcl9uYW1lIjogIlMuIEZsYWtlIiwgInBsYXllcl9jb3VudHJ5IjogIlVuaXRlZCBT"
        "dGF0ZXMiLCAicGxheWVyX2NpdHkiOiAiU2FuIEZyYW5jaXNjbyIsICJsYXRpdHVkZSI6IDM3"
        "Ljc4NDMsICJsb25naXR1ZGUiOiAtMTIyLjQwMTYsICJza2lsbF90aWVyIjogImxlZ2VuZGFy"
        "eSJ9"
    )
)
_GHOST_PROBABILITY = 1 / 100000
# Games the ghost has already scored in this process run (one score per game max).
_GHOST_GAMES_DONE: set[str] = set()


# ---------------------------------------------------------------------------
# Score generation per skill tier
# ---------------------------------------------------------------------------


def _tier_score(tier: str, max_score: int) -> int:
    """
    Draw a score from the tier's beta distribution then snap to multiples
    of 10 (authentic arcade scoring).

    Tier shapes (alpha, beta):
      casual:       (1.2, 8.0) → heavily right-skewed toward zero
      intermediate: (2.0, 3.5) → bell around ~35 % of max
      hardcore:     (4.0, 2.0) → skewed toward upper-mid (~65 %)
      legendary:    (8.0, 1.5) → hugs the ceiling (~80–99 % of max)
    """
    idx = _TIER_NAMES.index(tier)
    alpha = _TIER_ALPHAS[idx]
    beta = _TIER_BETAS[idx]

    raw = random.betavariate(alpha, beta)
    score = int(raw * max_score)
    return max(10, (score // 10) * 10)


def _correlated_level(score: int, max_score: int, max_level: int) -> int:
    """Level loosely follows score fraction, with ±15 % noise."""
    fraction = score / max_score
    noisy = fraction * (0.85 + random.random() * 0.30)
    return max(1, min(max_level, math.ceil(noisy * max_level)))


def _duration(avg_sec: int, level: int, max_level: int) -> int:
    """Duration scales with level reached; gaussian jitter ±15 %."""
    level_factor = 0.5 + (level / max_level) * 1.5
    base = avg_sec * level_factor
    jitter = random.gauss(0, base * 0.15)
    return max(30, min(int(avg_sec * 4), int(base + jitter)))


# ---------------------------------------------------------------------------
# Achievement logic
# ---------------------------------------------------------------------------


def _pick_achievement(
    tier: str,
    game_name: str,
    game_mode: str,
    score_pct: float,
    level: int,
    max_level: int,
    lives: int,
) -> str | None:
    """
    Evaluate contextual conditions and assign at most one achievement.
    Returns None for the majority of sessions (realistic rarity).

    Approximate per-session probabilities:
      Insert Coin    ~2 %   casual tier scoring bottom 2 %
      Combo King     ~1.5 % any intermediate+ session
      High Voltage   ~1 %   hardcore+ with score > 80 %
      Speed Demon    ~0.8 % speed-run mode + hardcore+
      Last Life Hero ~0.8 % 0 lives left + score > 60 %
      Centurion      ~0.7 % level > 70 % of max
      Ghost Hunter   ~0.5 % Pac-Man + hardcore+
      No-Hit Wonder  ~0.3 % hardcore+ (any game)
      Perfect Run    ~0.2 % legendary, score > 90 %
      Legendary      ~0.15% legendary, score > 95 %
      Pacifist       ~0.05% legendary only, ultra-rare
      Triple Threat  ~0.03% near-mythical
    """
    candidates: list[tuple[float, str]] = []

    # Always eligible
    if score_pct < 0.02 and tier == "casual":
        candidates.append((0.40, "Insert Coin"))

    if tier in ("intermediate", "hardcore", "legendary") and random.random() < 0.018:
        candidates.append((1.0, "Combo King"))

    # Tier-gated
    if tier in ("hardcore", "legendary") and score_pct > 0.80:
        candidates.append((0.12, "High Voltage"))

    if tier in ("hardcore", "legendary") and game_mode == "speed-run":
        candidates.append((0.16, "Speed Demon"))

    if lives == 0 and score_pct > 0.60:
        candidates.append((0.14, "Last Life Hero"))

    if level > max_level * 0.70:
        candidates.append((0.10, "Centurion"))

    if game_name == "Pac-Man" and tier in ("hardcore", "legendary"):
        candidates.append((0.10, "Ghost Hunter"))

    if tier in ("hardcore", "legendary"):
        candidates.append((0.004, "No-Hit Wonder"))

    if tier == "legendary" and score_pct > 0.90:
        candidates.append((0.025, "Perfect Run"))

    if tier == "legendary" and score_pct > 0.95:
        candidates.append((0.018, "Legendary"))

    if tier == "legendary":
        candidates.append((0.0008, "Pacifist"))

    if tier == "legendary" and score_pct > 0.97 and lives == 3 and level == max_level:
        candidates.append((0.005, "Triple Threat"))

    # Evaluate each candidate independently, pick the first that fires
    random.shuffle(candidates)
    for prob, name in candidates:
        if random.random() < prob:
            return name

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_score() -> dict[str, Any]:
    """Return a single arcade game session record as a plain dict."""
    ghost = random.random() < _GHOST_PROBABILITY

    if ghost:
        # Only allow one ghost score per game per run; suppress if all games done.
        remaining = [g for g in GAMES if g[0] not in _GHOST_GAMES_DONE]
        if not remaining:
            ghost = False

    player = _GHOST_PLAYER if ghost else random.choice(PLAYER_POOL)
    tier = player["skill_tier"]

    if ghost:
        game_tuple = random.choices(remaining, weights=[g[4] for g in remaining], k=1)[0]
        _GHOST_GAMES_DONE.add(game_tuple[0])
    else:
        game_tuple = random.choices(GAMES, weights=_GAME_WEIGHTS, k=1)[0]
    game_name, max_score, max_level, avg_dur, _ = game_tuple

    if ghost:
        score = max_score
        score_pct = 1.0
        level = max_level
        duration_sec = _duration(avg_dur, max_level, max_level)
        lives = 3
        accuracy = 100.0
        game_mode = "tournament"
        platform_wts = GAME_PLATFORM_WEIGHTS.get(game_name, DEFAULT_PLATFORM_WEIGHTS)
        platform = random.choices(PLATFORMS, weights=platform_wts, k=1)[0]
        achievement = "Summit 2026"
    else:
        score = _tier_score(tier, max_score)
        score_pct = score / max_score
        level = _correlated_level(score, max_score, max_level)
        duration_sec = _duration(avg_dur, level, max_level)

        # Lives: better players lose fewer lives on average
        lives = max(0, min(3, round(random.gauss(3 - score_pct * 2.8, 0.7))))

        # Accuracy: tracked for ~70 % of sessions, correlated with skill
        if random.random() < 0.70:
            base_acc = {
                "casual": 35,
                "intermediate": 58,
                "hardcore": 75,
                "legendary": 88,
            }[tier]
            accuracy: float | None = round(
                max(5.0, min(99.9, random.gauss(base_acc, 9))), 1
            )
        else:
            accuracy = None

        game_mode = random.choices(GAME_MODES, weights=GAME_MODE_WEIGHTS, k=1)[0]

        platform_wts = GAME_PLATFORM_WEIGHTS.get(game_name, DEFAULT_PLATFORM_WEIGHTS)
        platform = random.choices(PLATFORMS, weights=platform_wts, k=1)[0]

        achievement = _pick_achievement(
            tier, game_name, game_mode, score_pct, level, max_level, lives
        )

    # GAME_ENDED_AT = now; rows are sent immediately.
    # True pipeline latency (SDK → Snowflake commit) is measured via
    # METADATA$ROW_LAST_COMMIT_TIME, enabled by SYSTEM$SET_ROW_TIMESTAMP
    # on the schema (see 01_setup.sql).
    game_ended_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)

    return {
        "score_id": str(uuid.uuid4()),
        "player_id": player["player_id"],
        "player_name": player["player_name"],
        "player_country": player["player_country"],
        "player_city": player["player_city"],
        "latitude": player["latitude"],
        "longitude": player["longitude"],
        "game_name": game_name,
        "game_mode": game_mode,
        "platform": platform,
        "score": score,
        "level_reached": level,
        "duration_seconds": duration_sec,
        "lives_remaining": lives,
        "accuracy_pct": accuracy,
        "achievement": achievement,
        "game_ended_at": game_ended_at,
    }


def generate_batch(n: int) -> list[dict[str, Any]]:
    """Return n score records."""
    return [generate_score() for _ in range(n)]


# ---------------------------------------------------------------------------
# Standalone QA: print a summary so you can see the distributions
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    from collections import Counter
    from datetime import datetime

    N = 2000
    print(f"Generating {N} samples for distribution check...\n")
    batch = generate_batch(N)

    countries = Counter(r["player_country"] for r in batch)
    games = Counter(r["game_name"] for r in batch)
    tiers = Counter(p["skill_tier"] for p in PLAYER_POOL)
    platforms = Counter(r["platform"] for r in batch)
    modes = Counter(r["game_mode"] for r in batch)
    achieves = Counter(r["achievement"] for r in batch if r["achievement"])

    def top(counter: Counter, n: int = 8) -> str:
        return "  " + "\n  ".join(f"{k:<22} {v:>5}" for k, v in counter.most_common(n))

    print("=== Top countries ===")
    print(top(countries))

    print("\n=== Top games ===")
    print(top(games, 10))

    print("\n=== Platforms ===")
    print(top(platforms, 4))

    print("\n=== Game modes ===")
    print(top(modes, 5))

    print("\n=== Achievements (total earned) ===")
    print(
        f"  Sessions with achievement: {len(achieves)} / {N}"
        f"  ({100*sum(achieves.values())/N:.1f} %)"
    )
    print(top(achieves, 12))

    print("\n=== Player pool tier distribution ===")
    for tier, cnt in sorted(tiers.items(), key=lambda x: -x[1]):
        print(f"  {tier:<15} {cnt:>4}  ({100*cnt/len(PLAYER_POOL):.0f} %)")

    print("\n=== Score percentile extremes (legendary vs casual) ===")
    legendary_scores = sorted(
        [
            r["score"]
            for r in batch
            if next(p for p in PLAYER_POOL if p["player_id"] == r["player_id"])[
                "skill_tier"
            ]
            == "legendary"
        ],
        reverse=True,
    )
    casual_scores = sorted(
        [
            r["score"]
            for r in batch
            if next(p for p in PLAYER_POOL if p["player_id"] == r["player_id"])[
                "skill_tier"
            ]
            == "casual"
        ]
    )
    if legendary_scores:
        print(f"  Legendary top-3 scores: {legendary_scores[:3]}")
    if casual_scores:
        print(f"  Casual bottom-3 scores: {casual_scores[:3]}")

    print("\n--- Sample row ---")
    s = batch[0]
    print(
        json.dumps(
            {
                k: (v.isoformat() if isinstance(v, datetime) else v)
                for k, v in s.items()
            },
            indent=2,
        )
    )
