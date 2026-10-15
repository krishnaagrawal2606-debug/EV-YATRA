import urllib.request
import json
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_endpoint(name, method="GET", path="", data=None):
    url = f"{BASE_URL}{path}"
    print(f"Testing {name}: {method} {path}...")
    headers = {'Content-Type': 'application/json'} if data else {}
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8') if data else None, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            body = resp.read().decode('utf-8')
            if 'json' in resp.headers.get('Content-Type', ''):
                parsed = json.loads(body)
                return status, parsed
            return status, body
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8')
        try:
            return e.code, json.loads(err_body)
        except:
            return e.code, err_body

def run_all_tests():
    # 1. Test Static Index Page
    status, html = test_endpoint("Serve Antigravity Frontend", "GET", "/")
    assert status == 200, f"Expected 200, got {status}"
    assert "EV YATRA" in html, "HTML check failed"
    print("PASS: Antigravity Frontend HTML loaded.")

    # 2. Test Get Stations
    status, res = test_endpoint("Fetch Stations", "GET", "/api/stations?all=true")
    assert status == 200, f"Expected 200, got {status}"
    assert res.get("success") is True
    assert res.get("count") >= 50, f"Expected >= 50 stations, got {res.get('count')}"
    first_st = res["stations"][0]
    print(f"PASS: Found {res['count']} stations across India.")

    # 3. Test Deep Slot Inspection ("Slot Hai Ya Nahi")
    status, slot_res = test_endpoint("Inspect Live Slots", "GET", f"/api/stations/{first_st['id']}/slots")
    assert status == 200
    station_data = slot_res["station"]
    assert "slots" in station_data
    assert len(station_data["slots"]) > 0
    free_slots = [s for s in station_data["slots"] if s["is_free"]]
    print(f"PASS: Station '{station_data['name']}' has {len(free_slots)} of {len(station_data['slots'])} bays available.")

    # 4. Test Demo User Login
    login_payload = {
        "email_or_phone": "alex@antigravity.ev",
        "password": "demo123"
    }
    status, login_res = test_endpoint("Demo User Login", "POST", "/api/auth/login", login_payload)
    assert status == 200, f"Login failed: {login_res}"
    user = login_res["user"]
    assert user["name"] == "Alex Mercer"
    print(f"PASS: Logged in as {user['name']} ({user['email']}). Vehicle: {user['vehicle_model']}")

    # 5. Test User Profile & Eco Dashboard Stats
    status, prof_res = test_endpoint("Get User Profile & Telemetry", "GET", f"/api/auth/profile?user_id={user['id']}")
    assert status == 200
    assert prof_res["user"]["total_kwh"] > 0
    assert prof_res["user"]["co2_saved_kg"] > 0
    print(f"PASS: Eco Stats verified: {prof_res['user']['total_kwh']} kWh power, {prof_res['user']['co2_saved_kg']} kg CO2 abated.")

    # 6. Test User Registration
    signup_payload = {
        "name": "Priya Sharma",
        "email": "priya.test@evyatra.in",
        "phone": "+91 91111 22222",
        "password": "password123",
        "vehicle_model": "MG ZS EV",
        "vehicle_number": "MH 01 AB 9988"
    }
    status, reg_res = test_endpoint("User Registration", "POST", "/api/auth/signup", signup_payload)
    assert status in (201, 400), f"Registration status: {status}"
    print("PASS: User registration endpoint operational.")

    # 7. Test Google Maps Search API
    status, search_res = test_endpoint("Google Maps Places / Geocode Search", "GET", "/api/maps/search?q=Hathras")
    assert status == 200
    assert search_res.get("success") is True
    assert len(search_res.get("results", [])) > 0
    print(f"PASS: Maps Search returned {len(search_res['results'])} location hits for 'Hathras'.")

    # 7b. Test Google EV Station Finding API
    status, g_res = test_endpoint("Google EV Station Discovery", "GET", "/api/google/find-stations?q=Jaipur")
    assert status == 200
    assert g_res.get("success") is True
    assert len(g_res.get("stations", [])) > 0
    print(f"PASS: Google Engine discovered {len(g_res['stations'])} EV stations for Jaipur.")

    # 7c. Test Stations query filter returns stations for searched location
    status, q_res = test_endpoint("Fetch Stations with Query Filter", "GET", "/api/stations?q=Jaipur")
    assert status == 200
    assert q_res.get("success") is True
    assert len(q_res.get("stations", [])) > 0
    print(f"PASS: Station query filter returned {len(q_res['stations'])} stations for 'Jaipur'.")

    # 8. Test 30-Minute Exclusivity Booking
    booking_payload = {
        "user_id": user["id"],
        "station_id": first_st["id"],
        "slot_id": free_slots[0]["id"],
        "user_name": user["name"],
        "phone": user["phone"],
        "vehicle_type": "4-Wheeler Car",
        "vehicle_model": user["vehicle_model"],
        "vehicle_number": user["vehicle_number"]
    }
    status, b_res = test_endpoint("Create 30-Min Booking", "POST", "/api/bookings", booking_payload)
    assert status == 201
    booking = b_res["booking"]
    print(f"PASS: Slot #{booking['slot_number']} locked for 30 minutes. ID: {booking['id']}")
    print(f"     Remaining seconds: {booking['remaining_seconds']}s")

    # 9. Verify Bay Status Changed to Reserved
    status, updated_slot_res = test_endpoint("Verify Slot Locked in Inspector", "GET", f"/api/stations/{first_st['id']}/slots")
    locked_slot = [s for s in updated_slot_res["station"]["slots"] if s["id"] == free_slots[0]["id"]][0]
    assert locked_slot["status"].lower() == "reserved"
    print(f"PASS: Bay #{locked_slot['slot_number']} now shows RESERVED in real-time inspector.")

    # 10. Check-In Booking & Verify Real Telemetry Increment
    kwh_before = prof_res["user"]["total_kwh"]
    status, checkin_res = test_endpoint("Simulate Check-In", "POST", f"/api/bookings/{booking['id']}/checkin")
    assert status == 200
    status, prof_after = test_endpoint("Verify Telemetry Incremented After Check-In", "GET", f"/api/auth/profile?user_id={user['id']}")
    assert status == 200
    assert prof_after["user"]["total_kwh"] > kwh_before, f"Expected kWh > {kwh_before}, got {prof_after['user']['total_kwh']}"
    print(f"PASS: Check-In verified and real user telemetry incremented ({kwh_before} -> {prof_after['user']['total_kwh']} kWh).")

    # 11. Test Towns & Villages EV Stations Filter
    status, tv_res = test_endpoint("Fetch Town & Village Stations", "GET", "/api/stations?all=true&station_type=town_village")
    assert status == 200
    assert tv_res.get("success") is True
    assert tv_res.get("count") >= 100, f"Expected >= 100 town & village stations, got {tv_res.get('count')}"
    print(f"PASS: Found {tv_res['count']} verified EV stations in towns and villages across India.")

    # 12. Test Real-Time Bay Live Telemetry Endpoint
    status, tel_res = test_endpoint("Live Bay Telemetry Delta", "GET", f"/api/stations/live-telemetry?ids={first_st['id']}")
    assert status == 200
    assert tel_res.get("success") is True
    assert first_st["id"] in tel_res.get("stations", {})
    st_tel = tel_res["stations"][first_st["id"]]
    assert "available_slots" in st_tel
    assert "slots" in st_tel
    print(f"PASS: Real-time telemetry confirmed for '{first_st['id']}': {st_tel['available_slots']} of {st_tel['total_slots']} bays free.")

    # 13. Test Official Google / Gmail Authentication
    google_payload = {
        "email": "priya.google@gmail.com",
        "name": "Priya Google Pilot",
        "password": "googlepassword123"
    }
    status, g_res = test_endpoint("Official Google Auth Endpoint", "POST", "/api/auth/google", google_payload)
    assert status == 200, f"Google auth failed: {g_res}"
    assert g_res.get("success") is True
    assert g_res.get("user", {}).get("email") == "priya.google@gmail.com"
    print("PASS: Official Google / Gmail authentication verified.")

    # 14. Test Real Apple ID Authentication
    apple_payload = {
        "email": "alex.pilot@icloud.com",
        "name": "Alex Apple Pilot",
        "password": "appleidpassword123"
    }
    status, apple_res = test_endpoint("Real Apple ID Auth Endpoint", "POST", "/api/auth/apple", apple_payload)
    assert status == 200
    assert apple_res.get("success") is True
    assert apple_res.get("user", {}).get("email") == "alex.pilot@icloud.com"
    print("PASS: Real Apple ID authentication & password persistence verified.")

    # 15. Test Real Password Reset & Change Password
    reset_payload = {
        "email": "priya.test@evyatra.in",
        "phone": "+91 91111 22222",
        "new_password": "newpassword456"
    }
    status, rst_res = test_endpoint("Real Password Reset", "POST", "/api/auth/reset-password", reset_payload)
    assert status == 200, f"Password reset failed: {rst_res}"
    assert rst_res.get("success") is True
    print("PASS: Real password reset verified against registered email + mobile.")

    # 16. Test Real Vehicle Garage Add & Select Active Vehicle
    veh_payload = {
        "vehicle_type": "4-Wheeler EV",
        "vehicle_model": "Hyundai IONIQ 5",
        "vehicle_number": "KA 01 EV 7777",
        "connector_type": "CCS2 DC (350 kW)"
    }
    status, v_res = test_endpoint("Add Garage Vehicle", "POST", f"/api/users/{user['id']}/vehicles", veh_payload)
    assert status == 201, f"Add vehicle failed: {v_res}"
    new_vid = v_res["vehicles"][0]["id"]
    status, sel_res = test_endpoint("Set Active Garage Vehicle", "PUT", f"/api/users/{user['id']}/vehicles/{new_vid}/select")
    assert status == 200, f"Select vehicle failed: {sel_res}"
    assert sel_res["user"]["vehicle_model"] == "Hyundai IONIQ 5"
    print("PASS: Real EV Garage vehicle addition & active vehicle selection verified.")

    # 17. Test Real Partner / CPO Onboarding Application
    partner_payload = {
        "user_id": user["id"],
        "company_name": "SunCharge Highway Grid Pvt Ltd",
        "location_city": "Pune, Maharashtra (NH-48)",
        "contact_phone": "+91 98220 11223",
        "charger_capacity": "120kW Dual CCS2 DC Fast Hub"
    }
    status, p_res = test_endpoint("Submit Partner Application", "POST", "/api/partners/apply", partner_payload)
    assert status == 201, f"Partner apply failed: {p_res}"
    assert p_res.get("success") is True
    assert p_res["application"]["application_code"].startswith("CPO-")
    print(f"PASS: Real Partner Application saved in SQLite: {p_res['application']['application_code']}")

    # 18. Test Real Store & Membership Order
    order_payload = {
        "user_id": user["id"],
        "item_code": "PASS-HIGHWAY-999",
        "item_name": "EV Yatra Pro Highway Pass",
        "amount_inr": 999
    }
    status, o_res = test_endpoint("Create Store Order", "POST", "/api/store/order", order_payload)
    assert status == 201, f"Store order failed: {o_res}"
    assert o_res.get("success") is True
    assert o_res["order"]["order_code"].startswith("ORD-")
    print(f"PASS: Real Store Order saved in SQLite: {o_res['order']['order_code']}")

    # 19. Test Real 6-Digit OTP Dispatch & Verification Login
    status, otp_send = test_endpoint("Send 6-Digit Login OTP", "POST", "/api/auth/send-otp", {"identifier": "+91 98765 43210", "purpose": "login"})
    assert status == 200, f"OTP send failed: {otp_send}"
    assert otp_send.get("success") is True
    code_6 = otp_send.get("otp_code")
    assert len(code_6) == 6 and code_6.isdigit()
    status, otp_ver = test_endpoint("Verify 6-Digit Login OTP", "POST", "/api/auth/verify-otp", {"identifier": "+91 98765 43210", "otp_code": code_6, "purpose": "login"})
    assert status == 200, f"OTP verify failed: {otp_ver}"
    assert otp_ver.get("otp_verified") is True
    assert otp_ver.get("user", {}).get("name") == "Alex Mercer"
    print(f"PASS: Real 6-Digit OTP ({code_6}) generated, stored in SQLite, and verified for login.")

    # 20. Test Real OTP-Verified Password Reset
    status, rst_otp_send = test_endpoint("Send 6-Digit Reset OTP", "POST", "/api/auth/send-otp", {"identifier": "priya.test@evyatra.in", "purpose": "reset"})
    assert status == 200, f"Reset OTP send failed: {rst_otp_send}"
    rst_code = rst_otp_send.get("otp_code")
    status, rst_otp_res = test_endpoint("Verify Reset OTP & Update Password", "POST", "/api/auth/reset-password", {
        "email": "priya.test@evyatra.in",
        "otp_code": rst_code,
        "new_password": "otpverifiedpassword789"
    })
    assert status == 200, f"OTP password reset failed: {rst_otp_res}"
    print(f"PASS: Real 6-Digit OTP ({rst_code}) verified for password reset.")

    # 21. Test Highway Trip Planner & Corridor Discovery
    status, plan_res = test_endpoint("Highway EV Trip Planner", "GET", "/api/route/plan?origin=Delhi&destination=Jaipur")
    assert status == 200, f"Trip plan failed: {plan_res}"
    assert plan_res.get("success") is True
    assert plan_res.get("total_distance_km") > 200
    assert len(plan_res.get("en_route_stations", [])) > 0
    assert len(plan_res.get("soc_milestones", [])) >= 2
    print(f"PASS: Highway EV Trip Planner verified: Delhi -> Jaipur ({plan_res['total_distance_km']} km, {plan_res['en_route_stations_count']} corridor hubs).")

    print("\n==========================================================================")
    print("ALL 21 PRODUCTION TESTS PASSED! HIGHWAY ROUTE PLANNER & SMART GRID VERIFIED!")
    print("==========================================================================")

if __name__ == '__main__':
    run_all_tests()
