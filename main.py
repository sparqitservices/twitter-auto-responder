import functions_framework
import os
import json
import time
import random
import logging
from datetime import datetime, timedelta
import tweepy
from google.cloud import storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Twitter API credentials
TWITTER_API_KEY = "vH8AFvADm0F2KfxoqNp9zDAtI"
TWITTER_API_SECRET = "JQek8CKAKTLuW6L2Unyn2LgdnmcReYOwV3xQSXLGkBp6YKlNCL"
TWITTER_ACCESS_TOKEN = "1856733354088935432-Yb32CZIGtkWWb4Sn28v79oAKiZ4Uds"
TWITTER_ACCESS_SECRET = "23HWJIi5uy4xUvOPdFvKK26V25ZZcT4m7xULUciL2ScDa"
TWITTER_BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAANl%2B0AEAAAAAIG2Gvq3zvKzOSRxhKpM%2F31qxwP8%3DtbBWBXvaakEJaghzBdmU8ivoUXUFhMWDhHQzcXRsaoJKRgI4hc"

# Google Cloud Storage configuration
GCS_BUCKET_NAME = "twitter-responder-state"
STATE_FILE_NAME = "responder_state.json"

# Twitter user configuration
YOUR_TWITTER_USERNAME = "sparqitservices"

# Response configuration
TRIGGER_KEYWORDS = [
    "interested", "pdf", "guide", "download", "resource",
    "material", "info", "information", "details", "share"
]

EXCLUSION_KEYWORDS = [
    "spam", "scam", "fake", "don't dm", "dont dm", "no dm"
]

# Message templates for different types of interactions with A/B testing variants
DM_TEMPLATES = {
    "giveaway": {
        "A": [
            "Hi {username}! Thanks for your interest in my {content_type}. I've attached the {resource_name} as promised. Let me know if you have any questions!",
            "Hello {username}! I noticed you were interested in my {content_type}. Here's the {resource_name} you requested. Hope you find it useful!"
        ],
        "B": [
            "Hey {username}! Here's the {resource_description} you were looking for. This should help you get started right away!",
            "Thanks for engaging with my content, {username}! I'm sharing this {resource_description} with you - hope it helps with what you're working on."
        ]
    },
    "follow_up": {
        "A": [
            "Hey {username}! Just checking in - did you get a chance to look at the {resource_name} I sent? I'd love to hear your thoughts!"
        ],
        "B": [
            "Hi {username}! How are you finding the {resource_name}? If you have any questions about implementing what you learned, I'm here to help."
        ]
    }
}

# Resource definitions
RESOURCES = {
    "pdf_guide": {
        "name": "PDF Guide",
        "keywords": ["pdf", "guide", "document", "read"],
        "description": "comprehensive PDF guide"
    },
    "checklist": {
        "name": "Checklist",
        "keywords": ["checklist", "steps", "process", "todo"],
        "description": "step-by-step checklist"
    },
    "template": {
        "name": "Template",
        "keywords": ["template", "format", "example", "sample"],
        "description": "ready-to-use template"
    },
    "video_tutorial": {
        "name": "Video Tutorial",
        "keywords": ["video", "tutorial", "watch", "learn"],
        "description": "video tutorial"
    }
}

# Rate limiting configuration
DAILY_DM_LIMIT = 50
HOURLY_DM_LIMIT = 15
MIN_TIME_BETWEEN_DMS = 60  # seconds

