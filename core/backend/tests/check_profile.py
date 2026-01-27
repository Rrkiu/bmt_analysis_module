import sqlite3
import json

db_path = "/mnt/b/cd_p/bmt_demo/storage/calibrations.db"
profile_id = "profile_1765956553"

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM calibration_profiles WHERE profile_id = ?", (profile_id,))
row = cursor.fetchone()

if row:
    print(f"Profile ID: {row['profile_id']}")
    print(f"Profile Name: {row['profile_name']}")
    calibration_data = json.loads(row['calibration_data'])
    print("Calibration Data:")
    print(json.dumps(calibration_data, indent=2))
else:
    print(f"Profile {profile_id} not found in {db_path}")

conn.close()
