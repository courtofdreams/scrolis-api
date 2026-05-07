from service.MongoDBService import MongoDBService
import os

mongo = MongoDBService(
    "mongodb://root:password123@localhost:27017"
)

result = mongo.daily_topic_digests.delete_many({})

print(f"Deleted {result.deleted_count} documents")