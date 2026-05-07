from service.MongoDBService import MongoDBService
import os
from config import settings

mongo = MongoDBService(settings.MONGO_URI)

result = mongo.daily_topic_digests.delete_many({})

print(f"Deleted {result.deleted_count} documents")