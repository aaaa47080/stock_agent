import os
import sys
import requests
import json

def bootstrap_admin():
    print("=== Admin Bootstrap Tool ===")
    print("This tool helps you call the /bootstrap-admin endpoint.")
    
    base_url = input("Enter API Base URL [http://localhost:8080]: ").strip() or "http://localhost:8080"
    user_id = input("Enter User ID to promote: ").strip()
    token = input("Enter Access Token (Bearer): ").strip()
    
    if not user_id or not token:
        print("Error: User ID and Token are required.")
        return

    url = f"{base_url}/api/admin/bootstrap-admin?user_id={user_id}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    print(f"\nSending POST request to {url}...")
    try:
        response = requests.post(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        try:
            print("Response:", json.dumps(response.json(), indent=2, ensure_ascii=False))
        except:
            print("Response Text:", response.text)
            
        if response.status_code == 200:
            print("\nSUCCESS! User promoted to admin.")
        elif response.status_code == 403:
            print("\nFAILED: 403 Forbidden.")
            print("Possible reasons:")
            print("1. ALLOW_ADMIN_BOOTSTRAP is false in .env")
            print("2. Admins already exist, and you are not an admin.")
            print("3. No admins exist, but you are trying to promote someone else (Self-promotion only for first admin).")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    bootstrap_admin()
