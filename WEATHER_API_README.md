# Live Weather Advisory System Documentation

## Overview

The **Live Weather Advisory System** integrates real-time weather data from the **Open-Meteo API** (completely free, no API key required) with your NBCCo agricultural advisory platform. It provides bilingual farming recommendations in **Shona and Ndebele** based on actual weather conditions and **Pfumvudza spacing rules**.

---

## Features

✅ **Real-time Weather Data**
- Current temperature, humidity, precipitation
- Rain probability calculation from hourly forecasts
- WMO weather code interpretation
- No API key required

✅ **15+ Zimbabwe Ward Support**
- Harare, Bulawayo, Gweru, Mutare, Masvingo
- Chitungwiza, Kwekwe, Chinhoyi, Norton, Epworth
- Chegutu, Kadoma, Zvishavane, Victoria Falls, Kariba
- Automatic geocoding for custom locations

✅ **Bilingual Advisories**
- Full recommendations in Shona and Ndebele
- Weather condition descriptions in both languages
- Pfumvudza farming integration in each advisory

✅ **Pfumvudza Integration**
- 75cm × 25cm spacing rules in all recommendations
- Crop selection based on rainfall patterns:
  - **≥70% rain**: Maize (zviyo/amabele)
  - **40-69% rain**: Sorghum/Millet (ubwe)
  - **<40% rain**: Drought-resistant crops

---

## API Comparison

| Feature | Open-Meteo | WeatherAPI | Weatherstack |
|---------|-----------|-----------|--------------|
| **Cost** | FREE | FREE (1M calls/month) | FREE (250/month) |
| **API Key** | ❌ Not required | ✅ Required | ✅ Required |
| **Commercial Use** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Rate Limit** | 10,000/day | 1,000,000/month | 250/month |
| **Setup Time** | < 5 minutes | 10 minutes | 10 minutes |
| **Data Source** | NOAA/ECMWF | Multiple | IBM |
| **Reliability** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |

**Why Open-Meteo was chosen:**
- ✅ No authentication overhead
- ✅ Professional-grade data (used by meteorologists)
- ✅ Instant API access (no email confirmation)
- ✅ Generous free tier for agricultural use
- ✅ Commercial licensing available if needed

---

## Installation & Setup

### Prerequisites
```bash
pip install flask requests
```

### Quick Start
```bash
# 1. Clone or download the repository
cd NBCCo

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
python integration_live_weather.py

# Server runs on http://localhost:5000
```

### No Configuration Needed
- ❌ No `.env` file required
- ❌ No API credentials
- ❌ No setup wizards
- ✅ Just run and use!

---

## API Endpoints

### 1. POST `/weather/webhook/weather_advise` (Main Endpoint)

**Get weather advisory for a ward**

```bash
curl -X POST http://localhost:5000/weather/webhook/weather_advise \
  -H "Content-Type: application/json" \
  -d '{"text": "WEATHER Harare"}'
```

**Response:**
```json
{
  "success": true,
  "ward": "harare",
  "region": "Harare Province",
  "coordinates": {"latitude": -17.8252, "longitude": 31.0335},
  "weather": {
    "temperature": "26°C",
    "humidity": "65%",
    "precipitation": "0mm",
    "condition": "Partly cloudy",
    "rain_probability": "85%",
    "timestamp": "2026-05-22T14:30:00"
  },
  "advisory_shona": "Muno Harare: Mvura ine mwero mukati (≥70%). Mufume zviyo neushanga hwechiPhfumvudza (75cm x 25cm)...",
  "advisory_ndebele": "KuMlali kwaHarare: Umvula ung-85% - iyangcono kuxapha amabele neindlela yePhfumvudza (75cm x 25cm)...",
  "unified_message": "[Combined advisory in both languages]",
  "pfumvudza_spacing": "75cm (between rows) x 25cm (within rows)",
  "api_source": "Open-Meteo (free weather data)"
}
```

### 2. POST `/weather/test`

