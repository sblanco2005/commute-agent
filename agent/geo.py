from geopy.distance import geodesic

# Define zones
HOME_COORDS = (40.64101, -74.38390)
PENN_COORDS = (40.7506, -73.9935)
OFFICE_COORDS = (40.7581, -73.9700)
NEWARK_COORDS = (40.7347, -74.1641)

def is_near_location(lat, lon, target, threshold_m=10000):
    return geodesic((lat, lon), target).meters <= threshold_m

def get_location_zone(lat, lon):
    if is_near_location(lat, lon, HOME_COORDS):
        
        return "home"
    elif is_near_location(lat, lon, PENN_COORDS) or is_near_location(lat, lon, OFFICE_COORDS):
        return "nyc"
    elif is_near_location(lat, lon, NEWARK_COORDS):
        return "newark"
    return "unknown"