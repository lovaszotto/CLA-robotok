#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import sys
import os


def _github_headers() -> dict:
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'Robot Framework GitHub Fetcher'
    }
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers

def fetch_github_repos(username):
    """
    Fetch repositories for a GitHub user with proper UTF-8 encoding
    """
    url = f"https://api.github.com/users/{username}/repos"
    
    try:
        headers = _github_headers()

        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 403:
            # Rate limit esetén próbáljunk meg a meglévő fájlra támaszkodni.
            try:
                payload = response.json() or {}
            except Exception:
                payload = {}
            msg = (payload.get('message') or '').lower()
            if 'rate limit' in msg and os.path.exists('repos_response.json'):
                print("HTTP Error: 403 rate limit exceeded. Meglévő repos_response.json használata.")
                print("Tipp: állíts be GITHUB_TOKEN vagy GH_TOKEN env változót a nagyobb limithez.")
                return True

        response.raise_for_status()
        
        # Ensure proper encoding
        response.encoding = 'utf-8'
        
        # Parse JSON
        repos_data = response.json()
        
        # Save with UTF-8 encoding
        with open('repos_response.json', 'w', encoding='utf-8') as f:
            json.dump(repos_data, f, ensure_ascii=False, indent=2)
        
        print(f"Successfully fetched {len(repos_data)} repositories for {username}")
        print("Data saved to repos_response.json with proper UTF-8 encoding")
        
        return True
        
    except requests.RequestException as e:
        print(f"HTTP Error: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python fetch_github_repos.py <username>")
        sys.exit(1)
    
    username = sys.argv[1]
    success = fetch_github_repos(username)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()