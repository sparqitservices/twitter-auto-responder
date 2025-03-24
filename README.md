# Twitter Auto-Responder

![Twitter Auto-Responder Dashboard](screenshots/dashboard.png)

## Overview

Twitter Auto-Responder is an automated engagement tool that monitors your Twitter activity and sends personalized direct messages to users who interact with your content. Built with Python and Google Cloud, it helps content creators scale their audience engagement and distribute resources efficiently.

## Features

- **Automated DM Responses**: Sends personalized messages to users who engage with your tweets
- **Keyword Targeting**: Identifies engagement based on specific trigger keywords
- **Smart Resource Sharing**: Matches resources to user interests based on context
- **Follow-up System**: Automatically sends follow-up messages to increase conversion
- **Rate Limiting**: Respects Twitter API limits to prevent account restrictions
- **Analytics Dashboard**: Real-time metrics on engagement and conversion rates
- **Serverless Architecture**: Runs on Google Cloud Functions with scheduled execution

## Technology Stack

- **Python 3.9**: Core programming language
- **Tweepy**: Twitter API client library
- **Google Cloud Functions**: Serverless execution environment
- **Google Cloud Storage**: State management and dashboard hosting
- **Google Cloud Scheduler**: Automated execution timing
- **Bootstrap 5**: Dashboard UI framework

## System Architecture

![System Architecture](architecture.png)

The system operates through these components:
1. **Cloud Scheduler** triggers the Cloud Function every 30 minutes
2. **Cloud Function** fetches recent tweets and interactions
3. **Twitter API** provides engagement data and enables DM sending
4. **Cloud Storage** maintains state between executions and hosts the dashboard
5. **Analytics Dashboard** displays performance metrics and recent activity

## Setup Instructions

### Prerequisites

- Google Cloud Platform account
- Twitter Developer account with API access
- Python 3.9+

### Installation

1. Clone this repository:

git clone https://github.com/yourusername/twitter-auto-responder.git
cd twitter-auto-responder


2. Install dependencies:
pip install -r requirements.txt


3. Create a `.env` file with your credentials (see `.env.example`)

4. Create a Google Cloud Storage bucket:
gsutil mb gs://twitter-responder-state


5. Deploy the Cloud Function:
gcloud functions deploy twitter_auto_responder \
--runtime python39 \
--trigger-http \
--region us-central1 \
--timeout 540s \
--memory 256MB


6. Set up the Cloud Scheduler:
gcloud scheduler jobs create http twitter-responder-scheduler \
--schedule "*/30 * * * *" \
--uri "https://us-central1-YOUR-PROJECT-ID.cloudfunctions.net/twitter_auto_responder" \
--http-method GET \
--time-zone "Asia/Kolkata" \
--location us-central1


7. Make the dashboard bucket publicly accessible:
gsutil iam ch allUsers:objectViewer gs://twitter-responder-state


## Configuration Options

The system can be customized by modifying these variables in `main.py`:

- `TRIGGER_KEYWORDS`: Words that indicate interest in your content
- `EXCLUSION_KEYWORDS`: Words that indicate a user doesn't want DMs
- `DM_TEMPLATES`: Message templates for different interaction types
- `DAILY_DM_LIMIT`: Maximum DMs per day (default: 50)
- `HOURLY_DM_LIMIT`: Maximum DMs per hour (default: 15)

## Dashboard

The analytics dashboard provides real-time insights into your auto-responder's performance:

- Total DMs sent
- Engagement metrics
- Conversion rates
- Keyword performance
- Recent activity log
- Rate limit usage

Access your dashboard at:
https://storage.googleapis.com/twitter-responder-state/dashboard.html


## Security Considerations

- API credentials are stored as environment variables
- Rate limiting prevents API abuse
- User data is stored securely in Google Cloud Storage
- No sensitive information is displayed on the public dashboard

## Challenges and Solutions

### Challenge: Twitter API Rate Limits
**Solution**: Implemented tiered rate limiting with daily and hourly caps, plus minimum intervals between messages.

### Challenge: Maintaining State Between Executions
**Solution**: Used Google Cloud Storage to persist interaction history and metrics between function invocations.

### Challenge: Identifying Relevant Interactions
**Solution**: Developed a keyword-based filtering system with exclusion terms to target only genuinely interested users.

## Future Improvements

- Machine learning for response personalization
- A/B testing of different message templates
- Integration with CRM systems
- Multi-language support
- Enhanced analytics with conversion tracking
- Web interface for configuration changes

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Created by [Your Name](https://yourportfolio.com) - Feel free to connect on [Twitter](https://twitter.com/yourusername) or [LinkedIn](https://linkedin.com/in/yourusername).

---

*Note: This project is for educational purposes. Always respect Twitter's terms of service and privacy guidelines when implementing automated systems.*
