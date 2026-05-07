from datetime import datetime, timezone

from service.MongoDBService import MongoDBService
from config import settings

mongo_db_service = MongoDBService(settings.MONGO_URI)


def build_topics(topics_digest):
    topics = []

    for topic in topics_digest.get("topics", [])[:5]:
        topics.append({
            "topicId": topic.get("topic_id"),
            "headline": topic.get("headline"),
            "category": topic.get("category"),
            "shortSummary": topic.get("short_summary"),
            "keywords": topic.get("keywords", [])[:8],
            "nPosts": topic.get("n_posts", 0),
            "nPerspectives": topic.get("n_perspectives", 0),
        })

    return topics


def generate_summary(topics):
    headlines = [topic["headline"] for topic in topics[:3]]

    if not headlines:
        return "No major topics today."

    return f"Today's digest highlights {', '.join(headlines)}."


def run():
    digests = mongo_db_service.daily_topic_digests.find({})

    for digest in digests:
        try:
            topics_digest = digest.get("topicsDigest", {})
            run_date = digest.get("runDate")

            if not run_date:
                created_at = digest.get("createdAt")
                if isinstance(created_at, datetime):
                    run_date = created_at.date().isoformat()

            topics = build_topics(topics_digest)

            if not run_date:
                print(
                    f"Skipping historical snapshot for {digest.get('userId')} "
                    f"because no run date could be determined"
                )
                continue

            historical_digest = {
                "userId": digest.get("userId"),
                "date": run_date,
                "weekday": datetime.fromisoformat(run_date).strftime("%A"),
                "summary": generate_summary(topics),

                "topics": topics,

                "createdAt": digest.get("createdAt"),
                "snapshottedAt": datetime.now(timezone.utc),
            }

            mongo_db_service.historical_digests.update_one(
                {
                    "userId": historical_digest["userId"],
                    "date": historical_digest["date"],
                },
                {
                    "$set": historical_digest
                },
                upsert=True,
            )

            print(
                f"Snapshotted historical digest for "
                f"{historical_digest['userId']} "
                f"{historical_digest['date']}"
            )

        except Exception as e:
            print(f"Failed snapshot: {e}")


if __name__ == "__main__":
    run()