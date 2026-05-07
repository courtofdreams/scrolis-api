from social_topic_miner.summarizers import OpenAISummarizer, AnthropicSummarizer

from social_topic_miner import TopicMinerAPI, TopicMinerConfig
import json

class AnalysisService:
    def __init__(self, openai_api_key: str):
        self.topic_miner_api = TopicMinerAPI(summarizer=OpenAISummarizer(api_key=openai_api_key))

    def analyze(self, twitter_data: list, reddit_data: list):
        print(f"Analyzing {len(twitter_data)} tweets and {len(reddit_data)} reddit posts")
        all_posts = twitter_data + reddit_data
        # combined = {
        #     "posts": all_posts
        # }
        # with open("section1_data.json", "w") as f:
        #     json.dump(all_posts, f, indent=2)
        return self.topic_miner_api.section1(all_posts)
    
    def analyze_all(self, all_data: list):
        return self.topic_miner_api.section1(all_data)
    
    def get_query_for_topic(self, topic):
        return self.topic_miner_api.section2({"topic": topic})
    
    def get_different_perspectives(self, twitter_data: list, reddit_data: list, keywords: list[str]):
        all_posts = twitter_data + reddit_data
        data = {
            "new_posts": all_posts,
            "bubble_keywords": keywords
        }
        # with open("section3_data.json", "w") as f:
        #     json.dump(data, f, indent=2)
        return self.topic_miner_api.section3(data)