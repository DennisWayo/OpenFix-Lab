"""Export a self-contained interactive report from a recorded execution."""
import json
from pathlib import Path


def export_report(store, run_id, destination):
    run = store.read(run_id)
    integrity = store.audit(run_id)
    if not integrity["passed"]:
        raise ValueError("Evidence integrity failed; report export is blocked")
    files = {a["name"]:(store.root/run_id/a["name"]).read_text() for a in run["artifacts"] if a["name"].endswith(".patch")}
    payload = json.dumps({"run":run,"integrity":integrity,"files":files},ensure_ascii=False,allow_nan=False).replace("<","\\u003c")
    web = Path(__file__).resolve().parents[1]/"web"
    html = (web/"index.html").read_text()
    html = html.replace('<link rel="stylesheet" href="style.css">','<style>'+(web/"style.css").read_text()+'</style>')
    html = html.replace('<script src="app.js" defer></script>','')
    script = '<script>window.OPENFIX_REPORT='+payload+';</script><script>'+(web/"app.js").read_text()+'</script>'
    html = html.replace('</body>',script+'</body>')
    destination = Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(html)
    return destination
