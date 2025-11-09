#!/usr/bin/env python3
"""
Simple Linear API test to verify connectivity and authentication.
"""

import os
import requests
import json

def test_linear_api():
    """Test basic Linear API connectivity."""
    api_key = os.getenv("LINEAR_API_KEY")

    if not api_key:
        print("❌ LINEAR_API_KEY not set")
        return False

    print(f"✓ API key found: {api_key[:10]}...")

    # Simple query to test connection
    query = """
    {
        viewer {
            id
            name
            email
        }
    }
    """

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"{api_key}"
    }

    try:
        print("\n🔍 Testing Linear API connection...")
        response = requests.post(
            "https://api.linear.app/graphql",
            json={"query": query},
            headers=headers,
            timeout=10
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                print(f"❌ GraphQL Errors: {json.dumps(data['errors'], indent=2)}")
                return False
            else:
                print(f"✓ API Connection Successful!")
                print(f"  User: {data.get('data', {}).get('viewer', {}).get('name')}")
                print(f"  Email: {data.get('data', {}).get('viewer', {}).get('email')}")
                return True
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False

    except requests.exceptions.Timeout:
        print("❌ Request timed out")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

if __name__ == "__main__":
    success = test_linear_api()
    exit(0 if success else 1)
