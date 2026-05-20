# -*- coding: utf-8 -*-
"""
Merge GitHub + HuggingFace + CN seed data.
Deduplicate, score, split into seed/growth boards, output JSON.

Usage:
  python3 scripts/build_json.py

Output:
  data/seed.json    - 潜力榜 Top 1000
  data/growth.json  - 实力榜 Top 1000
"""

import json, re
from math import log10
from pathlib import Path

GITHUB_RAW = Path("data/raw/github.json")
HF_RAW     = Path("data/raw/hf.json")
CN_SEED    = Path("data/cn_seed.json")
OUT_SEED   = Path("data/seed.json")
OUT_GROWTH = Path("data/growth.json")
TOP_N      = 1000


# ── Scoring ──────────────────────────────────────────────────────────────────

def seed_score(p):
    """潜力榜：偏新、增长快（launchDays ≤ 540）"""
    stars   = min(log10(p.get("githubStars", 0) + 1) / 5, 1.0)
    likes   = min(log10(p.get("hfLikes",     0) + 1) / 4, 1.0)
    days    = p.get("launchDays", 999)
    recency = max(0.0, 1.0 - days / 540.0)
    raw = stars * 35 + likes * 35 + recency * 30
    return round(40 + raw * 0.6, 1)   # maps to 40~100


def growth_score(p):
    """实力榜：偏规模、存活久"""
    stars     = min(log10(p.get("githubStars", 0) + 1) / 5, 1.0)
    likes     = min(log10(p.get("hfLikes",     0) + 1) / 4, 1.0)
    days      = p.get("launchDays", 0)
    longevity = min(days / 365.0, 2.0) / 2.0
    raw = stars * 45 + likes * 35 + longevity * 20
    return round(40 + raw * 0.6, 1)


# ── Deduplication ─────────────────────────────────────────────────────────────

def url_key(url):
    """Normalize full URL path for dedup (not just domain)."""
    url = url.lower().strip().rstrip("/")
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    return url  # keep full path so github.com/a/b ≠ github.com/c/d


def dedup(products):
    seen = {}
    out  = []
    for p in products:
        key = url_key(p.get("url", ""))
        if not key or key in seen:
            continue
        seen[key] = True
        out.append(p)
    return out


# ── Badge logic ───────────────────────────────────────────────────────────────

def compute_badges(p):
    badges = []
    if p.get("launchDays", 999) <= 60:
        badges.append("new")
    if p.get("githubStars", 0) >= 5000 or p.get("hfLikes", 0) >= 500:
        badges.append("hot")
    return badges


# ── Desc builder ──────────────────────────────────────────────────────────────

def build_desc(p):
    parts = []
    if p.get("githubStars", 0) > 0:
        parts.append(f"⭐{fmt_num(p['githubStars'])}")
    if p.get("hfLikes", 0) > 0:
        parts.append(f"❤️{fmt_num(p['hfLikes'])}")
    days = p.get("launchDays", 0)
    if days > 0:
        parts.append(f"入榜{days}天")
    base = p.get("desc", "")
    if base and parts:
        return base[:60] + " · " + " · ".join(parts)
    return base or " · ".join(parts) or p.get("name", "")


def fmt_num(n):
    if n >= 10000:
        return f"{n/10000:.1f}万"
    if n >= 1000:
        return f"{n/1000:.1f}K"
    return str(n)


# ── Change stub ───────────────────────────────────────────────────────────────

def change_stub(rank):
    """Placeholder rank change — replace with real delta after first run."""
    if rank <= 10:
        return "new"
    return "—"


# ── Region inference ─────────────────────────────────────────────────────────

CN_KEYWORDS = ["中文", "chinese", "cn", "腾讯", "阿里", "百度", "字节", "华为",
               "深度", "智谱", "文心", "通义", "讯飞", "商汤"]

def infer_region(p):
    if p.get("region") == "cn":
        return "cn"
    text = (p.get("name", "") + " " + p.get("desc", "")).lower()
    if any(k in text for k in CN_KEYWORDS):
        return "cn"
    return p.get("region", "global")


# ── Main ─────────────────────────────────────────────────────────────────────

def load(path):
    if not path.exists():
        print(f"  Warning: {path} not found, skipping")
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def finalize(products, score_fn, label):
    for p in products:
        p["score"]  = score_fn(p)
        p["badges"] = compute_badges(p)
        p["desc"]   = build_desc(p)
        p["region"] = infer_region(p)

    products.sort(key=lambda p: p["score"], reverse=True)
    top = products[:TOP_N]

    for i, p in enumerate(top):
        p["rank"]   = i + 1
        p["change"] = change_stub(i + 1)

    print(f"  {label}: {len(top)} products (score {top[0]['score']} → {top[-1]['score']})")
    return top


def main():
    print("Loading raw data...")
    github   = load(GITHUB_RAW)
    hf       = load(HF_RAW)
    cn       = load(CN_SEED)
    print(f"  github={len(github)}, hf={len(hf)}, cn={len(cn)}")

    all_products = dedup(github + hf + cn)
    print(f"  After dedup: {len(all_products)}")

    # Split: seed favors new products; growth favors established ones
    # A product can appear in both boards with different scores
    print("\nBuilding 潜力榜 (seed)...")
    seed_candidates = [p for p in all_products if p.get("launchDays", 999) <= 600]
    if len(seed_candidates) < TOP_N:
        # Fallback: include all if not enough recent ones
        seed_candidates = all_products[:]
    seed = finalize(seed_candidates, seed_score, "seed")

    print("Building 实力榜 (growth)...")
    growth_candidates = [
        p for p in all_products
        if p.get("githubStars", 0) >= 50 or p.get("hfLikes", 0) >= 20
        or p.get("source") == "cn"
    ]
    if len(growth_candidates) < TOP_N:
        growth_candidates = all_products[:]
    growth = finalize(growth_candidates, growth_score, "growth")

    # Strip internal-only fields before output
    keep = {"id","name","desc","url","track","region","source",
            "score","rank","change","badges","githubStars","hfLikes","launchDays"}
    def clean(p):
        return {k: v for k, v in p.items() if k in keep}

    with open(OUT_SEED, "w", encoding="utf-8") as f:
        json.dump([clean(p) for p in seed], f, ensure_ascii=False, indent=2)

    with open(OUT_GROWTH, "w", encoding="utf-8") as f:
        json.dump([clean(p) for p in growth], f, ensure_ascii=False, indent=2)

    print(f"\nDone → {OUT_SEED} ({len(seed)} items)")
    print(f"Done → {OUT_GROWTH} ({len(growth)} items)")


if __name__ == "__main__":
    main()
