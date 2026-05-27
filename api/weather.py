from flask import Flask, request, jsonify
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from weather_advise_handler_live import get_live_weather_handler
except ImportError as e:
    print(f"Import error: {e}")
    get_live_weather_handler = None

app = Flask(__name__)
logger = logging.getLogger(__name__)

@app.route('/api/weather/webhook/weather_advise', methods=['POST'])
def weather_webhook():
    """Main weather advisory webhook endpoint"""
    try:
        if not get_live_weather_handler:
            return jsonify({
                "success": False,
                "error": "Weather handler not available"
            }), 500
            
        data = request.get_json() or {}
        text = data.get('text', '').strip()
        
        if not text:
            return jsonify({
                "success": False,
                "error": "Missing 'text' field in request body"
            }), 400
        
        handler = get_live_weather_handler()
        result = handler.process_weather_request(text)
        
        return jsonify(result), 200 if result.get("success") else 400
    
    except Exception as e:
        logger.error(f"Weather webhook error: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

@app.route('/api/weather/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "success": True,
        "status": "healthy",
        "service": "Weather Advisory"
    }), 200

@app.route('/api/weather/test', methods=['POST'])
def test_weather():
    """Test endpoint"""
    try:
        if not get_live_weather_handler:
            return jsonify({"error": "Weather handler unavailable"}), 500
            
        data = request.get_json() or {}
        ward = data.get('ward', 'Harare').strip()
        
        handler = get_live_weather_handler()
        result = handler.process_weather_request(f"WEATHER {ward}")
        
        return jsonify({"input_ward": ward, "result": result}), 200 if result.get("success") else 400
    
    except Exception as e:
        logger.error(f"Test endpoint error: {str(e)}")
        return jsonify({"error": str(e)}), 500
