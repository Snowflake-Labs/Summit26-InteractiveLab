"""
Summit 2026 Interactive Lab – Arcade Streaming
Configuration: game catalogue, world cities, player names, and tuning knobs.
"""

from __future__ import annotations

import os

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

# ---------------------------------------------------------------------------
# Snowflake connection (overridden by profile.json; used as fallback)
# ---------------------------------------------------------------------------
SNOWFLAKE_ACCOUNT = "YOUR_ACCOUNT_IDENTIFIER"  # e.g. "xy12345" or "orgname-accountname"
SNOWFLAKE_USER = "ARCADE_STREAMING_USER"
SNOWFLAKE_ROLE = "ARCADE_STREAMING_ROLE"
SNOWFLAKE_DATABASE = "ARCADE_DB"
SNOWFLAKE_SCHEMA = "PUBLIC"
SNOWFLAKE_PIPE = "ARCADE_SCORES-STREAMING"
PROFILE_JSON_PATH = os.path.join(_PROJECT_ROOT, "profile.json")

# ---------------------------------------------------------------------------
# Streaming tuning
# ---------------------------------------------------------------------------
NUM_CHANNELS = 1  # parallel SDK channels → higher throughput
TARGET_ROWS_PER_SEC = 1000  # approx rows/sec across all channels (0 = unlimited)
STATS_INTERVAL_SEC = 5  # how often to print throughput stats to console
BATCH_SIZE = 25  # rows per append_row loop before a short yield

# ---------------------------------------------------------------------------
# Player skill tiers
# (tier_name, population_weight, beta_alpha, beta_beta)
#
# Beta distribution shapes the score within [0, max_score]:
#   casual:       peaks near the bottom – most players stink
#   intermediate: roughly bell-shaped in the lower-middle
#   hardcore:     skewed toward the upper-middle
#   legendary:    hugs the ceiling – near-world-record scores
# ---------------------------------------------------------------------------
SKILL_TIERS: list[tuple[str, int, float, float]] = [
    # (name,         pop_weight, beta_α, beta_β)
    ("casual", 60, 1.2, 8.0),  # 60 % of players, low scores
    ("intermediate", 25, 2.0, 3.5),  # 25 % – decent
    ("hardcore", 12, 4.0, 2.0),  # 12 % – impressive
    ("legendary", 3, 8.0, 1.5),  #  3 % – leaderboard dominators
]

# ---------------------------------------------------------------------------
# Arcade game catalogue
# (game_name, max_score, max_level, avg_duration_sec, popularity_weight)
#
# Popularity weight drives how often each game appears in the stream:
#   high weight → Pac-Man / Tetris dominate the game counts query
#   low weight  → Joust / Tron are niche finds
# ---------------------------------------------------------------------------
GAMES: list[tuple[str, int, int, int, float]] = [
    # Classic icons – everyone plays these
    ("Pac-Man", 999_999, 256, 180, 5.0),
    ("Tetris", 9_999_999, 30, 90, 4.5),
    ("Street Fighter II", 100_000, 8, 600, 4.0),
    ("Space Invaders", 999_990, 99, 120, 3.5),
    ("Galaga", 3_000_000, 50, 150, 3.5),
    ("Mortal Kombat", 100_000, 10, 480, 3.0),
    # Second tier – popular but not dominant
    ("Donkey Kong", 1_000_000, 22, 120, 2.5),
    ("Tekken 3", 50_000, 8, 480, 2.5),
    ("NBA Jam", 999_999, 4, 600, 2.0),
    ("Frogger", 999_990, 50, 90, 2.0),
    ("Asteroids", 999_990, 50, 120, 2.0),
    # Niche classics
    ("Centipede", 999_999, 40, 100, 1.5),
    ("Dig Dug", 1_000_000, 100, 120, 1.5),
    ("Missile Command", 999_990, 127, 90, 1.5),
    ("Q*bert", 819_000, 36, 120, 1.5),
    ("Time Crisis", 99_999, 10, 600, 1.5),
    # Rarities – interesting to spot
    ("Defender", 9_999_999, 255, 180, 0.8),
    ("Robotron 2084", 9_999_999, 100, 120, 0.8),
    ("Tron", 999_999, 99, 180, 0.7),
    ("Joust", 1_000_000, 50, 150, 0.6),
]

# ---------------------------------------------------------------------------
# Game modes – classic is overwhelmingly most common
# ---------------------------------------------------------------------------
GAME_MODES = ["classic", "tournament", "co-op", "survival", "speed-run"]
GAME_MODE_WEIGHTS = [0.50, 0.20, 0.15, 0.10, 0.05]

