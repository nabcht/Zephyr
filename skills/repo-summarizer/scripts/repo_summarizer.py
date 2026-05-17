import os
import tempfile
import json
import zipfile
from collections import Counter
from urllib.parse import urlparse
import requests

def _download_repo_zip(repo_url: str) -> str:
    """Download the repository as a zip archive and return the path to the extracted folder.

    Supports GitHub HTTPS URLs of the form ``https://github.com/owner/repo``.
    """
    parsed = urlparse(repo_url)
    if parsed.netloc != 'github.com':
        raise ValueError('Only GitHub HTTPS URLs are supported')
    parts = parsed.path.strip('/').split('/')
    if len(parts) < 2:
        raise ValueError('Invalid GitHub repository URL')
    owner, repo = parts[0], parts[1].replace('.git', '')
    zip_url = f'https://github.com/{owner}/{repo}/archive/refs/heads/main.zip'
    resp = requests.get(zip_url, timeout=30)
    resp.raise_for_status()
    tmp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(tmp_dir, 'repo.zip')
    with open(zip_path, 'wb') as f:
        f.write(resp.content)
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(tmp_dir)
    # The zip extracts to a subfolder "repo-main" (or branch name)
    extracted_root = next(os.scandir(tmp_dir)).path
    return extracted_root

def summarize_repo(repo_url: str, depth: int = 1) -> dict:
    """Summarize a GitHub repository.

    Returns total files, a nested file tree, language breakdown by extension,
    and the most recent commit messages (fetched via GitHub API).
    """
    if not isinstance(repo_url, str) or not repo_url:
        raise ValueError('repo_url must be a non‑empty string')
    if depth < 1:
        raise ValueError('depth must be at least 1')

    repo_path = _download_repo_zip(repo_url)

    # Collect file paths
    file_paths = []
    for root, _, files in os.walk(repo_path):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), repo_path)
            file_paths.append(rel)
    total_files = len(file_paths)
    ext_counts = Counter(
        os.path.splitext(p)[1].lower() for p in file_paths if os.path.splitext(p)[1]
    )

    # Get recent commits via GitHub API
    api_url = f'https://api.github.com/repos/{owner}/{repo}/commits?per_page={depth}'
    commits_resp = requests.get(api_url, timeout=30)
    commits_resp.raise_for_status()
    commits_data = commits_resp.json()
    recent_commits = [
        {'sha': c.get('sha'), 'message': c.get('commit', {}).get('message')}
        for c in commits_data
    ]

    # Build simple file tree
    tree: dict = {}
    for path in file_paths:
        parts = path.split(os.sep)
        cur = tree
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = None

    return {
        'total_files': total_files,
        'file_tree': tree,
        'language_breakdown': dict(ext_counts),
        'recent_commits': recent_commits,
    }

if __name__ == '__main__':
    import argparse, pprint
    parser = argparse.ArgumentParser(description='Summarize a GitHub repo')
    parser.add_argument('url', help='GitHub repository HTTPS URL')
    parser.add_argument('--depth', type=int, default=3, help='Number of recent commits')
    args = parser.parse_args()
    result = summarize_repo(args.url, args.depth)
    pprint.pprint(result)
