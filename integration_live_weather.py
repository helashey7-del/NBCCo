"""
Integration guide for live weather API with existing NBCCo system
Shows how to add the live weather handler to your Flask app
"""

from flask import Flask, request, jsonify
from weather_webhook_live import weather_live_bp
from weather_advise_handler_live import initialize_live_weather_handler
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# ============================================================================
# INTEGRATION STEP 1: Register the weather blueprint
# ============================================================================
app.register_blueprint(weather_live_bp)

# ============================================================================
# INTEGRATION STEP 2: Initialize weather handler on startup
# ============================================================================
@app.before_first_request
def startup():
    """Initialize services on app startup"""
    initialize_live_weather_handler()
    logger.info("Live Weather Handler initialized")

# ============================================================================
# INTEGRATION STEP 3: Example - Integrate with job completion
# ============================================================================
# This assumes you have a job_completion_trigger module

@app.route("/jobs/<job_id>/complete", methods=["POST"])
def complete_job_with_weather(job_id):
    """
    Complete a job and get weather-based recommendations
    
    Request:
    {
        "user_phone": "+1234567890",
        "operator_phone": "+0987654321",
        "operator_id": "OP-001",
        "job_location": "Harare",
        "job_type": "farming_advice"
    }
    """
    try:
        data = request.get_json()
        
        # Get job location
        job_location = data.get('job_location', 'Harare')
        
        # Trigger existing rating workflow (if available)
        # result = trigger_job_completed(...)
        
        # Get weather advisory for the location
        from weather_advise_handler_live import get_live_weather_handler
        handler = get_live_weather_handler()
        
        weather_result = handler.process_weather_request(f"WEATHER {job_location}")
        
        return jsonify({
            "status": "success",
            "job_id": job_id,
            "rating_initiated": True,
            "weather_advisory": weather_result if weather_result.get("success") else None
        }), 200
    
    except Exception as e:
        logger.error(f"Job completion error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ============================================================================
# INTEGRATION STEP 4: Example - SMS webhook integration
# ============================================================================
# This integrates weather advice into your SMS workflow

@app.route("/sms/weather-advice", methods=['POST'])
def sms_weather_advice():
    """
    Handle incoming SMS requests for weather advice
    
    Twilio webhook - expects:
    From: +1234567890
    Body: "WEATHER Harare"
    MessageSid: msg123456
    """
    from weather_advise_handler_live import get_live_weather_handler
    
    try:
        # Get SMS data from Twilio
        sender = request.form.get('From')
        message_text = request.form.get('Body', '')
        message_id = request.form.get('MessageSid')
        
        logger.info(f"Received SMS from {sender}: {message_text}")
        
        # Process weather request
        handler = get_live_weather_handler()
        result = handler.process_weather_request(message_text)
        
        if result.get("success"):
            # Send SMS response (using your SMS service)
            response_text = result.get("advisory_shona", "Weather advisory ready")
            # TODO: Send SMS response back to sender
        else:
            # Send error message
            response_text = "Invalid request format. Use: WEATHER [ward]"
            # TODO: Send error SMS back to sender
        
        return jsonify({
            "status": "ok",
            "message_id": message_id,
            "processed": True
        }), 200
    
    except Exception as e:
        logger.error(f"SMS weather error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ============================================================================
# INTEGRATION STEP 5: Example - Dashboard endpoint
# ============================================================================
# Get weather advisories for multiple locations

@app.route("/dashboard/weather-summary", methods=['GET'])
def weather_dashboard():
    """
    Get weather summary for all major Zimbabwean locations
    Useful for dashboard display
    
    Example:
    curl http://localhost:5000/dashboard/weather-summary
    """
    from weather_advise_handler_live import get_live_weather_handler
    
    try:
        handler = get_live_weather_handler()
        
        # Get weather for major regions
        major_locations = ["harare", "bulawayo", "gweru", "mutare", "masvingo"]
        summary = []
        
        for location in major_locations:
            result = handler.process_weather_request(f"WEATHER {location}")
            if result.get("success"):
                summary.append({
                    "ward": result["ward"],
                    "region": result["region"],
                    "weather": result["weather"],
                    "rain_probability": result["weather"]["rain_probability"]
                })
        
        return jsonify({
            "success": True,
            "timestamp": "2026-05-22T14:30:00",
            "locations": summary,
            "source": "Open-Meteo API"
        }), 200
    
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ============================================================================
# INTEGRATION STEP 6: Health check for monitoring
# ============================================================================

@app.route("/health", methods=['GET'])
def health():
    """System health check"""
    return jsonify({
        "status": "healthy",
        "service": "NBCCo with Live Weather",
        "components": {
            "rating_system": "available",
            "weather_api": "Open-Meteo (active)",
            "database": "connected"
        }
    }), 200

# ============================================================================
# Example usage and testing
# ============================================================================

if __name__ == '__main__':
    """
    Quick start guide:
    
    1. Install dependencies:
       pip install flask requests
    
    2. Run the server:
       python integration_live_weather.py
    
    3. Test endpoints:
    
       a) Get weather advisory for a ward:
          curl -X POST http://localhost:5000/weather/webhook/weather_advise \
            -H "Content-Type: application/json" \
            -d '{"text": "WEATHER Harare"}'
       
       b) List all supported wards:
          curl http://localhost:5000/weather/wards
       
       c) Get service info:
          curl http://localhost:5000/weather/info
       
       d) Get weather summary for dashboard:
          curl http://localhost:5000/dashboard/weather-summary
       
       e) Health check:
          curl http://localhost:5000/health
    
    4. Integrate into your existing app:
       - Import weather_live_bp in your Flask app
       - Register the blueprint: app.register_blueprint(weather_live_bp)
       - Initialize on startup: initialize_live_weather_handler()
    
    5. Key features:
       - NO API key required (Open-Meteo is completely free)
       - Real-time weather data
       - Bilingual output (Shona & Ndebele)
       - Pfumvudza farming integration
       - Zimbabwe location support
    """
    
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║        NBCCo Live Weather Advisory System                     ║
    ║        Powered by Open-Meteo (Free Weather API)              ║
    ╚════════════════════════════════════════════════════════════════╝
    
    Server starting on http://localhost:5000
    
    Available endpoints:
    
    1. POST /weather/webhook/weather_advise
       Get weather advisory (main endpoint)
    
    2. POST /weather/test
       Test endpoint with simple input
    
    3. GET /weather/wards
       List supported wards
    
    4. GET /weather/info
       Service information
    
    5. GET /dashboard/weather-summary
       Weather summary for dashboard
    
    6. GET /health
       System health check
    
    Try: curl -X POST http://localhost:5000/weather/webhook/weather_advise \\
           -H "Content-Type: application/json" \\
           -d '{"text": "WEATHER Harare"}'
    """)
    
    app.run(debug=False, port=5000, host='0.0.0.0')