# ---------------------------------------------------------------------------
# Platform weights per game
# Key: game name.  Value: (arcade, console, mobile, pc) weights.
# Games missing from this dict use DEFAULT_PLATFORM_WEIGHTS.
# ---------------------------------------------------------------------------
GAME_PLATFORM_WEIGHTS: dict[str, tuple[float, float, float, float]] = {
    "Pac-Man": (0.65, 0.20, 0.12, 0.03),
    "Space Invaders": (0.60, 0.20, 0.15, 0.05),
    "Galaga": (0.65, 0.20, 0.10, 0.05),
    "Donkey Kong": (0.60, 0.25, 0.10, 0.05),
    "Frogger": (0.55, 0.20, 0.20, 0.05),
    "Street Fighter II": (0.40, 0.45, 0.05, 0.10),
    "Mortal Kombat": (0.35, 0.50, 0.05, 0.10),
    "Tekken 3": (0.20, 0.60, 0.05, 0.15),
    "NBA Jam": (0.25, 0.55, 0.08, 0.12),
    "Tetris": (0.10, 0.22, 0.53, 0.15),
    "Time Crisis": (0.70, 0.20, 0.05, 0.05),
}
DEFAULT_PLATFORM_WEIGHTS: tuple[float, float, float, float] = (0.45, 0.25, 0.18, 0.12)
PLATFORMS = ["arcade", "console", "mobile", "pc"]

# ---------------------------------------------------------------------------
# World cities with coordinates and activity weight
# (city, country, latitude, longitude, activity_weight)
#
# Activity weight controls how many players are based in each city:
#   Tokyo / Seoul → gaming capitals, very high
#   NYC / SF / London → large tech/gaming hubs
#   Smaller or developing-market cities → lower weight
# ---------------------------------------------------------------------------
WORLD_CITIES: list[tuple[str, str, float, float, float]] = [
    # North America
    ("San Francisco", "USA", 37.7749, -122.4194, 3.5),  # Summit host city!
    ("New York", "USA", 40.7128, -74.0060, 4.0),
    ("Seattle", "USA", 47.6062, -122.3321, 2.5),
    ("Chicago", "USA", 41.8781, -87.6298, 2.0),
    ("Austin", "USA", 30.2672, -97.7431, 2.0),
    ("Los Angeles", "USA", 34.0522, -118.2437, 3.0),
    ("Boston", "USA", 42.3601, -71.0589, 2.0),
    ("Denver", "USA", 39.7392, -104.9903, 1.5),
    ("Toronto", "Canada", 43.6532, -79.3832, 2.5),
    ("Vancouver", "Canada", 49.2827, -123.1207, 2.0),
    ("Mexico City", "Mexico", 19.4326, -99.1332, 2.0),
    # Europe
    ("London", "UK", 51.5074, -0.1278, 3.5),
    ("Berlin", "Germany", 52.5200, 13.4050, 3.0),
    ("Paris", "France", 48.8566, 2.3522, 2.5),
    ("Amsterdam", "Netherlands", 52.3676, 4.9041, 2.0),
    ("Madrid", "Spain", 40.4168, -3.7038, 2.0),
    ("Stockholm", "Sweden", 59.3293, 18.0686, 2.0),
    ("Zurich", "Switzerland", 47.3769, 8.5417, 1.5),
    ("Warsaw", "Poland", 52.2297, 21.0122, 2.0),
    ("Milan", "Italy", 45.4654, 9.1859, 1.5),
    ("Prague", "Czech Republic", 50.0755, 14.4378, 1.5),
    # Asia-Pacific – gaming heartland
    ("Tokyo", "Japan", 35.6762, 139.6503, 6.0),  # arcade culture capital
    ("Seoul", "South Korea", 37.5665, 126.9780, 6.0),  # esports capital
    ("Singapore", "Singapore", 1.3521, 103.8198, 3.0),
    ("Sydney", "Australia", -33.8688, 151.2093, 2.5),
    ("Melbourne", "Australia", -37.8136, 144.9631, 2.0),
    ("Mumbai", "India", 19.0760, 72.8777, 2.5),
    ("Bangalore", "India", 12.9716, 77.5946, 2.5),
    ("Beijing", "China", 39.9042, 116.4074, 3.0),
    ("Shanghai", "China", 31.2304, 121.4737, 3.0),
    ("Hong Kong", "China", 22.3193, 114.1694, 2.5),
    ("Taipei", "Taiwan", 25.0330, 121.5654, 3.0),
    ("Jakarta", "Indonesia", -6.2088, 106.8456, 2.0),
    ("Bangkok", "Thailand", 13.7563, 100.5018, 2.0),
    ("Kuala Lumpur", "Malaysia", 3.1390, 101.6869, 1.5),
    # Middle East & Africa
    ("Dubai", "UAE", 25.2048, 55.2708, 1.5),
    ("Tel Aviv", "Israel", 32.0853, 34.7818, 1.5),
    ("Nairobi", "Kenya", -1.2921, 36.8219, 0.5),
    ("Lagos", "Nigeria", 6.5244, 3.3792, 0.5),
    ("Cairo", "Egypt", 30.0444, 31.2357, 0.7),
    ("Johannesburg", "South Africa", -26.2041, 28.0473, 0.7),
    # Latin America
    ("São Paulo", "Brazil", -23.5505, -46.6333, 2.5),
    ("Buenos Aires", "Argentina", -34.6037, -58.3816, 1.5),
    ("Bogotá", "Colombia", 4.7110, -74.0721, 1.0),
    ("Santiago", "Chile", -33.4489, -70.6693, 1.0),
    ("Lima", "Peru", -12.0464, -77.0428, 0.8),
]

