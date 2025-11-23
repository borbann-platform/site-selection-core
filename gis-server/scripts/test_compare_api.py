import requests

API_URL = "http://localhost:8000/api/v1"


def test_compare():
    lat1 = 13.7444
    lon1 = 100.5349
    lat2 = 13.78
    lon2 = 100.5449

    payloads = [
        # Site A
        (
            "POST",
            "/site/analyze",
            {"latitude": lat1, "longitude": lon1, "target_category": "competitor"},
        ),
        (
            "POST",
            "/catchment/isochrone",
            {"latitude": lat1, "longitude": lon1, "minutes": 15, "mode": "walk"},
        ),
        (
            "POST",
            "/site/nearby",
            {
                "latitude": lat1,
                "longitude": lon1,
                "radius_meters": 2000,
                "categories": ["competitor"],
            },
        ),
        (
            "POST",
            "/site/nearby",
            {
                "latitude": lat1,
                "longitude": lon1,
                "radius_meters": 2000,
                "categories": ["mall", "train_station", "university"],
            },
        ),
        # Site B
        (
            "POST",
            "/site/analyze",
            {"latitude": lat2, "longitude": lon2, "target_category": "competitor"},
        ),
        (
            "POST",
            "/catchment/isochrone",
            {"latitude": lat2, "longitude": lon2, "minutes": 15, "mode": "walk"},
        ),
        (
            "POST",
            "/site/nearby",
            {
                "latitude": lat2,
                "longitude": lon2,
                "radius_meters": 2000,
                "categories": ["competitor"],
            },
        ),
        (
            "POST",
            "/site/nearby",
            {
                "latitude": lat2,
                "longitude": lon2,
                "radius_meters": 2000,
                "categories": ["mall", "train_station", "university"],
            },
        ),
    ]

    for method, endpoint, data in payloads:
        url = f"{API_URL}{endpoint}"
        print(f"Testing {method} {endpoint} with {data}")
        try:
            if method == "POST":
                res = requests.post(url, json=data)
            else:
                res = requests.get(url)

            if res.status_code != 200:
                print(f"FAILED: {res.status_code} - {res.text}")
            else:
                print("SUCCESS")
        except Exception as e:
            print(f"ERROR: {e}")


if __name__ == "__main__":
    test_compare()
