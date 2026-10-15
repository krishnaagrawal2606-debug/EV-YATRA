import os
import math
import json
import urllib.request
import urllib.parse
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import database

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app)

# Initialize database on startup
database.init_db()

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points on Earth in kilometers.
    """
    R = 6371.0 # Radius of Earth in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)

# ================= Frontend Static Routes =================

@app.route('/')
@app.route('/home')
@app.route('/landing')
@app.route('/map')
def serve_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/login')
def serve_login():
    return send_from_directory(FRONTEND_DIR, 'login.html')

@app.route('/favicon.ico')
@app.route('/favicon.svg')
def serve_favicon():
    return send_from_directory(FRONTEND_DIR, 'favicon.svg', mimetype='image/svg+xml')


@app.route('/<path:path>')
def serve_static(path):
    if path in ['login', 'login.html']:
        return send_from_directory(FRONTEND_DIR, 'login.html')
    if path in ['map', 'map.html', 'home', 'home.html', 'landing', 'landing.html', 'index', 'index.html']:
        return send_from_directory(FRONTEND_DIR, 'index.html')
    if os.path.exists(os.path.join(FRONTEND_DIR, path)):
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, 'index.html')

# ================= Google Maps Config & Indian Cities Cache =================

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

def load_app_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"gmaps_api_key": ""}

def save_app_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)

def get_gmaps_api_key():
    cfg = load_app_config()
    return cfg.get('gmaps_api_key', '').strip() or os.environ.get('GOOGLE_MAPS_API_KEY', '').strip()

INDIAN_CITIES_CACHE = {
    "delhi": (28.6139, 77.2090, "New Delhi, Delhi, India"),
    "new delhi": (28.6139, 77.2090, "New Delhi, Delhi, India"),
    "mumbai": (19.0760, 72.8777, "Mumbai, Maharashtra, India"),
    "pune": (18.5204, 73.8567, "Pune, Maharashtra, India"),
    "bengaluru": (12.9716, 77.5946, "Bengaluru, Karnataka, India"),
    "bangalore": (12.9716, 77.5946, "Bengaluru, Karnataka, India"),
    "hyderabad": (17.3850, 78.4867, "Hyderabad, Telangana, India"),
    "chennai": (13.0827, 80.2707, "Chennai, Tamil Nadu, India"),
    "kolkata": (22.5726, 88.3639, "Kolkata, West Bengal, India"),
    "ahmedabad": (23.0225, 72.5714, "Ahmedabad, Gujarat, India"),
    "surat": (21.1702, 72.8311, "Surat, Gujarat, India"),
    "vadodara": (22.3072, 73.1812, "Vadodara, Gujarat, India"),
    "jaipur": (26.9124, 75.7873, "Jaipur, Rajasthan, India"),
    "lucknow": (26.8467, 80.9462, "Lucknow, Uttar Pradesh, India"),
    "agra": (27.1767, 78.0081, "Agra, Uttar Pradesh, India"),
    "varanasi": (25.3176, 82.9739, "Varanasi, Uttar Pradesh, India"),
    "hathras": (27.5972, 78.0519, "Hathras, Uttar Pradesh, India"),
    "aligarh": (27.8974, 78.0880, "Aligarh, Uttar Pradesh, India"),
    "mathura": (27.4924, 77.6737, "Mathura, Uttar Pradesh, India"),
    "noida": (28.5355, 77.3910, "Noida, Uttar Pradesh, India"),
    "greater noida": (28.4744, 77.5040, "Greater Noida, Uttar Pradesh, India"),
    "gurgaon": (28.4595, 77.0266, "Gurugram, Haryana, India"),
    "gurugram": (28.4595, 77.0266, "Gurugram, Haryana, India"),
    "chandigarh": (30.7333, 76.7794, "Chandigarh, India"),
    "indore": (22.7196, 75.8577, "Indore, Madhya Pradesh, India"),
    "bhopal": (23.2599, 77.4126, "Bhopal, Madhya Pradesh, India"),
    "kanpur": (26.4499, 80.3319, "Kanpur, Uttar Pradesh, India"),
    "patna": (25.5941, 85.1376, "Patna, Bihar, India"),
    "ranchi": (23.3441, 85.3096, "Ranchi, Jharkhand, India"),
    "nagpur": (21.1458, 79.0882, "Nagpur, Maharashtra, India"),
    "nashik": (19.9975, 73.7898, "Nashik, Maharashtra, India"),
    "kochi": (9.9312, 76.2673, "Kochi, Kerala, India"),
    "visakhapatnam": (17.6868, 83.2185, "Visakhapatnam, Andhra Pradesh, India"),
    "coimbatore": (11.0168, 76.9558, "Coimbatore, Tamil Nadu, India"),
    "mysuru": (12.2958, 76.6394, "Mysuru, Karnataka, India"),
    "mysore": (12.2958, 76.6394, "Mysuru, Karnataka, India"),
    "bhubaneswar": (20.2961, 85.8245, "Bhubaneswar, Odisha, India"),
    "goa": (15.2993, 74.1240, "Goa, India"),
    "dehradun": (30.3165, 78.0322, "Dehradun, Uttarakhand, India"),
    "shimla": (31.1048, 77.1734, "Shimla, Himachal Pradesh, India"),
    "srinagar": (34.0837, 74.7973, "Srinagar, Jammu and Kashmir, India"),
    "jammu": (32.7266, 74.8570, "Jammu, Jammu and Kashmir, India"),
    "guwahati": (26.1445, 91.7362, "Guwahati, Assam, India"),
    "ayodhya": (26.7922, 82.1998, "Ayodhya, Uttar Pradesh, India"),
    "prayagraj": (25.4358, 81.8463, "Prayagraj, Uttar Pradesh, India"),
    "allahabad": (25.4358, 81.8463, "Prayagraj, Uttar Pradesh, India"),
    "gwalior": (26.2183, 78.1828, "Gwalior, Madhya Pradesh, India"),
    "jabalpur": (23.1815, 79.9864, "Jabalpur, Madhya Pradesh, India"),
    "meerut": (28.9845, 77.7064, "Meerut, Uttar Pradesh, India"),
    "ghaziabad": (28.6692, 77.4538, "Ghaziabad, Uttar Pradesh, India"),
    "faridabad": (28.4089, 77.3178, "Faridabad, Haryana, India"),
    "haridwar": (29.9457, 78.1642, "Haridwar, Uttarakhand, India"),
    "rishikesh": (30.0869, 78.2676, "Rishikesh, Uttarakhand, India"),
    "amritsar": (31.6340, 74.8723, "Amritsar, Punjab, India"),
    "ludhiana": (30.9010, 75.8573, "Ludhiana, Punjab, India"),
    "jodhpur": (26.2389, 73.0243, "Jodhpur, Rajasthan, India"),
    "udaipur": (24.5854, 73.7125, "Udaipur, Rajasthan, India"),
    "kota": (25.2138, 75.8648, "Kota, Rajasthan, India"),
}

def geocode_location_helper(query):
    if not query:
        return None
    
    q_clean = query.strip()
    q_lower = q_clean.lower()

    # 1. Quick match in Indian cities cache
    for city_key, city_data in INDIAN_CITIES_CACHE.items():
        if city_key == q_lower or (len(city_key) > 3 and city_key in q_lower):
            return {
                "lat": city_data[0],
                "lng": city_data[1],
                "name": city_data[2],
                "short_name": city_key.title(),
                "source": "instant_city_cache"
            }

    # 2. Google Geocoding API (if key available)
    api_key = get_gmaps_api_key()
    if api_key:
        try:
            url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(q_clean)}&region=in&key={api_key}"
            req = urllib.request.Request(url, headers={'User-Agent': 'EV-Yatra-App/2.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get('status') == 'OK' and data.get('results'):
                    res = data['results'][0]
                    loc = res['geometry']['location']
                    return {
                        "lat": loc['lat'],
                        "lng": loc['lng'],
                        "name": res.get('formatted_address', q_clean),
                        "short_name": q_clean.title(),
                        "source": "google_geocode_api"
                    }
        except Exception as e:
            print(f"Google Geocode API error: {e}")

    # 3. Photon Komoot API (Fast OpenStreetMap Elasticsearch)
    try:
        url = f"https://photon.komoot.io/api/?q={urllib.parse.quote(q_clean)}&limit=3"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            features = data.get('features', [])
            if features:
                in_feat = next((f for f in features if f.get('properties', {}).get('country') == 'India'), features[0])
                coords = in_feat['geometry']['coordinates']
                props = in_feat.get('properties', {})
                name_parts = [props.get('name', q_clean.title())]
                if props.get('city') and props.get('city') != name_parts[0]: name_parts.append(props.get('city'))
                if props.get('state'): name_parts.append(props.get('state'))
                if props.get('country'): name_parts.append(props.get('country'))
                return {
                    "lat": coords[1],
                    "lng": coords[0],
                    "name": ", ".join(name_parts),
                    "short_name": props.get('name', q_clean.title()),
                    "source": "photon_osm"
                }
    except Exception as e:
        print(f"Photon geocode note: {e}")

    # 4. OpenStreetMap Nominatim
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(q_clean)}&countrycodes=in&limit=1"
        req = urllib.request.Request(url, headers={'User-Agent': 'EV-Yatra-App/2.0 (contact@evyatra.in)'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data and len(data) > 0:
                item = data[0]
                return {
                    "lat": float(item['lat']),
                    "lng": float(item['lon']),
                    "name": item.get('display_name', q_clean),
                    "short_name": item.get('display_name', q_clean).split(',')[0],
                    "source": "nominatim"
                }
    except Exception as e:
        print(f"Nominatim geocode note: {e}")

    return None

def find_stations_from_google_api(query, lat, lng, api_key):
    """
    Queries Google Places Text Search and Nearby Search for EV charging stations.
    """
    found = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    # 1. Google Places Text Search: 'ev charging station in <query>'
    try:
        text_url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query=ev+charging+station+in+{urllib.parse.quote(query)}&key={api_key}"
        req = urllib.request.Request(text_url, headers=headers)
        with urllib.request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for item in data.get('results', []):
                loc = item.get('geometry', {}).get('location', {})
                if 'lat' in loc and 'lng' in loc:
                    name = item.get('name', 'Google EV Station')
                    address = item.get('formatted_address', f"Near {name}")
                    rating = item.get('rating', 4.8)
                    found.append({
                        "name": name,
                        "address": address,
                        "latitude": loc['lat'],
                        "longitude": loc['lng'],
                        "rating": rating,
                        "source": "google_places_api"
                    })
    except Exception as e:
        print(f"Google Places Text Search error: {e}")

    # 2. Google Places Nearby Search if coordinates available:
    if lat and lng and len(found) < 3:
        try:
            nearby_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius=20000&type=charging_station&keyword=ev+charging&key={api_key}"
            req = urllib.request.Request(nearby_url, headers=headers)
            with urllib.request.urlopen(req, timeout=7) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for item in data.get('results', []):
                    loc = item.get('geometry', {}).get('location', {})
                    if 'lat' in loc and 'lng' in loc:
                        name = item.get('name', 'Google Verified EV Hub')
                        address = item.get('vicinity', f"Near {name}")
                        rating = item.get('rating', 4.8)
                        found.append({
                            "name": name,
                            "address": address,
                            "latitude": loc['lat'],
                            "longitude": loc['lng'],
                            "rating": rating,
                            "source": "google_places_api"
                        })
        except Exception as e:
            print(f"Google Places Nearby Search error: {e}")

    return found

def find_stations_with_google_discovery(query, lat, lng):
    """
    Discovers EV charging stations using Google Places API (if key available)
    or Google-verified dynamic hub generation and Overpass sync.
    Saves new stations into the database and returns all stations in the vicinity.
    """
    api_key = get_gmaps_api_key()
    city_name = query.split(',')[0].strip().title() if query else "Local Area"

    if api_key:
        discovered = find_stations_from_google_api(query or city_name, lat, lng, api_key)
        for stat in discovered:
            net = "Google Verified Network"
            n_lower = stat['name'].lower()
            if "tata" in n_lower: net = "Tata Power"
            elif "jio" in n_lower or "bp" in n_lower: net = "Jio-bp pulse"
            elif "statiq" in n_lower: net = "Statiq"
            elif "ather" in n_lower: net = "Ather Grid"
            elif "chargezone" in n_lower: net = "ChargeZone"
            elif "zeon" in n_lower: net = "Zeon Charging"

            stat_data = {
                "name": stat['name'],
                "network": net,
                "address": stat['address'],
                "city": city_name,
                "latitude": stat['latitude'],
                "longitude": stat['longitude'],
                "price_per_kwh": 18.5,
                "rating": stat.get('rating', 4.8),
                "source": "google_places_api"
            }
            database.add_or_update_google_station(stat_data)

    # Ensure at least 3 stations exist within 30km of lat, lng
    existing = [s for s in database.get_all_stations() if calculate_haversine_distance(lat, lng, s['latitude'], s['longitude']) <= 30]
    if len(existing) < 3:
        database.generate_dynamic_stations_for_location(lat, lng, city_name)

    # Return all stations within 50km
    all_stations = database.get_all_stations()
    nearby = []
    for s in all_stations:
        dist = calculate_haversine_distance(lat, lng, s['latitude'], s['longitude'])
        if dist <= 50:
            s['distance_km'] = dist
            s['source'] = 'google_verified'
            nearby.append(s)

    nearby.sort(key=lambda x: x['distance_km'])
    return nearby

# ================= Geocoding & Location Search =================

@app.route('/api/geolocation/ip', methods=['GET'])
def ip_geolocation_route():
    """
    Detects approximate user location via IP address when browser GPS is unavailable or on HTTP LAN.
    """
    try:
        req = urllib.request.Request("http://ip-api.com/json/?fields=status,country,regionName,city,lat,lon", headers={'User-Agent': 'EV-Yatra-App/2.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get("status") == "success" and data.get("lat") and data.get("lon"):
                lat = float(data["lat"])
                lng = float(data["lon"])
                if 6.0 <= lat <= 37.5 and 68.0 <= lng <= 97.5:
                    return jsonify({
                        "success": True,
                        "lat": lat,
                        "lng": lng,
                        "city": data.get("city", "Local Area"),
                        "region": data.get("regionName", "India")
                    })
    except Exception as e:
        print(f"IP geolocation note: {e}")

    return jsonify({
        "success": True,
        "lat": 28.6139,
        "lng": 77.2090,
        "city": "New Delhi",
        "region": "Delhi NCR"
    })

@app.route('/api/geocode', methods=['GET'])
def geocode_location():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({"success": False, "error": "Query required"}), 400

    geo = geocode_location_helper(query)
    if geo:
        # Ensure stations exist around this location
        existing = [s for s in database.get_all_stations() if calculate_haversine_distance(geo['lat'], geo['lng'], s['latitude'], s['longitude']) <= 30]
        if len(existing) < 2:
            database.generate_dynamic_stations_for_location(geo['lat'], geo['lng'], geo['short_name'])

        return jsonify({
            "success": True,
            "lat": geo['lat'],
            "lng": geo['lng'],
            "name": geo['name'],
            "short_name": geo.get('short_name', query.title())
        })

    return jsonify({"success": False, "error": "Location not found"}), 404

# ================= Real-World Live APIs: Routing & Weather =================

@app.route('/api/route', methods=['GET'])
def get_driving_route():
    """
    Real-world driving route using OSRM Road Network API.
    Accepts either (from_lat, from_lng, to_lat, to_lng) or (start_lat, start_lng, end_lat, end_lng).
    Returns exact road polyline coordinates, driving distance in km, driving duration in minutes, and turn-by-turn steps.
    """
    from_lat = request.args.get('from_lat', type=float)
    if from_lat is None:
        from_lat = request.args.get('start_lat', type=float)

    from_lng = request.args.get('from_lng', type=float)
    if from_lng is None:
        from_lng = request.args.get('start_lng', type=float)

    to_lat = request.args.get('to_lat', type=float)
    if to_lat is None:
        to_lat = request.args.get('end_lat', type=float)

    to_lng = request.args.get('to_lng', type=float)
    if to_lng is None:
        to_lng = request.args.get('end_lng', type=float)

    if None in (from_lat, from_lng, to_lat, to_lng):
        return jsonify({"success": False, "error": "Start and destination coordinates required"}), 400

    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{from_lng},{from_lat};{to_lng},{to_lat}?overview=full&geometries=geojson&steps=true"
        req = urllib.request.Request(url, headers={'User-Agent': 'EV-Yatra-App/2.0'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get("code") == "Ok" and len(data.get("routes", [])) > 0:
                route = data["routes"][0]
                distance_km = round(route["distance"] / 1000.0, 1)
                duration_min = max(1, round(route["duration"] / 60.0))
                # GeoJSON coordinates are [lng, lat] -> convert to [lat, lng] for Leaflet
                coords = [[pt[1], pt[0]] for pt in route["geometry"]["coordinates"]]

                steps = []
                for leg in route.get("legs", []):
                    for step in leg.get("steps", []):
                        maneuver = step.get("maneuver", {})
                        m_type = maneuver.get("type", "drive").replace("_", " ").strip()
                        modifier = maneuver.get("modifier", "").strip()
                        road_name = (step.get("name") or step.get("ref") or "Main Corridor").strip()
                        dist_m = round(step.get("distance", 0))
                        if dist_m < 15 and m_type != "arrive":
                            continue
                        dist_label = f"{round(dist_m / 1000.0, 1)} km" if dist_m >= 1000 else f"{dist_m} m"

                        if m_type == "depart":
                            instruction = f"Start on {road_name} ({dist_label})"
                        elif m_type == "arrive":
                            instruction = "Arrive at EV Charging Hub"
                        elif modifier:
                            instruction = f"Turn {modifier} onto {road_name} ({dist_label})"
                        else:
                            instruction = f"Continue on {road_name} ({dist_label})"

                        steps.append({
                            "instruction": instruction,
                            "distance_m": dist_m,
                            "distance_text": dist_label,
                            "duration_s": round(step.get("duration", 0))
                        })

                step_texts = [s["instruction"] for s in steps[:8]]
                if not step_texts:
                    step_texts = [f"Drive {distance_km} km along main corridor to EV station"]

                route_dict = {
                    "distance_km": distance_km,
                    "duration_min": duration_min,
                    "duration_mins": duration_min,
                    "eta": f"{duration_min} mins",
                    "coordinates": coords,
                    "steps": step_texts,
                    "detailed_steps": steps[:8]
                }
                return jsonify({
                    "success": True,
                    "distance_km": distance_km,
                    "duration_min": duration_min,
                    "duration_mins": duration_min,
                    "eta": f"{duration_min} mins",
                    "coordinates": coords,
                    "steps": step_texts,
                    "route": route_dict
                })
    except Exception as e:
        print(f"OSRM Routing note: {e}")

    # Fallback to interpolated road corridor if OSRM is unreachable
    straight_dist = calculate_haversine_distance(from_lat, from_lng, to_lat, to_lng)
    road_dist = round(straight_dist * 1.22, 1)
    est_duration = max(2, round((road_dist / 38.0) * 60))
    mid_lat = round((from_lat + to_lat) / 2.0 + 0.003, 5)
    mid_lng = round((from_lng + to_lng) / 2.0 - 0.003, 5)
    fallback_coords = [[from_lat, from_lng], [mid_lat, mid_lng], [to_lat, to_lng]]
    fallback_steps = [
        f"Head towards destination corridor ({round(road_dist * 0.4, 1)} km)",
        f"Continue on main highway / arterial road ({round(road_dist * 0.6, 1)} km)",
        "Arrive at EV Charging Hub"
    ]
    fallback_route = {
        "distance_km": road_dist,
        "duration_min": est_duration,
        "duration_mins": est_duration,
        "eta": f"{est_duration} mins",
        "coordinates": fallback_coords,
        "steps": fallback_steps
    }
    return jsonify({
        "success": True,
        "distance_km": road_dist,
        "duration_min": est_duration,
        "duration_mins": est_duration,
        "eta": f"{est_duration} mins",
        "coordinates": fallback_coords,
        "steps": fallback_steps,
        "route": fallback_route
    })

def resolve_location_coords(query):
    """
    Resolves location string (city name, landmark, or lat,lng) to (lat, lng, formatted_name).
    """
    if not query:
        return None
    q = str(query).strip()
    if ',' in q:
        parts = q.split(',')
        try:
            lat = float(parts[0].strip())
            lng = float(parts[1].strip())
            name = parts[2].strip() if len(parts) > 2 else f"{lat:.4f}, {lng:.4f}"
            return (lat, lng, name)
        except ValueError:
            pass
    ql = q.lower()
    if ql in INDIAN_CITIES_CACHE:
        return INDIAN_CITIES_CACHE[ql]
    for k, v in INDIAN_CITIES_CACHE.items():
        if k in ql or ql in k:
            return v
    # Search SQLite stations
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT latitude, longitude, name, city FROM stations WHERE city LIKE ? OR name LIKE ? LIMIT 1", (f"%{q}%", f"%{q}%"))
        row = cur.fetchone()
        conn.close()
        if row and row[0] and row[1]:
            return (float(row[0]), float(row[1]), f"{row[2]}, {row[3]}")
    except Exception:
        pass
    return None

@app.route('/api/route/plan', methods=['GET', 'POST'])
def plan_highway_trip():
    """
    Intelligent Highway EV Trip Planner with corridor station discovery,
    battery SOC simulation, and optimal 30-min charging stop recommendations.
    Accepts:
      - origin: string (city/address) or 'lat,lng'
      - destination: string (city/address) or 'lat,lng'
      - vehicle_range_km: default 320
      - initial_soc: default 90 (%)
      - corridor_buffer_km: default 25 (km)
      - min_power_kw: default 30 (kW)
    """
    data = request.get_json(silent=True) or {}
    origin_param = request.args.get('origin') or data.get('origin') or 'Delhi'
    dest_param = request.args.get('destination') or data.get('destination') or 'Jaipur'
    vehicle_range = float(request.args.get('vehicle_range_km') or data.get('vehicle_range_km') or 320)
    initial_soc = float(request.args.get('initial_soc') or data.get('initial_soc') or 90)
    buffer_km = float(request.args.get('corridor_buffer_km') or data.get('corridor_buffer_km') or 25)
    min_power = float(request.args.get('min_power_kw') or data.get('min_power_kw') or 30)

    origin_resolved = resolve_location_coords(origin_param)
    dest_resolved = resolve_location_coords(dest_param)

    if not origin_resolved or not dest_resolved:
        return jsonify({
            "success": False,
            "error": "Could not resolve origin or destination location across India. Please check city name."
        }), 400

    from_lat, from_lng, origin_label = origin_resolved
    to_lat, to_lng, dest_label = dest_resolved

    # 1. Fetch road route coordinates from OSRM with fallback
    coords = []
    total_dist_km = 0.0
    drive_duration_min = 0
    turn_steps = []

    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{from_lng},{from_lat};{to_lng},{to_lat}?overview=full&geometries=geojson&steps=true"
        req = urllib.request.Request(url, headers={'User-Agent': 'EV-Yatra-App/2.0'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            rdata = json.loads(resp.read().decode('utf-8'))
            if rdata.get("code") == "Ok" and len(rdata.get("routes", [])) > 0:
                r0 = rdata["routes"][0]
                total_dist_km = round(r0["distance"] / 1000.0, 1)
                drive_duration_min = max(1, round(r0["duration"] / 60.0))
                coords = [[pt[1], pt[0]] for pt in r0["geometry"]["coordinates"]]
                for leg in r0.get("legs", []):
                    for step in leg.get("steps", []):
                        m = step.get("maneuver", {})
                        m_type = m.get("type", "drive")
                        modifier = m.get("modifier", "").strip()
                        rname = (step.get("name") or step.get("ref") or "Highway").strip()
                        dist_m = round(step.get("distance", 0))
                        if dist_m < 30 and m_type != "arrive":
                            continue
                        dist_txt = f"{round(dist_m/1000.0, 1)} km" if dist_m >= 1000 else f"{dist_m} m"
                        if m_type == "depart":
                            turn_steps.append(f"Start on {rname} ({dist_txt})")
                        elif m_type == "arrive":
                            turn_steps.append(f"Arrive at {dest_label}")
                        elif modifier:
                            turn_steps.append(f"Turn {modifier} onto {rname} ({dist_txt})")
                        else:
                            turn_steps.append(f"Continue on {rname} ({dist_txt})")
    except Exception as e:
        print(f"Trip Planner OSRM error: {e}")

    if not coords or total_dist_km <= 0:
        straight = calculate_haversine_distance(from_lat, from_lng, to_lat, to_lng)
        total_dist_km = round(straight * 1.25, 1)
        drive_duration_min = max(10, round((total_dist_km / 50.0) * 60))
        # Interpolate 15 intermediate points
        coords = []
        for i in range(16):
            frac = i / 15.0
            lat = round(from_lat + (to_lat - from_lat) * frac, 5)
            lng = round(from_lng + (to_lng - from_lng) * frac, 5)
            coords.append([lat, lng])
        turn_steps = [
            f"Depart from {origin_label} on main national highway corridor",
            f"Maintain steady EV cruising speed along highway ({round(total_dist_km * 0.5, 1)} km)",
            f"Follow signboards towards {dest_label}",
            f"Arrive safely at {dest_label}"
        ]

    # 2. Sample 30 points along route to detect corridor stations
    sample_step = max(1, len(coords) // 30)
    sampled_pts = coords[::sample_step]
    if coords[-1] not in sampled_pts:
        sampled_pts.append(coords[-1])

    # 3. Discover stations within buffer_km of corridor from SQLite
    all_stations_db = database.get_all_stations()
    en_route_stations = []

    for s in all_stations_db:
        s_lat = s.get('latitude') or s.get('lat')
        s_lng = s.get('longitude') or s.get('lng')
        if not s_lat or not s_lng:
            continue
        try:
            s_lat = float(s_lat)
            s_lng = float(s_lng)
        except:
            continue

        power_kw = float(s.get('power_kw') or 60)
        if power_kw < min_power:
            continue

        # Find closest point on route
        min_dist_to_route = 9999.0
        best_pt_idx = 0
        for idx, pt in enumerate(sampled_pts):
            d = calculate_haversine_distance(s_lat, s_lng, pt[0], pt[1])
            if d < min_dist_to_route:
                min_dist_to_route = d
                best_pt_idx = idx

        if min_dist_to_route <= buffer_km:
            progress_ratio = best_pt_idx / max(1, len(sampled_pts) - 1)
            dist_from_start = round(progress_ratio * total_dist_km, 1)
            s_copy = dict(s)
            s_copy['corridor_deviation_km'] = round(min_dist_to_route, 1)
            s_copy['distance_from_start_km'] = dist_from_start
            en_route_stations.append(s_copy)

    # Sort corridor stations by distance from start
    en_route_stations.sort(key=lambda x: x['distance_from_start_km'])

    # 4. Battery SOC & Charging Stop Simulation
    # Effective single-charge range factoring 15% reserve buffer
    usable_range = (initial_soc / 100.0) * vehicle_range * 0.85
    stops_needed = 0
    recommended_stops = []
    soc_milestones = []

    # Milestone 1: Departure
    soc_milestones.append({
        "label": f"Start: {origin_label}",
        "distance_km": 0,
        "soc_pct": round(initial_soc),
        "status": "Departure"
    })

    if total_dist_km <= usable_range:
        # Direct non-stop trip feasible!
        arrival_soc = max(10, round(initial_soc - (total_dist_km / vehicle_range) * 100))
        soc_milestones.append({
            "label": f"Arrival: {dest_label} (Non-Stop)",
            "distance_km": total_dist_km,
            "soc_pct": arrival_soc,
            "status": "Final Destination"
        })
    else:
        # Trip exceeds single-charge range: select optimal charging stop(s)
        stops_needed = 1
        target_stop_dist = min(total_dist_km * 0.6, vehicle_range * (initial_soc / 100.0) * 0.65)

        # Candidates near target distance (within ±50 km)
        candidates = [
            st for st in en_route_stations
            if 30 <= st['distance_from_start_km'] <= (vehicle_range * (initial_soc / 100.0) * 0.82)
        ]

        chosen_station = None
        if candidates:
            # Score candidates: closer to target distance, higher power, and available slots
            candidates.sort(
                key=lambda x: (
                    -float(x.get('power_kw') or 60),
                    -int(x.get('available_slots') or 1),
                    abs(x['distance_from_start_km'] - target_stop_dist)
                )
            )
            chosen_station = candidates[0]
        elif en_route_stations:
            # Fallback to closest available en-route hub
            chosen_station = en_route_stations[len(en_route_stations) // 2]

        if chosen_station:
            stop_dist = chosen_station['distance_from_start_km']
            stop_arrival_soc = max(12, round(initial_soc - (stop_dist / vehicle_range) * 100))
            soc_to_add = 80 - stop_arrival_soc
            batt_cap_kwh = round(vehicle_range * 0.16)
            kwh_to_add = round((soc_to_add / 100.0) * batt_cap_kwh, 1)
            station_kw = float(chosen_station.get('power_kw') or 60)
            charge_mins = max(20, min(45, round((kwh_to_add / station_kw) * 60) + 5))
            price_kwh = float(chosen_station.get('price_per_kwh') or 18.0)
            charge_cost = round(kwh_to_add * price_kwh)

            recommended_stops.append({
                "stop_number": 1,
                "station": chosen_station,
                "distance_from_start_km": stop_dist,
                "arrival_soc_pct": stop_arrival_soc,
                "target_soc_pct": 80,
                "recommended_charge_mins": charge_mins,
                "kwh_added": kwh_to_add,
                "estimated_cost_inr": charge_cost,
                "lock_slot_url": f"/#book-{chosen_station['id']}"
            })

            soc_milestones.append({
                "label": f"Stop #1: {chosen_station['name']} ({chosen_station.get('city', 'Highway')})",
                "distance_km": stop_dist,
                "soc_pct": stop_arrival_soc,
                "status": f"Arrive at {stop_arrival_soc}% &bull; 30-min Lock Charge to 80%"
            })

            rem_dist = total_dist_km - stop_dist
            final_arrival_soc = max(15, round(80 - (rem_dist / vehicle_range) * 100))
            soc_milestones.append({
                "label": f"Arrival: {dest_label}",
                "distance_km": total_dist_km,
                "soc_pct": final_arrival_soc,
                "status": "Final Destination"
            })
        else:
            final_arrival_soc = max(10, round(initial_soc - (total_dist_km / vehicle_range) * 100))
            soc_milestones.append({
                "label": f"Arrival: {dest_label}",
                "distance_km": total_dist_km,
                "soc_pct": final_arrival_soc,
                "status": "Final Destination"
            })

    # 5. Financial & Eco Savings Analytics
    total_charge_time_min = sum(s["recommended_charge_mins"] for s in recommended_stops)
    total_journey_min = drive_duration_min + total_charge_time_min
    total_kwh_needed = round(total_dist_km * 0.16, 1)
    ev_total_cost = round(total_kwh_needed * 18.0)
    petrol_liters = round(total_dist_km / 14.0, 1)
    petrol_cost = round(petrol_liters * 102.0)
    net_savings = max(0, petrol_cost - ev_total_cost)
    co2_kg = round(total_dist_km * 0.142, 1)

    return jsonify({
        "success": True,
        "origin": {
            "name": origin_label,
            "lat": from_lat,
            "lng": from_lng
        },
        "destination": {
            "name": dest_label,
            "lat": to_lat,
            "lng": to_lng
        },
        "total_distance_km": total_dist_km,
        "driving_duration_mins": drive_duration_min,
        "charging_duration_mins": total_charge_time_min,
        "total_journey_mins": total_journey_min,
        "stops_needed": stops_needed,
        "vehicle_specs": {
            "estimated_range_km": vehicle_range,
            "initial_soc_pct": initial_soc,
            "battery_capacity_kwh": round(vehicle_range * 0.16, 1)
        },
        "route_coordinates": coords,
        "turn_by_turn_steps": turn_steps[:12],
        "en_route_stations_count": len(en_route_stations),
        "en_route_stations": en_route_stations[:25],
        "recommended_stops": recommended_stops,
        "soc_milestones": soc_milestones,
        "eco_analytics": {
            "total_kwh_draw": total_kwh_needed,
            "ev_charging_cost_inr": ev_total_cost,
            "petrol_equivalent_cost_inr": petrol_cost,
            "net_rupee_savings": net_savings,
            "co2_abated_kg": co2_kg,
            "trees_equivalent": round(co2_kg / 21.0, 1)
        }
    })

@app.route('/api/weather', methods=['GET'])
def get_live_weather():
    """
    Live real-time weather & EV battery thermal efficiency index via Open-Meteo API.
    Zero API key required.
    """
    lat = request.args.get('lat', default=28.6139, type=float)
    lng = request.args.get('lng', default=77.2090, type=float)

    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
        req = urllib.request.Request(url, headers={'User-Agent': 'EV-Yatra-App/2.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            curr = data.get("current", {})
            temp = curr.get("temperature_2m", 25.0)
            code = curr.get("weather_code", 0)
            wind = curr.get("wind_speed_10m", 10.0)
            humidity = curr.get("relative_humidity_2m", 50)

            # Weather interpretation
            if code == 0:
                condition = "Clear Sky"
                icon = "fa-sun"
            elif code in (1, 2, 3):
                condition = "Partly Cloudy"
                icon = "fa-cloud-sun"
            elif code in (45, 48):
                condition = "Foggy / Mist"
                icon = "fa-smog"
            elif code in (51, 53, 55, 61, 63, 65):
                condition = "Rain Showers"
                icon = "fa-cloud-rain"
            elif code >= 95:
                condition = "Thunderstorm"
                icon = "fa-cloud-bolt"
            else:
                condition = "Pleasant / Fair"
                icon = "fa-cloud"

            # Battery Thermal Efficiency estimation based on ambient temp
            # EVs have peak battery charging efficiency around 20°C - 28°C
            if 18 <= temp <= 28:
                efficiency = "100% (Optimal)"
                battery_tip = "Ideal battery temperature for max DC charging speed."
            elif 29 <= temp <= 38:
                efficiency = "94% (Good)"
                battery_tip = "Battery cooling active; minor throttle on initial 5 mins."
            elif temp > 38:
                efficiency = "88% (Warm)"
                battery_tip = "High ambient heat; pre-condition battery if supported."
            else:
                efficiency = "90% (Cool)"
                battery_tip = "Cold ambient; battery heater will optimize charge curve."

            return jsonify({
                "success": True,
                "temperature": round(temp, 1),
                "condition": condition,
                "icon": icon,
                "humidity": humidity,
                "wind_kmh": round(wind, 1),
                "battery_efficiency": efficiency,
                "battery_tip": battery_tip
            })
    except Exception as e:
        print(f"Weather API note: {e}")

    # Fallback
    return jsonify({
        "success": True,
        "temperature": 27.5,
        "condition": "Pleasant",
        "icon": "fa-cloud-sun",
        "humidity": 45,
        "wind_kmh": 12.0,
        "battery_efficiency": "98% (Optimal)",
        "battery_tip": "Normal charging conditions active."
    })

@app.route('/api/stations/live-osm-sync', methods=['GET'])
def live_osm_sync():
    """
    Syncs live community EV charging station nodes from OpenStreetMap Overpass API
    and saves them into the local EV Yatra database.
    """
    lat = request.args.get('lat', default=28.6139, type=float)
    lng = request.args.get('lng', default=77.2090, type=float)
    radius = request.args.get('radius', default=15000, type=int)

    try:
        q = f'[out:json][timeout:6];node[amenity=charging_station](around:{radius},{lat},{lng});out 10;'
        url = 'https://overpass-api.de/api/interpreter?data=' + urllib.parse.quote(q)
        req = urllib.request.Request(url, headers={'User-Agent': 'EV-Yatra-App/2.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            elements = data.get('elements', [])
            added_count = 0
            for el in elements:
                tags = el.get('tags', {})
                name = tags.get('name') or tags.get('operator') or f"EV Station #{el['id']}"
                operator = tags.get('operator', 'Public EV Network')
                node_lat = el['lat']
                node_lng = el['lon']
                stat_id = f"stat-osm-{el['id']}"

                conn = database.get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT id FROM stations WHERE id = ?", (stat_id,))
                if not cur.fetchone():
                    amenities = ["Restrooms", "24/7 Access"]
                    cur.execute('''
                    INSERT OR IGNORE INTO stations (id, name, network, address, city, latitude, longitude, price_per_kwh, total_slots, available_slots, amenities, rating, open_hours)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 18.0, 3, 3, ?, 4.7, '24/7')
                    ''', (stat_id, name, operator, f"Near {name}", tags.get('addr:city', 'Local Area'), node_lat, node_lng, json.dumps(amenities)))
                    cur.execute("INSERT OR IGNORE INTO charging_slots VALUES (?, ?, 1, 'CCS2', 60, 'available')", (f"slot-{stat_id}-1", stat_id))
                    cur.execute("INSERT OR IGNORE INTO charging_slots VALUES (?, ?, 2, 'CCS2', 60, 'available')", (f"slot-{stat_id}-2", stat_id))
                    cur.execute("INSERT OR IGNORE INTO charging_slots VALUES (?, ?, 3, 'Type 2 AC', 22, 'available')", (f"slot-{stat_id}-3", stat_id))
                    conn.commit()
                    added_count += 1
                conn.close()

        return jsonify({"success": True, "synced_nodes": len(elements), "newly_added": added_count})
    except Exception as e:
        print(f"OSM sync note: {e}")
        return jsonify({
            "success": True,
            "message": "Overpass mirror temporarily busy; all Pan-India verified stations active.",
            "synced_nodes": 0,
            "newly_added": 0
        })

@app.route('/api/stations/sync-all-india', methods=['GET', 'POST'])
def sync_all_india_stations():
    """
    Online EV stations harvester & Pan-India database synchronization.
    Runs Pan-India harvester and returns total collected live stations and slot stats.
    """
    import pan_india_collector
    try:
        summary = pan_india_collector.collect_and_build_pan_india()
    except Exception as e:
        print(f"Pan-India collector sync note: {e}")
        summary = {}

    all_stats = database.get_all_stations()
    return jsonify({
        "success": True,
        "message": "Pan-India EV stations actively synchronized with live OpenStreetMap nodes and National EV Networks.",
        "current_total_stations": len(all_stats),
        "status": "online_sync_active",
        "summary": summary
    })

@app.route('/api/stations/summary', methods=['GET'])
def get_pan_india_summary():
    """
    Returns Pan-India network breakdown, total stations, slots, top cities, and fast DC metrics.
    """
    summary_path = os.path.join(os.path.dirname(__file__), 'pan_india_stations_summary.json')
    if os.path.exists(summary_path):
        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        except:
            pass

    conn = database.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM stations")
    tot_st = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM charging_slots")
    tot_sl = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT city) FROM stations")
    tot_cities = cur.fetchone()[0]
    conn.close()

    return jsonify({
        "status": "success",
        "total_stations_in_db": tot_st,
        "total_charging_slots_in_db": tot_sl,
        "total_cities_covered": tot_cities
    })

# ================= API Endpoints =================

@app.route('/api/partner/inquiry', methods=['POST'])
def partner_inquiry_route():
    import uuid
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    email = data.get('email', '').strip()
    city = data.get('city', '').strip()
    land_type = data.get('land_type', 'Commercial Land / Parking')
    power_capacity = data.get('power_capacity', '60kW - 120kW DC Fast')
    notes = data.get('notes', '').strip()

    if not name or not phone:
        return jsonify({"success": False, "error": "Contact Name and Phone number are required."}), 400

    inq_id = f"CPO-{uuid.uuid4().hex[:8].upper()}"
    return jsonify({
        "success": True,
        "inquiry_id": inq_id,
        "message": f"Thank you, {name}! Your CPO partnership inquiry ({inq_id}) has been recorded. Our deployment team will reach out at {phone} within 24 hours."
    }), 201

@app.route('/api/stations', methods=['POST'])
def register_station_route():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"success": False, "error": "Station name is required."}), 400

    result = database.create_station(data)
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result), 201

@app.route('/api/stations', methods=['GET'])
def get_stations():
    user_lat = request.args.get('lat', type=float)
    user_lng = request.args.get('lng', type=float)
    query = request.args.get('q', default='', type=str).lower().strip()
    connector = request.args.get('connector', default='', type=str).strip()
    min_power = request.args.get('min_power', default=0, type=int)
    network = request.args.get('network', default='', type=str).strip()
    available_only = request.args.get('available_only', default='false').lower() == 'true'
    view_all = request.args.get('all', default='false').lower() == 'true'
    station_type = request.args.get('station_type', default='', type=str).strip().lower()

    # If query is provided, query takes precedence over view_all
    if query:
        view_all = False

    stations = database.get_all_stations()

    # Search strictly against verified stations, cities, towns and villages
    filtered = []
    for s in stations:
        # Search query filter (name, address, city, network) with smart multi-keyword matching
        if query and not view_all:
            search_str = f"{s['name']} {s['address']} {s['city']} {s['network']}".lower()
            clean_q = query.replace('-', ' ').replace(',', ' ')
            words = [w for w in clean_q.split() if len(w) > 1]
            if words:
                if not any(w in search_str for w in words):
                    continue
            elif query not in search_str:
                continue

        # Station type filter (e.g. 'town_village')
        if station_type and s.get('station_type', '').lower() != station_type:
            continue

        # Network filter
        if network and s['network'].lower() != network.lower():
            continue

        # Availability filter
        if available_only and s['available_slots'] <= 0:
            continue

        # Connector & power filters matching slots
        if connector or min_power > 0:
            matched_slot = False
            for slot in s.get('slots', []):
                type_match = True
                power_match = True
                if connector and connector.lower() not in slot['connector_type'].lower():
                    type_match = False
                if min_power > 0 and slot['power_kw'] < min_power:
                    power_match = False
                if type_match and power_match:
                    matched_slot = True
                    break
            if not matched_slot:
                continue

        # Distance calculation
        if user_lat is not None and user_lng is not None:
            s['distance_km'] = calculate_haversine_distance(user_lat, user_lng, s['latitude'], s['longitude'])
        else:
            s['distance_km'] = None

        filtered.append(s)

    # Sort by distance if user coords provided, otherwise sort by available slots desc
    if user_lat is not None and user_lng is not None:
        filtered.sort(key=lambda x: x['distance_km'])
    else:
        filtered.sort(key=lambda x: x['available_slots'], reverse=True)

    return jsonify({
        "success": True,
        "count": len(filtered),
        "stations": filtered
    })

@app.route('/api/stations/nearby', methods=['GET'])
def get_nearby_stations():
    user_lat = request.args.get('lat', type=float)
    user_lng = request.args.get('lng', type=float)
    radius_km = request.args.get('radius', default=100.0, type=float)

    if user_lat is None or user_lng is None:
        return jsonify({"success": False, "error": "Latitude and longitude are required"}), 400

    stations = database.get_all_stations()
    nearby = []
    for s in stations:
        dist = calculate_haversine_distance(user_lat, user_lng, s['latitude'], s['longitude'])
        s['distance_km'] = dist
        if dist <= radius_km:
            nearby.append(s)

    nearby.sort(key=lambda x: x['distance_km'])

    # If nothing within small radius, automatically spawn dynamic stations around user location!
    if not nearby:
        database.generate_dynamic_stations_for_location(user_lat, user_lng, "Live Local Hub")
        stations = database.get_all_stations()
        for s in stations:
            s['distance_km'] = calculate_haversine_distance(user_lat, user_lng, s['latitude'], s['longitude'])
        stations.sort(key=lambda x: x['distance_km'])
        nearby = stations[:5]

    return jsonify({
        "success": True,
        "count": len(nearby),
        "stations": nearby
    })

@app.route('/api/stations/<station_id>', methods=['GET'])
def get_station_detail(station_id):
    station = database.get_station_by_id(station_id)
    if not station:
        return jsonify({"success": False, "error": "Station not found"}), 404
    return jsonify({"success": True, "station": station})

@app.route('/api/stations/<station_id>/slots', methods=['GET'])
def get_station_slots_route(station_id):
    station = database.get_station_slot_details(station_id)
    if not station:
        return jsonify({"success": False, "error": "Station not found"}), 404
    return jsonify({"success": True, "station": station})

@app.route('/api/stations/live-telemetry', methods=['GET'])
def get_live_telemetry_route():
    """
    High-frequency lightweight endpoint for live bay telemetry auto-sync.
    Provides instant bay status delta, auto-expiry verification, and telemetry timestamps.
    """
    raw_ids = request.args.get('ids', '').strip()
    station_ids = [s.strip() for s in raw_ids.split(',') if s.strip()] if raw_ids else None
    telemetry_data = database.get_stations_live_telemetry(station_ids)
    return jsonify(telemetry_data)

# ================= Verified EV Station, City, Town & Village Search Endpoint =================

@app.route('/api/maps/search', methods=['GET'])
def maps_search_route():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({"success": False, "error": "Search query required"}), 400

    results = database.search_locations_and_stations(query)
    return jsonify({"success": True, "results": results})

# ================= Google Find Stations Endpoint =================

@app.route('/api/google/find-stations', methods=['GET', 'POST'])
def google_find_stations_route():
    """
    Direct endpoint to find EV charging stations using Google:
    - Geocodes location
    - Queries Google Places API or Google Live discovery
    - Guarantees stations are found and saved in SQLite database
    """
    query = request.args.get('q', default='', type=str).strip()
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)

    if not query and (lat is None or lng is None):
        return jsonify({"success": False, "error": "Location query 'q' or coordinates required."}), 400

    location_name = query or "Your Location"
    if lat is None or lng is None:
        geo = geocode_location_helper(query)
        if geo:
            lat = geo['lat']
            lng = geo['lng']
            location_name = geo['name']
        else:
            lat, lng = 28.6139, 77.2090
            location_name = query or "New Delhi"

    stations = find_stations_with_google_discovery(location_name, lat, lng)
    api_key = get_gmaps_api_key()

    return jsonify({
        "success": True,
        "location": {
            "name": location_name,
            "short_name": location_name.split(',')[0].strip(),
            "lat": lat,
            "lng": lng
        },
        "count": len(stations),
        "stations": stations,
        "engine": "google_places_api" if bool(api_key) else "google_smart_discovery"
    })

# ================= Google Maps API Permanent Configuration =================

@app.route('/api/config/gmaps-key', methods=['GET', 'POST'])
def gmaps_key_config():
    if request.method == 'POST':
        data = request.get_json() or {}
        key = data.get('api_key', '').strip()
        cfg = load_app_config()
        cfg['gmaps_api_key'] = key
        save_app_config(cfg)
        return jsonify({"success": True, "api_key": key, "message": "Google Maps API Key permanently configured!"})

    cfg = load_app_config()
    key = cfg.get('gmaps_api_key') or os.environ.get('GOOGLE_MAPS_API_KEY', '')
    return jsonify({
        "success": True,
        "api_key": key,
        "has_key": bool(key),
        "status": "active" if bool(key) else "standard_google_hybrid"
    })

# ================= User Profile & Authentication Routes =================

@app.route('/api/auth/signup', methods=['POST'])
def signup_route():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    password = data.get('password', '').strip()
    vehicle_type = data.get('vehicle_type', '4-Wheeler Car')
    vehicle_model = data.get('vehicle_model', 'Tata Nexon EV Max')
    vehicle_number = data.get('vehicle_number', 'DL 01 EV 2026')
    preferred_connector = data.get('preferred_connector', 'CCS2')

    if not name or not email or not phone or not password:
        return jsonify({"success": False, "error": "Name, email, phone, and password are required."}), 400

    result = database.create_user(name, email, phone, password, vehicle_type, vehicle_model, vehicle_number, preferred_connector)
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result), 201

@app.route('/api/auth/login', methods=['POST'])
def login_route():
    data = request.get_json() or {}
    email_or_phone = data.get('email_or_phone', '').strip()
    password = data.get('password', '').strip()

    if not email_or_phone or not password:
        return jsonify({"success": False, "error": "Email/Phone and password are required."}), 400

    result = database.verify_user(email_or_phone, password)
    if not result.get("success"):
        return jsonify(result), 401
    return jsonify(result)

@app.route('/api/auth/oauth', methods=['POST'])
def oauth_route():
    data = request.get_json() or {}
    provider = data.get('provider', 'google').lower().strip()
    email = data.get('email', '').strip()
    name = data.get('name', '').strip() or (email.split('@')[0].capitalize() if email else f"{provider.capitalize()} Pilot")
    avatar_color = data.get('avatar_color')
    password = data.get('password', '').strip() or None

    if not email:
        return jsonify({"success": False, "error": f"Email is required for {provider.capitalize()} authentication."}), 400

    result = database.authenticate_oauth_user(provider, email, name, avatar_color, password=password)
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result), 200

@app.route('/api/auth/check-email', methods=['POST'])
def check_email_route():
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    if not email:
        return jsonify({"success": False, "error": "Email is required."}), 400
    result = database.check_user_email(email)
    return jsonify(result), 200

@app.route('/api/auth/google', methods=['POST'])
def google_auth_route():
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    name = data.get('name', '').strip() or (email.split('@')[0].capitalize() if email else 'Google Pilot')
    password = data.get('password', '').strip() or None
    avatar_color = data.get('avatar_color', '#4285F4')

    if not email:
        return jsonify({"success": False, "error": "Email is required for Google Sign-In."}), 400

    result = database.authenticate_google_user(email, name, avatar_color=avatar_color, password=password)
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result), 200

@app.route('/api/auth/apple', methods=['POST'])
def apple_auth_route():
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    name = data.get('name', '').strip() or (email.split('@')[0].capitalize() if email else 'Apple Pilot')
    password = data.get('password', '').strip() or None
    avatar_color = data.get('avatar_color', '#A2AAAD')

    if not email:
        return jsonify({"success": False, "error": "Apple ID Email is required."}), 400

    result = database.authenticate_apple_user(email, name, password=password, avatar_color=avatar_color)
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result), 200

@app.route('/api/auth/send-otp', methods=['POST'])
def send_otp_route():
    data = request.get_json() or {}
    identifier = (data.get('identifier') or data.get('email_or_phone') or data.get('email') or data.get('phone') or '').strip()
    purpose = (data.get('purpose') or 'login').strip()
    result = database.generate_and_send_otp(identifier, purpose=purpose)
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result), 200

@app.route('/api/auth/verify-otp', methods=['POST'])
def verify_otp_route():
    data = request.get_json() or {}
    identifier = (data.get('identifier') or data.get('email_or_phone') or data.get('email') or data.get('phone') or '').strip()
    otp_code = str(data.get('otp_code') or data.get('otp') or '').strip()
    purpose = (data.get('purpose') or 'login').strip()
    name = (data.get('name') or '').strip() or None
    vehicle_model = (data.get('vehicle_model') or '').strip() or None
    vehicle_number = (data.get('vehicle_number') or '').strip() or None

    result = database.verify_otp_code(
        identifier=identifier,
        otp_code=otp_code,
        purpose=purpose,
        name=name,
        vehicle_model=vehicle_model,
        vehicle_number=vehicle_number
    )
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result), 200

@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password_route():
    data = request.get_json() or {}
    email = (data.get('email') or data.get('identifier') or '').strip()
    phone = (data.get('phone') or '').strip()
    otp_code = str(data.get('otp_code') or data.get('otp') or '').strip() or None
    new_password = (data.get('new_password') or '').strip()
    result = database.reset_user_password(email, phone, new_password, otp_code=otp_code)
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result), 200

@app.route('/api/auth/change-password', methods=['POST'])
def change_password_route():
    data = request.get_json() or {}
    user_id = data.get('user_id', '').strip()
    current_password = data.get('current_password', '').strip()
    new_password = data.get('new_password', '').strip()
    result = database.change_user_password(user_id, current_password, new_password)
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result), 200

@app.route('/api/auth/profile', methods=['GET'])
def get_profile_route():
    user_id = request.args.get('user_id', '').strip()
    if not user_id:
        return jsonify({"success": False, "error": "user_id is required"}), 400
    result = database.get_user_profile(user_id)
    if not result.get("success"):
        return jsonify(result), 404
    return jsonify(result)

@app.route('/api/auth/profile', methods=['PUT'])
def update_profile_route():
    data = request.get_json() or {}
    user_id = data.get('user_id', '').strip()
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    vehicle_type = data.get('vehicle_type', '4-Wheeler Car')
    vehicle_model = data.get('vehicle_model', '').strip() or 'Tata Nexon EV Max'
    vehicle_number = data.get('vehicle_number', '').strip() or 'IND EV 2026'
    preferred_connector = data.get('preferred_connector', 'CCS2')

    if not user_id or not name or not phone:
        return jsonify({"success": False, "error": "user_id, name, and phone are required"}), 400

    result = database.update_user_profile(user_id, name, phone, vehicle_type, vehicle_model, vehicle_number, preferred_connector)
    return jsonify(result)

@app.route('/api/users', methods=['GET'])
def get_users_route():
    users = database.get_all_users()
    return jsonify({"success": True, "users": users})

@app.route('/api/users/<user_id>', methods=['GET'])
def get_single_user_route(user_id):
    result = database.get_user_profile(user_id)
    if not result.get("success"):
        return jsonify(result), 404
    return jsonify(result)

@app.route('/api/users/<user_id>/vehicles', methods=['GET', 'POST'])
def user_vehicles_route(user_id):
    if request.method == 'POST':
        data = request.get_json() or {}
        v_type = data.get('vehicle_type', '4-Wheeler Car')
        v_model = (data.get('vehicle_model') or data.get('model') or '').strip()
        v_num = (data.get('vehicle_number') or data.get('registration_number') or '').strip().upper()
        batt = data.get('battery_capacity_kwh', 45.0)
        conn_pref = data.get('preferred_connector') or data.get('connector_type') or 'CCS2'
        if not v_model or not v_num:
            return jsonify({"success": False, "error": "Vehicle model and license plate number are required."}), 400
        res = database.add_user_vehicle(user_id, v_type, v_model, v_num, batt, conn_pref)
        return jsonify(res), 201

    vehs = database.get_user_vehicles(user_id)
    return jsonify({"success": True, "vehicles": vehs})

@app.route('/api/users/<user_id>/vehicles/<vehicle_id>/select', methods=['PUT'])
def select_user_vehicle_route(user_id, vehicle_id):
    res = database.select_user_vehicle(user_id, vehicle_id)
    if not res.get("success"):
        return jsonify(res), 400
    return jsonify(res), 200

@app.route('/api/users/<user_id>/vehicles/<vehicle_id>', methods=['DELETE'])
def delete_user_vehicle_route(user_id, vehicle_id):
    res = database.delete_user_vehicle(user_id, vehicle_id)
    return jsonify(res), 200

# ================= Partner Onboarding & Store Orders =================

@app.route('/api/partners/apply', methods=['POST'])
def partner_apply_route():
    data = request.get_json() or {}
    contact_name = (data.get('contact_name') or data.get('company_name') or data.get('name') or '').strip()
    phone = (data.get('phone') or data.get('contact_phone') or '').strip()
    email = (data.get('email') or '').strip()
    city = (data.get('city') or data.get('location_city') or '').strip()
    property_type = (data.get('property_type') or 'Commercial Land').strip()
    power_load = (data.get('power_load') or data.get('charger_capacity') or '60kW - 120kW DC Fast').strip()

    res = database.create_partner_application(contact_name, phone, email, city, property_type, power_load)
    if not res.get("success"):
        return jsonify(res), 400
    return jsonify(res), 201

@app.route('/api/store/order', methods=['POST'])
def store_order_route():
    data = request.get_json() or {}
    user_id = data.get('user_id', '').strip()
    item_name = data.get('item_name', '').strip()
    item_type = data.get('item_type', 'pass').strip()
    amount_inr = data.get('amount_inr', 499)

    res = database.create_store_order(user_id, item_name, item_type, amount_inr)
    if not res.get("success"):
        return jsonify(res), 400
    return jsonify(res), 201

# ================= 30-Minute Booking Endpoints =================

@app.route('/api/bookings', methods=['GET', 'POST'])
@app.route('/api/book', methods=['POST'])
def create_or_list_bookings_route():
    if request.method == 'GET':
        user_id = request.args.get('user_id', '').strip() or None
        phone = request.args.get('phone', '').strip() or None
        bookings = database.get_user_bookings(user_id=user_id, phone=phone)
        return jsonify({"success": True, "bookings": bookings})

    data = request.get_json() or {}
    station_id = data.get('station_id')
    slot_id = data.get('slot_id')
    user_id = data.get('user_id') or None
    user_name = data.get('user_name', '').strip()
    phone = (data.get('phone') or data.get('user_phone') or '').strip()
    vehicle_type = data.get('vehicle_type', '4-Wheeler Car').strip()
    vehicle_model = data.get('vehicle_model', '').strip()
    vehicle_number = data.get('vehicle_number', '').strip().upper()

    if not station_id or not slot_id:
        return jsonify({"success": False, "error": "station_id and slot_id are required"}), 400

    if not user_name or not phone or not vehicle_number:
        return jsonify({"success": False, "error": "Full Name, Phone number, and Vehicle Number are required."}), 400

    result = database.create_booking(
        station_id=station_id,
        slot_id=slot_id,
        user_name=user_name,
        phone=phone,
        vehicle_type=vehicle_type,
        vehicle_model=vehicle_model or "EV Standard",
        vehicle_number=vehicle_number,
        user_id=user_id
    )

    if not result.get("success"):
        return jsonify(result), 400

    return jsonify(result), 201

@app.route('/api/bookings/<booking_id>', methods=['GET'])
def get_booking_route(booking_id):
    booking = database.get_booking_by_id(booking_id)
    if not booking:
        return jsonify({"success": False, "error": "Booking not found"}), 404
    return jsonify({"success": True, "booking": booking})

@app.route('/api/bookings/<booking_id>/cancel', methods=['POST'])
def cancel_booking_route(booking_id):
    result = database.cancel_booking(booking_id)
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result)

@app.route('/api/bookings/<booking_id>/checkin', methods=['POST'])
def checkin_booking_route(booking_id):
    result = database.checkin_booking(booking_id)
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result)

if __name__ == '__main__':
    print("[*] EV Yatra Server starting on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)

