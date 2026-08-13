import httpx

base = "https://fair-assessment-api.onrender.com"

r = httpx.post(
    f"{base}/profiles/import/fip-url",
    params={"profile_name": "SS Import Test"},
    json={"url": f"{base}/profiles/Social%20Sciences%20Profile/export/turtle"}
)
print("Status:", r.status_code)
print("Response:", r.text)