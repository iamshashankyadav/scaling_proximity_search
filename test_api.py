import unittest
from fastapi.testclient import TestClient
from main import app, load_locations, get_graph, CSV_FILE, DEFAULT_LINK
import numpy as np
import pandas as pd
class TestProximitySearchAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # pehle data load kar rhe
        load_locations(CSV_FILE)
        get_graph(DEFAULT_LINK)
        cls.client = TestClient(app)
        cls.df = pd.read_csv('locations - locations.csv')

    def test_root_and_health(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "online")
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "healthy")

    def test_search_get_with_link_param(self):
        # query with link file
        res = self.client.get("/search/?lat=0.5&long=0.5&cat=pharmacy&rad=0.2&link=link.txt")
        self.assertEqual(res.status_code, 200)
        ids = res.json()
        self.assertIsInstance(ids, list)
        self.assertEqual(len(ids), 10)
        for item in ids:
            self.assertIsInstance(item, int)

    def test_search_get_without_link_param_defaults(self):
        # agar link na bheje to default uthana chahiye
        res = self.client.get("/search/?lat=0.5&long=0.5&cat=pharmacy&rad=0.2")
        self.assertEqual(res.status_code, 200)
        ids = res.json()
        self.assertIsInstance(ids, list)
        self.assertEqual(len(ids), 10)

    def test_search_get_no_trailing_slash(self):
        res = self.client.get("/search?lat=0.5&long=0.5&cat=pharmacy&rad=0.2&link=link.txt")
        self.assertEqual(res.status_code, 200)
        ids = res.json()
        self.assertEqual(len(ids), 10)

    def test_search_post_json(self):
        # json payload testing
        payload = {
            "lat": 0.5,
            "long": 0.5,
            "cat": "bank",
            "rad": 0.2,
            "link": "link.txt"
        }
        res = self.client.post("/search/", json=payload)
        self.assertEqual(res.status_code, 200)
        ids = res.json()
        self.assertEqual(len(ids), 10)

    def test_radius_correctness(self):
        # circular distance verify kr rhe
        qlat, qlon, qcat, qrad = 0.35, 0.65, "hospital", 0.25
        res = self.client.get(f"/search/?lat={qlat}&long={qlon}&cat={qcat}&rad={qrad}&link=link.txt")
        self.assertEqual(res.status_code, 200)
        ids = res.json()
        self.assertEqual(len(ids), 10)

        sub_df = self.df[self.df['Category'].str.lower() == qcat.lower()]
        for loc_id in ids:
            row = sub_df[sub_df['ID'] == loc_id].iloc[0]
            dlat = row['Latitude'] - qlat
            dlon = row['Longitude'] - qlon
            euclidean = np.sqrt(dlat**2 + dlon**2)
            self.assertLessEqual(euclidean, qrad + 1e-9, f"Location {loc_id} exceeds radius {qrad}")
    def test_case_insensitivity(self):
        # case sensitivity check
        res1 = self.client.get("/search/?lat=0.5&long=0.5&cat=Restaurant&rad=0.3&link=link.txt")
        res2 = self.client.get("/search/?lat=0.5&long=0.5&cat=restaurant&rad=0.3&link=link.txt")
        self.assertEqual(res1.json(), res2.json())
    def test_boundary_corners(self):
        # corners query testing
        corners = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)]
        for clat, clon in corners:
            res = self.client.get(f"/search/?lat={clat}&long={clon}&cat=school&rad=0.5&link=link.txt")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(len(res.json()), 10)

    def test_missing_params(self):
        # missing rad pe 400 aana chahiye
        res = self.client.get("/search/?lat=0.5&long=0.5&cat=school")
        self.assertEqual(res.status_code, 400)
        
        # missing cat pe 400 aana chahiye
        res = self.client.get("/search/?lat=0.5&long=0.5&rad=0.2")
        self.assertEqual(res.status_code, 400)

if __name__ == '__main__':
    unittest.main()
