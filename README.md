# Automated Rating Handler for NBCCo

A production-ready system for automatically collecting operator ratings via SMS and managing quality assurance.

## Features

✅ **Automated SMS Workflows**
- Automatically sends rating prompts when jobs complete
- Captures 1-5 star ratings via inbound SMS
- Sends confirmation messages to users

✅ **Performance Tracking**
- Calculates moving average ratings
- Tracks operator statistics (min, max, std deviation)
- Identifies top performers and at-risk operators

✅ **Quality Assurance**
- Auto-bans operators with average rating < 3.0 across 2+ transactions
- Blocks banned operators from future job matching
- Notifies operators of ban status

✅ **Analytics & Reporting**
- Real-time performance dashboards
- Comprehensive operator statistics
- Historical rating trends

## System Architecture

```
Job Completion Event
        |
        v
[RatingHandler] --> [Database] (Stores job, request, operator data)
        |
        v
[SMSService] --> [Twilio API] (Sends rating prompt SMS)
        |
        v
User Replies 1-5
        |
        v
[SMSWebhook] <-- [Twilio API] (Receives inbound SMS)
        |
        v
[RatingHandler] --> [Database] (Stores rating, updates average)
        |
        v
[Auto-Ban Logic] --> [Database] (Updates operator status if needed)
```

## Installation

### Prerequisites
- Python 3.8+
- Twilio account (or use mock service for testing)
- SQLite3

### Setup

1. **Clone or download the project files**

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your Twilio credentials:
   ```
   TWILIO_ACCOUNT_SID=your_account_sid
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_PHONE_NUMBER=+1234567890
   USE_MOCK_SMS=false
   ```

4. **For development/testing** (no Twilio needed):
   ```
   USE_MOCK_SMS=true
   ```

## Usage

### Starting the Webhook Server

```bash
python sms_webhook.py
```

Server runs on `http://localhost:5000` by default.

### Integrating with Your Application

```python
from job_completion_trigger import initialize, trigger_job_completed

# Initialize once at startup
initialize()

# When a job completes, trigger the rating workflow
result = trigger_job_completed(
    job_id="JOB-12345",
    user_phone="+1234567890",      # Customer's phone
    operator_phone="+0987654321",   # Operator's phone
    operator_id="OP-001"            # Operator's database ID
)

print(result)
# Output: {"status": "success", "message": "Rating prompt sent", "request_id": "REQ-..."}
```

### Testing with Mock SMS

For development without Twilio:

```bash
# Set USE_MOCK_SMS=true in .env
python sms_webhook.py
```

#### Test Endpoints

**1. Simulate Job Completion**
```bash
curl -X POST http://localhost:5000/test-job-complete \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "JOB-123",
    "user_phone": "+1234567890",
    "operator_phone": "+0987654321",
    "operator_id": "OP-1"
  }'
```

**2. Simulate Rating Submission**
```bash
curl -X POST http://localhost:5000/test-rating \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "REQ-JOB-123-1234567890",
    "operator_id": "OP-1",
    "rating": 4
  }'
```

**3. Get Operator Statistics**
```bash
curl http://localhost:5000/stats/operators/OP-1
```

**4. Get Top Performers**
```bash
curl http://localhost:5000/stats/top-performers
```

**5. Get At-Risk Operators**
```bash
curl http://localhost:5000/stats/at-risk
```

**6. View Mock Messages (testing only)**
```bash
curl http://localhost:5000/mock/sent-messages
```

**7. Health Check**
```bash
curl http://localhost:5000/health
```

## API Reference

### Webhook Endpoints

#### POST `/sms/webhook`
Twilio webhook endpoint for inbound SMS.

**Expected Twilio form data:**
- `From`: Sender's phone number
- `Body`: Message text (rating 1-5)
- `MessageSid`: Unique message ID

**Response:**
```json
{
  "status": "success",
  "rating": 4,
  "new_average": 3.75,
  "transaction_count": 4,
  "ban_applied": false
}
```

#### POST `/test-job-complete`
Test endpoint to simulate job completion.

**Request Body:**
```json
{
  "job_id": "JOB-123",
  "user_phone": "+1234567890",
  "operator_phone": "+0987654321",
  "operator_id": "OP-1"
}
```

#### POST `/test-rating`
Test endpoint to submit a rating.

**Request Body:**
```json
{
  "request_id": "REQ-JOB-123-1234567890",
  "operator_id": "OP-1",
  "rating": 4
}
```

#### GET `/stats/operators/<operator_id>`
Get statistics for an operator.

