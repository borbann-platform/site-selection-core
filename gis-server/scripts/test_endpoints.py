import os
import sys

# Add the project root to sys.path so we can import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_analyze_site():
    payload = {
        "latitude": 13.7563,
        "longitude": 100.5018,
        "radius_meters": 1000,
        "target_category": "cafe",
    }

    print(f"Testing POST /api/v1/site/analyze with payload: {payload}")

    try:
        response = client.post("/api/v1/site/analyze", json=payload)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Response JSON:")
            print(response.json())
        else:
            print("Error Response:")
            print(response.text)
    except Exception as e:
        print(f"An error occurred: {e}")


def test_root():
    print("Testing GET /")
    try:
        response = client.get("/")
        print(f"Status Code: {response.status_code}")
        print("Response JSON:")
        print(response.json())
    except Exception as e:
        print(f"An error occurred: {e}")


def test_nearby_pois():
    payload = {
        "latitude": 13.7563,
        "longitude": 100.5018,
        "radius_meters": 500,
        "categories": ["cafe", "school"],
    }

    print(f"Testing POST /api/v1/site/nearby with payload: {payload}")

    try:
        response = client.post("/api/v1/site/nearby", json=payload)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Found {len(data['features'])} features.")
            if len(data["features"]) > 0:
                print("First feature properties:", data["features"][0]["properties"])
        else:
            print("Error Response:")
            print(response.text)
    except Exception as e:
        print(f"An error occurred: {e}")


def test_isochrone():
    payload = {"latitude": 13.7563, "longitude": 100.5018, "minutes": 5, "mode": "walk"}

    print(f"Testing POST /api/v1/catchment/isochrone with payload: {payload}")

    try:
        response = client.post("/api/v1/catchment/isochrone", json=payload)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Response JSON (Geometry Type):")
            data = response.json()
            print(data["geometry"]["type"])
        else:
            print("Error Response:")
            print(response.text)
    except Exception as e:
        print(f"An error occurred: {e}")


def test_catchment_analyze():
    payload = {"latitude": 13.7563, "longitude": 100.5018, "minutes": 5, "mode": "walk"}

    print(f"Testing POST /api/v1/catchment/analyze with payload: {payload}")

    try:
        response = client.post("/api/v1/catchment/analyze", json=payload)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Population: {data['population']}")
            print(f"Score: {data['score']}")
        else:
            print("Error Response:")
            print(response.text)
    except Exception as e:
        print(f"An error occurred: {e}")


def test_persistence():
    # 1. Create Project
    project_payload = {"name": "Test Project", "description": "A test project"}
    print(f"Testing POST /api/v1/projects with payload: {project_payload}")
    try:
        response = client.post("/api/v1/projects", json=project_payload)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            project_data = response.json()
            project_id = project_data["id"]
            print(f"Created Project ID: {project_id}")

            # 2. Save Site
            # First get analysis data
            catchment_payload = {
                "latitude": 13.7563,
                "longitude": 100.5018,
                "minutes": 5,
                "mode": "walk",
            }
            analysis_response = client.post(
                "/api/v1/catchment/analyze", json=catchment_payload
            )
            analysis_data = analysis_response.json()

            site_payload = {
                "name": "Test Site 1",
                "location": {"type": "Point", "coordinates": [100.5018, 13.7563]},
                "score": analysis_data["score"],
                "analysis_data": analysis_data,
            }

            print(f"Testing POST /api/v1/projects/{project_id}/sites")
            save_response = client.post(
                f"/api/v1/projects/{project_id}/sites", json=site_payload
            )
            print(f"Status Code: {save_response.status_code}")
            if save_response.status_code == 200:
                print("Site saved successfully.")

                # 3. List Sites
                print(f"Testing GET /api/v1/projects/{project_id}/dashboard")
                list_response = client.get(f"/api/v1/projects/{project_id}/dashboard")
                print(f"Status Code: {list_response.status_code}")
                if list_response.status_code == 200:
                    sites = list_response.json()
                    print(f"Found {len(sites)} saved sites.")
            else:
                print("Error Saving Site:")
                print(save_response.text)
        else:
            print("Error Creating Project:")
            print(response.text)
    except Exception as e:
        print(f"An error occurred: {e}")


def test_cannibalization():
    print("Testing POST /api/v1/analytics/cannibalization")
    payload = {
        "new_site": {"lat": 13.7563, "lon": 100.5018},
        "existing_sites": [
            {"id": "branch_1", "lat": 13.7600, "lon": 100.5100},
            {"id": "branch_2", "lat": 13.7500, "lon": 100.4900},
        ],
        "beta": 2.0,
    }
    response = client.post("/api/v1/analytics/cannibalization", json=payload)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(
            f"New Site Expected Visits: {data['new_site_prediction']['expected_visits']:.2f}"
        )
        print(f"Market Share: {data['new_site_prediction']['market_share']:.2%}")
        for impact in data["existing_sites_impact"]:
            print(
                f"Site {impact['site_id']} Retained Visits: {impact['retained_visits']:.2f}"
            )
    else:
        print("Error:")
        print(response.text)


if __name__ == "__main__":
    test_root()
    test_analyze_site()
    test_nearby_pois()
    test_isochrone()
    test_catchment_analyze()
    test_persistence()
    test_cannibalization()
    test_cannibalization()