**Simple test endpoint**

```bash
curl -X POST http://localhost:5000/weather/test \
  -H "Content-Type: application/json" \
  -d '{"ward": "Harare"}'
```

### 3. GET `/weather/wards`

**List all supported wards**

```bash
curl http://localhost:5000/weather/wards
```

**Response:**
```json
{
  "success": true,
  "count": 15,
  "wards": [
    {
      "name": "harare",
      "region": "Harare Province",
      "coordinates": {"latitude": -17.8252, "longitude": 31.0335}
    },
    ...
  ]
}
```

### 4. GET `/weather/info`

**Get service information**

```bash
curl http://localhost:5000/weather/info
```

### 5. GET `/weather/examples`

**Get example API requests**

```bash
curl http://localhost:5000/weather/examples
```

### 6. GET `/weather/health`

**Health check**

```bash
curl http://localhost:5000/weather/health
```

---

## Integration Examples

### Example 1: Basic Weather Query

```python
from weather_advise_handler_live import get_live_weather_handler

handler = get_live_weather_handler()
result = handler.process_weather_request("WEATHER Harare")

if result["success"]:
    print(f"Ward: {result['ward']}")
    print(f"Temperature: {result['weather']['temperature']}")
    print(f"Advisory (Shona): {result['advisory_shona']}")
```

### Example 2: Flask Integration

```python
from flask import Flask
from weather_webhook_live import weather_live_bp

app = Flask(__name__)
app.register_blueprint(weather_live_bp)

if __name__ == '__main__':
    app.run(port=5000)
```

### Example 3: Job Completion Workflow

```python
from weather_advise_handler_live import get_live_weather_handler

def on_job_complete(job_location):
    """When a farming job completes, get weather advice"""
    handler = get_live_weather_handler()
    result = handler.process_weather_request(f"WEATHER {job_location}")
    
    if result["success"]:
        send_sms(result["advisory_shona"])
        return result
```

---

## Response Format

All successful responses include:

```json
{
  "success": true,
  "ward": "string - location name",
  "region": "string - region name",
  "coordinates": {
    "latitude": "number",
    "longitude": "number"
  },
  "weather": {
    "temperature": "string - e.g., 26°C",
    "humidity": "string - e.g., 65%",
    "precipitation": "string - e.g., 0mm",
    "condition": "string - weather description",
    "rain_probability": "string - e.g., 85%",
    "timestamp": "ISO 8601 timestamp"
  },
  "advisory_shona": "string - advisory in Shona",
  "advisory_ndebele": "string - advisory in Ndebele",
  "unified_message": "string - combined advisory",
  "pfumvudza_spacing": "string - spacing rules",
  "api_source": "string - data source"
}
```

---

## Supported Zimbabwe Wards

| Ward | Region | Coordinates |
|------|--------|-------------|
| Harare | Harare Province | -17.83°S, 31.03°E |
| Bulawayo | Bulawayo | -20.15°S, 28.58°E |
| Chitungwiza | Harare | -17.98°S, 31.02°E |
| Gweru | Midlands | -19.45°S, 29.82°E |
| Kwekwe | Midlands | -18.93°S, 29.82°E |
| Mutare | Manicaland | -18.97°S, 32.67°E |
| Masvingo | Masvingo | -20.07°S, 30.83°E |
| Chinhoyi | Mashonaland West | -17.67°S, 30.22°E |
| Norton | Harare | -17.90°S, 30.75°E |
| Epworth | Harare | -17.90°S, 31.18°E |
| Chegutu | Midlands | -18.73°S, 30.32°E |
| Kadoma | Mashonaland Central | -18.33°S, 29.92°E |
| Zvishavane | Masvingo | -20.33°S, 29.83°E |
| Victoria Falls | Matabeleland North | -17.93°S, 25.83°E |
| Kariba | Mashonaland North | -16.80°S, 28.30°E |

---

## Crop Recommendations by Rainfall