class TwitterAutoResponder:
    def __init__(self):
        # Initialize Twitter API clients
        self.auth = tweepy.OAuth1UserHandler(
            TWITTER_API_KEY, TWITTER_API_SECRET,
            TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
        )
        self.api = tweepy.API(self.auth)
        self.client = tweepy.Client(
            bearer_token=TWITTER_BEARER_TOKEN,
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET
        )

        # Initialize GCS client
        self.storage_client = storage.Client(project="twitter-responder-454617")

        # Load state from GCS
        self.state = self.load_state()

        # Initialize state if it doesn't exist
        if not self.state:
            self.state = {
                "processed_tweets": {},
                "processed_users": {},
                "dm_count": {
                    "daily": 0,
                    "hourly": 0,
                    "last_reset": datetime.now().isoformat(),
                    "last_hourly_reset": datetime.now().isoformat()
                },
                "last_dm_time": datetime.now().isoformat(),
                "metrics": {
                    "total_dms_sent": 0,
                    "responses_by_keyword": {},
                    "conversion_rate": 0,
                    "total_interactions": 0,
                    "ab_test_results": {"A": 0, "B": 0}
                }
            }

    def load_state(self):
        """Load state from Google Cloud Storage"""
        try:
            bucket = self.storage_client.bucket(GCS_BUCKET_NAME)
            blob = bucket.blob(STATE_FILE_NAME)

            if blob.exists():
                content = blob.download_as_text()
                state = json.loads(content)
                logger.info("State loaded successfully from GCS")
                return state
            else:
                logger.info("No existing state found in GCS")
                return None
        except Exception as e:
            logger.error(f"Error loading state: {str(e)}")
            return None

    def save_state(self):
        """Save state to Google Cloud Storage"""
        try:
            bucket = self.storage_client.bucket(GCS_BUCKET_NAME)
            blob = bucket.blob(STATE_FILE_NAME)

            # Convert datetime objects to strings
            state_copy = json.loads(json.dumps(self.state, default=str))

            blob.upload_from_string(
                json.dumps(state_copy, indent=2),
                content_type="application/json"
            )
            logger.info("State saved successfully to GCS")
        except Exception as e:
            logger.error(f"Error saving state: {str(e)}")

    def reset_rate_limits_if_needed(self):
        """Reset rate limits if a day or hour has passed"""
        now = datetime.now()
        last_reset = datetime.fromisoformat(self.state["dm_count"]["last_reset"])
        last_hourly_reset = datetime.fromisoformat(self.state["dm_count"]["last_hourly_reset"])

        # Reset daily limit if a day has passed
        if (now - last_reset).days >= 1:
            self.state["dm_count"]["daily"] = 0
            self.state["dm_count"]["last_reset"] = now.isoformat()
            logger.info("Daily DM limit reset")

        # Reset hourly limit if an hour has passed
        if (now - last_hourly_reset).seconds >= 3600:
            self.state["dm_count"]["hourly"] = 0
            self.state["dm_count"]["last_hourly_reset"] = now.isoformat()
            logger.info("Hourly DM limit reset")

    def can_send_dm(self):
        """Check if we can send a DM based on rate limits"""
        self.reset_rate_limits_if_needed()

        # Check if we've hit the daily or hourly limit
        if self.state["dm_count"]["daily"] >= DAILY_DM_LIMIT:
            logger.info("Daily DM limit reached")
            return False

        if self.state["dm_count"]["hourly"] >= HOURLY_DM_LIMIT:
            logger.info("Hourly DM limit reached")
            return False

        # Check if minimum time between DMs has passed
        last_dm_time = datetime.fromisoformat(self.state["last_dm_time"])
        time_since_last_dm = (datetime.now() - last_dm_time).seconds

        if time_since_last_dm < MIN_TIME_BETWEEN_DMS:
            logger.info(f"Minimum time between DMs not reached. Waiting {MIN_TIME_BETWEEN_DMS - time_since_last_dm} more seconds")
            return False

        return True

    def get_my_recent_tweets(self, count=10):
        """Get your recent tweets"""
        try:
            user_id = self.client.get_user(username=YOUR_TWITTER_USERNAME).data.id
            tweets = self.client.get_users_tweets(
                id=user_id,
                max_results=count,
                tweet_fields=["created_at", "public_metrics"]
            )
            return tweets.data if tweets.data else []
        except Exception as e:
            logger.error(f"Error getting recent tweets: {str(e)}")
            return []

    def get_tweet_interactions(self, tweet_id):
        """Get users who have interacted with a tweet"""
        interactions = {
            "likers": [],
            "retweeters": [],
            "repliers": []
        }

        try:
            # Get users who liked the tweet
            liking_users = self.client.get_liking_users(tweet_id)
            if liking_users.data:
                interactions["likers"] = liking_users.data

            # Get users who retweeted the tweet
            retweeters = self.client.get_retweeters(tweet_id)
            if retweeters.data:
                interactions["retweeters"] = retweeters.data

            # Get replies to the tweet
            tweet = self.client.get_tweet(
                tweet_id,
                expansions=["referenced_tweets.id", "author_id"],
                tweet_fields=["conversation_id"]
            )

            if tweet.data:
                conversation_id = tweet.data.conversation_id
                # Get replies in the conversation
                search_query = f"conversation_id:{conversation_id}"
                replies = self.client.search_recent_tweets(
                    query=search_query,
                    max_results=100,
                    expansions=["author_id"],
                    tweet_fields=["created_at", "text"]
                )

                if replies.data:
                    interactions["repliers"] = []
                    for reply in replies.data:
                        # Check if this is a reply to our tweet
                        if reply.author_id != tweet.data.author_id:
                            # Get user info
                            user = self.client.get_user(id=reply.author_id).data
                            if user:
                                interactions["repliers"].append({
                                    "user": user,
                                    "text": reply.text,
                                    "created_at": reply.created_at
                                })

            return interactions
        except Exception as e:
            logger.error(f"Error getting tweet interactions: {str(e)}")
            return interactions

    def should_respond_to_comment(self, comment_text):
        """Check if we should respond to a comment based on keywords"""
        comment_lower = comment_text.lower()

        # Check for exclusion keywords first
        for keyword in EXCLUSION_KEYWORDS:
            if keyword.lower() in comment_lower:
                return False, None

        # Check for trigger keywords
        for keyword in TRIGGER_KEYWORDS:
            if keyword.lower() in comment_lower:
                return True, keyword

        return False, None

    def get_resource_for_user(self, tweet_text, reply_text):
        """Determine the best resource to send based on tweet and reply content"""
        # Combine tweet and reply text for analysis
        combined_text = (tweet_text + " " + reply_text).lower()

        # Score each resource based on keyword matches
        resource_scores = {}
        for resource_id, resource_data in RESOURCES.items():
            score = 0
            for keyword in resource_data["keywords"]:
                if keyword in combined_text:
                    score += 1
            resource_scores[resource_id] = score

        # Get the resource with the highest score
        if resource_scores:
            best_resource_id = max(resource_scores.items(), key=lambda x: x[1])[0]
            if resource_scores[best_resource_id] > 0:
                return RESOURCES[best_resource_id]

        # Default resource if no matches
        return {
            "name": "Guide",
            "description": "educational guide"
        }

    def get_user_segment(self, user_id, username):
        """Determine user segment based on past interactions"""
        if str(user_id) in self.state["processed_users"]:
            user_data = self.state["processed_users"][str(user_id)]
            dm_count = user_data.get("dm_count", 0)

            if dm_count >= 3:
                return "highly_engaged"
            elif dm_count >= 1:
                return "engaged"

        # Check if user is a follower
        try:
            friendship = self.api.get_friendship(source_screen_name=YOUR_TWITTER_USERNAME, target_screen_name=username)
            if friendship[0].followed_by:
                return "follower"
        except Exception as e:
            logger.error(f"Error checking friendship: {str(e)}")

        return "new"

    def send_dm(self, user_id, username, content_type="giveaway", resource_name="guide", resource_description="educational guide"):
        """Send a direct message to a user with A/B testing"""
        if not self.can_send_dm():
            return False

        try:
            # Select A/B test variant (50/50 split)
            variant = "A" if random.random() < 0.5 else "B"

            # Select a random message template from the variant
            templates = DM_TEMPLATES[content_type][variant]
            template = random.choice(templates)

            # Format the message
            message = template.format(
                username=username,
                content_type=content_type,
                resource_name=resource_name,
                resource_description=resource_description
            )

            # Send the DM
            self.client.create_direct_message(participant_id=user_id, text=message)

            # Update rate limiting counters
            self.state["dm_count"]["daily"] += 1
            self.state["dm_count"]["hourly"] += 1
            self.state["last_dm_time"] = datetime.now().isoformat()

            # Update metrics
            self.state["metrics"]["total_dms_sent"] += 1

            # Track A/B test results
            if "ab_test_results" not in self.state["metrics"]:
                self.state["metrics"]["ab_test_results"] = {"A": 0, "B": 0}

            self.state["metrics"]["ab_test_results"][variant] += 1

            # Track keyword that triggered the response
            if "responses_by_keyword" not in self.state["metrics"]:
                self.state["metrics"]["responses_by_keyword"] = {}

            if content_type not in self.state["metrics"]["responses_by_keyword"]:
                self.state["metrics"]["responses_by_keyword"][content_type] = 0

            self.state["metrics"]["responses_by_keyword"][content_type] += 1

            # Mark user as processed
            self.state["processed_users"][str(user_id)] = {
                "username": username,
                "last_dm_sent": datetime.now().isoformat(),
                "dm_count": self.state["processed_users"].get(str(user_id), {}).get("dm_count", 0) + 1,
                "content_type": content_type,
                "resource_name": resource_name,
                "resource_description": resource_description,
                "ab_test_variant": variant
            }

            logger.info(f"DM sent to {username} (ID: {user_id}) using variant {variant}")
            return True
        except Exception as e:
            logger.error(f"Error sending DM to {username}: {str(e)}")
            return False

    def process_tweet_interactions(self, tweet_id, tweet_text):
        """Process interactions on a tweet and send DMs to users who meet criteria"""
        if str(tweet_id) in self.state["processed_tweets"]:
            # Only process new interactions since last check
            last_processed = datetime.fromisoformat(self.state["processed_tweets"][str(tweet_id)]["last_processed"])
        else:
            # First time processing this tweet
            self.state["processed_tweets"][str(tweet_id)] = {
                "last_processed": datetime.now().isoformat(),
                "processed_users": []
            }
            last_processed = datetime.now() - timedelta(days=7)  # Process interactions from the last 7 days

        # Get interactions
        interactions = self.get_tweet_interactions(tweet_id)

        # Process replies first (they have the most intent)
        for reply in interactions.get("repliers", []):
            user = reply["user"]
            user_id = user.id
            username = user.username

            # Skip if we've already processed this user for this tweet
            if str(user_id) in self.state["processed_tweets"][str(tweet_id)]["processed_users"]:
                continue

            # Skip if we've already sent a DM to this user recently
            if str(user_id) in self.state["processed_users"]:
                last_dm = datetime.fromisoformat(self.state["processed_users"][str(user_id)]["last_dm_sent"])
                if (datetime.now() - last_dm).days < 7:  # Don't DM the same user more than once a week
                    continue

            # Check if the reply contains trigger keywords
            should_respond, keyword = self.should_respond_to_comment(reply["text"])

            if should_respond:
                # Get user segment
                user_segment = self.get_user_segment(user_id, username)
                logger.info(f"User @{username} is in segment: {user_segment}")

                # Determine resource based on tweet and reply content
                resource = self.get_resource_for_user(tweet_text, reply["text"])
                resource_name = resource["name"]
                resource_description = resource["description"]

                # Customize approach based on segment
                if user_segment == "highly_engaged":
                    # For highly engaged users, offer premium content
                    resource_name = "Premium " + resource_name
                    resource_description = "premium " + resource_description

                # Send DM
                success = self.send_dm(
                    user_id,
                    username,
                    "giveaway",
                    resource_name,
                    resource_description
                )

                if success:
                    # Mark user as processed for this tweet
                    self.state["processed_tweets"][str(tweet_id)]["processed_users"].append(str(user_id))

                    # Update dashboard after sending DM
                    self.create_metrics_dashboard()

        # Update last processed time
        self.state["processed_tweets"][str(tweet_id)]["last_processed"] = datetime.now().isoformat()

        # Update metrics
        self.state["metrics"]["total_interactions"] += len(interactions.get("likers", [])) + len(interactions.get("retweeters", [])) + len(interactions.get("repliers", []))
        if self.state["metrics"]["total_interactions"] > 0:
            self.state["metrics"]["conversion_rate"] = (self.state["metrics"]["total_dms_sent"] / self.state["metrics"]["total_interactions"]) * 100

    def send_follow_up_messages(self):
        """Send follow-up messages to users who received a giveaway DM more than 3 days ago"""
        for user_id, user_data in self.state["processed_users"].items():
            # Skip if we've already sent more than 2 DMs to this user
            if user_data.get("dm_count", 0) >= 3:
                continue

            # Check if it's been at least 3 days since the last DM
            last_dm = datetime.fromisoformat(user_data["last_dm_sent"])
            days_since_last_dm = (datetime.now() - last_dm).days

            if days_since_last_dm >= 3 and days_since_last_dm < 4:  # Send follow-up only once, on day 3
                # Send follow-up DM
                success = self.send_dm(
                    int(user_id),
                    user_data["username"],
                    "follow_up",
                    user_data.get("resource_name", "guide"),
                    user_data.get("resource_description", "educational guide")
                )

                if success:
                    logger.info(f"Follow-up DM sent to {user_data['username']}")

    def create_metrics_dashboard(self):
        """Create a simple HTML dashboard for metrics"""
        try:
            # Create HTML
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Twitter Auto Responder Metrics</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .card {{ background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                    .metric {{ font-size: 24px; font-weight: bold; color: #1DA1F2; }}
                    .label {{ font-size: 14px; color: #666; }}
                    .container {{ max-width: 800px; margin: 0 auto; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Twitter Auto Responder Metrics</h1>
                    <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

                    <div class="card">
                        <div class="metric">{self.state["metrics"].get('total_dms_sent', 0)}</div>
                        <div class="label">Total DMs Sent</div>
                    </div>

                    <div class="card">
                        <div class="metric">{self.state["metrics"].get('total_interactions', 0)}</div>
                        <div class="label">Total Interactions</div>
                    </div>

                    <div class="card">
                        <div class="metric">{self.state["metrics"].get('conversion_rate', 0):.2f}%</div>
                        <div class="label">Conversion Rate</div>
                    </div>

                    <h2>A/B Testing Results</h2>
                    <div class="card">
                        <div class="metric">Variant A: {self.state["metrics"].get('ab_test_results', {}).get('A', 0)}</div>
                        <div class="metric">Variant B: {self.state["metrics"].get('ab_test_results', {}).get('B', 0)}</div>
                    </div>

                    <h2>Responses by Keyword</h2>
                    <div class="card">
                        <table width="100%">
                            <tr>
                                <th align="left">Keyword</th>
                                <th align="right">Count</th>
                            </tr>
            """

            # Add keyword stats
            for keyword, count in self.state["metrics"].get("responses_by_keyword", {}).items():
                html += f"""
                            <tr>
                                <td>{keyword}</td>
                                <td align="right">{count}</td>
                            </tr>
                """

            html += """
                        </table>
                    </div>

                    <h2>Recent Activity</h2>
                    <div class="card">
                        <table width="100%">
                            <tr>
                                <th align="left">Username</th>
                                <th align="left">Resource</th>
                                <th align="left">Segment</th>
                                <th align="right">Date</th>
                            </tr>
            """

            # Add recent activity
            recent_users = sorted(
                self.state.get("processed_users", {}).items(),
                key=lambda x: x[1].get("last_dm_sent", ""),
                reverse=True
            )[:10]

            for user_id, user_data in recent_users:
                # Get user segment
                segment = self.get_user_segment(int(user_id), user_data.get('username', ''))

                html += f"""
                            <tr>
                                <td>@{user_data.get('username', '')}</td>
                                <td>{user_data.get('resource_name', '')}</td>
                                <td>{segment}</td>
                                <td align="right">{user_data.get('last_dm_sent', '').split('T')[0]}</td>
                            </tr>
                """

            html += """
                        </table>
                    </div>
                </div>
            </body>
            </html>
            """

            # Save dashboard to Cloud Storage
            bucket = self.storage_client.bucket(GCS_BUCKET_NAME)
            dashboard_blob = bucket.blob("dashboard.html")
            dashboard_blob.upload_from_string(html, content_type="text/html")

            # Make it publicly accessible
            dashboard_blob.make_public()

            logger.info(f"Dashboard updated and available at: {dashboard_blob.public_url}")
            return dashboard_blob.public_url
        except Exception as e:
            logger.error(f"Error creating dashboard: {str(e)}")
            return None

    def run(self):
        """Main function to run the auto-responder"""
        logger.info("Starting Twitter Auto Responder")

        try:
            # Get recent tweets
            recent_tweets = self.get_my_recent_tweets(count=5)

            if not recent_tweets:
                logger.info("No recent tweets found")
                return

            # Process each tweet
            for tweet in recent_tweets:
                logger.info(f"Processing tweet: {tweet.id}")
                self.process_tweet_interactions(tweet.id, tweet.text)

            # Send follow-up messages
            self.send_follow_up_messages()

            # Create metrics dashboard
            dashboard_url = self.create_metrics_dashboard()
            if dashboard_url:
                logger.info(f"Dashboard available at: {dashboard_url}")

            # Save state
            self.save_state()

            logger.info("Twitter Auto Responder completed successfully")
        except Exception as e:
            logger.error(f"Error running Twitter Auto Responder: {str(e)}")

# This is the Cloud Functions entry point
@functions_framework.http
def twitter_auto_responder(request):
    """HTTP Cloud Function entry point"""
    try:
        responder = TwitterAutoResponder()
        responder.run()
        return "Twitter Auto Responder executed successfully"
    except Exception as e:
        logger.error(f"Error in Cloud Function: {str(e)}")
        return f"Error: {str(e)}", 500

# For local testing
if __name__ == "__main__":
    responder = TwitterAutoResponder()
    responder.run()
