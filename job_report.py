import os
import sys
import html
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth


def get_config():
    """Read required API connection settings from environment variables."""
    base_url = os.environ.get("RMJ_URL")
    username = os.environ.get("RMJ_USER")
    password = os.environ.get("RMJ_PASSWORD")

    missing = [k for k, v in {
        "RMJ_URL": base_url,
        "RMJ_USER": username,
        "RMJ_PASSWORD": password,
    }.items() if not v]
    if missing:
        sys.exit(f"Missing required environment variable(s): {', '.join(missing)}")

    return base_url.rstrip("/"), username, password


def fetch_job_definitions(base_url, username, password):
    """Fetch all job definitions from the paginated RunMyJobs API."""
    url = f"{base_url}/scheduler/api/job-definitions"
    auth = HTTPBasicAuth(username, password)
    headers = {"Accept": "application/json"}

    jobs = []
    while url:
        response = requests.get(url, auth=auth, headers=headers, timeout=60)
        response.raise_for_status()
        payload = response.json()

        items = payload.get("items", payload if isinstance(payload, list) else [])
        jobs.extend(items)

        next_link = None
        for link in payload.get("links", []) if isinstance(payload, dict) else []:
            if link.get("rel") == "next":
                next_link = link.get("href")
                break
        url = next_link

    return jobs


def extract_fields(job):
    """Extract the report columns from a single job definition payload."""
    partition = job.get("partition") or job.get("jobPartition") or ""
    name = job.get("name") or job.get("jobName") or ""
    queue = job.get("defaultQueue") or job.get("queue") or ""

    if isinstance(partition, dict):
        partition = partition.get("name", "")
    if isinstance(queue, dict):
        queue = queue.get("name", "")

    return partition, name, queue


def build_html(rows):
    """Build an HTML table report from the collected job rows."""
    body_rows = "\n".join(
        f"    <tr><td>{html.escape(str(p))}</td>"
        f"<td>{html.escape(str(n))}</td>"
        f"<td>{html.escape(str(q))}</td></tr>"
        for p, n, q in rows
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>RunMyJobs Job Definitions Report</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 24px; }}
  h1 {{ color: #1f3a68; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 8px 12px; text-align: left; }}
  th {{ background-color: #1f3a68; color: white; }}
  tr:nth-child(even) {{ background-color: #f4f6fa; }}
</style>
</head>
<body>
  <h1>RunMyJobs Job Definitions Report</h1>
  <p>Total job definitions: {len(rows)}</p>
  <table>
    <thead>
      <tr><th>Job Partition</th><th>Job Name</th><th>Default Queue</th></tr>
    </thead>
    <tbody>
{body_rows}
    </tbody>
  </table>
</body>
</html>
"""


def main():
    """Generate the job definition HTML report and surface operational errors clearly."""
    try:
        base_url, username, password = get_config()
        jobs = fetch_job_definitions(base_url, username, password)
        rows = [extract_fields(job) for job in jobs]

        output_path = Path("output") / "job_report.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(build_html(rows), encoding="utf-8")
    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        sys.exit(f"HTTP error while fetching job definitions (status {status_code}): {exc}")
    except requests.exceptions.RequestException as exc:
        sys.exit(f"Network error while fetching job definitions: {exc}")
    except ValueError as exc:
        sys.exit(f"Received invalid data from the API: {exc}")
    except OSError as exc:
        sys.exit(f"Failed to write the report file: {exc}")

    print(f"Wrote {len(rows)} job definitions to {output_path}")


if __name__ == "__main__":
    main()
