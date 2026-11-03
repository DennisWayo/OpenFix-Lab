"""Read public GitHub issues and pin a repository revision."""
import base64
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .evidence import utcnow

ISSUE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/issues/([1-9][0-9]*)/?$")


def get(path):
    headers = {"Accept":"application/vnd.github+json","User-Agent":"OpenFix-Lab"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    try:
        with urlopen(Request("https://api.github.com"+path,headers=headers),timeout=20) as response:
            data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError("GitHub response exceeded the size limit")
            return json.loads(data)
    except HTTPError as exc:
        raise RuntimeError(f"GitHub returned HTTP {exc.code}; check repository access and API rate limits") from None
    except (URLError, TimeoutError):
        raise RuntimeError("GitHub could not be reached from this host") from None


def ingest(issue_url, source_paths=None):
    match = ISSUE.fullmatch(issue_url)
    if not match:
        raise ValueError("Use a public GitHub issue URL such as https://github.com/owner/repo/issues/123")
    owner, repo, number = match.groups()
    prefix = f"/repos/{owner}/{repo}"
    issue = get(prefix+"/issues/"+number)
    if "pull_request" in issue:
        raise ValueError("This URL identifies a pull request; supply an issue URL")
    commit = get(prefix+"/commits/HEAD")
    query = f"repo:{owner}/{repo} is:pr is:open {number}"
    try:
        search = get("/search/issues?"+urlencode({"q":query,"per_page":20}))
        prs = [{"url":item["html_url"],"title":item["title"]} for item in search.get("items",[])]
        pr_check = {"status":"searched","query":query,"matches":prs,
                    "limitation":"Text search candidates require human review; an empty result does not establish that no repair is underway."}
    except RuntimeError as exc:
        pr_check = {"status":"unavailable","reason":str(exc)}
    files = {}
    for path in (source_paths or [])[:3]:
        if not isinstance(path,str) or not path or path.startswith("/") or ".." in path.split("/") or len(path)>300:
            raise ValueError("Source paths must be relative repository file paths")
        item = get(prefix+"/contents/"+quote(path,safe="/")+"?ref="+commit["sha"])
        if not isinstance(item,dict) or item.get("type")!="file" or item.get("size",0)>150000:
            raise ValueError("Each source context must be a file smaller than 150 KB")
        files[path] = base64.b64decode(item["content"]).decode("utf-8")
    return {"issue_url":issue_url.rstrip("/"),"revision":commit["sha"],"issue_body":issue.get("body") or issue["title"],
            "title":issue["title"],"issue_state":issue["state"],"retrieved_at":utcnow(),
            "related_pull_requests":pr_check,"source_files":files}