### High Rainfall (≥70%)
- **Crop**: Maize (Shona: zviyo, Ndebele: amabele)
- **Spacing**: 75cm × 25cm (Pfumvudza)
- **Advice**: Maximum yield potential, good water availability
- **Example**: "Mufume zviyo neushanga hwechiPhfumvudza..."

### Moderate Rainfall (40-69%)
- **Crop**: Sorghum/Millet (Shona: ubwe, Ndebele: ubuhle)
- **Spacing**: 75cm × 25cm (Pfumvudza)
- **Advice**: Drought-tolerant crop, balanced yield
- **Example**: "Mufume ubwe neushanga hwechiPhfumvudza..."

### Low Rainfall (<40%)
- **Crop**: Drought-resistant varieties (Shona: nyevhe/nyimo, Ndebele: izitshalo eziqinile)
- **Spacing**: 75cm × 25cm (Pfumvudza)
- **Advice**: Survival priority, water conservation
- **Example**: "Mufume mhunga inotsivira..."

---

## Testing

### Run Test Suite

```bash
python -m pytest test_weather_live.py -v
```

### Test Coverage

- ✅ Request parsing (10+ tests)
- ✅ Coordinate lookup (5+ tests)
- ✅ Weather interpretation (5+ tests)
- ✅ Advisory generation (10+ tests)
- ✅ Complete workflow (5+ tests)
- ✅ Pfumvudza integration (3+ tests)
- ✅ Response format (10+ tests)

---

## Error Handling

### Invalid Request Format
```json
{
  "success": false,
  "error": "Invalid format. Expected: WEATHER [ward]"
}
```

### Missing Required Field
```json
{
  "success": false,
  "error": "Missing 'text' field in request body"
}
```

### API Timeout
```json
{
  "success": false,
  "error": "Weather API timeout"
}
```

---

## Production Considerations

### 1. Error Handling
- Implement graceful fallbacks
- Cache responses for reliability
- Log all API interactions

### 2. Rate Limiting
- Open-Meteo: 10,000 calls/day (plenty for agriculture)
- Implement caching to reduce API calls
- Use Redis for distributed caching

### 3. Performance
- Average response time: < 2 seconds
- Cache responses for 30 minutes
- Batch requests for multiple locations

### 4. Scaling
```python
# Use Redis for caching
from redis import Redis
cache = Redis()

@app.route('/weather/advise', methods=['POST'])
def cached_weather():
    ward = request.json['text'].split()[-1]
    cache_key = f"weather:{ward}"
    
    # Check cache first
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Get fresh data
    handler = get_live_weather_handler()
    result = handler.process_weather_request(f"WEATHER {ward}")
    
    # Cache for 30 minutes
    cache.setex(cache_key, 1800, json.dumps(result))
    
    return result
```

### 5. Monitoring
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('weather_advisor.log'),
        logging.StreamHandler()
    ]
)
```

---

## Troubleshooting

### "Connection timeout"
- Check internet connection
- Verify Open-Meteo is accessible
- Default timeout: 10 seconds
- Increase in `LiveWeatherAdvisoryHandler(timeout=20)`

### "Invalid ward name"
- Use supported ward names (see list above)
- Format: `WEATHER WardName`
- Case-insensitive: "harare" = "HARARE"

### "No rain data available"
- Some locations may have limited historical data
- System defaults to simulated data if unavailable
- Check `api_source` in response

### "API rate limit exceeded"
- Open-Meteo: 10,000 calls/day
- Implement caching for high-volume use
- See Production Considerations section

---

## Support & Documentation

- **API Docs**: https://open-meteo.com/en/docs
- **Weather Codes**: https://open-meteo.com/en/docs
- **Geocoding**: https://open-meteo.com/en/docs/geocoding-api
- **GitHub**: https://github.com/helashey7-del/NBCCo

---

## License

MIT License - See LICENSE file for details

---

**Last Updated**: 2026-05-22  
**Version**: 1.0.0  
**Status**: Production Ready ✅
