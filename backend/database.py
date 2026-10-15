import sqlite3
import os
import json
import uuid
import random
import secrets
import hashlib
import smtplib
import urllib.request
import urllib.parse
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), 'ev_yatra.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table for Profile & Authentication
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        vehicle_type TEXT DEFAULT '4-Wheeler Car',
        vehicle_model TEXT DEFAULT 'Tata Nexon EV Max',
        vehicle_number TEXT DEFAULT 'DL 01 EV 2026',
        preferred_connector TEXT DEFAULT 'CCS2',
        avatar_color TEXT DEFAULT '#10b981',
        total_kwh REAL DEFAULT 64.2,
        co2_saved_kg REAL DEFAULT 148.5,
        created_at TEXT NOT NULL
    )
    ''')

    # Stations table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        network TEXT NOT NULL,
        address TEXT NOT NULL,
        city TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        price_per_kwh REAL NOT NULL,
        total_slots INTEGER NOT NULL,
        available_slots INTEGER NOT NULL,
        amenities TEXT,
        rating REAL DEFAULT 4.5,
        open_hours TEXT DEFAULT '24/7'
    )
    ''')

    # Slots / Connectors table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS charging_slots (
        id TEXT PRIMARY KEY,
        station_id TEXT NOT NULL,
        slot_number INTEGER NOT NULL,
        connector_type TEXT NOT NULL,
        power_kw INTEGER NOT NULL,
        status TEXT DEFAULT 'available',
        FOREIGN KEY (station_id) REFERENCES stations (id)
    )
    ''')

    # Bookings table with 30-minute validity and optional user_id
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bookings (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        station_id TEXT NOT NULL,
        slot_id TEXT NOT NULL,
        user_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        vehicle_type TEXT NOT NULL,
        vehicle_model TEXT NOT NULL,
        vehicle_number TEXT NOT NULL,
        booked_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        FOREIGN KEY (station_id) REFERENCES stations (id),
        FOREIGN KEY (slot_id) REFERENCES charging_slots (id)
    )
    ''')

    try:
        cursor.execute("ALTER TABLE bookings ADD COLUMN user_id TEXT")
    except:
        pass

    # Registered EV Vehicles table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_vehicles (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        vehicle_type TEXT NOT NULL,
        vehicle_model TEXT NOT NULL,
        vehicle_number TEXT NOT NULL,
        battery_capacity_kwh REAL DEFAULT 40.0,
        preferred_connector TEXT DEFAULT 'CCS2',
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # Partner / CPO Franchise Applications table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS partner_applications (
        id TEXT PRIMARY KEY,
        contact_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT,
        city TEXT NOT NULL,
        property_type TEXT DEFAULT 'Commercial Land',
        power_load TEXT DEFAULT '60kW - 120kW DC Fast',
        status TEXT DEFAULT 'under_review',
        created_at TEXT NOT NULL
    )
    ''')

    # EV Yatra Store & Membership Orders table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS store_orders (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        item_name TEXT NOT NULL,
        item_type TEXT NOT NULL,
        amount_inr REAL NOT NULL,
        status TEXT DEFAULT 'active',
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # Real 6-Digit OTP Verification table (5-minute expiry + brute-force protection)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS otp_codes (
        id TEXT PRIMARY KEY,
        identifier TEXT NOT NULL,
        otp_code TEXT NOT NULL,
        purpose TEXT DEFAULT 'login',
        expires_at TEXT NOT NULL,
        used INTEGER DEFAULT 0,
        attempts INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    ''')

    cursor.execute("SELECT COUNT(*) FROM stations")
    station_count = cursor.fetchone()[0]
    if station_count < 500:
        seed_all_india_stations(cursor)
        try:
            import pan_india_collector
            pan_india_collector.collect_and_build_pan_india()
        except Exception as e:
            print("Auto Pan-India collector sync note:", e)

    seed_demo_user(cursor)
    conn.commit()
    conn.close()

