````markdown
# NBCCo Automated Rating Handler

## Overview

This is a production-ready automated rating system for the NBCCo platform. When a job is completed, the system:

1. **Sends SMS Prompt**: "Reply 1 to 5 to rate this operator"
2. **Captures Rating**: Validates inbound 1-5 integer response
3. **Calculates Moving Average**: Updates operator's average rating in real-time
4. **Auto-Bans Low Performers**: If rating < 3.0 AND transactions > 2:
   - Sets account status to "Banned"
   - Blocks operator from future matching queues
   - Notifies operator via SMS

## Features

✅ Automated SMS workflow for job rating  
✅ Real-time moving average calculations  
✅ Conditional auto-ban logic for low performers  
✅ Operator performance analytics & reporting  
✅ Production-ready with comprehensive error handling  
✅ SQLite database with schema & indices  
✅ Twilio integration + mock service for testing  
✅ Flask webhook server for inbound SMS  
✅ Comprehensive logging & monitoring  

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ Your Application (NBCCo)                             │
└──────────────────┬──────────────────────────────────┘
                   │ Job Completion Event
                   ▼
┌──────────────────────────────────────────────────────┐
│ job_completion_trigger.py (Event Handler)            │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────┐
│ rating_handler.py (Orchestration)                    │
├─ Sends SMS prompt ──────┐                            │
├─ Creates rating request │                            │
└─ Monitors for response  │                            │
                          ▼
┌─────────────────────────────────────────────────────┐
│ sms_service.py (Twilio)                             │
│ Sends: "Reply 1 to 5 to rate this operator"        │
└─────────────────────────────────────────────────────┘
                          │
         User replies (1-5) via SMS
                          │
                          ▼
┌──────────────────────────────────────────────────────┐
│ sms_webhook.py (Flask Server - /sms/webhook)        │
│ Receives inbound SMS                                │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────┐
│ rating_handler.py (Process Rating Reply)            │
├─ Validates rating (1-5)                             │
├─ Records in database                                │
├─ Calculates new average                             │
├─ Checks ban conditions                              │
└─────────────────┬────────────────────────────────────┘
                  │
    ┌─────────────┴─────────────┐
    │                           │
    ▼                           ▼
Rating < 3.0 &            Normal Case
Transactions > 2          │
    │                     │
    ▼                     ▼
┌─────────────────┐   ┌──────────────────┐
│ BAN OPERATOR    │   │ Update Average   │
│ - Status        │   │ Send Confirmation│
│ - Block Queue   │   │ SMS              │
│ - Notify        │   │                  │
└─────────────────┘   └──────────────────┘
    │                     │
    └─────────────┬───────┘
                  ▼
         ┌─────────────────────┐
         │ database.py         │
         │ SQLite Persistence  │
         └─────────────────────┘
```

## Installation

### 1. Clone/Download Files

```bash
# Files to include:
- rating_handler.py
- database.py
- rating_calculator.py
- sms_service.py
- sms_webhook.py
- job_completion_trigger.py
- requirements.txt
- .env.example
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env

# Edit .env with your values:
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
USE_MOCK_SMS=false  # Set to true for testing
```

## Usage

### Option 1: Using Mock SMS (Development/Testing)

```bash
# Set environment variable
export USE_MOCK_SMS=true

# Run webhook server
python sms_webhook.py

# In another terminal, test:
curl -X POST http://localhost:5000/test-job-complete \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "JOB-123",
    "user_phone": "+1111111111",
    "operator_phone": "+2222222222",
    "operator_id": "OP-1"
  }'

# Test rating submission:
curl -X POST http://localhost:5000/test-rating \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "REQ-JOB-123",
    "operator_id": "OP-1",
    "rating": 4
  }'
```

### Option 2: Using Real Twilio (Production)

```bash
# Update .env with Twilio credentials
export USE_MOCK_SMS=false

# Run webhook server
python sms_webhook.py

# Deploy on public server with HTTPS
# Update Twilio webhook URL to: https://your-domain.com/sms/webhook
```

### Option 3: Integrate with Your Code

```python
from job_completion_trigger import trigger_job_completed

# In your job completion handler:
def on_job_complete(job_id, customer_phone, operator_phone, operator_id):
    # Your job logic here...
    
    # Trigger rating workflow
    result = trigger_job_completed(
        job_id=job_id,
        user_phone=customer_phone,
        operator_phone=operator_phone,
        operator_id=operator_id
    )
    
    if result.get("status") == "success":
        print(f"Rating request sent: {result.get('request_id')}")
    else:
        print(f"Failed to send rating: {result.get('message')}")
