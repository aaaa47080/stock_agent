
import os
import sys
import time
import requests
import subprocess
import signal

def run_test():
    # Start API server on port 8112
    print("Starting API server on port 8112...")
    env = os.environ.copy()
    env["PORT"] = "8112"
    
    # Using python to run uvicorn programmatically or via command
    # We'll use subprocess to run uvicorn
    cmd = [sys.executable, "-m", "uvicorn", "api_server:app", "--host", "127.0.0.1", "--port", "8112"]
    
    # Start server
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    try:
        # Wait for server startup
        print("Waiting for server to start...")
        time.sleep(10) # Give it 10 seconds to initialize DB and everything
        
        # Test endpoint
        url = "http://127.0.0.1:8112/api/forum/me/payments?user_id=test-user-001"
        print(f"Testing URL: {url}")
        
        try:
            # We need a valid token normally, but if TEST_MODE is on, maybe we can bypass?
            # Or use test-user-001 as token if TEST_MODE logic allows
            headers = {"Authorization": "Bearer test-user-001"}
            response = requests.get(url, headers=headers)
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Body: {response.text}")
            
            if response.status_code == 500:
                print("❌ Reproduced 500 Internal Server Error")
            elif response.status_code == 200:
                print("✅ Request successful")
            else:
                print(f"⚠️ Unexpected status: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
            
    finally:
        # Kill server
        print("Stopping server...")
        proc.terminate()
        try:
            outs, errs = proc.communicate(timeout=5)
            print("--- Server Output ---")
            print(outs.decode('utf-8', errors='ignore'))
            print("--- Server Errors ---")
            print(errs.decode('utf-8', errors='ignore'))
        except:
            proc.kill()

if __name__ == "__main__":
    run_test()
