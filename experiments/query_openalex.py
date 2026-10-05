import urllib.request
import json

queries = [
    "DNA cryptography vehicular ad hoc network",
    "dynamic DNA cipher moving target defense VANET",
    "lightweight DNA encryption V2X safety messages"
]

for q in queries:
    print(f"\n==================== Query: {q} ====================")
    url = f"https://api.openalex.org/works?search={urllib.parse.quote(q)}&per-page=5"
    req = urllib.request.Request(url, headers={"User-Agent": "mailto:researcher@antigravity.ai"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            print(f"Total matching works found: {data['meta']['count']}")
            for item in data.get("results", []):
                print(f"- Title: {item.get('display_name')}")
                print(f"  Year: {item.get('publication_year')} | Citations: {item.get('cited_by_count')}")
                print(f"  DOI: {item.get('doi')}")
                authors = [a.get("author", {}).get("display_name", "") for a in item.get("authorships", [])[:3]]
                print(f"  Authors: {', '.join(authors)}")
    except Exception as e:
        print(f"Error executing query {q}: {e}")
