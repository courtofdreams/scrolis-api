# cron/calculate_topic_preferences.py

import os
from datetime import datetime, timezone
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://root:password123@localhost:27017")
DATABASE_NAME = "scrolis"

client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]

daily_topic_digests = db["daily_topic_digests"]
user_topic_preferences = db["user_topic_preferences"]


def calculate_topic_preferences():
    today = datetime.now(timezone.utc).date().isoformat()

    digests = daily_topic_digests.find({})
    now = datetime.now(timezone.utc)

    for digest in digests:
        user_id = digest.get("userId")
        topics = digest.get("topicsDigest", {}).get("topics", [])

        if not user_id or not topics:
            continue

        category_counts = {}

        for topic in topics:
            category = topic.get("category", "Unknown")
            category_counts[category] = category_counts.get(category, 0) + 1

        total_topics = len(topics)

        categories = [
            {
                "category": category,
                "count": count,
                "percentage": round((count / total_topics) * 100),
            }
            for category, count in category_counts.items()
        ]

        user_topic_preferences.update_one(
            {"userId": user_id, "date": today},
            {
                "$set": {
                    "userId": user_id,
                    "date": today,
                    "categories": categories,
                    "totalTopics": total_topics,
                    "updatedAt": now,
                },
                "$setOnInsert": {
                    "createdAt": now,
                },
            },
            upsert=True,
        )

    print("User topic preferences calculated successfully.")


if __name__ == "__main__":
    calculate_topic_preferences()