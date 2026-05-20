# -*- coding: utf-8 -*-
"""
Fetch AI repos from GitHub Search API (no token required).
Rate limit: 10 req/min unauthenticated → 8s delay between pages.
Max results: 1000 (GitHub hard limit per query).
Output: data/raw/github.json
"""

import json, time, sys
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

API = "https://api.github.com/search/repositories"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "ai-horizon-scraper/1.0",
}
QUERY = "topic:artificial-intelligence"
OUT   = "data/raw/github.json"
PAGES = 10        # 10 × 100 = 1000 (GitHub hard cap)
DELAY = 8         # seconds between requests


def fetch_page(page):
    url = f"{API}?q={QUERY}&sort=stars&order=desc&per_page=100&page={page}"
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except HTTPError as e:
        print(f"  HTTP {e.code} on page {page}: {e.reason}")
        return None
    except URLError as e:
        print(f"  Network error on page {page}: {e.reason}")
        return None


def normalize(repo):
    topics = repo.get("topics") or []
    return {
        "id":           f"gh-{repo['id']}",
        "name":         repo.get("name", ""),
        "desc":         (repo.get("description") or "")[:120],
        "url":          repo.get("html_url", ""),
        "track":        map_track(topics, repo.get("language") or ""),
        "region":       "global",
        "source":       "github",
        "githubStars":  repo.get("stargazers_count", 0),
        "hfLikes":      0,
        "launchDays":   days_since(repo.get("created_at", "")),
        "topics":       topics,
        "language":     repo.get("language") or "",
        "pushedAt":     repo.get("pushed_at", ""),
    }


TRACK_MAP = [
    (["code", "coding", "copilot", "autocomplete", "developer-tools", "ide"],     "productivity"),
    (["education", "learning", "tutoring", "elearning", "edtech"],                "edu"),
    (["medical", "healthcare", "health", "clinical", "drug", "biomedical"],       "health"),
    (["finance", "fintech", "trading", "investment", "quant"],                    "finance"),
    (["text-generation", "nlp", "writing", "content", "copywriting", "gpt"],      "content"),
    (["emotion", "mental-health", "therapy", "companion", "social"],              "emotion"),
    (["enterprise", "business", "saas", "crm", "erp", "workflow"],                "enterprise"),
    (["entertainment", "gaming", "game", "music", "art", "creative"],             "entertainment"),
    (["retail", "ecommerce", "shopping", "recommendation"],                       "retail"),
    (["infrastructure", "mlops", "deployment", "serving", "vector", "embedding"], "infra"),
    (["professional", "legal", "hr", "recruiting", "research"],                   "professional"),
    (["social", "community", "chat", "messaging"],                                "social"),
]


def map_track(topics, language):
    t = [x.lower() for x in topics] + [language.lower()]
    for keywords, track in TRACK_MAP:
        if any(k in t for k in keywords):
            return track
    return "productivity"


def days_since(iso_str):
    if not iso_str:
        return 999
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 999


def main():
    results = []
    for page in range(1, PAGES + 1):
        print(f"Fetching page {page}/{PAGES}...", end=" ", flush=True)
        data = fetch_page(page)
        if data is None:
            print("skipped")
            continue
        items = data.get("items", [])
        results.extend([normalize(r) for r in items])
        print(f"got {len(items)} repos (total {len(results)})")
        if page < PAGES:
            time.sleep(DELAY)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(results)} repos → {OUT}")


if __name__ == "__main__":
    main()
