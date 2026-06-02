from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformSpec:
    key: str
    label: str
    width: int
    height: int
    category: str


# Catálogo de formatos de imagen, agrupado por categoría para la UI.
_SPECS = [
    # ---------------- IAB (display estándar) ----------------
    PlatformSpec("iab_medium_rectangle", "Medium Rectangle", 300, 250, "IAB"),
    PlatformSpec("iab_large_rectangle", "Large Rectangle", 336, 280, "IAB"),
    PlatformSpec("iab_leaderboard", "Leaderboard", 728, 90, "IAB"),
    PlatformSpec("iab_large_leaderboard", "Large Leaderboard", 970, 90, "IAB"),
    PlatformSpec("iab_billboard", "Billboard", 970, 250, "IAB"),
    PlatformSpec("iab_half_page", "Half Page", 300, 600, "IAB"),
    PlatformSpec("iab_wide_skyscraper", "Wide Skyscraper", 160, 600, "IAB"),
    PlatformSpec("iab_skyscraper", "Skyscraper", 120, 600, "IAB"),
    PlatformSpec("iab_portrait", "Portrait", 300, 1050, "IAB"),
    PlatformSpec("iab_mobile_leaderboard", "Mobile Leaderboard", 320, 50, "IAB"),
    PlatformSpec("iab_large_mobile_banner", "Large Mobile Banner", 320, 100, "IAB"),
    PlatformSpec("iab_mobile_banner", "Banner", 468, 60, "IAB"),
    PlatformSpec("iab_square", "Square", 250, 250, "IAB"),
    PlatformSpec("iab_small_square", "Small Square", 200, 200, "IAB"),
    # ---------------- Facebook ----------------
    PlatformSpec("fb_feed_square", "Feed 1:1", 1080, 1080, "Facebook"),
    PlatformSpec("fb_feed_landscape", "Feed enlace 1.91:1", 1200, 630, "Facebook"),
    PlatformSpec("fb_stories", "Stories 9:16", 1080, 1920, "Facebook"),
    PlatformSpec("fb_reels", "Reels 9:16", 1080, 1920, "Facebook"),
    # ---------------- Instagram ----------------
    PlatformSpec("ig_square", "Feed 1:1", 1080, 1080, "Instagram"),
    PlatformSpec("ig_portrait", "Feed 4:5", 1080, 1350, "Instagram"),
    PlatformSpec("ig_landscape", "Feed 1.91:1", 1080, 566, "Instagram"),
    PlatformSpec("ig_stories", "Stories 9:16", 1080, 1920, "Instagram"),
    PlatformSpec("ig_reels", "Reels 9:16", 1080, 1920, "Instagram"),
    # ---------------- TikTok ----------------
    PlatformSpec("tt_feed", "In-Feed 9:16", 1080, 1920, "TikTok"),
    PlatformSpec("tt_square", "1:1", 1080, 1080, "TikTok"),
]

PLATFORMS = {p.key: p for p in _SPECS}

# Orden de categorías para la interfaz
CATEGORY_ORDER = ["IAB", "Facebook", "Instagram", "TikTok"]
