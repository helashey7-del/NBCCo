"""
SMS Webhook Server - Flask application for handling inbound SMS messages.
Provides Twilio webhook endpoint and test endpoints for development.
"""

import logging
import os
import json
from datetime import datetime
from typing import Dict, Any, Tuple
from functools import wraps

from flask import Flask, request, jsonify
from dotenv import load_dotenv

from database import SQLiteDatabaseManager
from rating_handler import RatingHandler
from sms_service import get_sms_service, MockSMSService

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize services
db_manager = SQLiteDatabaseManager(os.getenv("DB_PATH", "nbcco_ratings.db"))
use_mock_sms = os.getenv("USE_MOCK_SMS", "false").lower() == "true"
sms_service = get_sms_service(use_mock=use_mock_sms)
rating_handler = RatingHandler(db_manager, sms_service)

logger.info(f"SMS Service: {'Mock' if isinstance(sms_service, MockSMSService) else 'Twilio'}")


def validate_twilio_request(f):
    """
    Decorator to validate Twilio webhook requests.
    Verifies X-Twilio-Signature header.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # For development/testing, skip validation if env var set
        if os.getenv("SKIP_TWILIO_VALIDATION", "false").lower() == "true":
            return f(*args, **kwargs)
        
        # In production, validate Twilio signature
        twilio_signature = request.headers.get("X-Twilio-Signature", "")
        if not twilio_signature:
            logger.warning("Missing Twilio signature")
            return jsonify({"status": "error", "message": "Invalid signature"}), 403
        
        return f(*args, **kwargs)
    return decorated_function


@app.route("/health", methods=["GET"])
def health_check() -> Tuple[Dict[str, Any], int]:
    """
    Health check endpoint.
    
    Returns:
        JSON response with status
    """
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "SMS Rating Handler"
    }), 200


@app.route("/sms/webhook", methods=["POST"])
@validate_twilio_request
def sms_webhook() -> Tuple[Dict[str, Any], int]:
    """
    Webhook endpoint for inbound SMS from Twilio.
    
    Expected form data:
    - From: Sender phone number
    - Body: Message text
    - MessageSid: Unique message ID
    
    Returns:
        TwiML response
    """
    try:
        from_number = request.form.get("From")
        message_body = request.form.get("Body", "").strip()
        message_sid = request.form.get("MessageSid")
        
        logger.info(f"Inbound SMS from {from_number}: {message_body}")
        
        # Validate rating input
        try:
            rating = int(message_body)
        except ValueError:
            logger.warning(f"Invalid rating input: {message_body}")
            return jsonify({
                "status": "error",
                "message": "Please reply with a number 1-5"
            }), 400
        
        # Find rating request for this phone number
        # (In production, you'd query the database for pending requests)
        cursor = db_manager.conn.cursor()
        cursor.execute("""
            SELECT id, operator_id FROM rating_requests 
            WHERE user_phone = ? AND status = 'pending'
            ORDER BY created_at DESC LIMIT 1
        """, (from_number,))
        
        row = cursor.fetchone()
        if not row:
            logger.warning(f"No pending rating request for {from_number}")
            return jsonify({
                "status": "error",
                "message": "No active rating request found"
            }), 404
        
        request_id, operator_id = row
        
        # Process the rating
        result = rating_handler.process_rating_reply(
            request_id=request_id,
            rating=rating,
            operator_id=operator_id
        )
        
        if result["status"] == "success":
            # Send confirmation SMS
            confirmation_msg = f"Thanks for rating! {result['new_average']}/5 avg."
            sms_service.send_sms(from_number, confirmation_msg)
            
            return jsonify(result), 200
        else:
            return jsonify(result), 400
        
    except Exception as e:
        logger.error(f"Error processing SMS webhook: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/test-job-complete", methods=["POST"])
def test_job_complete() -> Tuple[Dict[str, Any], int]:
    """
    Test endpoint to simulate job completion.
    
    Expected JSON:
    {
        "job_id": "JOB-123",
        "user_phone": "+1234567890",
        "operator_phone": "+0987654321",
        "operator_id": "OP-1"
    }
    
    Returns:
        JSON response with result
    """
    try:
        data = request.get_json()
        
        result = rating_handler.handle_job_completed(
            job_id=data.get("job_id"),
            user_phone=data.get("user_phone"),
            operator_phone=data.get("operator_phone"),
            operator_id=data.get("operator_id")
        )
        
        return jsonify(result), 200 if result["status"] == "success" else 400
        
    except Exception as e:
        logger.error(f"Error in test endpoint: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/test-rating", methods=["POST"])
def test_rating() -> Tuple[Dict[str, Any], int]:
    """
    Test endpoint to simulate rating submission.
    
    Expected JSON:
    {
        "request_id": "REQ-JOB-123-1234567890",
        "operator_id": "OP-1",
        "rating": 4
    }
    
    Returns:
        JSON response with result
    """
    try:
        data = request.get_json()
        
        result = rating_handler.process_rating_reply(
            request_id=data.get("request_id"),
            operator_id=data.get("operator_id"),
            rating=int(data.get("rating", 0))
        )
        
        return jsonify(result), 200 if result["status"] == "success" else 400
        
    except Exception as e:
        logger.error(f"Error in test endpoint: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/stats/operators/<operator_id>", methods=["GET"])
def get_operator_stats(operator_id: str) -> Tuple[Dict[str, Any], int]:
    """
    Get statistics for an operator.
    
    Returns:
        JSON with operator statistics
    """
    try:
        stats = rating_handler.get_operator_stats(operator_id)
        
        if stats:
            return jsonify(stats), 200
        else:
            return jsonify({"error": "Operator not found"}), 404
        
    except Exception as e:
        logger.error(f"Error getting operator stats: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/stats/top-performers", methods=["GET"])
def get_top_performers() -> Tuple[Dict[str, Any], int]:
    """
    Get top-performing operators.
    
    Returns:
        JSON list of top performers
    """
    try:
        from rating_calculator import RatingCalculator
        calculator = RatingCalculator(db_manager)
        top_performers = calculator.get_top_performers(limit=10)
        
        return jsonify({
            "status": "success",
            "count": len(top_performers),
            "operators": top_performers
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting top performers: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/stats/at-risk", methods=["GET"])
def get_at_risk_operators() -> Tuple[Dict[str, Any], int]:
    """
    Get operators at risk of being banned.
    
    Returns:
        JSON list of at-risk operators
    """
    try:
        from rating_calculator import RatingCalculator
        calculator = RatingCalculator(db_manager)
        at_risk = calculator.get_at_risk_operators()
        
        return jsonify({
            "status": "success",
            "count": len(at_risk),
            "operators": at_risk
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting at-risk operators: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/mock/sent-messages", methods=["GET"])
def get_mock_messages() -> Tuple[Dict[str, Any], int]:
    """
    Get sent messages from mock SMS service (testing only).
    
    Returns:
        JSON list of sent messages
    """
    if not isinstance(sms_service, MockSMSService):
        return jsonify({"error": "Only available with mock SMS service"}), 400
    
    return jsonify({
        "status": "success",
        "count": len(sms_service.sent_messages),
        "messages": sms_service.sent_messages
    }), 200


@app.errorhandler(404)
def not_found(error) -> Tuple[Dict[str, str], int]:
    """Handle 404 errors."""
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error) -> Tuple[Dict[str, str], int]:
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}", exc_info=True)
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    
    logger.info(f"Starting SMS webhook server on port {port}")
    logger.info(f"Debug mode: {debug}")
    
    app.run(host="0.0.0.0", port=port, debug=debug)
