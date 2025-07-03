from math import radians, cos, sin, asin, sqrt

# New York Penn Station location
PENN_LAT = 40.7506
PENN_LON = -73.9935

def haversine(lat1, lon1, lat2, lon2):
    # Earth radius in km
    R = 6371.0

    # Convert degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c  # Distance in km

def is_near_penn_station(lat, lon, threshold_meters=300):
    """Returns True if you're within ~300m of Penn Station."""
    distance_km = haversine(lat, lon, PENN_LAT, PENN_LON)
    return distance_km * 1000 <= threshold_meters