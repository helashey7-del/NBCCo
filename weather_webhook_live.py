"""
Flask routes for live weather advisory webhook
Provides REST endpoints for weather queries
"""

from flask import Blueprint, request, jsonify
import logging
from weather_advise_handler_live import get_live_weather_handler

logger = logging.getLogger(__name__)

# Create blueprint
weather_live_bp = Blueprint('weather_live', __name__, url_prefix='/weather')

# ============================================================================
# Main Webhook Endpoint
# ============================================================================

@weather_live_bp.route('/webhook/weather_advise', methods=['POST'])
def weather_webhook():
    """
    Main weather advisory webhook endpoint
    
    POST /weather/webhook/weather_advise
    
    Request body:
    {
        "text": "WEATHER Harare"
    }
    
    Response:
    {
        "success": true,
        "ward": "harare",
        "weather": {
            "temperature": "26°C",
            "humidity": "65%",
            "rain_probability": "85%",
            "condition": "Partly cloudy"
        },
        "advisory_shona": "...",
        "advisory_ndebele": "...",
        "unified_message": "...",
        "pfumvudza_spacing": "75cm x 25cm"
    }
    """
    try:
        # Get JSON request body
        data = request.get_json() or {}
        text = data.get('text', '').strip()
        
        # Validate input
        if not text:
            return jsonify({
                "success": False,
                "error": "Missing 'text' field in request body"
            }), 400
        
        # Process the weather request
        handler = get_live_weather_handler()
        result = handler.process_weather_request(text)
        
        # Return result
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    
    except Exception as e:
        logger.error(f"Weather webhook error: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

# ============================================================================
# Test Endpoint
# ============================================================================

@weather_live_bp.route('/test', methods=['POST'])
def test_weather():
    """
    Simple test endpoint for weather queries
    
    POST /weather/test
    
    Request body:
    {
        "ward": "Harare"
    }
    """
    try:
        data = request.get_json() or {}
        ward = data.get('ward', 'Harare').strip()
        
        handler = get_live_weather_handler()
        result = handler.process_weather_request(f"WEATHER {ward}")
        
        return jsonify({
            "input_ward": ward,
            "result": result
        }), 200 if result.get("success") else 400
    
    except Exception as e:
        logger.error(f"Test endpoint error: {str(e)}")
        return jsonify({
            "error": str(e)
        }), 500

# ============================================================================
# Utility Endpoints
# ============================================================================

@weather_live_bp.route('/wards', methods=['GET'])
def list_wards():
    """
    List all supported wards and regions
    
    GET /weather/wards
    
    Response:
    {
        "success": true,
        "total_wards": 15,
        "wards": [
            {"name": "harare", "region": "Harare Province", "lat": -17.8252, "lon": 31.0335},
            ...
        ]
    }
    """
    try:
        handler = get_live_weather_handler()
        wards_list = []
        
        for ward_name, ward_data in handler.ZIMBABWE_WARDS.items():
            wards_list.append({
                "name": ward_name.replace("_", " ").title(),
                "region": ward_data["region"],
                "latitude": ward_data["lat"],
                "longitude": ward_data["lon"]
            })
        
        return jsonify({
            "success": True,
            "total_wards": len(wards_list),
            "wards": sorted(wards_list, key=lambda x: x["name"])
        }), 200
    
    except Exception as e:
        logger.error(f"List wards error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@weather_live_bp.route('/examples', methods=['GET'])
def examples():
    """
    Get example API requests and responses
    
    GET /weather/examples
    """
    return jsonify({
        "success": True,
        "examples": [
            {
                "description": "Get weather advisory for Harare",
                "method": "POST",
                "endpoint": "/weather/webhook/weather_advise",
                "request": {
                    "text": "WEATHER Harare"
                }
            },
            {
                "description": "Get weather advisory for Bulawayo",
                "method": "POST",
                "endpoint": "/weather/webhook/weather_advise",
                "request": {
                    "text": "WEATHER Bulawayo"
                }
            },
            {
                "description": "List all supported wards",
                "method": "GET",
                "endpoint": "/weather/wards"
            },
            {
                "description": "Check service info",
                "method": "GET",
                "endpoint": "/weather/info"
            },
            {
                "description": "Health check",
                "method": "GET",
                "endpoint": "/weather/health"
            }
        ]
    }), 200

@weather_live_bp.route('/info', methods=['GET'])
def service_info():
    """
    Get service information
    
    GET /weather/info
    """
    return jsonify({
        "success": True,
        "service": "NBCCo Live Weather Advisory",
        "version": "1.0.0",
        "api_source": "Open-Meteo (Free Weather API)",
        "features": [
            "Real-time weather data",
            "Bilingual advisories (Shona & Ndebele)",
            "Pfumvudza farming integration",
            "15+ Zimbabwe ward support",
            "Automatic geocoding",
            "Zero configuration (no API key required)"
        ],
        "endpoints": {
            "webhook": "/weather/webhook/weather_advise",
            "test": "/weather/test",
            "wards": "/weather/wards",
            "examples": "/weather/examples",
            "info": "/weather/info",
            "health": "/weather/health"
        },
        "documentation": "See /weather/examples for usage"
    }), 200

@weather_live_bp.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint
    
    GET /weather/health
    """
    return jsonify({
        "success": True,
        "status": "healthy",
        "service": "Weather Advisory",
        "api_provider": "Open-Meteo",
        "rate_limit": "10,000 calls/day"
    }), 200

# ============================================================================
# Advanced Endpoints
# ============================================================================

@weather_live_bp.route('/compare-wards', methods=['POST'])
def compare_wards():
    """
    Compare weather across multiple wards
    
    POST /weather/compare-wards
    
    Request body:
    {
        "wards": ["Harare", "Bulawayo", "Mutare"]
    }
    """
    try:
        data = request.get_json() or {}
        wards = data.get('wards', [])
        
        if not wards or not isinstance(wards, list):
            return jsonify({
                "success": False,
                "error": "Missing or invalid 'wards' array"
            }), 400
        
        handler = get_live_weather_handler()
        comparison = []
        
        for ward in wards:
            result = handler.process_weather_request(f"WEATHER {ward}")
            if result.get("success"):
                comparison.append({
                    "ward": result.get("ward"),
                    "weather": result.get("weather"),
                    "rain_probability": result.get("weather", {}).get("rain_probability")
                })
        
        return jsonify({
            "success": True,
            "comparison_count": len(comparison),
            "wards_compared": comparison
        }), 200
    
    except Exception as e:
        logger.error(f"Compare wards error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@weather_live_bp.route('/forecast-season/<ward>', methods=['GET'])
def seasonal_forecast(ward):
    """
    Get seasonal planting forecast for a ward
    
    GET /weather/forecast-season/Harare
    """
    try:
        handler = get_live_weather_handler()
        result = handler.process_weather_request(f"WEATHER {ward}")
        
        if not result.get("success"):
            return jsonify(result), 400
        
        rain_prob = int(result.get("weather", {}).get("rain_probability", "0").rstrip("%"))
        
        # Determine planting season
        if rain_prob >= 70:
            season = "Excellent for maize planting"
            crop = "Maize (Zviyo/Amabele)"
        elif rain_prob >= 40:
            season = "Good for sorghum/millet planting"
            crop = "Sorghum (Ubwe)"
        else:
            season = "Prepare for drought-resistant crops"
            crop = "Drought-resistant varieties"
        
        return jsonify({
            "success": True,
            "ward": ward,
            "rain_probability": f"{rain_prob}%",
            "planting_season": season,
            "recommended_crop": crop,
            "pfumvudza_spacing": "75cm x 25cm",
            "advisory": result.get("advisory_shona")
        }), 200
    
    except Exception as e:
        logger.error(f"Seasonal forecast error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ============================================================================
# Error Handlers
# ============================================================================

@weather_live_bp.errorhandler(400)
def bad_request(error):
    """Handle 400 Bad Request"""
    return jsonify({
        "success": False,
        "error": "Bad Request"
    }), 400

@weather_live_bp.errorhandler(404)
def not_found(error):
    """Handle 404 Not Found"""
    return jsonify({
        "success": False,
        "error": "Endpoint not found"
    }), 404

@weather_live_bp.errorhandler(500)
def server_error(error):
    """Handle 500 Server Error"""
    return jsonify({
        "success": False,
        "error": "Internal Server Error"
    }), 500
