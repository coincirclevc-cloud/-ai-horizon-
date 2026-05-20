# -*- coding: utf-8 -*-
"""
Fetch AI Spaces from HuggingFace API (no token required).
HuggingFace limit max = 500 per request → use skip for pagination.
Output: data/raw/hf.json
"""

import json, time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

API   = "https://huggingface.co/api/spaces"
OUT   = "data/raw/hf.json"
LIMIT = 500    # HF hard max per request
PAGES = 2      # 2 × 500 = 1000
DELAY = 3      # seconds between requests

HEADERS = {
    "User-Agent": "ai-horizon-scraper/1.0",
}


def fetch_page(skip):
    url = f"{API}?sort=likes&limit={LIMIT}&skip={skip}&full=true"
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except HTTPError as e:
        print(f"  HTTP {e.code} skip={skip}: {e.reason}")
        return []
    except URLError as e:
        print(f"  Network error skip={skip}: {e.reason}")
        return []


def normalize(space):
    sid  = space.get("id", "")
    tags = space.get("tags") or []
    card = space.get("cardData") or {}
    return {
        "id":          f"hf-{sid.replace('/', '-')}",
        "name":        sid.split("/")[-1] if "/" in sid else sid,
        "desc":        (card.get("short_description") or
                        space.get("title") or "")[:120],
        "url":         f"https://huggingface.co/spaces/{sid}",
        "track":       map_track(tags),
        "region":      "global",
        "source":      "huggingface",
        "githubStars": 0,
        "hfLikes":     space.get("likes", 0),
        "launchDays":  days_since(space.get("createdAt", "")),
        "tags":        tags,
    }


TRACK_MAP = [
    (["code", "coding", "code-generation", "programming", "developer"],          "productivity"),
    (["education", "learning", "quiz", "tutoring"],                               "edu"),
    (["medical", "health", "clinical", "biomedical", "drug"],                     "health"),
    (["finance", "trading", "investment"],                                         "finance"),
    (["text-generation", "nlp", "writing", "summarization", "translation"],       "content"),
    (["emotion", "mental-health", "therapy", "companionship"],                    "emotion"),
    (["enterprise", "business", "productivity", "workflow", "automation"],        "enterprise"),
    (["image-generation", "audio", "music", "video", "creative", "art"],          "entertainment"),
    (["recommendation", "ecommerce", "retail"],                                   "retail"),
    (["embeddings", "vector", "mlops", "deployment", "inference", "model"],       "infra"),
    (["legal", "research", "scientific", "professional"],                         "professional"),
    (["social", "chat", "conversation", "chatbot"],                               "social"),
]


def map_track(tags):
    t = [x.lower() for x in tags]
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
    for i in range(PAGES):
        skip = i * LIMIT
        print(f"Fetching skip={skip}...", end=" ", flush=True)
        items = fetch_page(skip)
        normalized = [normalize(s) for s in items]
        results.extend(normalized)
        print(f"got {len(items)} spaces (total {len(results)})")
        if i < PAGES - 1:
            time.sleep(DELAY)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(results)} spaces → {OUT}")


if __name__ == "__main__":
    main()
