# ⚡ EV Yatra - Smart Live EV Station Finder & 30-Minute Slot Booking Platform

**EV Yatra** is a full-stack, production-grade web platform for discovering live electric vehicle (EV) charging stations and booking charging slots with a **guaranteed 30-minute validity lock**.

---

## 🌟 Key Features

1. **Continuous Real-Time GPS Tracking & Satellite HUD**:
   - `navigator.geolocation.watchPosition` live stream continuously tracking user location, speed, accuracy, and compass heading.
   - Smooth map camera follow mode with animated precision radar circle.
   - Floating GPS Telemetry HUD displaying live coordinates, precision (±m), driving speed (km/h), and bearing.
   - Real-time station proximity distance recalculation as user moves.
   - Real-time road navigation distance and ETA tracking along active electric routes.

2. **Continuous Charging Bay Telemetry Engine**:
   - High-frequency 10-second background auto-synchronization polling `/api/stations/live-telemetry`.
   - Real-time bay occupancy state delta reflecting instantly on station cards with visual highlight animations.
   - Dynamic in-modal slot inspector updates (freeing up bays in real-time without modal re-opening).
   - Automated 30-minute reservation auto-expiry cleanup and synchronization.
   - Manual instant-sync trigger via Telemetry status pill.

3. **Real-time EV Station Discovery**:
   - 1,600+ verified charging nodes across Pan-India and rural corridors.
   - Multi-keyword Google Places & Nominatim search engine with autocomplete.
   - Filter by Towns & Villages (280+), Fast DC (&ge;50kW), CCS-2, Type 2 AC, or Available Now.
   - Live distance calculation via Haversine great-circle formula.

4. **30-Minute Exclusivity Slot Booking Engine**:
   - Lock a specific charging slot/connector exclusively for **30 minutes**.
   - Live countdown timer with second-by-second ticking down and visual progress track.
   - Sticky active reservation bar with animated liquid cyber battery.
   - Auto-expiry mechanism releasing slots back to public pool if user does not arrive in 30 minutes.
   - **Arrived & Plug In (Check-In)** action transitioning slot to charging.
   - **Cancel Slot** action instantly restoring slot availability.
   - Digital Entry Pass with QR code representation and booking verification ID (e.g. `EVY-A1B2C3D4`).

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+ (Python 3.13 tested)
- Flask & Flask-CORS (`pip install flask flask-cors`)

### Run Application

In the project root folder:
```powershell
python backend/server.py
```

Then open your browser at:
```
http://localhost:5000
```

---

## 📁 Architecture

```
EV YATRA/
├── backend/
│   ├── server.py                   # Flask REST API & static server
│   ├── database.py                 # SQLite database, 30-min booking engine & auth
│   ├── pan_india_collector.py      # Pan-India station sync & collector engine
│   ├── ev_yatra.db                 # SQLite database (1,619+ stations across India)
│   ├── osm_india_stations.json     # Curated OpenStreetMap nodes
│   ├── pan_india_stations_summary.json # Station network telemetry summary
│   ├── config.json                 # Optional API keys & system settings
│   └── test_api.py                 # 20-suite end-to-end production test suite
├── frontend/
│   ├── index.html                  # Full EV Yatra single-page platform & Leaflet map
│   ├── home.css                    # Responsive dark/emerald design system & mobile drawer
│   ├── home.js                     # Unified map, slot inspector, OTP auth & routing controller
│   ├── login.html                  # Dedicated standalone sign-in / registration portal
│   └── assets/
│       └── hero_bg.jpg             # High-definition banner image
└── README.md
```