# ---------------------------------------------------------------------------
# Achievements
# (name, description, rarity_label)
# Probabilities are assigned in generator.py based on tier + context.
# ---------------------------------------------------------------------------
ACHIEVEMENT_DEFS: list[tuple[str, str]] = [
    ("Perfect Run", "rare"),  # legendary tier, near-perfect score
    ("High Voltage", "uncommon"),  # hardcore+, high score pct
    ("No-Hit Wonder", "rare"),  # hardcore+, took zero damage
    ("Speed Demon", "uncommon"),  # speed-run mode + good score
    ("Last Life Hero", "uncommon"),  # 0 lives left, still top-tier score
    ("Centurion", "uncommon"),  # reached a high level
    ("Combo King", "common"),  # intermediate+, any game
    ("Ghost Hunter", "uncommon"),  # Pac-Man specific, hardcore+
    ("Pacifist", "legendary"),  # ultra-rare: avoid all enemies
    ("Triple Threat", "legendary"),  # near-mythical: three perfect metrics
    ("Legendary", "rare"),  # legendary tier, near-max score
    ("Insert Coin", "common"),  # ironic: scored in the bottom 1%
]

# ---------------------------------------------------------------------------
# Player first/last name pools
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    "Aiden",
    "Alex",
    "Ali",
    "Amara",
    "Ana",
    "Andre",
    "Anjali",
    "Aria",
    "Ben",
    "Caleb",
    "Carlos",
    "Chen",
    "Chiara",
    "Chloe",
    "Daniel",
    "David",
    "Elena",
    "Emma",
    "Ethan",
    "Fatima",
    "Felix",
    "Finn",
    "Gabriel",
    "Grace",
    "Hana",
    "Hassan",
    "Ian",
    "Isabel",
    "Jae",
    "Jake",
    "James",
    "Jasmine",
    "Javier",
    "Ji-ho",
    "Jonas",
    "Julia",
    "Kai",
    "Kenji",
    "Kevin",
    "Lena",
    "Leo",
    "Leila",
    "Liam",
    "Lin",
    "Luca",
    "Lucas",
    "Luna",
    "Maya",
    "Miguel",
    "Min",
    "Mohamed",
    "Nadia",
    "Nathan",
    "Nia",
    "Noah",
    "Nour",
    "Oliver",
    "Olivia",
    "Omar",
    "Priya",
    "Rafael",
    "Rania",
    "Ryan",
    "Sakura",
    "Sam",
    "Santiago",
    "Sara",
    "Seon",
    "Sofia",
    "Soren",
    "Tariq",
    "Tomas",
    "Uma",
    "Victor",
    "Wei",
    "Yuki",
    "Zara",
    "Zoe",
]

LAST_NAMES = [
    "Adams",
    "Ahmed",
    "Ali",
    "Anderson",
    "Andersson",
    "Benali",
    "Brown",
    "Castillo",
    "Chen",
    "Costa",
    "Davis",
    "Diaz",
    "Dubois",
    "Ferrari",
    "Fischer",
    "Flores",
    "Garcia",
    "Gonzalez",
    "Gupta",
    "Hansen",
    "Hernandez",
    "Hoffmann",
    "Huang",
    "Jensen",
    "Jones",
    "Johansson",
    "Kim",
    "Kumar",
    "Lee",
    "Li",
    "Liu",
    "Lopez",
    "Martin",
    "Martinez",
    "Mendes",
    "Moller",
    "Müller",
    "Nakamura",
    "Nguyen",
    "Nielsen",
    "Park",
    "Patel",
    "Perez",
    "Petrov",
    "Popescu",
    "Rahman",
    "Ramirez",
    "Reyes",
    "Rodriguez",
    "Rossi",
    "Sato",
    "Schmidt",
    "Silva",
    "Smith",
    "Souza",
    "Suzuki",
    "Tanaka",
    "Taylor",
    "Torres",
    "Tran",
    "Vargas",
    "Wang",
    "Williams",
    "Wilson",
    "Wu",
    "Yamamoto",
    "Zhang",
    "Zhou",
]
