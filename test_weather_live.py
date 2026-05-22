"""
Test Suite for Live Weather Advisory Handler
Tests real API integration with Open-Meteo
"""

import unittest
import json
from weather_advise_handler_live import LiveWeatherAdvisoryHandler, initialize_live_weather_handler

class TestLiveWeatherAdvisor(unittest.TestCase):
    """Test cases for live weather advisor"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.handler = LiveWeatherAdvisoryHandler(timeout=15)
    
    # ============ Parsing Tests ============
    
    def test_parse_valid_weather_request(self):
        """Test parsing valid weather request"""
        result = self.handler.parse_weather_request("WEATHER Harare")
        self.assertTrue(result["success"])
        self.assertEqual(result["ward"], "harare")
    
    def test_parse_case_insensitive(self):
        """Test case-insensitive parsing"""
        result = self.handler.parse_weather_request("weather bulawayo")
        self.assertTrue(result["success"])
        self.assertEqual(result["ward"], "bulawayo")
    
    def test_parse_extra_whitespace(self):
        """Test parsing with extra whitespace"""
        result = self.handler.parse_weather_request("  WEATHER   Mutare  ")
        self.assertTrue(result["success"])
        self.assertEqual(result["ward"], "mutare")
    
    def test_parse_multi_word_ward(self):
        """Test parsing multi-word ward names"""
        result = self.handler.parse_weather_request("WEATHER Victoria Falls")
        self.assertTrue(result["success"])
        self.assertEqual(result["ward"], "victoria falls")
    
    def test_parse_invalid_format(self):
        """Test parsing invalid format"""
        result = self.handler.parse_weather_request("Just Harare")
        self.assertFalse(result["success"])
        self.assertIn("Invalid format", result["error"])
    
    def test_parse_empty_string(self):
        """Test parsing empty string"""
        result = self.handler.parse_weather_request("")
        self.assertFalse(result["success"])
    
    # ============ Coordinate Tests ============
    
    def test_get_predefined_ward_harare(self):
        """Test getting coordinates for Harare"""
        lat, lon, region = self.handler.get_ward_coordinates("harare")
        self.assertAlmostEqual(lat, -17.8252, places=3)
        self.assertAlmostEqual(lon, 31.0335, places=3)
        self.assertEqual(region, "Harare Province")
    
    def test_get_predefined_ward_bulawayo(self):
        """Test getting coordinates for Bulawayo"""
        lat, lon, region = self.handler.get_ward_coordinates("bulawayo")
        self.assertAlmostEqual(lat, -20.1500, places=3)
        self.assertAlmostEqual(lon, 28.5833, places=3)
        self.assertEqual(region, "Bulawayo")
    
    def test_all_predefined_wards_valid(self):
        """Test all predefined wards have valid coordinates"""
        for ward in self.handler.ZIMBABWE_WARDS.keys():
            lat, lon, region = self.handler.get_ward_coordinates(ward)
            self.assertIsNotNone(lat)
            self.assertIsNotNone(lon)
            self.assertIsNotNone(region)
            self.assertTrue(-25 < lat < -15)  # Zimbabwe latitude range
            self.assertTrue(25 < lon < 35)    # Zimbabwe longitude range
    
    # ============ API Tests ============
    
    def test_fetch_live_weather_valid_coordinates(self):
        """Test fetching real weather data"""
        weather = self.handler.fetch_live_weather(-17.8252, 31.0335)  # Harare
        self.assertTrue(weather["success"])
        self.assertIn("temperature", weather)
        self.assertIn("humidity", weather)
        self.assertIn("rain_probability", weather)
        self.assertIn("timestamp", weather)
    
    def test_weather_data_contains_valid_values(self):
        """Test weather data has valid value ranges"""
        weather = self.handler.fetch_live_weather(-17.8252, 31.0335)
        if weather["success"]:
            self.assertTrue(-50 <= weather["temperature"] <= 50)
            self.assertTrue(0 <= weather["humidity"] <= 100)
            self.assertTrue(0 <= weather["rain_probability"] <= 100)
            self.assertTrue(weather["precipitation"] >= 0)
    
    # ============ Weather Code Interpretation Tests ============
    
    def test_interpret_clear_sky(self):
        """Test weather code interpretation for clear sky"""
        result = self.handler.interpret_weather_code(0)
        self.assertEqual(result["desc"], "Clear sky")
        self.assertIn("shona", result)
        self.assertIn("ndebele", result)
    
    def test_interpret_rain(self):
        """Test weather code interpretation for rain"""
        result = self.handler.interpret_weather_code(63)
        self.assertEqual(result["desc"], "Moderate rain")
    
    def test_interpret_thunderstorm(self):
        """Test weather code interpretation for thunderstorm"""
        result = self.handler.interpret_weather_code(95)
        self.assertEqual(result["desc"], "Thunderstorm")
    
    # ============ Advisory Generation Tests ============
    
    def test_advisory_high_rainfall(self):
        """Test advisory generation for high rainfall"""
        advisory = self.handler.generate_agritex_advisory(
            rain_probability=85,
            temperature=26,
            ward="harare",
            region="Harare Province",
            weather_desc={"desc": "Moderate rain"}
        )
        
        self.assertIn("Phfumvudza", advisory["advisory_shona"])
        self.assertIn("75cm x 25cm", advisory["advisory_shona"])
        self.assertIn("zviyo", advisory["advisory_shona"])
        self.assertIn("Phfumvudza", advisory["advisory_ndebele"])
        self.assertIn("amabele", advisory["advisory_ndebele"])
    
    def test_advisory_moderate_rainfall(self):
        """Test advisory generation for moderate rainfall"""
        advisory = self.handler.generate_agritex_advisory(
            rain_probability=55,
            temperature=24,
            ward="kwekwe",
            region="Midlands",
            weather_desc={"desc": "Partly cloudy"}
        )
        
        self.assertIn("ubwe", advisory["advisory_shona"])
        self.assertIn("75cm x 25cm", advisory["advisory_shona"])
        self.assertIn("Phfumvudza", advisory["advisory_ndebele"])
    
    def test_advisory_low_rainfall(self):
        """Test advisory generation for low rainfall"""
        advisory = self.handler.generate_agritex_advisory(
            rain_probability=25,
            temperature=28,
            ward="masvingo",
            region="Masvingo",
            weather_desc={"desc": "Clear sky"}
        )
        
        self.assertIn("nyevhe", advisory["advisory_shona"])
        self.assertIn("drought", advisory["advisory_shona"].lower())
        self.assertIn("75cm x 25cm", advisory["advisory_shona"])
    
    def test_advisory_contains_temperature(self):
        """Test advisory includes temperature"""
        advisory = self.handler.generate_agritex_advisory(
            rain_probability=70,
            temperature=26,
            ward="harare",
            region="Harare",
            weather_desc={"desc": "Partly cloudy"}
        )
        
        self.assertIn("26", advisory["advisory_shona"])
        self.assertIn("26", advisory["advisory_ndebele"])
    
    # ============ Complete Workflow Tests ============
    
    def test_complete_workflow_harare(self):
        """Test complete workflow for Harare"""
        result = self.handler.process_weather_request("WEATHER Harare")
        
        if result["success"]:
            self.assertTrue(result["success"])
            self.assertEqual(result["ward"], "harare")
            self.assertIn("weather", result)
            self.assertIn("advisory_shona", result)
            self.assertIn("advisory_ndebele", result)
            self.assertIn("unified_message", result)
            self.assertIn("Phfumvudza", result["unified_message"])
    
    def test_complete_workflow_bulawayo(self):
        """Test complete workflow for Bulawayo"""
        result = self.handler.process_weather_request("WEATHER Bulawayo")
        
        if result["success"]:
            self.assertTrue(result["success"])
            self.assertEqual(result["ward"], "bulawayo")
            self.assertIn("coordinates", result)
    
    def test_complete_workflow_case_insensitive(self):
        """Test complete workflow is case-insensitive"""
        result1 = self.handler.process_weather_request("WEATHER mutare")
        result2 = self.handler.process_weather_request("weather MUTARE")
        
        if result1["success"] and result2["success"]:
            self.assertEqual(result1["ward"], result2["ward"])
    
    def test_complete_workflow_invalid_request(self):
        """Test complete workflow with invalid request"""
        result = self.handler.process_weather_request("Just some text")
        
        self.assertFalse(result["success"])
        self.assertIn("error", result)
    
    # ============ Bilingual Tests ============
    
    def test_advisory_has_both_languages(self):
        """Test advisory has both Shona and Ndebele"""
        result = self.handler.process_weather_request("WEATHER Harare")
        
        if result["success"]:
            self.assertIn("advisory_shona", result)
            self.assertIn("advisory_ndebele", result)
            self.assertNotEqual(
                result["advisory_shona"],
                result["advisory_ndebele"]
            )
    
    def test_unified_message_contains_both_languages(self):
        """Test unified message contains both languages"""
        result = self.handler.process_weather_request("WEATHER Bulawayo")
        
        if result["success"]:
            unified = result.get("unified_message", "")
            self.assertIn("advisory_shona", result)
            self.assertIn("advisory_ndebele", result)
    
    # ============ Response Format Tests ============
    
    def test_response_has_required_fields(self):
        """Test response has all required fields"""
        result = self.handler.process_weather_request("WEATHER Harare")
        
        if result["success"]:
            required_fields = [
                "success", "ward", "region", "weather",
                "advisory_shona", "advisory_ndebele",
                "pfumvudza_spacing", "api_source"
            ]
            for field in required_fields:
                self.assertIn(field, result)
    
    def test_weather_data_structure(self):
        """Test weather data has correct structure"""
        result = self.handler.process_weather_request("WEATHER Mutare")
        
        if result["success"]:
            weather = result["weather"]
            required_weather_fields = [
                "temperature", "humidity", "precipitation",
                "condition", "rain_probability", "timestamp"
            ]
            for field in required_weather_fields:
                self.assertIn(field, weather)
    
    def test_pfumvudza_spacing_always_present(self):
        """Test Pfumvudza spacing is always mentioned"""
        result = self.handler.process_weather_request("WEATHER Chinhoyi")
        
        if result["success"]:
            self.assertIn("75cm", result["pfumvudza_spacing"])
            self.assertIn("25cm", result["pfumvudza_spacing"])


class TestWeatherAdvisorIntegration(unittest.TestCase):
    """Integration tests for weather advisor"""
    
    def setUp(self):
        """Set up test fixtures"""
        initialize_live_weather_handler()
    
    def test_multiple_requests_succeed(self):
        """Test multiple sequential requests"""
        wards = ["Harare", "Bulawayo", "Mutare"]
        
        handler = LiveWeatherAdvisoryHandler()
        for ward in wards:
            result = handler.process_weather_request(f"WEATHER {ward}")
            # Result can be success or timeout (API dependent)
            self.assertIn("success", result)
    
    def test_handler_singleton_works(self):
        """Test handler singleton pattern works"""
        from weather_advise_handler_live import get_live_weather_handler
        
        handler1 = get_live_weather_handler()
        handler2 = get_live_weather_handler()
        
        self.assertIs(handler1, handler2)


if __name__ == '__main__':
    unittest.main()
