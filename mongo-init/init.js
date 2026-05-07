db = db.getSiblingDB("scrolis");

db.createCollection("user_logs", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["userId", "lastLogin", "loginStreak"],
      properties: {
        userId: { bsonType: "string" },
        lastLogin: { bsonType: "date" },
        updatedAt: { bsonType: "date" },
        loginStreak: { bsonType: "int" },
      },
    },
  },
});

db.createCollection("daily_topic_digests", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: [
        "userId",
        "topicsDigest",
        "createdAt",
        "differentPerspectivesDigest",
        "updatedAt",
      ],
      properties: {
        userId: { bsonType: "string" },
        createdAt: { bsonType: "date" },
        updatedAt: { bsonType: "date" },
        runDate: { bsonType: "string" },
        digest: { bsonType: "string" },
        topicsDigest: {
          bsonType: "object",
        },
        differentPerspectivesDigest: {
          bsonType: "array",
        },
      },
    },
  },
});

db.createCollection("historical_digests", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: [
        "userId",
        "date",
        "weekday",
        "summary",
        "topics",
        "createdAt",
        "snapshottedAt",
      ],
      properties: {
        userId: { bsonType: "string" },
        date: { bsonType: "string" },
        weekday: { bsonType: "string" },
        summary: { bsonType: "string" },

        createdAt: { bsonType: "date" },
        snapshottedAt: { bsonType: "date" },

        topics: {
          bsonType: "array",
          items: {
            bsonType: "object",
            required: [
              "topicId",
              "headline",
              "category",
              "keywords",
              "nPosts",
            ],
            properties: {
              topicId: { bsonType: "int" },
              headline: { bsonType: "string" },
              category: { bsonType: "string" },
              shortSummary: { bsonType: "string" },

              keywords: {
                bsonType: "array",
                items: {
                  bsonType: "string",
                },
              },

              nPosts: { bsonType: "int" },
              nPerspectives: { bsonType: "int" },
            },
          },
        },
      },
    },
  },
});

db.createCollection("user_topic_preferences", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: [
        "userId",
        "date",
        "categories",
        "totalTopics",
        "createdAt",
        "updatedAt",
      ],
      properties: {
        userId: { bsonType: "string" },
        date: { bsonType: "string" },
        totalTopics: { bsonType: "int" },
        createdAt: { bsonType: "date" },
        updatedAt: { bsonType: "date" },
        categories: {
          bsonType: "array",
          items: {
            bsonType: "object",
            required: ["category", "count", "percentage"],
            properties: {
              category: { bsonType: "string" },
              count: { bsonType: "int" },
              percentage: { bsonType: "int" },
            },
          },
        },
      },
    },
  },
});

db.daily_topic_digests.createIndex(
  { userId: 1, runDate: 1 },
  { unique: true }
);

db.daily_topic_digests.createIndex({
  userId: 1,
  runDate: -1,
});

db.historical_digests.createIndex(
  { userId: 1, date: 1 },
  { unique: true }
);

db.historical_digests.createIndex({
  userId: 1,
  date: -1,
});

db.user_topic_preferences.createIndex(
  { userId: 1, date: 1 },
  { unique: true }
);

db.user_topic_preferences.createIndex({
  userId: 1,
  date: -1,
});