```

## API Endpoints

### SMS Webhook
**POST** `/sms/webhook`
- Receives inbound SMS from Twilio
- Required: From, Body, MessageSid
- Optional: request_id, job_id, operator_id

### Test Job Completion
**POST** `/test-job-complete`
```json
{
  "job_id": "JOB-123",
  "user_phone": "+1111111111",
  "operator_phone": "+2222222222",
  "operator_id": "OP-1"
}
```

### Test Rating
**POST** `/test-rating`
```json
{
  "request_id": "REQ-123",
  "operator_id": "OP-1",
  "rating": 4
}
```

### Health Check
**GET** `/health`
Returns: `{"status": "healthy", "timestamp": "...", "service": "NBCCo Rating Handler"}`

### Get Operator Stats
**GET** `/stats?operator_id=OP-1`
Returns comprehensive operator statistics

### Get At-Risk Operators
**GET** `/operators/at-risk`
Returns operators below 3.0 average with >2 transactions

## Database Schema

### operators
- id (TEXT PRIMARY KEY)
- name (TEXT)
- phone_number (TEXT UNIQUE)
- email (TEXT)
- status (TEXT: 'Active' or 'Banned')
- average_rating (REAL)
- blocked_from_queue (BOOLEAN)
- created_at, updated_at (TIMESTAMP)

### jobs
- id (TEXT PRIMARY KEY)
- operator_id (FOREIGN KEY)
- user_phone (TEXT)
- operator_phone (TEXT)
- status (TEXT: 'Pending', 'Completed')
- completion_time (TIMESTAMP)

### rating_requests
- id (TEXT PRIMARY KEY)
- job_id (FOREIGN KEY)
- operator_id (FOREIGN KEY)
- user_phone (TEXT)
- status (TEXT: 'pending', 'completed')
- created_at, completed_at (TIMESTAMP)

### ratings
- id (INTEGER PRIMARY KEY)
- request_id (FOREIGN KEY)
- operator_id (FOREIGN KEY)
- rating (INTEGER: 1-5)
- feedback (TEXT)
- timestamp (TIMESTAMP)

## Ban Logic

An operator is automatically banned when:

```python
IF average_rating < 3.0 AND total_transactions > 2:
    status = "Banned"
    blocked_from_queue = True
    send_ban_notification()
```

Example:
- Operator completes 3 jobs with ratings: 2, 2, 3
- Average: 2.33 (< 3.0)
- Transactions: 3 (> 2)
- **Result**: Operator is BANNED

## Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| TWILIO_ACCOUNT_SID | - | Twilio account identifier |
| TWILIO_AUTH_TOKEN | - | Twilio authentication token |
| TWILIO_PHONE_NUMBER | - | Twilio phone number for SMS |
| USE_MOCK_SMS | true | Use mock service (development) |
| SKIP_TWILIO_VALIDATION | false | Skip webhook signature validation |
| DEBUG | false | Flask debug mode |
| PORT | 5000 | Server port |
| DATABASE_PATH | nbcco_ratings.db | SQLite database file |

## Troubleshooting

### SMS not sending
- Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN
- Ensure TWILIO_PHONE_NUMBER is valid
- For testing, set USE_MOCK_SMS=true

### Ratings not processing
- Check database file exists (nbcco_ratings.db)
- Verify operator_id is provided
- Check logs for error messages

### Webhook not receiving messages
- Ensure server is publicly accessible
- Update Twilio webhook URL
- Verify SKIP_TWILIO_VALIDATION setting
- Check Flask debug logs

## Performance Metrics

The system includes analytics via `rating_calculator.py`:

```python
from rating_calculator import RatingCalculator

calc = RatingCalculator(db_manager)

# Get top performers
top_10 = calc.get_top_performers(limit=10)

# Get at-risk operators
at_risk = calc.get_at_risk_operators(rating_threshold=3.0)

# Get performance score (0-100)
score = calc.calculate_performance_score(operator_id)

# Get recent trends
trends = calc.get_recent_ratings(operator_id, days=7)
```

## Production Deployment

### Using Gunicorn
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 sms_webhook:app
```

### Using Docker
```dockerfile
FROM python:3.9
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "sms_webhook:app"]
```

### Environment Setup
- Use environment variables for all secrets
- Enable HTTPS for webhook URL
- Set up database backups
- Enable monitoring/logging to external service
- Configure rate limiting

## License

Proprietary - NBCCo

## Support

For issues or questions, refer to the inline code documentation or contact the development team.
````
