import json
import subprocess
import sys

def get_branches(repo_full_name):
    """Git paranccsal lekéri egy repository összes branch-ét"""
    try:
        # Git ls-remote parancs a branch-ek lekéréséhez
        result = subprocess.run(
            ['git', 'ls-remote', '--heads', f'https://github.com/{repo_full_name}.git'],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode == 0:
            branches = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    # A kimenet formátuma: "commit_hash refs/heads/branch_name"
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        branch_ref = parts[1]
                        branch_name = branch_ref.replace('refs/heads/', '')
                        branches.append(branch_name)
            return branches
        else:
            return [f"Hiba: {result.stderr}"]
    except Exception as e:
        return [f"Kivétel: {str(e)}"]

# JSON fájl beolvasása és feldolgozása
with open('repos_response.json', 'r') as f:
    data = json.load(f)

print("=== REPOSITORY LISTA BRANCH-EKKEL ===")
for repo in data:
    print(f"Repository: {repo['name']}")
    print(f"Full Name: {repo['full_name']}")
    
    # Branch-ek lekérése
    print("Branch-ek:")
    branches = get_branches(repo['full_name'])
    for branch in branches:
        print(f"  - {branch}")
    
    print("=" * 50)