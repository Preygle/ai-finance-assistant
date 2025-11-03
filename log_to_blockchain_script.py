import requests
import json
import re

# --- CONFIGURATION ---
FLASK_APP_URL = "http://127.0.0.1:5000"
USERNAME = "preygle"
PASSWORD = "password"
# ---------------------

session = requests.Session()


def extract_csrf_token(html_text):
    """Extract CSRF token from an HTML page."""
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html_text)
    if match:
        return match.group(1)
    return None


def login(username, password):
    """Login to the Flask app and preserve session."""
    login_url = f"{FLASK_APP_URL}/login"

    print("Fetching CSRF token from login page...")
    response = session.get(login_url)
    if response.status_code != 200:
        print(f"Failed to fetch login page: {response.status_code}")
        return False

    csrf_token = extract_csrf_token(response.text)
    if not csrf_token:
        print("Could not find CSRF token in login page. Login may fail.")
        return False

    print("CSRF token found.")
    print(f"Attempting to log in as {username}...")

    login_data = {
        "username": username,
        "password": password,
        "csrf_token": csrf_token
    }

    response = session.post(login_url, data=login_data, allow_redirects=True)
    if "Login successful!" in response.text or response.url.endswith("/dashboard"):
        print(f"Successfully logged in as {username}.")
        return True
    else:
        print(f"Login failed. Response code: {response.status_code}")
        print(response.text[:500])
        return False


def get_csrf_token_from_session():
    """Try to find CSRF token after login."""
    # Try from cookies first
    token = session.cookies.get('csrf_token')
    if token:
        return token

    # Fallback: scrape from /transactions or homepage
    try:
        res = session.get(f"{FLASK_APP_URL}/transactions")
        token = extract_csrf_token(res.text)
        if token:
            print("Found CSRF token from /transactions page.")
            return token
    except Exception as e:
        print(f"Error fetching CSRF token from /transactions: {e}")

    return None


def log_transactions_to_blockchain():
    """Send a POST request to /log_to_blockchain with session auth and CSRF token."""
    if not login(USERNAME, PASSWORD):
        print("Cannot proceed: Login failed.")
        return

    print("\n--- SESSION COOKIES ---")
    for cookie in session.cookies:
        print(
            f"Name: {cookie.name} | Value: {cookie.value} | Domain: {cookie.domain}")
    print("-----------------------\n")

    csrf_token = get_csrf_token_from_session()
    if not csrf_token:
        print("Failed to acquire CSRF token after login.")
        return

    headers = {"X-CSRFToken": csrf_token}
    log_url = f"{FLASK_APP_URL}/log_to_blockchain"

    print(f"Sending POST request to {log_url} ...")
    response = session.post(log_url, headers=headers)

    try:
        response.raise_for_status()
        result = response.json()
        print("\n✅ Blockchain logging successful:")
        print(json.dumps(result, indent=2))
    except json.JSONDecodeError:
        print("❌ Failed to decode JSON response:")
        print(response.text[:500])
    except Exception as e:
        print(f"❌ Error while logging to blockchain: {e}")
        print(response.text[:500])


if __name__ == "__main__":
    log_transactions_to_blockchain()