**Response:**
```json
{
  "operator_id": "OP-1",
  "name": "John Operator",
  "phone_number": "+0987654321",
  "status": "Active",
  "average_rating": 4.5,
  "total_ratings": 4,
  "completed_transactions": 4,
  "min_rating": 4,
  "max_rating": 5,
  "std_deviation": 0.5,
  "blocked_from_queue": false,
  "rating_breakdown": {"1": 0, "2": 0, "3": 0, "4": 2, "5": 2}
}
```

#### GET `/stats/top-performers`
Get top 10 performing operators.

#### GET `/stats/at-risk`
Get operators at risk of being banned.

#### GET `/health`
Health check endpoint.

## Auto-Ban Logic

Operators are automatically banned when:
- **Average rating < 3.0 stars** AND
- **More than 2 completed transactions**

When an operator is banned:
1. Account status updated to "Banned"
2. Blocked from future job matching queue
3. Notification SMS sent to operator

## Database Schema

### Tables

**operators**
- `id` (TEXT, PRIMARY KEY)
- `name` (TEXT)
- `phone_number` (TEXT, UNIQUE)
- `email` (TEXT)
- `status` (TEXT: 'Active', 'Banned')
- `average_rating` (REAL)
- `created_at` (TIMESTAMP)
- `updated_at` (TIMESTAMP)
- `blocked_from_queue` (BOOLEAN)

**jobs**
- `id` (TEXT, PRIMARY KEY)
- `operator_id` (TEXT, FK)
- `user_phone` (TEXT)
- `operator_phone` (TEXT)
- `status` (TEXT: 'Pending', 'Completed')
- `completion_time` (TIMESTAMP)
- `created_at` (TIMESTAMP)

**rating_requests**
- `id` (TEXT, PRIMARY KEY)
- `job_id` (TEXT, FK)
- `operator_id` (TEXT, FK)
- `user_phone` (TEXT)
- `status` (TEXT: 'pending', 'completed')
- `created_at` (TIMESTAMP)
- `completed_at` (TIMESTAMP)

**ratings**
- `id` (INTEGER, PRIMARY KEY)
- `request_id` (TEXT, FK)
- `operator_id` (TEXT, FK)
- `rating` (INTEGER: 1-5)
- `feedback` (TEXT)
- `timestamp` (TIMESTAMP)

## Configuration

### Environment Variables

```
# Twilio
TWILIO_ACCOUNT_SID          Your Twilio account SID
TWILIO_AUTH_TOKEN           Your Twilio auth token
TWILIO_PHONE_NUMBER         Twilio phone number for sending SMS

# SMS Service
USE_MOCK_SMS                true/false - Use mock service for testing
SKIP_TWILIO_VALIDATION      true/false - Skip signature validation (dev only)

# Database
DB_PATH                     Path to SQLite database (default: nbcco_ratings.db)

# Flask
FLASK_DEBUG                 true/false - Enable debug mode
PORT                        Port to run on (default: 5000)
```

## Troubleshooting

### "Missing Twilio credentials"
- Set `USE_MOCK_SMS=true` in .env to use mock service
- OR add real Twilio credentials to .env

### "No pending rating request found"
- Ensure job completion was triggered first
- Check that user_phone matches between job completion and rating submission

### "Invalid rating input"
- User must reply with a number 1-5
- No additional text or characters

### Database Locked
- Ensure only one instance of the application is running
- SQLite doesn't handle concurrent writes well in production

## Production Considerations

1. **Database**: Replace SQLite with PostgreSQL/MySQL for production
2. **SMS Provider**: Configure real Twilio credentials
3. **Webhooks**: Set up proper HTTPS and deploy to a public server
4. **Security**: Validate Twilio signatures in production
5. **Monitoring**: Add logging and monitoring
6. **Scaling**: Use message queue (Redis/RabbitMQ) for high volume

## Example Integration

```python
# main.py
from flask import Flask
from job_completion_trigger import initialize, trigger_job_completed

app = Flask(__name__)

# Initialize at startup
@app.before_first_request
def startup():
    initialize(db_path="nbcco_ratings.db", use_mock_sms=False)

# In your job completion handler
@app.route("/jobs/<job_id>/complete", methods=["POST"])
def complete_job(job_id):
    # ... your job completion logic ...
    
    # Trigger rating workflow
    result = trigger_job_completed(
        job_id=job_id,
        user_phone=request.json["user_phone"],
        operator_phone=request.json["operator_phone"],
        operator_id=request.json["operator_id"]
    )
    
    return {"status": "ok", "rating_initiated": result["status"] == "success"}

if __name__ == "__main__":
    app.run()
```

## License

MIT License - See LICENSE file for details

## Support

For issues or questions, please contact the development team.
