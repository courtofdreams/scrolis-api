import datetime
import logging

from pymongo import MongoClient

DATABASE_NAME = "scrolis"
DAILY_TOPIC_DIGESTS_COLLECTION = "daily_topic_digests"
USER_PREFERENCES_COLLECTION = "user_topic_preferences"
USER_LOGS_COLLECTION = "user_logs"
logger = logging.getLogger(__name__)

class MongoDBService:
    def __init__(self, uri):
        logger.info("Connecting to MongoDB...")
        self.client = MongoClient(uri)
        self.db = self.client[DATABASE_NAME]
        self.daily_topic_digests = self.db[DAILY_TOPIC_DIGESTS_COLLECTION]
        self.client_logs = self.db[USER_LOGS_COLLECTION]
        self.user_topic_preferences = self.db[USER_PREFERENCES_COLLECTION]

    def _normalize_user_id(self, user_id):
        return str(user_id)

    def _normalize_datetime(self, value):
        if value is None:
            return None

        if isinstance(value, str):
            value = datetime.datetime.fromisoformat(value)

        if value.tzinfo is not None:
            return value.astimezone(datetime.timezone.utc).replace(tzinfo=None)

        return value

    def find_daily_topic_digests_by_user_id(self, user_id):
        query = {"userId": self._normalize_user_id(user_id)}
        return self.daily_topic_digests.find_one(query)

    def create_daily_topic_digest(self, user_id, topics_digest):
        now = datetime.datetime.utcnow()
        document = {
            "userId": self._normalize_user_id(user_id),
            "topicsDigest": topics_digest,
            "createdAt": now,
            "differentPerspectivesDigest": [],
            "updatedAt": now,   
        }
        result = self.daily_topic_digests.insert_one(document)
        return result.inserted_id
    
    def update_daily_topic_digest_by_topic_id(self, user_id, enriched_result):
        """
        enriched_result = {
            "topic_id": "topic_1",
            "wandering": [...],
            "uncharted": [...]
        }
        Upserts the entry in differentPerspectivesDigest matching topic_id.
        """
        normalized_user_id = self._normalize_user_id(user_id)
        topic_id = enriched_result.get("topic_id")
        now = datetime.datetime.utcnow()
        entry = {
            **enriched_result,        # topic_id, wandering, uncharted (or whatever shape)
            "updatedAt": now
        }

        result = self.daily_topic_digests.update_one(
            {
                "userId": normalized_user_id,
                "differentPerspectivesDigest.topic_id": topic_id   
            },
            {
                "$set": {
                    "differentPerspectivesDigest.$[entry]": entry,  
                    "updatedAt": now
                }
            },
            array_filters=[{"entry.topic_id": topic_id}]     
        )

        if result.matched_count == 0:
            result = self.daily_topic_digests.update_one(
                {"userId": normalized_user_id},
                {
                    "$push": {"differentPerspectivesDigest": entry},
                    "$set": {"updatedAt": now}
                }
            )

        return result.modified_count > 0

    def delete_daily_topic_digest(self, query):
        result = self.daily_topic_digests.delete_one(query)
        return result.deleted_count
    
    def find_user_logs_by_user_id(self, user_id):
        query = {"userId": self._normalize_user_id(user_id)}
        return self.client_logs.find_one(query)
    
    def update_user_log(self, user_id):
        normalized_user_id = self._normalize_user_id(user_id)
        find_result = self.client_logs.find_one({"userId": normalized_user_id})
        now = datetime.datetime.utcnow()
        logs = {}
        if find_result:
            logs = {
                key: value
                for key, value in find_result.items()
                if key != "_id"
            }

            last_login_value = logs.get("lastLogin")
            if last_login_value:
                last_login_date = self._normalize_datetime(last_login_value)
                if last_login_date is not None:
                    if (now - last_login_date).days == 1:
                        logs["loginStreak"] += 1
                    else:
                        logs["loginStreak"] = 0
                    logs["lastLogin"] = now
                else:
                    logs["loginStreak"] = 0
                    logs["lastLogin"] = now
        else:
            logs = {"userId": normalized_user_id, "lastLogin": now, "loginStreak": 0}
        
        query = {"userId": normalized_user_id}
        update = {"$set": logs}
        result = self.client_logs.update_one(query, update, upsert=True) 
        if result.modified_count > 0 or result.upserted_id is not None:
            logging.info(f"User log for user {normalized_user_id} updated successfully.")
        else:
            logging.error(f"Failed to update user log for user {normalized_user_id}.")
        
        return logs
    
    
    def find_user_topic_preferences_by_user_id(self, user_id):
        normalized_user_id = self._normalize_user_id(user_id)

        cursor = self.user_topic_preferences.find(
            {"userId": normalized_user_id},
            {
                "_id": 0,
                "userId": 1,
                "date": 1,
                "categories": 1,
                "totalTopics": 1,
                "createdAt": 1,
                "updatedAt": 1,
            },
        ).sort("date", -1)

        return list(cursor)