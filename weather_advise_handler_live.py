"""
Weather Advisory Handler with Live API Integration
Connects to Open-Meteo API (free, no API key required)
Processes weather requests and returns Agritex advisory in Shona/Ndebele
"""

import requests
import logging
from typing import Dict, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class LiveWeatherAdvisoryHandler:
    """
    Handler for weather advisory requests using real-time weather data
    from Open-Meteo API (free weather data provider)
    """
    
    # Open-Meteo API endpoints (no authentication required)
    OPENMETEO_BASE_URL = "https://api.open-meteo.com/v1"
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1"
    
    # Zimbabwe provinces and major wards with coordinates
    ZIMBABWE_WARDS = {
        "harare": {"lat": -17.8252, "lon": 31.0335, "region": "Harare Province"},
        "bulawayo": {"lat": -20.1500, "lon": 28.5833, "region": "Bulawayo"},
        "chitungwiza": {"lat": -17.9833, "lon": 31.0167, "region": "Harare"},
        "gweru": {"lat": -19.4500, "lon": 29.8167, "region": "Midlands"},
        "kwekwe": {"lat": -18.9333, "lon": 29.8167, "region": "Midlands"},
        "mutare": {"lat": -18.9667, "lon": 32.6667, "region": "Manicaland"},
        "masvingo": {"lat": -20.0667, "lon": 30.8333, "region": "Masvingo"},
        "chinhoyi": {"lat": -17.6667, "lon": 30.2167, "region": "Mashonaland West"},
        "norton": {"lat": -17.9000, "lon": 30.7500, "region": "Harare"},
        "epworth": {"lat": -17.9000, "lon": 31.1833, "region": "Harare"},
        "chegutu": {"lat": -18.7333, "lon": 30.3167, "region": "Midlands"},
        "kadoma": {"lat": -18.3333, "lon": 29.9167, "region": "Mashonaland Central"},
        "zvishavane": {"lat": -20.3333, "lon": 29.8333, "region": "Masvingo"},
        "victoria_falls": {"lat": -17.9333, "lon": 25.8333, "region": "Matabeleland North"},
        "kariba": {"lat": -16.8000, "lon": 28.3000, "region": "Mashonaland North"},
    }
    
    def __init__(self, timeout: int = 10):
        """
        Initialize the handler
        
        Args:
            timeout: Request timeout in seconds (default: 10)
        """
        self.timeout = timeout
        self.session = requests.Session()
        
    def parse_weather_request(self, text: str) -> Dict:
        """
        Parse weather request in format: "WEATHER [ward]"
        
        Args:
            text: The incoming request text
            
        Returns:
            Dict with success status and parsed ward
        """
        import re
        
        text = text.strip()
        match = re.match(r'^WEATHER\s+(.+)$', text, re.IGNORECASE)
        
        if not match:
            return {
                "success": False,
                "error": 'Invalid format. Expected: WEATHER [ward]'
            }
        
        ward = match.group(1).strip().lower()
        return {"success": True, "ward": ward}
    
    def get_ward_coordinates(self, ward: str) -> Tuple[float, float, str]:
        """
        Get coordinates for a ward (predefined or via geocoding)
        
        Args:
            ward: Ward name
            
        Returns:
            Tuple of (latitude, longitude, region_name)
        """
        # Check predefined Zimbabwe wards first
        ward_lower = ward.lower().replace(" ", "_")
        if ward_lower in self.ZIMBABWE_WARDS:
            data = self.ZIMBABWE_WARDS[ward_lower]
            return data["lat"], data["lon"], data["region"]
        
        # Try geocoding API for other locations
        try:
            params = {
                "name": ward,
                "country": "Zimbabwe",
                "language": "en",
                "limit": 1
            }
            
            response = self.session.get(
                f"{self.GEOCODING_URL}/search",
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            if data.get("results"):
                result = data["results"][0]
                lat = result.get("latitude")
                lon = result.get("longitude")
                admin = result.get("admin1", "Zimbabwe")
                return lat, lon, admin
        
        except Exception as e:
            logger.error(f"Geocoding error for {ward}: {str(e)}")
        
        # Default to Harare if not found
        logger.warning(f"Ward {ward} not found, defaulting to Harare")
        harare = self.ZIMBABWE_WARDS["harare"]
        return harare["lat"], harare["lon"], harare["region"]
    
    def fetch_live_weather(self, lat: float, lon: float) -> Dict:
        """
        Fetch real-time weather data from Open-Meteo API
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Dict with weather data
        """
        try:
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code",
                "hourly": "precipitation_probability",
                "forecast_days": 1,
                "timezone": "Africa/Harare"
            }
            
            response = self.session.get(
                f"{self.OPENMETEO_BASE_URL}/forecast",
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            current = data.get("current", {})
            hourly = data.get("hourly", {})
            
            # Calculate rain probability from hourly data
            precip_probs = hourly.get("precipitation_probability", [])
            rain_probability = int(sum(precip_probs) / len(precip_probs)) if precip_probs else 0
            
            return {
                "success": True,
                "temperature": current.get("temperature_2m", 0),
                "temperature_unit": current.get("temperature_2m_unit", "°C"),
                "humidity": current.get("relative_humidity_2m", 0),
                "precipitation": current.get("precipitation", 0),
                "weather_code": current.get("weather_code", 0),
                "rain_probability": rain_probability,
                "timestamp": current.get("time", datetime.now().isoformat())
            }
        
        except requests.exceptions.Timeout:
            logger.error("Weather API request timed out")
            return {"success": False, "error": "Weather API timeout"}
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Weather API error: {str(e)}")
            return {"success": False, "error": f"Weather API error: {str(e)}"}
        
        except Exception as e:
            logger.error(f"Unexpected error fetching weather: {str(e)}")
            return {"success": False, "error": "Failed to fetch weather data"}
    
    def interpret_weather_code(self, code: int) -> Dict:
        """
        Interpret WMO weather code
        
        Args:
            code: WMO weather code
            
        Returns:
            Dict with weather description
        """
        # WMO Weather interpretation codes
        weather_codes = {
            0: {"desc": "Clear sky", "shona": "Zuva rinopenya", "ndebele": "Ilanga"},
            1: {"desc": "Mainly clear", "shona": "Zuva rinopenya", "ndebele": "Ilanga"},
            2: {"desc": "Partly cloudy", "shona": "Mawurumidze", "ndebele": "Amafu"},
            3: {"desc": "Overcast", "shona": "Mawurumidze", "ndebele": "Amafu"},
            45: {"desc": "Foggy", "shona": "Chirwi", "ndebele": "Isipho"},
            48: {"desc": "Foggy/rime", "shona": "Chirwi", "ndebele": "Isipho"},
            51: {"desc": "Light drizzle", "shona": "Mvura imbire", "ndebele": "Umvula"},
            61: {"desc": "Slight rain", "shona": "Mvura imbire", "ndebele": "Umvula"},
            63: {"desc": "Moderate rain", "shona": "Mvura yakawanda", "ndebele": "Umvula omkhulu"},
            65: {"desc": "Heavy rain", "shona": "Mvura yakawanda zvakajeka", "ndebele": "Umvula omkhulu kakhulu"},
            80: {"desc": "Slight rain showers", "shona": "Mvura yakavhara", "ndebele": "Umvula okuhambisa"},
            82: {"desc": "Heavy rain showers", "shona": "Mvura yakavhara", "ndebele": "Umvula okuhambisa"},
            85: {"desc": "Heavy snow showers", "shona": "Snhoo", "ndebele": "Isinovisi"},
            95: {"desc": "Thunderstorm", "shona": "Mhepo ne mvura", "ndebele": "Umhepo nomvula"},
        }
        
        return weather_codes.get(code, {"desc": "Unknown", "shona": "Zvisikwa", "ndebele": "Okungaqondakali"})
    
    def generate_agritex_advisory(
        self,
        rain_probability: int,
        temperature: float,
        ward: str,
        region: str,
        weather_desc: Dict
    ) -> Dict:
        """
        Generate Agritex advisory based on live weather data
        
        Args:
            rain_probability: Rain probability percentage
            temperature: Temperature in Celsius
            ward: Ward name
            region: Region name
            weather_desc: Weather description dict
            
        Returns:
            Dict with Shona and Ndebele advisories
        """
        
        # Determine crop based on rain probability using Pfumvudza guidelines
        if rain_probability >= 70:
            # High rainfall - suitable for maize with Pfumvudza
            advisory_shona = (
                f"Muno {ward.title()} ({region}): Zuva rinafungiro yemvura ine mwero mukati (≥70%). "
                f"Mufume zviyo (maize) neushanga hwechiPhfumvudza (75cm x 25cm). "
                f"Temperature iri {temperature}°C inotsigira zviyo. "
                f"Mvura inofanira kusvika 60-100mm kuti iite nzira dzakakura. "
                f"Mufume kwakapera manheru wasvika mangwanani kuti mvura isike zvishoma."
            )
            
            advisory_ndebele = (
                f"KuMlali kwa{ward.title()} ({region}): Umvula ung-{rain_probability}% - iyangcono kuxapha amabele. "
                f"Lindele amabele neindlela yePhfumvudza (75cm x 25cm). "
                f"Izinga lokushisa ingu-{temperature}°C - ilungile. "
                f"Umvula ofanele ukusika: 60-100mm ngesinyathelo. "
                f"Lindela umvula ovama ngebusuku nomosiqaleko."
            )
        
        elif rain_probability >= 40:
            # Moderate rainfall - suitable for sorghum/millet with Pfumvudza
            advisory_shona = (
                f"Muno {ward.title()} ({region}): Mvula ine mwero muhango (40-70%). "
                f"Mufume ubwe (sorghum) neushanga hwechiPhfumvudza (75cm x 25cm). "
                f"Temperature iri {temperature}°C - yakakwanisa. "
                f"Ubwe hunozviwa mvura yeshoma, nokuti ino-drought resistant. "
                f"Shandura nzira dzakakura dzekugara nemagetsi matunzvi."
            )
            
            advisory_ndebele = (
                f"KuMlali kwa{ward.title()} ({region}): Umvula ung-{rain_probability}% - iyangcono kuthiya. "
                f"Lindele ubuhle (sorghum) neindlela yePhfumvudza (75cm x 25cm). "
                f"Izinga lokushisa ingu-{temperature}°C - okungcono. "
                f"Isitshalo esiqinile kule mihla. "
                f"Lindela indlela yokuhlala engcono nokuswela umvula."
            )
        
        else:
            # Low rainfall - suitable for drought-resistant crops with Pfumvudza
            advisory_shona = (
                f"Muno {ward.title()} ({region}): Mvura ine kugara kwakaseri (<40%). "
                f"Mufume mhunga inotsivira (nyevhe, nyimo) neushanga hwechiPhfumvudza (75cm x 25cm). "
                f"Temperature iri {temperature}°C - yakaomesa zvikara. "
                f"Mufume zviyo zvakashoma uye zvakakosheswa kuzviwa mvura. "
                f"Shandura nzira dzakakura dzekugara nemagetsi matunzvi kana makazi."
            )
            
            advisory_ndebele = (
                f"KuMlali kwa{ward.title()} ({region}): Umvula ung-{rain_probability}% - iyasela. "
                f"Lindele izitshalo eziqinile neindlela yePhfumvudza (75cm x 25cm). "
                f"Isidla somuntu nesiliva (drought resistant) - amabele omuntu nesiliva. "
                f"Izinga lokushisa ingu-{temperature}°C - kuhamba ngenkosi. "
                f"Lindela insiza yomhlaba neendlela zokuhlala engcono."
            )
        
        return {
            "advisory_shona": advisory_shona,
            "advisory_ndebele": advisory_ndebele
        }
    
    def process_weather_request(self, text: str) -> Dict:
        """
        Complete workflow: parse request, fetch weather, generate advisory
        
        Args:
            text: Incoming request text (e.g., "WEATHER Harare")
            
        Returns:
            Complete response with weather data and advisories
        """
        
        # Step 1: Parse request
        parsed = self.parse_weather_request(text)
        if not parsed["success"]:
            return {
                "success": False,
                "error": parsed["error"]
            }
        
        ward = parsed["ward"]
        
        # Step 2: Get coordinates
        lat, lon, region = self.get_ward_coordinates(ward)
        
        # Step 3: Fetch live weather
        weather = self.fetch_live_weather(lat, lon)
        if not weather["success"]:
            return {
                "success": False,
                "error": weather["error"],
                "ward": ward
            }
        
        # Step 4: Interpret weather
        weather_desc = self.interpret_weather_code(weather["weather_code"])
        
        # Step 5: Generate advisory
        advisory = self.generate_agritex_advisory(
            rain_probability=weather["rain_probability"],
            temperature=weather["temperature"],
            ward=ward,
            region=region,
            weather_desc=weather_desc
        )
        
        # Step 6: Return complete response
        return {
            "success": True,
            "ward": ward,
            "region": region,
            "coordinates": {"latitude": lat, "longitude": lon},
            "weather": {
                "temperature": f"{weather['temperature']}°C",
                "humidity": f"{weather['humidity']}%",
                "precipitation": f"{weather['precipitation']}mm",
                "condition": weather_desc["desc"],
                "condition_shona": weather_desc["shona"],
                "condition_ndebele": weather_desc["ndebele"],
                "rain_probability": f"{weather['rain_probability']}%",
                "timestamp": weather["timestamp"]
            },
            "advisory_shona": advisory["advisory_shona"],
            "advisory_ndebele": advisory["advisory_ndebele"],
            "unified_message": f"{advisory['advisory_shona']}\n\n{advisory['advisory_ndebele']}",
            "pfumvudza_spacing": "75cm (between rows) x 25cm (within rows)",
            "api_source": "Open-Meteo (free weather data)"
        }


# Global instance
_handler = None

def initialize_live_weather_handler():
    """Initialize the live weather handler"""
    global _handler
    _handler = LiveWeatherAdvisoryHandler()
    logger.info("Live Weather Handler initialized")

def get_live_weather_handler() -> LiveWeatherAdvisoryHandler:
    """Get the handler instance"""
    global _handler
    if _handler is None:
        initialize_live_weather_handler()
    return _handler
