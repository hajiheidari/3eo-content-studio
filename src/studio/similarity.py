"""Bounded, advisory lexical matching; no embeddings, network or approval decisions."""

import argparse
import hashlib
import heapq
import json
import os
import re
import unicodedata

from sqlalchemy import func, or_, select
from sqlalchemy.orm.exc import StaleDataError

from .storage import Item, database

ALGORITHM = "lexical-v1"
MIN_TOKENS = 12
MIN_UNIQUE = 8
SCAN_SIZE = 200
THRESHOLD = 0.80
TRANSLATION = str.maketrans("يىك٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "ییک01234567890123456789")


def tokens(text):
    value = unicodedata.normalize("NFKC", text).casefold().translate(TRANSLATION)
    value = "".join(c for c in value if unicodedata.category(c) != "Mn" and c != "ـ")
    value = value.replace("\u200c", " ").replace("\u200d", " ")
    return re.findall(r"[^\W_]+", value)


def signature(words):
    if len(words) < MIN_TOKENS or len(set(words)) < MIN_UNIQUE:
        return None
    def hashed(value):
        return hashlib.sha256(value.encode()).hexdigest()[:16]
    return {
        "digest": hashlib.sha256(" ".join(words).encode()).hexdigest(),
        "length": len(words),
        "words": heapq.nsmallest(128, {hashed(word) for word in words}),
        "shingles": heapq.nsmallest(256, {hashed(" ".join(words[i:i + 5]))
                                          for i in range(len(words) - 4)}),
    }


def profile(transcript, research):
    research = json.loads(research) if research else {}
    return json.dumps({
        "algorithm": ALGORITHM,
        "title_fa": research.get("title_fa", ""),
        "transcript": signature(tokens(transcript or "")),
        "research": signature(tokens(" ".join(research.get(key, "") for key in
                                               ("title_fa", "summary_fa", "angle_fa")))),
    }, ensure_ascii=False)


def overlap(left, right, size):
    left, right = set(left), set(right)
    sample = heapq.nsmallest(size, left | right)
    return sum(value in left and value in right for value in sample) / len(sample) if sample else 0


def compare(left, right, left_status, right_status):
    if left.get("algorithm") != ALGORITHM or right.get("algorithm") != ALGORITHM:
        return None
    matches = []
    for basis in ("transcript", "research"):
        # A research revision remains stored for history while MORE_RESEARCH is pending.
        if basis == "research" and ({left_status, right_status} & {"DISCOVERED", "MORE_RESEARCH"}):
            continue
        a, b = left.get(basis), right.get(basis)
        if not a or not b:
            continue
        if a["digest"] == b["digest"]:
            matches.append({"basis": basis, "score": 1.0, "match": "same_normalized_text"})
            continue
        if min(a["length"], b["length"]) / max(a["length"], b["length"]) < 0.6:
            continue
        score = 0.7 * overlap(a["shingles"], b["shingles"], 256) + 0.3 * overlap(a["words"], b["words"], 128)
        if score >= THRESHOLD:
            matches.append({"basis": basis, "score": round(score, 3), "match": "high_lexical_overlap"})
    return max(matches, key=lambda match: match["score"]) if matches else None


def candidates(session, source, before_id=None, limit=5):
    current = json.loads(source.similarity_profile or profile(source.transcript, source.research))
    query = select(Item.id, Item.url, Item.status, Item.version, Item.similarity_profile).where(
        Item.id != source.id, Item.similarity_profile.isnot(None))
    if before_id is not None:
        query = query.where(Item.id < before_id)
    rows = session.execute(query.order_by(Item.id.desc()).limit(SCAN_SIZE + 1)).all()
    more = len(rows) > SCAN_SIZE
    rows, matches = rows[:SCAN_SIZE], []
    for row in rows:
        indexed = json.loads(row.similarity_profile)
        match = compare(current, indexed, source.status, row.status)
        if match:
            matches.append({"id": row.id, "url": row.url, "status": row.status,
                            "version": row.version, "title_fa": indexed.get("title_fa", ""),
                            **match})
    matches.sort(key=lambda match: (-match["score"], match["id"]))
    unindexed = session.scalar(select(func.count()).select_from(Item).where(
        Item.id != source.id, Item.similarity_profile.is_(None),
        or_(Item.transcript.isnot(None), Item.research.isnot(None))))
    return {"algorithm": ALGORITHM, "advisory_only": True, "matches": matches[:limit],
            "scanned": len(rows), "more_to_scan": more,
            "next_before_id": rows[-1].id if more else None, "unindexed_count": unindexed,
            "sufficient_text": bool(current.get("transcript") or (current.get("research") and
                                      source.status not in {"DISCOVERED", "MORE_RESEARCH"}))}


def backfill(sessions, limit=1000, batch_size=50):
    if not 1 <= limit <= 100000 or not 1 <= batch_size <= 200:
        raise ValueError("Invalid backfill bounds")
    examined, indexed, conflicts, invalid, after_id = 0, 0, 0, [], 0
    while examined < limit:
        with sessions() as session:
            rows = list(session.scalars(select(Item).where(
                Item.id > after_id, Item.similarity_profile.is_(None),
                or_(Item.transcript.isnot(None), Item.research.isnot(None)),
            ).order_by(Item.id).limit(min(batch_size, limit - examined))))
            if not rows:
                break
            valid_in_batch = 0
            for item in rows:
                try:
                    item.similarity_profile = profile(item.transcript, item.research)
                    valid_in_batch += 1
                except (ValueError, TypeError, AttributeError):
                    invalid.append(item.id)
            examined += len(rows)
            after_id = rows[-1].id
            try:
                session.commit()
                indexed += valid_in_batch
            except StaleDataError:
                session.rollback()
                conflicts += len(rows)
    return {"examined": examined, "indexed": indexed, "conflicts": conflicts, "invalid_ids": invalid}


def main():
    parser = argparse.ArgumentParser(description="Index existing source text for advisory matching")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=50)
    args = parser.parse_args()
    engine, sessions = database(os.getenv("DATABASE_URL", "sqlite:///./studio.db"))
    try:
        print(json.dumps(backfill(sessions, args.limit, args.batch_size)))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