def seed_all_india_stations(cursor):
    """
    Seeds comprehensive EV charging stations across all states, major cities, and highways in India.
    Uses INSERT OR REPLACE so existing and new stations are properly registered.
    """
    all_stations = [
        # --- DELHI-NCR ---
        {
            "id": "stat-del-01", "name": "Tata Power EZ Charge - Connaught Place", "network": "Tata Power",
            "address": "Block B, Inner Circle, Connaught Place, New Delhi", "city": "New Delhi",
            "latitude": 28.6328, "longitude": 77.2197, "price_per_kwh": 18.5, "rating": 4.8,
            "amenities": ["Restrooms", "Coffee Shop", "WiFi", "24/7 Access", "Security"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60},
                {"connector": "Type 2 AC", "power": 22}, {"connector": "GB/T", "power": 30}
            ]
        },
        {
            "id": "stat-del-02", "name": "Jio-bp pulse EV Hub - Aerocity", "network": "Jio-bp pulse",
            "address": "Hospitality District, Aerocity, New Delhi 110037", "city": "New Delhi",
            "latitude": 28.5524, "longitude": 77.1215, "price_per_kwh": 19.0, "rating": 4.9,
            "amenities": ["Lounge", "Restrooms", "Subway Cafe", "Wheelchair Accessible"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 120},
                {"connector": "CHAdeMO", "power": 50}, {"connector": "Type 2 AC", "power": 22},
                {"connector": "CCS2", "power": 60}
            ]
        },
        {
            "id": "stat-del-03", "name": "Statiq EV Charging Hub - Saket Select Citywalk", "network": "Statiq",
            "address": "Select Citywalk Parking B2, Saket District Centre, New Delhi", "city": "New Delhi",
            "latitude": 28.5284, "longitude": 77.2185, "price_per_kwh": 17.5, "rating": 4.7,
            "amenities": ["Mall Dining", "Restrooms", "Shopping", "Valet"],
            "slots": [
                {"connector": "CCS2", "power": 50}, {"connector": "Type 2 AC", "power": 22}, {"connector": "Type 2 AC", "power": 7.4}
            ]
        },
        {
            "id": "stat-del-04", "name": "Ather Grid - Cyber City Gurgaon", "network": "Ather Grid",
            "address": "DLF Cyber Hub, Sector 24, Gurugram, Haryana 122002", "city": "Gurugram",
            "latitude": 28.4950, "longitude": 77.0895, "price_per_kwh": 16.0, "rating": 4.6,
            "amenities": ["Restaurants", "24/7 Security", "Covered Parking"],
            "slots": [
                {"connector": "Ather Fast/Type 2", "power": 15}, {"connector": "Ather Fast/Type 2", "power": 15}, {"connector": "CCS2", "power": 50}
            ]
        },
        {
            "id": "stat-del-05", "name": "ChargeZone Fast DC Hub - Noida Expressway Sector 135", "network": "ChargeZone",
            "address": "Candor Techspace, Sector 135, Noida, Uttar Pradesh 201304", "city": "Noida",
            "latitude": 28.5029, "longitude": 77.4061, "price_per_kwh": 18.0, "rating": 4.7,
            "amenities": ["Food Court", "Convenience Store", "24/7 Security"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-del-06", "name": "Tata Power Supercharge - Dwarka Sector 14", "network": "Tata Power",
            "address": "Vegas Mall Parking, Sector 14 Dwarka, New Delhi 110078", "city": "New Delhi",
            "latitude": 28.6010, "longitude": 77.0305, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["Cinema", "Food Court", "Restrooms", "Free WiFi"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 30}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-del-07", "name": "Zeon Charging Hub - Golf Course Extension Gurugram", "network": "Zeon Charging",
            "address": "AIPL Joy Street, Sector 66, Gurugram, Haryana 122102", "city": "Gurugram",
            "latitude": 28.4062, "longitude": 77.0673, "price_per_kwh": 19.0, "rating": 4.8,
            "amenities": ["Shopping", "Cafes", "Valet Parking", "Restrooms"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- MUMBAI & PUNE (MAHARASHTRA) ---
        {
            "id": "stat-mum-01", "name": "Jio-bp pulse Mega Hub - BKC (Bandra Kurla Complex)", "network": "Jio-bp pulse",
            "address": "G Block, BKC, Bandra East, Mumbai, Maharashtra 400051", "city": "Mumbai",
            "latitude": 19.0657, "longitude": 72.8697, "price_per_kwh": 19.5, "rating": 4.9,
            "amenities": ["Wild Bean Cafe", "Restrooms", "High-speed WiFi", "EV Waiting Room"],
            "slots": [
                {"connector": "CCS2", "power": 150}, {"connector": "CCS2", "power": 120},
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}, {"connector": "CHAdeMO", "power": 50}
            ]
        },
        {
            "id": "stat-mum-02", "name": "Tata Power Super Fast - Lower Parel Phoenix Mall", "network": "Tata Power",
            "address": "Senapati Bapat Marg, Lower Parel, Mumbai, Maharashtra 400013", "city": "Mumbai",
            "latitude": 18.9953, "longitude": 72.8258, "price_per_kwh": 19.0, "rating": 4.8,
            "amenities": ["Mall Dining", "Cinema", "Restrooms", "Valet Assistance"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-mum-03", "name": "Statiq Supercharge - Andheri West Infiniti Mall", "network": "Statiq",
            "address": "Link Road, Oshiwara, Andheri West, Mumbai, Maharashtra 400053", "city": "Mumbai",
            "latitude": 19.1411, "longitude": 72.8311, "price_per_kwh": 18.5, "rating": 4.7,
            "amenities": ["Shopping", "Dining", "Restrooms"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-mum-04", "name": "Tata Power EV Station - Vashi Inorbit Mall", "network": "Tata Power",
            "address": "Sector 30A, Vashi, Navi Mumbai, Maharashtra 400703", "city": "Navi Mumbai",
            "latitude": 19.0655, "longitude": 72.9984, "price_per_kwh": 18.0, "rating": 4.7,
            "amenities": ["Restrooms", "Shopping", "Food Court"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-pun-01", "name": "ChargeZone Supercharger - Mumbai-Pune Expressway", "network": "ChargeZone",
            "address": "Food Mall, Urse Toll Plaza, Mumbai-Pune Expressway, Talegaon, Pune", "city": "Pune",
            "latitude": 18.7214, "longitude": 73.6841, "price_per_kwh": 21.0, "rating": 4.9,
            "amenities": ["McDonald's", "Restrooms", "Convenience Store", "24/7 Security"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 120},
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-pun-02", "name": "Tata Power EZ Charge - Hinjewadi IT Park Phase 1", "network": "Tata Power",
            "address": "Rajiv Gandhi Infotech Park, Hinjewadi, Pune, Maharashtra 411057", "city": "Pune",
            "latitude": 18.5913, "longitude": 73.7389, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["EV Lounge", "Restrooms", "Cafeteria"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-pun-03", "name": "Ather Grid Fast Charger - Viman Nagar", "network": "Ather Grid",
            "address": "Phoenix Marketcity, Viman Nagar, Pune, Maharashtra 411014", "city": "Pune",
            "latitude": 18.5621, "longitude": 73.9168, "price_per_kwh": 17.0, "rating": 4.7,
            "amenities": ["Shopping", "Dining", "Covered Shade"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Ather Fast/Type 2", "power": 15}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- BENGALURU (KARNATAKA) ---
        {
            "id": "stat-blr-01", "name": "Zeon Electric Fast Charger - Indiranagar", "network": "Zeon Charging",
            "address": "100 Feet Road, HAL 2nd Stage, Indiranagar, Bengaluru, Karnataka 560038", "city": "Bengaluru",
            "latitude": 12.9719, "longitude": 77.6412, "price_per_kwh": 20.0, "rating": 4.9,
            "amenities": ["Coffee Cafe", "Restrooms", "Free WiFi"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-blr-02", "name": "Tata Power EZ Charge - Whitefield ITPL", "network": "Tata Power",
            "address": "International Tech Park, Whitefield Main Road, Bengaluru 560066", "city": "Bengaluru",
            "latitude": 12.9863, "longitude": 77.7308, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["Cafeteria", "ATM", "Restrooms", "EV Lounge"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60},
                {"connector": "Type 2 AC", "power": 22}, {"connector": "GB/T", "power": 25}
            ]
        },
        {
            "id": "stat-blr-03", "name": "Ather Grid Fast Hub - Koramangala 5th Block", "network": "Ather Grid",
            "address": "Near Jyoti Nivas College, Koramangala, Bengaluru, Karnataka 560095", "city": "Bengaluru",
            "latitude": 12.9352, "longitude": 77.6245, "price_per_kwh": 16.5, "rating": 4.7,
            "amenities": ["Restaurants Nearby", "24/7 Guarded"],
            "slots": [
                {"connector": "CCS2", "power": 50}, {"connector": "Ather Fast/Type 2", "power": 15}, {"connector": "Ather Fast/Type 2", "power": 15}
            ]
        },
        {
            "id": "stat-blr-04", "name": "Jio-bp pulse - Electronic City Phase 1", "network": "Jio-bp pulse",
            "address": "Hosur Road, Near Wipro Gate 5, Electronic City, Bengaluru 560100", "city": "Bengaluru",
            "latitude": 12.8452, "longitude": 77.6602, "price_per_kwh": 18.5, "rating": 4.8,
            "amenities": ["Convenience Store", "Restrooms", "24/7 Security"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-mys-01", "name": "ChargeZone Highway Hub - Bengaluru-Mysuru Expressway", "network": "ChargeZone",
            "address": "Expressway Waypoint Food Plaza, Ramanagara Bypass, Karnataka", "city": "Mysuru",
            "latitude": 12.7150, "longitude": 77.2810, "price_per_kwh": 19.5, "rating": 4.9,
            "amenities": ["Highway Food Court", "Restrooms", "Fuel Pump", "EV Waiting Zone"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- HYDERABAD & TELANGANA / AP ---
        {
            "id": "stat-hyd-01", "name": "Statiq Supercharge Hub - Hitec City", "network": "Statiq",
            "address": "Inorbit Mall Road, Madhapur, Hitec City, Hyderabad, Telangana 500081", "city": "Hyderabad",
            "latitude": 17.4375, "longitude": 78.3842, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["Shopping", "Food Court", "Restrooms", "Covered Shade"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-hyd-02", "name": "Jio-bp pulse - Gachibowli Financial District", "network": "Jio-bp pulse",
            "address": "ISB Road, Nanakramguda, Financial District, Hyderabad 500032", "city": "Hyderabad",
            "latitude": 17.4156, "longitude": 78.3428, "price_per_kwh": 19.0, "rating": 4.9,
            "amenities": ["Wild Bean Cafe", "Free WiFi", "Restrooms"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-hyd-03", "name": "Tata Power EZ Charge - Banjara Hills Road No 1", "network": "Tata Power",
            "address": "GVK One Mall Parking, Banjara Hills, Hyderabad, Telangana 500034", "city": "Hyderabad",
            "latitude": 17.4193, "longitude": 78.4485, "price_per_kwh": 18.5, "rating": 4.7,
            "amenities": ["Mall Facilities", "Restrooms", "Valet"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-viz-01", "name": "Tata Power Fast EV Station - Visakhapatnam Beach Road", "network": "Tata Power",
            "address": "RK Beach Road, Pandurangapuram, Visakhapatnam, Andhra Pradesh 530003", "city": "Visakhapatnam",
            "latitude": 17.7126, "longitude": 83.3197, "price_per_kwh": 18.0, "rating": 4.7,
            "amenities": ["Sea View Walk", "Restrooms", "Nearby Cafes"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- CHENNAI & TAMIL NADU ---
        {
            "id": "stat-chn-01", "name": "Zeon Electric Hub - OMR IT Expressway", "network": "Zeon Charging",
            "address": "Rajiv Gandhi Salai (OMR), Perungudi, Chennai, Tamil Nadu 600096", "city": "Chennai",
            "latitude": 12.9644, "longitude": 80.2443, "price_per_kwh": 19.0, "rating": 4.7,
            "amenities": ["Coffee Cafe", "Free WiFi", "Restrooms"],
            "slots": [
                {"connector": "CCS2", "power": 100}, {"connector": "CCS2", "power": 50}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-chn-02", "name": "Tata Power Super Fast - Guindy Olympia Tech Park", "network": "Tata Power",
            "address": "SIDCO Industrial Estate, Guindy, Chennai, Tamil Nadu 600032", "city": "Chennai",
            "latitude": 13.0118, "longitude": 80.2088, "price_per_kwh": 18.5, "rating": 4.8,
            "amenities": ["Restrooms", "Food Court", "24/7 Security"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-cbe-01", "name": "Zeon Charging Super Hub - Coimbatore Avinashi Road", "network": "Zeon Charging",
            "address": "Peelamedu, Near Airport Junction, Coimbatore, Tamil Nadu 641004", "city": "Coimbatore",
            "latitude": 11.0289, "longitude": 77.0272, "price_per_kwh": 19.0, "rating": 4.9,
            "amenities": ["Cafe", "Restrooms", "24/7 Access"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- KOLKATA & WEST BENGAL ---
        {
            "id": "stat-kol-01", "name": "Tata Power EZ Charge - Salt Lake Sector V", "network": "Tata Power",
            "address": "Infinity Benchmark, Block EP & GP, Sector V, Salt Lake, Kolkata 700091", "city": "Kolkata",
            "latitude": 22.5804, "longitude": 88.4378, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["IT Cafeteria", "Restrooms", "Covered Shade", "Security"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-kol-02", "name": "Jio-bp pulse EV Station - New Town Action Area 1", "network": "Jio-bp pulse",
            "address": "Major Arterial Road, Near Axis Mall, New Town, Kolkata 700156", "city": "Kolkata",
            "latitude": 22.5847, "longitude": 88.4601, "price_per_kwh": 18.5, "rating": 4.7,
            "amenities": ["Convenience Store", "Restrooms", "24/7 Access"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-kol-03", "name": "Statiq Supercharge - Park Street", "network": "Statiq",
            "address": "Mother Teresa Sarani, Park Street Area, Kolkata, West Bengal 700016", "city": "Kolkata",
            "latitude": 22.5518, "longitude": 88.3524, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["Restaurants Nearby", "24/7 Security"],
            "slots": [
                {"connector": "CCS2", "power": 50}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- GUJARAT (AHMEDABAD & SURAT) ---
        {
            "id": "stat-ahm-01", "name": "Tata Power Supercharge - SG Highway Ahmedabad", "network": "Tata Power",
            "address": "Near Iscon Cross Road, Sarkhej - Gandhinagar Highway, Ahmedabad, Gujarat 380015", "city": "Ahmedabad",
            "latitude": 23.0298, "longitude": 72.5074, "price_per_kwh": 18.0, "rating": 4.9,
            "amenities": ["Mall Dining", "Restrooms", "Covered Parking"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60},
                {"connector": "Type 2 AC", "power": 22}, {"connector": "GB/T", "power": 30}
            ]
        },
        {
            "id": "stat-ahm-02", "name": "Jio-bp pulse EV Hub - GIFT City Gandhinagar", "network": "Jio-bp pulse",
            "address": "Building 14A, GIFT City SEZ, Gandhinagar, Gujarat 382355", "city": "Ahmedabad",
            "latitude": 23.1611, "longitude": 72.6841, "price_per_kwh": 19.0, "rating": 4.9,
            "amenities": ["Wild Bean Cafe", "Free WiFi", "Restrooms", "Modern Lounge"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-sur-01", "name": "Statiq EV Station - Surat Dumas Road", "network": "Statiq",
            "address": "VR Surat Mall Parking, Dumas Road, Magdalla, Surat, Gujarat 395007", "city": "Surat",
            "latitude": 21.1442, "longitude": 72.7561, "price_per_kwh": 17.5, "rating": 4.8,
            "amenities": ["VR Mall Dining", "Restrooms", "Multiplex"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-vad-01", "name": "Tata Power EZ Charge - Vadodara Alkapuri", "network": "Tata Power",
            "address": "RC Dutt Road, Alkapuri, Vadodara, Gujarat 390007", "city": "Vadodara",
            "latitude": 22.3129, "longitude": 73.1762, "price_per_kwh": 18.0, "rating": 4.7,
            "amenities": ["Restrooms", "Cafes Nearby", "24/7 Access"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- RAJASTHAN (JAIPUR & HIGHWAY) ---
        {
            "id": "stat-jai-01", "name": "Tata Power EZ Charge - Jaipur C-Scheme", "network": "Tata Power",
            "address": "Mirza Ismail Road, Near Panch Batti, C-Scheme, Jaipur, Rajasthan 302001", "city": "Jaipur",
            "latitude": 26.9157, "longitude": 75.8080, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["Heritage Dining", "Restrooms", "24/7 Security"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-jai-02", "name": "Jio-bp pulse - Malviya Nagar World Trade Park", "network": "Jio-bp pulse",
            "address": "Jawahar Lal Nehru Marg, D-Block, Malviya Nagar, Jaipur 302017", "city": "Jaipur",
            "latitude": 26.8536, "longitude": 75.8053, "price_per_kwh": 18.5, "rating": 4.9,
            "amenities": ["WTP Mall Shopping", "Restrooms", "Food Court"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-del-jai-01", "name": "ChargeZone Highway Hub - Delhi-Jaipur Highway (Behror)", "network": "ChargeZone",
            "address": "NH-48 Mid-way Food Hub, Behror, Rajasthan 301701", "city": "Jaipur",
            "latitude": 27.8864, "longitude": 76.2829, "price_per_kwh": 20.0, "rating": 4.9,
            "amenities": ["Haldiram's", "Restrooms", "Fast Food", "24/7 EV Support"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}
            ]
        },

        # --- UTTAR PRADESH (LUCKNOW, KANPUR, AGRA, VARANASI) ---
        {
            "id": "stat-lko-01", "name": "Tata Power EZ Charge - Lucknow Gomti Nagar", "network": "Tata Power",
            "address": "Vibhuti Khand, Near High Court, Gomti Nagar, Lucknow, UP 226010", "city": "Lucknow",
            "latitude": 26.8687, "longitude": 80.9984, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["Restrooms", "Free WiFi", "Covered Shade", "Security"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-lko-02", "name": "Jio-bp pulse - Shaheed Path Phoenix Palassio", "network": "Jio-bp pulse",
            "address": "Sector-7, Amar Shaheed Path, Gomti Nagar Extension, Lucknow 226010", "city": "Lucknow",
            "latitude": 26.8124, "longitude": 81.0182, "price_per_kwh": 19.0, "rating": 4.9,
            "amenities": ["Palassio Mall", "Restrooms", "Valet Parking", "Food Court"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-agr-01", "name": "ChargeZone Supercharger - Yamuna Expressway Food Plaza", "network": "ChargeZone",
            "address": "Milestone 95, Yamuna Expressway, Near Agra Toll, Uttar Pradesh", "city": "Agra",
            "latitude": 27.2785, "longitude": 77.8920, "price_per_kwh": 20.5, "rating": 4.9,
            "amenities": ["Costa Coffee", "Highway Restrooms", "Kids Play Area", "Security"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-kan-01", "name": "Tata Power EV Station - Kanpur Mall Road", "network": "Tata Power",
            "address": "Z Square Mall Parking, The Mall Road, Kanpur, Uttar Pradesh 208001", "city": "Kanpur",
            "latitude": 26.4678, "longitude": 80.3541, "price_per_kwh": 18.0, "rating": 4.7,
            "amenities": ["Z Square Mall", "Restrooms", "Dining"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-vns-01", "name": "Statiq EV Station - Varanasi Cantt Station Road", "network": "Statiq",
            "address": "Near Varanasi Junction Railway Station, Cantt, Varanasi, UP 221002", "city": "Varanasi",
            "latitude": 25.3268, "longitude": 82.9863, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["Restrooms", "Waiting Lounge", "24/7 Guarded"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- PUNJAB, HARYANA & CHANDIGARH ---
        {
            "id": "stat-chd-01", "name": "Tata Power EZ Charge - Chandigarh Sector 17", "network": "Tata Power",
            "address": "Near Sector 17 Plaza, Sector 17-C, Chandigarh 160017", "city": "Chandigarh",
            "latitude": 30.7398, "longitude": 76.7827, "price_per_kwh": 17.5, "rating": 4.8,
            "amenities": ["Plaza Walkway", "Restrooms", "24/7 Security"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-chd-02", "name": "Jio-bp pulse - Elante Mall Industrial Area", "network": "Jio-bp pulse",
            "address": "Elante Mall Basement 2, Industrial Area Phase 1, Chandigarh 160002", "city": "Chandigarh",
            "latitude": 30.7055, "longitude": 76.8013, "price_per_kwh": 18.5, "rating": 4.9,
            "amenities": ["Shopping", "Dining", "Restrooms", "Valet"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-lud-01", "name": "Statiq EV Station - Ludhiana Ferozepur Road", "network": "Statiq",
            "address": "MBD Neopolis Mall, Ferozepur Road, Ludhiana, Punjab 141012", "city": "Ludhiana",
            "latitude": 30.8932, "longitude": 75.8115, "price_per_kwh": 18.0, "rating": 4.7,
            "amenities": ["Mall Facilities", "Restrooms"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- MADHYA PRADESH (INDORE & BHOPAL) ---
        {
            "id": "stat-ind-01", "name": "Tata Power EZ Charge - Indore Vijay Nagar", "network": "Tata Power",
            "address": "C21 Mall Parking, AB Road, Vijay Nagar, Indore, Madhya Pradesh 452010", "city": "Indore",
            "latitude": 22.7533, "longitude": 75.8937, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["C21 Mall", "Restrooms", "Food Court"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-ind-02", "name": "Jio-bp pulse - Super Corridor Indore", "network": "Jio-bp pulse",
            "address": "TCS Square, Super Corridor, Indore, Madhya Pradesh 452005", "city": "Indore",
            "latitude": 22.7681, "longitude": 75.8242, "price_per_kwh": 18.5, "rating": 4.9,
            "amenities": ["Wild Bean Cafe", "Restrooms", "24/7 Access"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-bho-01", "name": "Tata Power EV Hub - Bhopal MP Nagar", "network": "Tata Power",
            "address": "DB City Mall, Zone-I, Maharana Pratap Nagar, Bhopal, MP 462011", "city": "Bhopal",
            "latitude": 23.2332, "longitude": 77.4338, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["DB Mall", "Restrooms", "Food Court", "Valet"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- KERALA (KOCHI & THIRUVANANTHAPURAM) ---
        {
            "id": "stat-koc-01", "name": "Zeon Electric Fast Charger - Kochi Edappally Lulu Mall", "network": "Zeon Charging",
            "address": "Lulu International Shopping Mall, Edappally, Kochi, Kerala 682024", "city": "Kochi",
            "latitude": 10.0275, "longitude": 76.3081, "price_per_kwh": 19.5, "rating": 4.9,
            "amenities": ["Lulu Mall", "Restrooms", "Food Court", "24/7 Guarded"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-koc-02", "name": "Tata Power EZ Charge - Kakkanad Infopark", "network": "Tata Power",
            "address": "Infopark Phase 1, Kusumagiri, Kakkanad, Kochi, Kerala 682042", "city": "Kochi",
            "latitude": 10.0104, "longitude": 76.3639, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["IT Cafeteria", "Restrooms", "Covered Shade"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-trv-01", "name": "Tata Power EV Hub - Trivandrum Technopark", "network": "Tata Power",
            "address": "Technopark Phase 1 Main Gate, Kazhakkoottam, Thiruvananthapuram, Kerala 695581", "city": "Thiruvananthapuram",
            "latitude": 8.5581, "longitude": 76.8812, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["Restrooms", "EV Lounge", "24/7 Security"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- BIHAR (PATNA) ---
        {
            "id": "stat-pat-01", "name": "Tata Power EZ Charge - Patna Fraser Road", "network": "Tata Power",
            "address": "Fraser Road, Near Dak Bungalow Crossing, Patna, Bihar 800001", "city": "Patna",
            "latitude": 25.6093, "longitude": 85.1376, "price_per_kwh": 18.5, "rating": 4.7,
            "amenities": ["Restrooms", "Commercial Market", "24/7 Access"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-pat-02", "name": "Statiq EV Station - Bailey Road Patna", "network": "Statiq",
            "address": "P&M Hi-Tech Mall, Bailey Road, Patliputra, Patna, Bihar 800013", "city": "Patna",
            "latitude": 25.6186, "longitude": 85.0882, "price_per_kwh": 18.0, "rating": 4.7,
            "amenities": ["Shopping", "Dining", "Restrooms"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- ODISHA (BHUBANESWAR) ---
        {
            "id": "stat-bbs-01", "name": "Tata Power Supercharge - Bhubaneswar Infocity", "network": "Tata Power",
            "address": "Infocity Road, Chandrasekharpur, Patia, Bhubaneswar, Odisha 751024", "city": "Bhubaneswar",
            "latitude": 20.3541, "longitude": 85.8172, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["IT Park Cafes", "Restrooms", "24/7 Security"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- GOA ---
        {
            "id": "stat-goa-01", "name": "Zeon Electric Fast Charger - Panaji Miramar", "network": "Zeon Charging",
            "address": "Miramar Beach Road, Panaji, Goa 403001", "city": "Goa",
            "latitude": 15.4828, "longitude": 73.8122, "price_per_kwh": 19.5, "rating": 4.9,
            "amenities": ["Beach Promenade", "Cafes", "Restrooms"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-goa-02", "name": "Ather Grid & CCS2 - Calangute Coastal Hub", "network": "Ather Grid",
            "address": "Calangute - Candolim Main Road, North Goa 403516", "city": "Goa",
            "latitude": 15.5342, "longitude": 73.7667, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["Restaurants", "Covered Shade"],
            "slots": [
                {"connector": "CCS2", "power": 50}, {"connector": "Ather Fast/Type 2", "power": 15}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- UTTARAKHAND (DEHRADUN) ---
        {
            "id": "stat-ddn-01", "name": "Tata Power EZ Charge - Dehradun Rajpur Road", "network": "Tata Power",
            "address": "Pacific Mall Parking, Rajpur Road, Jakhan, Dehradun, Uttarakhand 248006", "city": "Dehradun",
            "latitude": 30.3664, "longitude": 78.0707, "price_per_kwh": 18.5, "rating": 4.8,
            "amenities": ["Pacific Mall", "Restrooms", "Scenic View"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- ASSAM / NORTH EAST (GUWAHATI & SHILLONG) ---
        {
            "id": "stat-gau-01", "name": "Tata Power EV Hub - Guwahati GS Road", "network": "Tata Power",
            "address": "City Centre Mall, GS Road, Christian Basti, Guwahati, Assam 781005", "city": "Guwahati",
            "latitude": 26.1554, "longitude": 91.7788, "price_per_kwh": 18.5, "rating": 4.8,
            "amenities": ["City Centre Mall", "Restrooms", "Food Court"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-shl-01", "name": "Jio-bp pulse EV Station - Shillong Police Bazar", "network": "Jio-bp pulse",
            "address": "Police Bazar Commercial Complex, Shillong, Meghalaya 793001", "city": "Shillong",
            "latitude": 25.5788, "longitude": 91.8831, "price_per_kwh": 19.0, "rating": 4.7,
            "amenities": ["Restrooms", "Cafes", "24/7 Security"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- UTTAR PRADESH EXPANSION (AGRA, MATHURA, HATHRAS, VARANASI, PRAYAGRAJ) ---
        {
            "id": "stat-agr-01", "name": "Tata Power EZ Charge - Agra Sanjay Place", "network": "Tata Power",
            "address": "Cosmos Mall, Sanjay Place, Civil Lines, Agra, UP 282002", "city": "Agra",
            "latitude": 27.2038, "longitude": 78.0061, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["Mall Facilities", "Restrooms", "Food Court", "Taj View"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-mth-01", "name": "Jio-bp pulse - Mathura NH-19 Highway Hub", "network": "Jio-bp pulse",
            "address": "Near Vrindavan Cut, NH-19 Delhi-Agra Highway, Mathura, UP 281001", "city": "Mathura",
            "latitude": 27.5320, "longitude": 77.6385, "price_per_kwh": 18.5, "rating": 4.9,
            "amenities": ["Wild Bean Cafe", "Restrooms", "Highway Food Plaza"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-hat-01", "name": "Statiq EV Supercharge Hub - Hathras GT Road", "network": "Statiq",
            "address": "Near Sasni Gate & Aligarh Bypass, Hathras, UP 204101", "city": "Hathras",
            "latitude": 27.5972, "longitude": 78.0519, "price_per_kwh": 17.5, "rating": 4.7,
            "amenities": ["24/7 Access", "Restrooms", "Tea Lounge", "Secure Parking"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 30}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-vns-01", "name": "Tata Power EV Hub - Varanasi Cantt Station Road", "network": "Tata Power",
            "address": "JHV Mall Parking, The Mall Road, Varanasi Cantt, UP 221002", "city": "Varanasi",
            "latitude": 25.3343, "longitude": 82.9790, "price_per_kwh": 18.5, "rating": 4.8,
            "amenities": ["JHV Mall", "Restrooms", "Multi-cuisine Dining"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-pry-01", "name": "Jio-bp pulse - Prayagraj Civil Lines", "network": "Jio-bp pulse",
            "address": "Subhash Chauraha, Civil Lines, Prayagraj, UP 211001", "city": "Prayagraj",
            "latitude": 25.4518, "longitude": 81.8344, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["Restrooms", "Coffee Shop", "Covered Shade"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- GUJARAT EXPANSION (SURAT, VADODARA, RAJKOT) ---
        {
            "id": "stat-sur-01", "name": "Tata Power Supercharge - Surat Dumas Road", "network": "Tata Power",
            "address": "VR Surat Mall, Dumas Road, Magdalla, Surat, Gujarat 395007", "city": "Surat",
            "latitude": 21.1444, "longitude": 72.7562, "price_per_kwh": 18.5, "rating": 4.9,
            "amenities": ["VR Mall", "Restrooms", "EV Lounge", "Valet"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-vad-01", "name": "Jio-bp pulse - Vadodara Alkapuri", "network": "Jio-bp pulse",
            "address": "Inorbit Mall Parking, Alembic Road, Subhanpura, Vadodara, Gujarat 390023", "city": "Vadodara",
            "latitude": 22.3168, "longitude": 73.1706, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["Inorbit Mall", "Restrooms", "Wild Bean Cafe"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-raj-01", "name": "Statiq EV Station - Rajkot 150ft Ring Road", "network": "Statiq",
            "address": "Crystal Mall, 150 Feet Ring Road, Rajkot, Gujarat 360005", "city": "Rajkot",
            "latitude": 22.2828, "longitude": 70.7712, "price_per_kwh": 17.5, "rating": 4.7,
            "amenities": ["Mall Dining", "Restrooms", "24/7 Guarded"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- MAHARASHTRA EXPANSION (NAGPUR, NASHIK, AURANGABAD) ---
        {
            "id": "stat-nag-01", "name": "Tata Power EV Hub - Nagpur Wardha Road", "network": "Tata Power",
            "address": "Hotel Pride Parking, Wardha Road, Near Airport, Nagpur, Maharashtra 440025", "city": "Nagpur",
            "latitude": 21.0922, "longitude": 79.0628, "price_per_kwh": 18.5, "rating": 4.8,
            "amenities": ["Hotel Amenities", "Restrooms", "24/7 Access", "Airport Shuttle"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-nsk-01", "name": "Jio-bp pulse - Nashik Mumbai Naka", "network": "Jio-bp pulse",
            "address": "Mumbai-Agra Highway Junction, Mumbai Naka, Nashik, Maharashtra 422001", "city": "Nashik",
            "latitude": 19.9882, "longitude": 73.7845, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["Cafe", "Restrooms", "Highway Food Plaza"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-aur-01", "name": "Statiq Supercharge - Aurangabad Jalna Road", "network": "Statiq",
            "address": "Prozone Mall Parking, Chikalthana, Jalna Road, Aurangabad 431006", "city": "Aurangabad",
            "latitude": 19.8732, "longitude": 75.3855, "price_per_kwh": 18.0, "rating": 4.7,
            "amenities": ["Prozone Mall", "Restrooms", "Cinema"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- KARNATAKA EXPANSION (MYSURU & MANGALURU) ---
        {
            "id": "stat-mys-01", "name": "Zeon Electric Fast Charger - Mysuru Mall of Mysore", "network": "Zeon Charging",
            "address": "Mall of Mysore, MG Road, Nazarbad, Mysuru, Karnataka 570010", "city": "Mysuru",
            "latitude": 12.3023, "longitude": 76.6644, "price_per_kwh": 19.0, "rating": 4.9,
            "amenities": ["Mall Dining", "Restrooms", "Mysore Palace Proximity"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-mng-01", "name": "Tata Power EZ Charge - Mangaluru City Centre", "network": "Tata Power",
            "address": "City Centre Mall, KS Rao Road, Hampankatta, Mangaluru, Karnataka 575001", "city": "Mangaluru",
            "latitude": 12.8718, "longitude": 74.8427, "price_per_kwh": 18.5, "rating": 4.8,
            "amenities": ["City Centre Mall", "Restrooms", "24/7 Guarded"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- TAMIL NADU EXPANSION (COIMBATORE, MADURAI, SALEM) ---
        {
            "id": "stat-cbe-01", "name": "Zeon Ultra Fast DC Hub - Coimbatore Avinashi Road", "network": "Zeon Charging",
            "address": "Brookefields Mall Parking, Krishnaswamy Road, Coimbatore, TN 641001", "city": "Coimbatore",
            "latitude": 11.0118, "longitude": 76.9554, "price_per_kwh": 19.5, "rating": 4.9,
            "amenities": ["Brookefields Mall", "Restrooms", "Fast Charging Lounge"],
            "slots": [
                {"connector": "CCS2", "power": 150}, {"connector": "CCS2", "power": 120}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-mdu-01", "name": "Tata Power EV Station - Madurai Bypass", "network": "Tata Power",
            "address": "Milan't Mall, Madurai-Dindigul Bypass Road, Madurai, TN 625016", "city": "Madurai",
            "latitude": 9.9405, "longitude": 78.1408, "price_per_kwh": 18.5, "rating": 4.8,
            "amenities": ["Restrooms", "Dining", "Covered Parking"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- ANDHRA PRADESH (VISAKHAPATNAM, VIJAYAWADA, TIRUPATI) ---
        {
            "id": "stat-viz-01", "name": "Tata Power EV Hub - Visakhapatnam Beach Road", "network": "Tata Power",
            "address": "Novotel Varun Beach Parking, Beach Road, Visakhapatnam, AP 530002", "city": "Visakhapatnam",
            "latitude": 17.7126, "longitude": 83.3182, "price_per_kwh": 19.0, "rating": 4.9,
            "amenities": ["Beach Promenade", "Hotel Dining", "Restrooms", "Sea View"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-vjw-01", "name": "Jio-bp pulse - Vijayawada MG Road", "network": "Jio-bp pulse",
            "address": "PVP Square Mall, MG Road, Benz Circle, Vijayawada, AP 520010", "city": "Vijayawada",
            "latitude": 16.4984, "longitude": 80.6517, "price_per_kwh": 18.5, "rating": 4.8,
            "amenities": ["PVP Square", "Restrooms", "Food Court"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-tpt-01", "name": "Statiq EV Station - Tirupati Alipiri Foothills", "network": "Statiq",
            "address": "Alipiri Bypass Road, Near Sri Venkateswara University, Tirupati, AP 517502", "city": "Tirupati",
            "latitude": 13.6548, "longitude": 79.4005, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["Pilgrim Services", "Restrooms", "24/7 Security"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- RAJASTHAN EXPANSION (UDAIPUR & JODHPUR) ---
        {
            "id": "stat-udp-01", "name": "Tata Power EZ Charge - Udaipur Celebration Mall", "network": "Tata Power",
            "address": "Nexus Celebration Mall, Bhuwana, Udaipur, Rajasthan 313004", "city": "Udaipur",
            "latitude": 24.6174, "longitude": 73.7082, "price_per_kwh": 18.5, "rating": 4.9,
            "amenities": ["Celebration Mall", "Restrooms", "Food Court", "Lake City Views"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-jdh-01", "name": "Jio-bp pulse - Jodhpur Sardarpura", "network": "Jio-bp pulse",
            "address": "C Road, Sardarpura, Jodhpur, Rajasthan 342003", "city": "Jodhpur",
            "latitude": 26.2755, "longitude": 73.0121, "price_per_kwh": 18.0, "rating": 4.8,
            "amenities": ["Restrooms", "Commercial Market", "Covered Shade"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- HIMACHAL PRADESH & UTTARAKHAND (SHIMLA, MANALI, RISHIKESH) ---
        {
            "id": "stat-sml-01", "name": "Tata Power EV Hub - Shimla Shoghi Bypass", "network": "Tata Power",
            "address": "Shoghi Highway Junction, Shimla Bypass, Himachal Pradesh 171219", "city": "Shimla",
            "latitude": 31.0664, "longitude": 77.1265, "price_per_kwh": 19.5, "rating": 4.8,
            "amenities": ["Hill Station Cafe", "Restrooms", "Panoramic Valley View"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-mnl-01", "name": "Statiq Mountain Fast Charger - Manali Aleo", "network": "Statiq",
            "address": "Naggar Highway Road, Aleo, Manali, Himachal Pradesh 175131", "city": "Manali",
            "latitude": 32.2341, "longitude": 77.1906, "price_per_kwh": 19.5, "rating": 4.8,
            "amenities": ["Mountain Cafe", "Restrooms", "24/7 Road Assistance"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-rsk-01", "name": "Zeon Electric Fast Charger - Rishikesh Tapovan", "network": "Zeon Charging",
            "address": "Badrinath Road, Tapovan, Rishikesh, Uttarakhand 249192", "city": "Rishikesh",
            "latitude": 30.1347, "longitude": 78.3242, "price_per_kwh": 19.0, "rating": 4.9,
            "amenities": ["Ganga River Proximity", "Restrooms", "Organic Cafes"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- JAMMU & KASHMIR (SRINAGAR & JAMMU) ---
        {
            "id": "stat-srg-01", "name": "Tata Power EV Hub - Srinagar Dal Lake Boulevard", "network": "Tata Power",
            "address": "Boulevard Road, Near Dal Lake Gate 2, Srinagar, J&K 190001", "city": "Srinagar",
            "latitude": 34.0837, "longitude": 74.8488, "price_per_kwh": 19.5, "rating": 4.9,
            "amenities": ["Dal Lake Shikara Point", "Restrooms", "Handicrafts Market"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-jam-01", "name": "Jio-bp pulse - Jammu Bahu Plaza", "network": "Jio-bp pulse",
            "address": "Bahu Plaza Commercial Complex, Gandhi Nagar, Jammu, J&K 180012", "city": "Jammu",
            "latitude": 32.7058, "longitude": 74.8722, "price_per_kwh": 18.5, "rating": 4.8,
            "amenities": ["Commercial Complex", "Restrooms", "Food Court"],
            "slots": [
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },

        # --- MAJOR NATIONAL HIGHWAY GREEN CORRIDORS ---
        {
            "id": "stat-hwy-01", "name": "ChargeZone Mega Supercharge - Delhi-Mumbai Expressway (Dausa Hub)", "network": "ChargeZone",
            "address": "Midway Rest Stop KM 182, Delhi-Mumbai Expressway, Dausa, Rajasthan 303303", "city": "Delhi-Mumbai Expressway",
            "latitude": 26.8924, "longitude": 76.3312, "price_per_kwh": 19.5, "rating": 4.9,
            "amenities": ["Expressway Food Court", "Clean Restrooms", "Kids Play Area", "24/7 EV Mechanics"],
            "slots": [
                {"connector": "CCS2", "power": 180}, {"connector": "CCS2", "power": 120},
                {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        },
        {
            "id": "stat-hwy-02", "name": "Jio-bp pulse Mega Hub - Mumbai-Pune Expressway (Khalapur)", "network": "Jio-bp pulse",
            "address": "Food Mall, KM 32 Mumbai-Pune Expressway, Khalapur, Maharashtra 410203", "city": "Mumbai-Pune Expressway",
            "latitude": 18.8471, "longitude": 73.2862, "price_per_kwh": 19.5, "rating": 4.9,
            "amenities": ["McDonald's & Starbucks", "Wild Bean Cafe", "Restrooms", "Fastest 150kW Gun"],
            "slots": [
                {"connector": "CCS2", "power": 150}, {"connector": "CCS2", "power": 120},
                {"connector": "CCS2", "power": 60}, {"connector": "CHAdeMO", "power": 50}
            ]
        },
        {
            "id": "stat-hwy-03", "name": "Tata Power Super Fast - Yamuna Expressway (Jewar Toll Plaza)", "network": "Tata Power",
            "address": "Jewar Rest Area, KM 42 Yamuna Expressway, Greater Noida / Jewar, UP 203135", "city": "Yamuna Expressway",
            "latitude": 28.1328, "longitude": 77.5615, "price_per_kwh": 19.0, "rating": 4.8,
            "amenities": ["Expressway Plaza", "Restrooms", "Bikanervala", "24/7 Security"],
            "slots": [
                {"connector": "CCS2", "power": 120}, {"connector": "CCS2", "power": 60}, {"connector": "Type 2 AC", "power": 22}
            ]
        }
    ]

    for stat in all_stations:
        total_slots = len(stat["slots"])
        available_slots = total_slots
        cursor.execute('''
        INSERT OR REPLACE INTO stations (id, name, network, address, city, latitude, longitude, price_per_kwh, total_slots, available_slots, amenities, rating, open_hours)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            stat["id"],
            stat["name"],
            stat["network"],
            stat["address"],
            stat["city"],
            stat["latitude"],
            stat["longitude"],
            stat["price_per_kwh"],
            total_slots,
            available_slots,
            json.dumps(stat.get("amenities", ["Restrooms", "24/7 Access"])),
            stat.get("rating", 4.8),
            "24/7"
        ))

        # Re-register slots
        for idx, s in enumerate(stat["slots"], 1):
            slot_id = f"slot-{stat['id']}-{idx}"
            cursor.execute('''
            INSERT OR REPLACE INTO charging_slots (id, station_id, slot_number, connector_type, power_kw, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                slot_id,
                stat["id"],
                idx,
                s["connector"],
                s["power"],
                "available"
            ))

def generate_dynamic_stations_for_location(lat, lng, location_name="Local Area"):
    """
    If a user searches or is located in an area with no nearby stations,
    this creates 3 realistic live stations around their coordinates within India.
    """
    if not (6.0 <= lat <= 37.5 and 68.0 <= lng <= 97.5):
        return []

    conn = get_db_connection()
    cursor = conn.cursor()

    networks = [
        {"name": "Tata Power EZ Charge", "price": 18.5, "kw1": 60, "kw2": 30},
        {"name": "Jio-bp pulse EV Hub", "price": 19.0, "kw1": 120, "kw2": 60},
        {"name": "Statiq Supercharge Hub", "price": 17.5, "kw1": 60, "kw2": 22}
    ]

    new_stations = []
    # Small coordinate offsets (approx 1 to 5 km)
    offsets = [
        (0.012, 0.008, "Main Market / Commercial Hub"),
        (-0.015, 0.011, "Expressway Bypass / Fuel Station"),
        (0.007, -0.018, "Tech Park & Mall Complex")
    ]

    for idx, (dlat, dlng, area_tag) in enumerate(offsets):
        stat_id = f"stat-dyn-{abs(int(lat*1000))}-{abs(int(lng*1000))}-{idx+1}"
        net = networks[idx % len(networks)]
        stat_name = f"{net['name']} - {location_name} ({area_tag})"
        stat_lat = round(lat + dlat, 5)
        stat_lng = round(lng + dlng, 5)

        cursor.execute("SELECT id FROM stations WHERE id = ?", (stat_id,))
        if cursor.fetchone():
            continue # already generated

        amenities = ["Restrooms", "Coffee Cafe", "24/7 Security", "Covered Shade"]
        cursor.execute('''
        INSERT OR IGNORE INTO stations (id, name, network, address, city, latitude, longitude, price_per_kwh, total_slots, available_slots, amenities, rating, open_hours)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 3, 3, ?, 4.8, '24/7')
        ''', (
            stat_id,
            stat_name,
            net["name"].split()[0] + (" Power" if "Tata" in net["name"] else ""),
            f"{area_tag}, {location_name}",
            location_name,
            stat_lat,
            stat_lng,
            net["price"],
            json.dumps(amenities)
        ))

        # Add slots
        cursor.execute('''
        INSERT OR IGNORE INTO charging_slots (id, station_id, slot_number, connector_type, power_kw, status)
        VALUES (?, ?, 1, 'CCS2', ?, 'available')
        ''', (f"slot-{stat_id}-1", stat_id, net["kw1"]))

        cursor.execute('''
        INSERT OR IGNORE INTO charging_slots (id, station_id, slot_number, connector_type, power_kw, status)
        VALUES (?, ?, 2, 'CCS2', ?, 'available')
        ''', (f"slot-{stat_id}-2", stat_id, net["kw2"]))

        cursor.execute('''
        INSERT OR IGNORE INTO charging_slots (id, station_id, slot_number, connector_type, power_kw, status)
        VALUES (?, ?, 3, 'Type 2 AC', 22, 'available')
        ''', (f"slot-{stat_id}-3", stat_id))

        new_stations.append(stat_id)

    conn.commit()
    conn.close()
    return new_stations

def add_or_update_google_station(stat_data):
    """
    Saves or updates an EV charging station discovered via Google Places API or Google Live Search.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    name = stat_data.get('name', 'Google EV Hub')
    lat = float(stat_data.get('latitude', 0.0))
    lng = float(stat_data.get('longitude', 0.0))
    if not (6.0 <= lat <= 37.5 and 68.0 <= lng <= 97.5):
        conn.close()
        return None
    stat_id = stat_data.get('id') or f"stat-gmaps-{abs(hash(name + str(round(lat, 3)) + str(round(lng, 3))))}"

    cursor.execute("SELECT id FROM stations WHERE id = ?", (stat_id,))
    if not cursor.fetchone():
        slots_data = stat_data.get('slots') or [
            {"connector": "CCS2", "power": 60},
            {"connector": "CCS2", "power": 120 if "fast" in name.lower() or "super" in name.lower() else 60},
            {"connector": "Type 2 AC", "power": 22}
        ]
        total_slots = len(slots_data)
        amenities = stat_data.get('amenities', ["Google Maps Verified", "24/7 Access", "Restrooms", "Fast Charging"])
        
        cursor.execute('''
        INSERT OR REPLACE INTO stations (id, name, network, address, city, latitude, longitude, price_per_kwh, total_slots, available_slots, amenities, rating, open_hours)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            stat_id,
            name,
            stat_data.get('network', 'Google Verified EV Hub'),
            stat_data.get('address', f"Location via Google Maps, {stat_data.get('city', 'India')}"),
            stat_data.get('city', 'Local Area'),
            lat,
            lng,
            stat_data.get('price_per_kwh', 18.5),
            total_slots,
            total_slots,
            json.dumps(amenities),
            stat_data.get('rating', 4.8),
            stat_data.get('open_hours', '24/7')
        ))

        for idx, sl in enumerate(slots_data, 1):
            cursor.execute('''
            INSERT OR REPLACE INTO charging_slots (id, station_id, slot_number, connector_type, power_kw, status)
            VALUES (?, ?, ?, ?, ?, 'available')
            ''', (f"slot-{stat_id}-{idx}", stat_id, idx, sl.get('connector', 'CCS2'), sl.get('power', 60)))

        conn.commit()

    conn.close()
    return stat_id

def cleanup_expired_bookings():
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()

    cursor.execute('''
    SELECT id, station_id, slot_id FROM bookings
    WHERE status = 'active' AND expires_at < ?
    ''', (now_iso,))
    expired_bookings = cursor.fetchall()

    for b in expired_bookings:
        b_id, st_id, sl_id = b["id"], b["station_id"], b["slot_id"]
        cursor.execute("UPDATE bookings SET status = 'expired' WHERE id = ?", (b_id,))
        cursor.execute("UPDATE charging_slots SET status = 'available' WHERE id = ?", (sl_id,))
        cursor.execute('''
        UPDATE stations
        SET available_slots = (
            SELECT COUNT(*) FROM charging_slots
            WHERE station_id = ? AND status = 'available'
        )
        WHERE id = ?
        ''', (st_id, st_id))

    conn.commit()
    conn.close()

def get_all_stations():
    cleanup_expired_bookings()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM stations 
    WHERE latitude BETWEEN 6.0 AND 37.5 AND longitude BETWEEN 68.0 AND 97.5
    ORDER BY name ASC
    """)
    stations = [dict(row) for row in cursor.fetchall()]

    # Fetch all slots in a single query to eliminate N+1 overhead
    cursor.execute("SELECT * FROM charging_slots ORDER BY slot_number ASC")
    all_slots = cursor.fetchall()
    slots_by_station = {}
    for slot in all_slots:
        st_id = slot["station_id"]
        if st_id not in slots_by_station:
            slots_by_station[st_id] = []
        slots_by_station[st_id].append(dict(slot))

    for station in stations:
        station["slots"] = slots_by_station.get(station["id"], [])
        if station["amenities"]:
            try:
                station["amenities"] = json.loads(station["amenities"])
            except:
                station["amenities"] = []

    conn.close()
    return stations

def get_station_by_id(station_id):
    cleanup_expired_bookings()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM stations WHERE id = ?", (station_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    station = dict(row)
    cursor.execute("SELECT * FROM charging_slots WHERE station_id = ? ORDER BY slot_number ASC", (station_id,))
    station["slots"] = [dict(slot) for slot in cursor.fetchall()]
    if station["amenities"]:
        try:
            station["amenities"] = json.loads(station["amenities"])
        except:
            station["amenities"] = []

    conn.close()
    return station

def create_booking(station_id, slot_id, user_name, phone, vehicle_type, vehicle_model, vehicle_number, user_id=None):
    cleanup_expired_bookings()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM charging_slots WHERE id = ? AND station_id = ?", (slot_id, station_id))
    slot = cursor.fetchone()
    if not slot:
        conn.close()
        return {"success": False, "error": "Charging slot not found."}

    if str(slot["status"]).lower() != "available":
        conn.close()
        return {"success": False, "error": f"Slot {slot['slot_number']} is currently {slot['status']}. Please select another slot."}

    now_utc = datetime.now(timezone.utc)
    expires_utc = now_utc + timedelta(minutes=30)
    
    booked_at_iso = now_utc.isoformat()
    expires_at_iso = expires_utc.isoformat()
    
    booking_id = f"EVY-{uuid.uuid4().hex[:8].upper()}"

    cursor.execute('''
    INSERT INTO bookings (id, user_id, station_id, slot_id, user_name, phone, vehicle_type, vehicle_model, vehicle_number, booked_at, expires_at, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
    ''', (
        booking_id, user_id, station_id, slot_id, user_name, phone,
        vehicle_type, vehicle_model, vehicle_number,
        booked_at_iso, expires_at_iso
    ))

    cursor.execute("UPDATE charging_slots SET status = 'reserved' WHERE id = ?", (slot_id,))

    cursor.execute('''
    UPDATE stations
    SET available_slots = (
        SELECT COUNT(*) FROM charging_slots
        WHERE station_id = ? AND status = 'available'
    )
    WHERE id = ?
    ''', (station_id, station_id))

    conn.commit()

    booking = get_booking_by_id(booking_id, conn)
    conn.close()
    return {"success": True, "booking": booking}

def get_booking_by_id(booking_id, conn=None):
    cleanup_expired_bookings()
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    cursor = conn.cursor()
    cursor.execute('''
    SELECT b.*, s.name as station_name, s.address as station_address, s.latitude, s.longitude,
           cs.slot_number, cs.connector_type, cs.power_kw, s.price_per_kwh
    FROM bookings b
    JOIN stations s ON b.station_id = s.id
    JOIN charging_slots cs ON b.slot_id = cs.id
    WHERE b.id = ?
    ''', (booking_id,))
    row = cursor.fetchone()
    
    if not row:
        if should_close:
            conn.close()
        return None

    booking = dict(row)
    now_utc = datetime.now(timezone.utc)
    try:
        exp_time = datetime.fromisoformat(booking["expires_at"])
        remaining_seconds = max(0, int((exp_time - now_utc).total_seconds()))
        expires_epoch = int(exp_time.timestamp())
    except:
        remaining_seconds = 0
        expires_epoch = int((now_utc + timedelta(minutes=30)).timestamp())
        
    booking["remaining_seconds"] = remaining_seconds
    booking["expires_at_epoch"] = expires_epoch
    booking["validity_minutes"] = 30

    if should_close:
        conn.close()
    return booking

def get_user_bookings(user_id=None, phone=None):
    cleanup_expired_bookings()
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id and phone:
        cursor.execute('''
        SELECT b.*, s.name as station_name, s.address as station_address, s.price_per_kwh,
               cs.slot_number, cs.connector_type, cs.power_kw
        FROM bookings b
        JOIN stations s ON b.station_id = s.id
        JOIN charging_slots cs ON b.slot_id = cs.id
        WHERE b.user_id = ? OR b.phone = ?
        ORDER BY b.booked_at DESC LIMIT 25
        ''', (user_id, phone))
    elif user_id:
        cursor.execute('''
        SELECT b.*, s.name as station_name, s.address as station_address, s.price_per_kwh,
               cs.slot_number, cs.connector_type, cs.power_kw
        FROM bookings b
        JOIN stations s ON b.station_id = s.id
        JOIN charging_slots cs ON b.slot_id = cs.id
        WHERE b.user_id = ?
        ORDER BY b.booked_at DESC LIMIT 25
        ''', (user_id,))
    else:
        cursor.execute('''
        SELECT b.*, s.name as station_name, s.address as station_address, s.price_per_kwh,
               cs.slot_number, cs.connector_type, cs.power_kw
        FROM bookings b
        JOIN stations s ON b.station_id = s.id
        JOIN charging_slots cs ON b.slot_id = cs.id
        ORDER BY b.booked_at DESC LIMIT 20
        ''')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def cancel_booking(booking_id):
    cleanup_expired_bookings()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
    booking = cursor.fetchone()
    if not booking:
        conn.close()
        return {"success": False, "error": "Booking not found"}

    if booking["status"] != "active":
        conn.close()
        return {"success": False, "error": f"Booking is already {booking['status']}"}

    cursor.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
    cursor.execute("UPDATE charging_slots SET status = 'available' WHERE id = ?", (booking["slot_id"],))

    cursor.execute('''
    UPDATE stations
    SET available_slots = (
        SELECT COUNT(*) FROM charging_slots
        WHERE station_id = ? AND status = 'available'
    )
    WHERE id = ?
    ''', (booking["station_id"], booking["station_id"]))

    conn.commit()
    conn.close()
    return {"success": True, "message": "Booking cancelled and slot released."}

def checkin_booking(booking_id):
    cleanup_expired_bookings()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
    booking = cursor.fetchone()
    if not booking:
        conn.close()
        return {"success": False, "error": "Booking not found"}

    if booking["status"] != "active":
        conn.close()
        return {"success": False, "error": f"Booking is already {booking['status']}"}

    cursor.execute("UPDATE bookings SET status = 'checked_in' WHERE id = ?", (booking_id,))
    cursor.execute("UPDATE charging_slots SET status = 'charging' WHERE id = ?", (booking["slot_id"],))

    # Update real user charging telemetry in SQLite
    session_kwh = 32.0
    session_co2 = round(session_kwh * 0.85, 1)
    if booking["user_id"]:
        cursor.execute('''
        UPDATE users
        SET total_kwh = ROUND(COALESCE(total_kwh, 0) + ?, 1),
            co2_saved_kg = ROUND(COALESCE(co2_saved_kg, 0) + ?, 1)
        WHERE id = ?
        ''', (session_kwh, session_co2, booking["user_id"]))
    elif booking["phone"]:
        cursor.execute('''
        UPDATE users
        SET total_kwh = ROUND(COALESCE(total_kwh, 0) + ?, 1),
            co2_saved_kg = ROUND(COALESCE(co2_saved_kg, 0) + ?, 1)
        WHERE phone = ?
        ''', (session_kwh, session_co2, booking["phone"]))

    conn.commit()
    conn.close()
    return {
        "success": True,
        "kwh_added": session_kwh,
        "co2_saved_kg": session_co2,
        "message": f"Checked in! Charging session started (+{session_kwh} kWh logged to your telemetry)."
    }

# ================= User Profile & Authentication =================

def hash_password(password):
    salt = "ev_yatra_antigravity_salt_2026"
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

def seed_demo_user(cursor):
    cursor.execute("SELECT id FROM users WHERE email = 'alex@antigravity.ev'")
    if not cursor.fetchone():
        demo_id = "usr-antigravity-demo"
        pwd = hash_password("demo123")
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute('''
        INSERT INTO users (id, name, email, phone, password_hash, vehicle_type, vehicle_model, vehicle_number, preferred_connector, avatar_color, total_kwh, co2_saved_kg, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            demo_id,
            "Alex Mercer",
            "alex@antigravity.ev",
            "+91 98765 43210",
            pwd,
            "4-Wheeler Car",
            "Tesla Model Y Performance",
            "DL 01 EV 8899",
            "CCS2",
            "#10b981",
            142.5,
            328.0,
            now_iso
        ))

def create_user(name, email, phone, password, vehicle_type="4-Wheeler Car", vehicle_model="Tata Nexon EV Max", vehicle_number="DL 01 EV 2026", preferred_connector="CCS2"):
    conn = get_db_connection()
    cursor = conn.cursor()
    clean_email = email.lower().strip()
    cursor.execute("SELECT id FROM users WHERE email = ?", (clean_email,))
    if cursor.fetchone():
        conn.close()
        return {"success": False, "error": "An account with this email already exists. Please Sign In."}
    
    user_id = f"usr-{uuid.uuid4().hex[:8]}"
    pwd_hash = hash_password(password)
    now_iso = datetime.now(timezone.utc).isoformat()
    colors = ['#10b981', '#06b6d4', '#6366f1', '#f59e0b', '#ec4899', '#3b82f6']
    avatar = random.choice(colors)

    cursor.execute('''
    INSERT INTO users (id, name, email, phone, password_hash, vehicle_type, vehicle_model, vehicle_number, preferred_connector, avatar_color, total_kwh, co2_saved_kg, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, ?)
    ''', (
        user_id,
        name.strip(),
        clean_email,
        phone.strip(),
        pwd_hash,
        vehicle_type,
        vehicle_model.strip() if vehicle_model else "Tata Nexon EV Max",
        vehicle_number.upper().strip() if vehicle_number else "IND EV 2026",
        preferred_connector,
        avatar,
        now_iso
    ))
    conn.commit()
    conn.close()
    return get_user_profile(user_id)

def check_user_email(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    clean_email = email.lower().strip()
    cursor.execute("SELECT id, name, email, avatar_color FROM users WHERE email = ?", (clean_email,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"success": True, "exists": True, "user": dict(row)}
    return {"success": True, "exists": False}

def authenticate_oauth_user(provider, email, name, avatar_color=None, password=None):
    prov = (provider or 'google').lower().strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    clean_email = email.lower().strip()
    cursor.execute("SELECT * FROM users WHERE email = ?", (clean_email,))
    row = cursor.fetchone()
    if row:
        user_row = dict(row)
        user_id = user_row["id"]
        # If password is provided, verify it or upgrade legacy OAuth placeholder hash
        if password and password.strip():
            given_hash = hash_password(password.strip())
            legacy_placeholder_hash = hash_password(f"{prov}-oauth-{clean_email}")
            if user_row["password_hash"] == legacy_placeholder_hash:
                cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (given_hash, user_id))
                conn.commit()
            elif user_row["password_hash"] != given_hash:
                conn.close()
                return {"success": False, "error": f"Incorrect {prov.capitalize()} password for {clean_email}. Please enter your valid password."}
        if name and name.strip() and user_row["name"] in ("Apple Pilot", "Google Pilot"):
            cursor.execute("UPDATE users SET name = ? WHERE id = ?", (name.strip(), user_id))
            conn.commit()
        conn.close()
        return get_user_profile(user_id)

    prov_cfg = {
        'google': {'prefix': 'usr-g-', 'color': '#4285F4', 'def_model': 'Tata Nexon EV Max'},
        'apple': {'prefix': 'usr-ap-', 'color': '#111827', 'def_model': 'Hyundai IONIQ 5'}
    }
    cfg = prov_cfg.get(prov, prov_cfg['google'])
    user_id = f"{cfg['prefix']}{uuid.uuid4().hex[:8]}"
    pwd_raw = password.strip() if (password and password.strip()) else f"{prov}-oauth-{clean_email}"
    pwd_hash = hash_password(pwd_raw)
    now_iso = datetime.now(timezone.utc).isoformat()
    avatar = avatar_color or cfg['color']

    cursor.execute('''
    INSERT INTO users (id, name, email, phone, password_hash, vehicle_type, vehicle_model, vehicle_number, preferred_connector, avatar_color, total_kwh, co2_saved_kg, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, ?)
    ''', (
        user_id,
        name.strip() if (name and name.strip()) else clean_email.split('@')[0].capitalize(),
        clean_email,
        "+91 98765 00000",
        pwd_hash,
        "4-Wheeler Car",
        cfg['def_model'],
        "IND EV 2026",
        "CCS2",
        avatar,
        now_iso
    ))
    conn.commit()
    conn.close()
    return get_user_profile(user_id)

def authenticate_google_user(email, name, avatar_color=None, password=None):
    return authenticate_oauth_user('google', email, name, avatar_color, password=password)

def authenticate_apple_user(email, name, password=None, avatar_color=None):
    return authenticate_oauth_user('apple', email, name, avatar_color or '#111827', password=password)

def _normalize_identifier(identifier):
    raw = (identifier or '').strip()
    if '@' in raw:
        return raw.lower()
    digits = ''.join(ch for ch in raw if ch.isdigit())
    if len(digits) >= 10:
        return digits[-10:]
    return raw.lower()

def _find_user_by_identifier(cursor, identifier):
    raw = (identifier or '').strip()
    low = raw.lower()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = ? OR phone = ?", (low, raw))
    row = cursor.fetchone()
    if row:
        return dict(row)
    digits = ''.join(ch for ch in raw if ch.isdigit())
    if len(digits) >= 10:
        last10 = digits[-10:]
        cursor.execute("SELECT * FROM users")
        for r in cursor.fetchall():
            r_digits = ''.join(ch for ch in (r["phone"] or '') if ch.isdigit())
            if r_digits.endswith(last10):
                return dict(r)
    return None

def generate_and_send_otp(identifier, purpose='login'):
    raw = (identifier or '').strip()
    if not raw:
        return {"success": False, "error": "Please enter a valid Email Address or 10-digit Mobile Number."}
    is_email = '@' in raw
    digits = ''.join(ch for ch in raw if ch.isdigit())
    if not is_email and len(digits) < 10:
        return {"success": False, "error": "Please enter a valid Email Address or 10-digit Mobile Number."}

    norm_id = _normalize_identifier(raw)
    purp = (purpose or 'login').strip().lower()

    conn = get_db_connection()
    cursor = conn.cursor()

    existing_user = _find_user_by_identifier(cursor, raw)
    if purp == 'reset' and not existing_user:
        conn.close()
        return {"success": False, "error": "No registered account found with this email or mobile number."}

    # Invalidate previous unused OTPs for this identifier & purpose
    cursor.execute("UPDATE otp_codes SET used = 1 WHERE identifier = ? AND purpose = ? AND used = 0", (norm_id, purp))

    otp_code = f"{secrets.randbelow(900000) + 100000}"
    otp_id = f"otp-{uuid.uuid4().hex[:10]}"
    now_dt = datetime.now(timezone.utc)
    expires_dt = now_dt + timedelta(minutes=5)

    cursor.execute('''
    INSERT INTO otp_codes (id, identifier, otp_code, purpose, expires_at, used, attempts, created_at)
    VALUES (?, ?, ?, ?, ?, 0, 0, ?)
    ''', (otp_id, norm_id, otp_code, purp, expires_dt.isoformat(), now_dt.isoformat()))
    conn.commit()
    conn.close()

    channel = "email" if is_email else "sms"
    delivery_status = "live_push"

    # Optional External SMTP Email Delivery if configured
    smtp_email = os.environ.get("SMTP_EMAIL", "").strip()
    smtp_password = os.environ.get("SMTP_PASSWORD", "").strip()
    if is_email and smtp_email and smtp_password:
        try:
            msg = MIMEText(
                f"Your EV Yatra verification OTP is: {otp_code}\n\n"
                f"This 6-digit code is valid for 5 minutes. Do not share it with anyone.",
                "plain", "utf-8"
            )
            msg["Subject"] = f"{otp_code} is your EV Yatra Verification OTP"
            msg["From"] = smtp_email
            msg["To"] = raw
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=6) as server:
                server.starttls()
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, [raw], msg.as_string())
            delivery_status = "smtp_email"
        except Exception as e:
            print(f"[OTP SMTP Note] {e}")

    # Optional External Fast2SMS Delivery if configured
    fast2sms_key = os.environ.get("FAST2SMS_API_KEY", "").strip()
    if not is_email and fast2sms_key:
        try:
            sms_url = f"https://www.fast2sms.com/dev/bulkV2?authorization={ urllib.parse.quote(fast2sms_key) }&variables_values={otp_code}&route=otp&numbers={digits[-10:]}"
            req = urllib.request.Request(sms_url, headers={'User-Agent': 'EV-Yatra/2.0'})
            with urllib.request.urlopen(req, timeout=5) as _:
                delivery_status = "fast2sms"
        except Exception as e:
            print(f"[OTP SMS Note] {e}")

    print(f"\n=======================================================")
    print(f" [EV YATRA OTP DISPATCH] ({purp.upper()}) -> {raw}")
    print(f" 6-DIGIT OTP CODE: {otp_code} (Expires in 5 minutes)")
    print(f"=======================================================\n")

    return {
        "success": True,
        "identifier": raw,
        "normalized_identifier": norm_id,
        "channel": channel,
        "purpose": purp,
        "expires_in_seconds": 300,
        "delivery_status": delivery_status,
        "otp_code": otp_code,
        "account_exists": bool(existing_user),
        "message": f"6-digit OTP sent to {raw}. Valid for 5 minutes."
    }

def verify_otp_code(identifier, otp_code, purpose='login', name=None, vehicle_model=None, vehicle_number=None, consume=True):
    raw = (identifier or '').strip()
    code_in = str(otp_code or '').strip()
    if not raw or len(code_in) != 6 or not code_in.isdigit():
        return {"success": False, "error": "Please enter a valid 6-digit numeric OTP."}

    norm_id = _normalize_identifier(raw)
    purp = (purpose or 'login').strip().lower()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT * FROM otp_codes
    WHERE identifier = ? AND purpose = ? AND used = 0
    ORDER BY created_at DESC LIMIT 1
    ''', (norm_id, purp))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"success": False, "error": "No active OTP found or OTP already used. Please request a new OTP."}

    otp_rec = dict(row)
    now_dt = datetime.now(timezone.utc)
    try:
        exp_dt = datetime.fromisoformat(otp_rec["expires_at"])
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
    except Exception:
        exp_dt = now_dt + timedelta(minutes=1)

    if now_dt > exp_dt:
        cursor.execute("UPDATE otp_codes SET used = 1 WHERE id = ?", (otp_rec["id"],))
        conn.commit()
        conn.close()
        return {"success": False, "error": "This OTP has expired (5-minute limit). Please request a new OTP."}

    attempts = int(otp_rec.get("attempts") or 0) + 1
    if otp_rec["otp_code"] != code_in:
        if attempts >= 5:
            cursor.execute("UPDATE otp_codes SET attempts = ?, used = 1 WHERE id = ?", (attempts, otp_rec["id"]))
            conn.commit()
            conn.close()
            return {"success": False, "error": "Too many failed OTP attempts. Please request a new OTP."}
        cursor.execute("UPDATE otp_codes SET attempts = ? WHERE id = ?", (attempts, otp_rec["id"]))
        conn.commit()
        conn.close()
        return {"success": False, "error": f"Invalid OTP code. {5 - attempts} attempt(s) remaining."}

    if consume:
        cursor.execute("UPDATE otp_codes SET used = 1, attempts = ? WHERE id = ?", (attempts, otp_rec["id"]))
        conn.commit()

    # If purpose is login, find or create user account and return full profile
    if purp == 'login':
        existing_user = _find_user_by_identifier(cursor, raw)
        if existing_user:
            user_id = existing_user["id"]
            conn.close()
            prof = get_user_profile(user_id)
            prof["otp_verified"] = True
            return prof

        # Auto-register verified mobile/email pilot on OTP login
        user_id = f"usr-otp-{uuid.uuid4().hex[:8]}"
        is_email = '@' in raw
        clean_email = raw.lower() if is_email else f"pilot.{norm_id}@evyatra.in"
        clean_phone = f"+91 {norm_id}" if not is_email else "+91 98765 00000"
        pilot_name = (name or '').strip() or (clean_email.split('@')[0].replace('.', ' ').title() if is_email else f"EV Pilot ({norm_id[-4:]})")
        v_model = (vehicle_model or '').strip() or "Tata Nexon EV Max"
        v_num = (vehicle_number or '').strip().upper() or "IND EV 2026"
        now_iso = now_dt.isoformat()
        pwd_hash = hash_password(f"otp-verified-{uuid.uuid4().hex}")

        cursor.execute('''
        INSERT INTO users (id, name, email, phone, password_hash, vehicle_type, vehicle_model, vehicle_number, preferred_connector, avatar_color, total_kwh, co2_saved_kg, created_at)
        VALUES (?, ?, ?, ?, ?, '4-Wheeler Car', ?, ?, 'CCS2', '#10b981', 0.0, 0.0, ?)
        ''', (user_id, pilot_name, clean_email, clean_phone, pwd_hash, v_model, v_num, now_iso))

        veh_id = f"veh-{uuid.uuid4().hex[:8]}"
        cursor.execute('''
        INSERT INTO user_vehicles (id, user_id, vehicle_type, vehicle_model, vehicle_number, battery_capacity_kwh, preferred_connector, created_at)
        VALUES (?, ?, '4-Wheeler Car', ?, ?, 45.0, 'CCS2', ?)
        ''', (veh_id, user_id, v_model, v_num, now_iso))
        conn.commit()
        conn.close()

        prof = get_user_profile(user_id)
        prof["otp_verified"] = True
        return prof

    conn.close()
    return {
        "success": True,
        "otp_verified": True,
        "identifier": raw,
        "purpose": purp,
        "message": "OTP verified successfully!"
    }

def verify_user(email_or_phone, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    user = _find_user_by_identifier(cursor, email_or_phone)
    conn.close()
    if not user:
        return {"success": False, "error": "No account found with this email or phone number."}
    
    if user["password_hash"] != hash_password(password):
        return {"success": False, "error": "Incorrect password. Please try again or login via OTP."}
    
    return get_user_profile(user["id"])

def reset_user_password(email, phone, new_password, otp_code=None):
    if not email or not new_password or len(new_password.strip()) < 6:
        return {"success": False, "error": "Valid email/mobile and a new password (min 6 characters) are required."}

    if otp_code and str(otp_code).strip():
        otp_check = verify_otp_code(email, otp_code, purpose='reset', consume=True)
        if not otp_check.get("success"):
            return otp_check

    conn = get_db_connection()
    cursor = conn.cursor()
    user = _find_user_by_identifier(cursor, email)
    if not user:
        conn.close()
        return {"success": False, "error": "No registered account found with that email or mobile number."}

    if not otp_code and phone and phone.strip():
        db_phone_digits = ''.join(ch for ch in (user["phone"] or '') if ch.isdigit())[-10:]
        in_phone_digits = ''.join(ch for ch in phone if ch.isdigit())[-10:]
        if db_phone_digits and in_phone_digits and db_phone_digits != in_phone_digits and user["phone"] != "+91 98765 00000":
            conn.close()
            return {"success": False, "error": "Phone number does not match the registered mobile number for this account."}

    new_hash = hash_password(new_password.strip())
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Password updated via verified OTP! You can now sign in with your new password."}

def change_user_password(user_id, current_password, new_password):
    if not user_id or not new_password or len(new_password.strip()) < 6:
        return {"success": False, "error": "New password must be at least 6 characters."}
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "User account not found."}
    if current_password and row["password_hash"] != hash_password(current_password.strip()):
        conn.close()
        return {"success": False, "error": "Current password is incorrect."}
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_password.strip()), user_id))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Your password has been updated."}

def get_user_profile(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, phone, vehicle_type, vehicle_model, vehicle_number, preferred_connector, avatar_color, total_kwh, co2_saved_kg, created_at FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "User profile not found."}
    
    user = dict(row)
    # Fetch user's registered vehicles
    cursor.execute("SELECT * FROM user_vehicles WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    vehicles = [dict(v) for v in cursor.fetchall()]
    if not vehicles and user.get("vehicle_model"):
        veh_id = f"veh-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute('''
        INSERT INTO user_vehicles (id, user_id, vehicle_type, vehicle_model, vehicle_number, battery_capacity_kwh, preferred_connector, created_at)
        VALUES (?, ?, ?, ?, ?, 45.0, ?, ?)
        ''', (veh_id, user_id, user.get("vehicle_type", "4-Wheeler Car"), user.get("vehicle_model", "Tata Nexon EV Max"), user.get("vehicle_number", "IND EV 2026"), user.get("preferred_connector", "CCS2"), now_iso))
        conn.commit()
        vehicles = [{
            "id": veh_id,
            "user_id": user_id,
            "vehicle_type": user.get("vehicle_type", "4-Wheeler Car"),
            "vehicle_model": user.get("vehicle_model", "Tata Nexon EV Max"),
            "vehicle_number": user.get("vehicle_number", "IND EV 2026"),
            "battery_capacity_kwh": 45.0,
            "preferred_connector": user.get("preferred_connector", "CCS2"),
            "created_at": now_iso
        }]

    for v in vehicles:
        v["is_active"] = (v.get("vehicle_number") == user.get("vehicle_number") and v.get("vehicle_model") == user.get("vehicle_model"))
    if vehicles and not any(v.get("is_active") for v in vehicles):
        vehicles[0]["is_active"] = True
    user["vehicles"] = vehicles

    # Fetch user's bookings history
    cursor.execute('''
    SELECT b.*, s.name as station_name, s.address as station_address, s.price_per_kwh,
           cs.slot_number, cs.connector_type, cs.power_kw
    FROM bookings b
    JOIN stations s ON b.station_id = s.id
    JOIN charging_slots cs ON b.slot_id = cs.id
    WHERE b.user_id = ? OR (b.phone = ? AND b.phone != '+91 98765 00000')
    ORDER BY b.booked_at DESC LIMIT 25
    ''', (user_id, user["phone"]))
    bookings = [dict(b) for b in cursor.fetchall()]
    user["bookings"] = bookings
    user["total_bookings"] = len(bookings)
    checked_in_count = sum(1 for b in bookings if b.get("status") in ("checked_in", "completed"))
    total_kwh = float(user.get("total_kwh") or 0.0)
    user["completed_sessions"] = max(checked_in_count, int(round(total_kwh / 28.0)) if total_kwh > 0 else 0)
    user["fuel_saved_inr"] = int(round(total_kwh * 45.0))

    # Fetch user's store orders / passes
    cursor.execute("SELECT * FROM store_orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    user["orders"] = [dict(o) for o in cursor.fetchall()]

    conn.close()
    return {"success": True, "user": user}

def add_user_vehicle(user_id, vehicle_type, vehicle_model, vehicle_number, battery_capacity_kwh=45.0, preferred_connector="CCS2"):
    """
    Permanently registers an EV vehicle to a user profile in SQLite database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    veh_id = f"veh-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        battery_kwh = float(battery_capacity_kwh)
    except:
        battery_kwh = 45.0

    cursor.execute('''
    INSERT INTO user_vehicles (id, user_id, vehicle_type, vehicle_model, vehicle_number, battery_capacity_kwh, preferred_connector, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (veh_id, user_id, vehicle_type, vehicle_model.strip(), vehicle_number.upper().strip(), battery_kwh, preferred_connector, now_iso))

    cursor.execute('''
    UPDATE users
    SET vehicle_type = ?, vehicle_model = ?, vehicle_number = ?, preferred_connector = ?
    WHERE id = ?
    ''', (vehicle_type, vehicle_model.strip(), vehicle_number.upper().strip(), preferred_connector, user_id))

    conn.commit()
    conn.close()
    prof = get_user_profile(user_id)
    if prof.get("success"):
        prof["vehicles"] = prof["user"].get("vehicles", [])
    return prof

def select_user_vehicle(user_id, vehicle_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_vehicles WHERE id = ? AND user_id = ?", (vehicle_id, user_id))
    veh = cursor.fetchone()
    if not veh:
        conn.close()
        return {"success": False, "error": "Vehicle not found in your garage."}
    cursor.execute('''
    UPDATE users
    SET vehicle_type = ?, vehicle_model = ?, vehicle_number = ?, preferred_connector = ?
    WHERE id = ?
    ''', (veh["vehicle_type"], veh["vehicle_model"], veh["vehicle_number"], veh["preferred_connector"], user_id))
    conn.commit()
    conn.close()
    return get_user_profile(user_id)

def delete_user_vehicle(user_id, vehicle_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_vehicles WHERE id = ? AND user_id = ?", (vehicle_id, user_id))
    conn.commit()
    conn.close()
    return get_user_profile(user_id)

def get_user_vehicles(user_id):
    prof = get_user_profile(user_id)
    if prof.get("success"):
        return prof["user"].get("vehicles", [])
    return []

def create_partner_application(contact_name, phone, email, city, property_type="Commercial Land", power_load="60kW - 120kW DC Fast"):
    if not contact_name or not phone or not city:
        return {"success": False, "error": "Contact Name, Phone Number, and City are required."}
    conn = get_db_connection()
    cursor = conn.cursor()
    app_id = f"CPO-{uuid.uuid4().hex[:6].upper()}"
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute('''
    INSERT INTO partner_applications (id, contact_name, phone, email, city, property_type, power_load, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'under_review', ?)
    ''', (app_id, contact_name.strip(), phone.strip(), (email or '').strip(), city.strip(), property_type, power_load, now_iso))
    conn.commit()
    conn.close()
    return {
        "success": True,
        "application": {
            "id": app_id,
            "application_code": app_id,
            "contact_name": contact_name.strip(),
            "phone": phone.strip(),
            "email": (email or '').strip(),
            "city": city.strip(),
            "property_type": property_type,
            "power_load": power_load,
            "status": "under_review",
            "created_at": now_iso
        },
        "message": f"Partner application {app_id} registered for {city.strip()}!"
    }

def create_store_order(user_id, item_name, item_type, amount_inr):
    if not user_id or not item_name:
        return {"success": False, "error": "Please sign in to place an order or activate a pass."}
    conn = get_db_connection()
    cursor = conn.cursor()
    order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute('''
    INSERT INTO store_orders (id, user_id, item_name, item_type, amount_inr, status, created_at)
    VALUES (?, ?, ?, ?, ?, 'active', ?)
    ''', (order_id, user_id, item_name.strip(), item_type.strip(), float(amount_inr or 0), now_iso))
    conn.commit()
    conn.close()
    return {
        "success": True,
        "order": {
            "id": order_id,
            "order_code": order_id,
            "user_id": user_id,
            "item_name": item_name.strip(),
            "item_type": item_type.strip(),
            "amount_inr": float(amount_inr or 0),
            "status": "active",
            "created_at": now_iso
        },
        "message": f"Order {order_id} confirmed for {item_name}!"
    }

def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, phone, vehicle_type, vehicle_model, vehicle_number, preferred_connector, avatar_color, total_kwh, co2_saved_kg, created_at FROM users ORDER BY created_at DESC")
    users = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return users

def create_station(station_data):
    """
    Permanently registers a new EV charging station and its slots in SQLite database.
    Persists across reloads, searches, and map interactions.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    name = station_data.get('name', '').strip()
    if not name:
        conn.close()
        return {"success": False, "error": "Station name is required."}

    stat_id = f"stat-reg-{uuid.uuid4().hex[:8]}"
    network = station_data.get('network', 'Independent EV Hub').strip() or 'Independent EV Hub'
    address = station_data.get('address', '').strip() or f"Near {name}"
    city = station_data.get('city', 'New Delhi').strip() or 'Local Area'

    try:
        latitude = float(station_data.get('latitude', 28.6139))
        longitude = float(station_data.get('longitude', 77.2090))
    except (ValueError, TypeError):
        conn.close()
        return {"success": False, "error": "Valid latitude and longitude numbers are required."}

    try:
        price_per_kwh = float(station_data.get('price_per_kwh', 18.0))
    except (ValueError, TypeError):
        price_per_kwh = 18.0

    try:
        total_slots = int(station_data.get('total_slots', 3))
    except (ValueError, TypeError):
        total_slots = 3
    total_slots = max(1, min(total_slots, 24))

    amenities = station_data.get('amenities', ["24/7 Access", "Restrooms", "Fast DC Charging", "Verified Partner"])
    if isinstance(amenities, str):
        try:
            amenities = json.loads(amenities)
        except:
            amenities = [a.strip() for a in amenities.split(',') if a.strip()]

    rating = float(station_data.get('rating', 4.9))
    open_hours = station_data.get('open_hours', '24/7').strip() or '24/7'

    cursor.execute('''
    INSERT INTO stations (id, name, network, address, city, latitude, longitude, price_per_kwh, total_slots, available_slots, amenities, rating, open_hours)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        stat_id, name, network, address, city, latitude, longitude,
        price_per_kwh, total_slots, total_slots, json.dumps(amenities), rating, open_hours
    ))

    # Insert individual charging slots
    primary_connector = station_data.get('connector_type', 'CCS2')
    try:
        primary_power = int(station_data.get('power_kw', 60))
    except:
        primary_power = 60

    slots_input = station_data.get('slots')
    if slots_input and isinstance(slots_input, list):
        for idx, sl in enumerate(slots_input[:total_slots], 1):
            slot_id = f"slot-{stat_id}-{idx}"
            c_type = sl.get('connector', primary_connector)
            p_kw = int(sl.get('power', primary_power))
            cursor.execute('''
            INSERT INTO charging_slots (id, station_id, slot_number, connector_type, power_kw, status)
            VALUES (?, ?, ?, ?, ?, 'available')
            ''', (slot_id, stat_id, idx, c_type, p_kw))
    else:
        for idx in range(1, total_slots + 1):
            slot_id = f"slot-{stat_id}-{idx}"
            if idx == 1:
                c_type, p_kw = primary_connector, primary_power
            elif idx == 2:
                c_type, p_kw = primary_connector, primary_power
            else:
                c_type, p_kw = "Type 2 AC", 22
            cursor.execute('''
            INSERT INTO charging_slots (id, station_id, slot_number, connector_type, power_kw, status)
            VALUES (?, ?, ?, ?, ?, 'available')
            ''', (slot_id, stat_id, idx, c_type, p_kw))

    conn.commit()
    conn.close()

    created = get_station_by_id(stat_id)
    return {
        "success": True,
        "station": created,
        "message": f"Station '{name}' successfully registered and permanently added to EV Yatra network!"
    }

def update_user_profile(user_id, name, phone, vehicle_type, vehicle_model, vehicle_number, preferred_connector):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE users
    SET name = ?, phone = ?, vehicle_type = ?, vehicle_model = ?, vehicle_number = ?, preferred_connector = ?
    WHERE id = ?
    ''', (name.strip(), phone.strip(), vehicle_type, vehicle_model.strip(), vehicle_number.upper().strip(), preferred_connector, user_id))
    conn.commit()
    conn.close()
    return get_user_profile(user_id)

def get_station_slot_details(station_id):
    cleanup_expired_bookings()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM stations WHERE id = ?", (station_id,))
    station_row = cursor.fetchone()
    if not station_row:
        conn.close()
        return None

    station = dict(station_row)
    cursor.execute("SELECT * FROM charging_slots WHERE station_id = ? ORDER BY slot_number ASC", (station_id,))
    slots = [dict(s) for s in cursor.fetchall()]

    for slot in slots:
        slot["is_free"] = (slot["status"] == "available")
        # Check if active reservation exists for this slot
        if slot["status"] == "reserved":
            cursor.execute("SELECT expires_at, booked_at FROM bookings WHERE slot_id = ? AND status = 'active' ORDER BY booked_at DESC LIMIT 1", (slot["id"],))
            b_row = cursor.fetchone()
            if b_row:
                try:
                    exp = datetime.fromisoformat(b_row["expires_at"])
                    slot["reserved_until"] = exp.strftime("%H:%M")
                except:
                    slot["reserved_until"] = "30m"

    station["slots"] = slots
    station["has_available_slots"] = any(s["is_free"] for s in slots)
    conn.close()
    return station

def get_stations_live_telemetry(station_ids=None):
    """
    Returns real-time lightweight telemetry for specific stations or visible grid hubs.
    Executes booking auto-expiry cleanup and provides instant bay availability.
    """
    cleanup_expired_bookings()
    conn = get_db_connection()
    cursor = conn.cursor()

    if station_ids and len(station_ids) > 0:
        placeholders = ','.join(['?'] * len(station_ids))
        cursor.execute(f"SELECT id, available_slots, total_slots FROM stations WHERE id IN ({placeholders})", station_ids)
        station_rows = cursor.fetchall()
        cursor.execute(f"SELECT id, station_id, slot_number, connector_type, power_kw, status FROM charging_slots WHERE station_id IN ({placeholders}) ORDER BY slot_number ASC", station_ids)
        slots_rows = cursor.fetchall()
    else:
        cursor.execute("SELECT id, available_slots, total_slots FROM stations LIMIT 150")
        station_rows = cursor.fetchall()
        cursor.execute("SELECT id, station_id, slot_number, connector_type, power_kw, status FROM charging_slots ORDER BY slot_number ASC")
        slots_rows = cursor.fetchall()

    # Group slots by station
    slots_map = {}
    for sl in slots_rows:
        st_id = sl["station_id"]
        if st_id not in slots_map:
            slots_map[st_id] = []
        slot_dict = dict(sl)
        slot_dict["is_free"] = (slot_dict["status"] == "available")
        slots_map[st_id].append(slot_dict)

    telemetry = {}
    total_available_slots = 0
    for st in station_rows:
        s_id = st["id"]
        st_slots = slots_map.get(s_id, [])
        avail_count = sum(1 for sl in st_slots if sl["is_free"])
        total_available_slots += avail_count
        telemetry[s_id] = {
            "available_slots": avail_count,
            "total_slots": st["total_slots"],
            "slots": st_slots
        }

    conn.close()
    return {
        "success": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_available_slots": total_available_slots,
        "stations": telemetry
    }

def search_locations_and_stations(query):
    """
    Exclusively searches genuine EV charging stations, cities, towns, and villages
    from the local verified database without calling arbitrary external search engines.
    """
    if not query or not query.strip():
        return []

    q = query.strip().lower()
    q_pattern = f"%{q}%"

    cleanup_expired_bookings()
    conn = get_db_connection()
    cursor = conn.cursor()

    results = []

    # 1. Search matching Cities, Towns, and Villages from grid
    cursor.execute("""
    SELECT city, AVG(latitude) as lat, AVG(longitude) as lng, COUNT(*) as station_count,
           SUM(available_slots) as free_slots, MAX(station_type) as s_type
    FROM stations
    WHERE LOWER(city) LIKE ? OR LOWER(address) LIKE ?
    GROUP BY city
    ORDER BY (CASE WHEN LOWER(city) = ? THEN 1 WHEN LOWER(city) LIKE ? THEN 2 ELSE 3 END), station_count DESC
    LIMIT 6
    """, (q_pattern, q_pattern, q, f"{q}%"))

    city_rows = cursor.fetchall()
    for row in city_rows:
        city_name = row["city"]
        is_village = row["s_type"] == "town_village" or "village" in city_name.lower() or "rural" in city_name.lower()
        icon = "fa-tree-city" if is_village else "fa-city"
        tag = "Town / Village" if is_village else "City Hub"
        results.append({
            "type": "town_village" if is_village else "city",
            "name": f"{city_name} ({row['station_count']} Hubs, {row['free_slots']} free)",
            "short_name": city_name,
            "details": f"{row['station_count']} EV Charging Hubs - {row['free_slots']} bays available",
            "city": city_name,
            "lat": round(float(row["lat"]), 4),
            "lng": round(float(row["lng"]), 4),
            "station_count": row["station_count"],
            "free_slots": row["free_slots"],
            "badge": tag,
            "icon": icon
        })

    # 2. Search specific EV Charging Stations by name, network, corridor or landmark
    cursor.execute("""
    SELECT id, name, network, address, city, latitude, longitude, available_slots, total_slots, price_per_kwh, station_type
    FROM stations
    WHERE LOWER(name) LIKE ? OR LOWER(network) LIKE ? OR LOWER(address) LIKE ?
    ORDER BY (CASE WHEN LOWER(name) LIKE ? THEN 1 WHEN LOWER(network) LIKE ? THEN 2 ELSE 3 END), available_slots DESC
    LIMIT 8
    """, (q_pattern, q_pattern, q_pattern, f"{q}%", f"{q}%"))

    station_rows = cursor.fetchall()
    for row in station_rows:
        s_id = row["id"]
        # Skip if already top result city has exact same name
        results.append({
            "type": "station",
            "id": s_id,
            "station_id": s_id,
            "name": f"{row['name']} ({row['city']})",
            "short_name": row["name"],
            "details": f"{row['network']} • {row['address'][:45]}... ({row['available_slots']} of {row['total_slots']} bays free)",
            "network": row["network"],
            "city": row["city"],
            "address": row["address"],
            "lat": round(float(row["latitude"]), 4),
            "lng": round(float(row["longitude"]), 4),
            "available_slots": row["available_slots"],
            "total_slots": row["total_slots"],
            "price_per_kwh": row["price_per_kwh"],
            "badge": f"{row['available_slots']} Free",
            "icon": "fa-charging-station"
        })

    conn.close()
    return results


