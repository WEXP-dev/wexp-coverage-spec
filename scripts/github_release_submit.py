#!/usr/bin/env python3
"""Submit one reviewed, existing RFCXML file after an explicit GitHub release.

This adapter uses the documented Datatracker API, not a draft build action.
The release workflow retains the reservation before calling ``submit``. There
is no automatic retry; GitHub history/artifact retention bounds replay checks.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import datatracker_submit as transport

RESERVATION_STEP = "Retain attempt before submission"
SUCCESS_KEYS = {"id", "name", "rev", "status_url", "submission_url"}


def require(predicate, message):
    if not predicate:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def validate_event(config, event, env):
    require(env.get("GITHUB_EVENT_NAME") == "release" and event.get("action") == "published",
            "Only an explicitly published release can request submission")
    require(env.get("GITHUB_RUN_ATTEMPT") == "1", "Do not rerun a submission workflow")
    require(env.get("GITHUB_REPOSITORY") == config["repository"], "Wrong repository")
    require(str(env.get("GITHUB_REPOSITORY_ID")) == str(config["repository_id"]), "Wrong repository ID")
    release = event["release"]
    require(type(release.get("id")) is int and release["id"] > 0, "Missing release ID")
    require(release.get("draft") is False, "A draft release cannot request submission")
    require(release.get("tag_name") == config["identity"], "Wrong revision tag")
    require(env.get("GITHUB_REF") == "refs/tags/" + config["identity"], "Wrong event ref")
    require(re.fullmatch(r"[0-9a-f]{40}", env.get("GITHUB_SHA", "")), "A full source commit is required")
    require(re.fullmatch(r"[0-9]+", env.get("GITHUB_RUN_ID", "")), "Missing workflow run ID")
    return release


def validate_files(config, root, today=None):
    root = Path(root).resolve()
    selected = {}
    for key in ("xml", "manifest"):
        item = config[key]
        rel = Path(item["path"])
        require(not rel.is_absolute() and ".." not in rel.parts, "Unsafe input path")
        path = root / rel
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root),
                "Input must be a regular file inside the checkout")
        data = path.read_bytes()
        require(sha256(data) == item["sha256"], f"{key} digest differs from the reviewed configuration")
        if "bytes" in item:
            require(len(data) == item["bytes"], f"{key} length mismatch")
        selected[key] = (path, data)
    xml = selected["xml"][1]
    require(b"<!DOCTYPE" not in xml and b"<!ENTITY" not in xml, "Standalone RFCXML is required")
    document = ET.fromstring(xml)
    require(document.tag == "rfc" and document.get("version") == "3", "RFCXML v3 is required")
    require(document.get("docName") == config["identity"], "XML identity mismatch")
    require(document.get("ipr") == "trust200902", "Unexpected IPR declaration")
    require(document.get("submissionType", "IETF") == "IETF", "Unexpected submission stream")
    addresses = {e.text.strip().casefold() for e in document.findall("./front/author/address/email") if e.text}
    require(config["submitter"].casefold() in addresses, "Submitter is absent from manuscript authors")
    stamp = document.find("./front/date")
    require(stamp is not None, "Document date is missing")
    month = stamp.get("month")
    month_number = int(month) if month and month.isdecimal() else datetime.strptime(month, "%B").month
    document_date = date(int(stamp.get("year")), month_number, int(stamp.get("day")))
    require(abs(((today or datetime.now(timezone.utc).date()) - document_date).days) <= 3,
            "Document date is outside the current Datatracker submission window; prepare a new candidate")
    return selected["xml"][0]


class GitHub:
    """Read-only GitHub metadata queries; no Datatracker access here."""
    def __init__(self, repository, token):
        self.base = "https://api.github.com/repos/" + repository
        self.token = token

    def get(self, suffix):
        request = urllib.request.Request(self.base + suffix, headers={
            "Accept": "application/vnd.github+json", "Authorization": "Bearer " + self.token,
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "wexp-release-preflight/1",
        })
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    def pages(self, suffix, key):
        for page in range(1, 101):
            separator = "&" if "?" in suffix else "?"
            items = self.get(f"{suffix}{separator}per_page=100&page={page}")[key]
            yield from items
            if len(items) < 100:
                return
        raise ValueError("GitHub history exceeds the bounded pagination limit; inspect it manually")


def validate_checks(checks, required):
    latest = {}
    for check in checks:
        if check.get("app", {}).get("slug") != "github-actions":
            continue
        name = check.get("name")
        if name not in latest or check["id"] > latest[name]["id"]:
            latest[name] = check
    for name in required:
        check = latest.get(name, {})
        require(check.get("status") == "completed" and check.get("conclusion") == "success",
                "The latest required check is not successful: " + name)
    return [{"name": name, "id": latest[name]["id"], "url": latest[name].get("html_url")}
            for name in required]


def reject_prior_attempts(api, config, current_run_id):
    runs = api.pages("/actions/workflows/" + config["workflow_file"] + "/runs?event=release", "workflow_runs")
    inspected = []
    for run in runs:
        if int(run["id"]) >= int(current_run_id):
            continue
        # Include all attempts: a failed rerun must not hide its original send.
        jobs = api.pages(f"/actions/runs/{run['id']}/jobs?filter=all", "jobs")
        for job in jobs:
            if job.get("name") != config["job_name"]:
                continue
            for step in job.get("steps", []):
                require(not (step.get("name") == RESERVATION_STEP and step.get("conclusion") == "success"),
                        "A prior run retained an attempt for this revision; inspect its outcome, do not resubmit")
            require(job.get("status") == "completed", "An earlier submission job is unresolved")
        inspected.append(run["id"])
    return inspected


def preflight(config_path, output, env=None, api=None, root=Path(".")):
    env = dict(os.environ if env is None else env)
    config_bytes = Path(config_path).read_bytes()
    config = json.loads(config_bytes)
    event = read_json(env["GITHUB_EVENT_PATH"])
    release = validate_event(config, event, env)
    xml = validate_files(config, root)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    require(head == env["GITHUB_SHA"], "Checkout does not match the release commit")
    api = api or GitHub(config["repository"], env["GH_TOKEN"])
    require(api.get("")["id"] == config["repository_id"], "Remote repository identity changed")
    require(api.get("/branches/main")["commit"]["sha"] == head,
            "Release must select the currently reviewed main commit")
    checks = validate_checks(api.pages(f"/commits/{head}/check-runs", "check_runs"), config["required_checks"])
    prior_runs = reject_prior_attempts(api, config, env["GITHUB_RUN_ID"])
    result = {
        "schema": "wexp-github-submission-attempt-v1", "state": "ATTEMPT_RESERVED",
        "recorded_at": utc_now(), "identity": config["identity"],
        "repository": config["repository"], "repository_id": config["repository_id"],
        "source_commit": head, "release_id": release["id"], "release_url": release["html_url"],
        "release_tag": release["tag_name"], "run_id": int(env["GITHUB_RUN_ID"]), "run_attempt": 1,
        "actor": env.get("GITHUB_ACTOR"), "configuration_sha256": sha256(config_bytes),
        "xml": config["xml"], "submitter": config["submitter"], "replaces": [],
        "successful_checks": checks, "earlier_release_runs_inspected": prior_runs,
        "destination": transport.DATATRACKER_SUBMISSION_URL,
        "network_submission_performed": None, "publication_verified": False,
        "meaning": "Reserved before a possible POST. Read this run's outcome before considering another attempt.",
        "retention": "Actions artifacts: 90 days. Preserve the release, workflow history and a separate durable archive.",
    }
    write_json(Path(output) / "attempt.json", result)
    return result


def accepted_response(response, identity):
    name, revision = identity.rsplit("-", 1)
    body = response.body
    sid = str(body.get("id", ""))
    return bool(response.ok and re.fullmatch(r"[0-9]+", sid) and body.get("name") == name and
                body.get("rev") == revision and
                body.get("status_url") == f"{transport.DATATRACKER_SUBMISSION_URL}/{sid}/status")


def public_response(response):
    """Retain known protocol fields; unknown future fields might be private."""
    data = response.body
    known = {key: data[key] for key in SUCCESS_KEYS if key in data}
    omitted = set(data) - SUCCESS_KEYS - {"error"}
    for key in ("status_url", "submission_url"):
        value = known.get(key)
        if value is None:
            continue
        parsed = urlsplit(value) if isinstance(value, str) else None
        expected = (r"/api/submission/[0-9]+/status" if key == "status_url"
                    else r"/submit/status/[0-9]+/?")
        if not (parsed and parsed.scheme == "https" and parsed.netloc == "datatracker.ietf.org" and
                re.fullmatch(expected, parsed.path) and not parsed.query and not parsed.fragment):
            known.pop(key)
            omitted.add(key)
    if "error" in data and isinstance(data["error"], str):
        known["error"] = data["error"][:1000]
    messages = data.get("messages")
    if isinstance(messages, str):
        known["messages"] = messages[:4000]
        omitted.discard("messages")
    elif isinstance(messages, list) and all(isinstance(value, str) for value in messages):
        known["messages"] = [value[:1000] for value in messages[:20]]
        omitted.discard("messages")
    known["unretained_response_fields"] = sorted(omitted)
    return known


def read_status(url):
    require(re.fullmatch(re.escape(transport.DATATRACKER_SUBMISSION_URL) + r"/[0-9]+/status", url),
            "Unexpected submission status URL")
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    request = urllib.request.Request(url, headers={"User-Agent": "wexp-spec-publication-pipeline/1"})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
        return json.load(response)


def observe_status(response_body, getter=read_status, sleeper=time.sleep):
    """Bounded status GETs; never retries the manuscript POST."""
    observations = []
    for number in range(6):
        observed = {"observed_at": utc_now()}
        try:
            data = getter(response_body["status_url"])
            require(str(data.get("id")) == str(response_body["id"]), "Status ID mismatch")
            require(isinstance(data.get("state"), str) and re.fullmatch(r"[a-z][a-z-]*", data["state"]),
                    "Unexpected status state")
            require(isinstance(data.get("state_desc"), str), "Unexpected status description")
            observed.update(id=str(data["id"]), state=data["state"], state_desc=data["state_desc"][:1000])
        except Exception as exc:
            observed.update(state="UNKNOWN", error_type=type(exc).__name__)
        observations.append(observed)
        if observed["state"] != "validating" or number == 5:
            break
        sleeper(5)
    return {"schema": "wexp-datatracker-status-observations-v1", "status_url": response_body["status_url"],
            "observations": observations, "publication_verified": False,
            "meaning": "API state is observed separately from official XML/TXT byte verification."}


def submit(config_path, attempt_path, output, env=None, root=Path("."), api=None,
           status_getter=read_status, status_sleeper=time.sleep):
    env = dict(os.environ if env is None else env)
    raw_config = Path(config_path).read_bytes()
    config = json.loads(raw_config)
    event = read_json(env["GITHUB_EVENT_PATH"])
    release = validate_event(config, event, env)
    attempt = read_json(attempt_path)
    require(attempt["configuration_sha256"] == sha256(raw_config), "Configuration changed after reservation")
    require(attempt["source_commit"] == env["GITHUB_SHA"] and
            attempt["run_id"] == int(env["GITHUB_RUN_ID"]) and attempt["release_id"] == release["id"],
            "Attempt reservation belongs to another release/run/commit")
    artifact_id = env.get("ATTEMPT_ARTIFACT_ID", "")
    artifact_digest = env.get("ATTEMPT_ARTIFACT_DIGEST", "")
    require(re.fullmatch(r"[0-9]+", artifact_id) and re.fullmatch(r"[0-9a-f]{64}", artifact_digest),
            "The workflow has not retained the pre-submission attempt artifact")
    api = api or GitHub(config["repository"], env["GH_TOKEN"])
    retained = api.get("/actions/artifacts/" + artifact_id)
    require(retained.get("workflow_run", {}).get("id") == attempt["run_id"] and
            retained.get("workflow_run", {}).get("head_sha") == env["GITHUB_SHA"] and
            retained.get("name") == f"{config['identity']}-attempt-{attempt['run_id']}" and
            retained.get("digest") == "sha256:" + artifact_digest and
            retained.get("expired") is False and retained.get("size_in_bytes", 0) > 0,
            "Retained attempt artifact does not identify this workflow run")
    xml = validate_files(config, root)
    request = transport.prepare_request(xml, user=config["submitter"],
        artifact_identity=config["identity"], authorization_id=release["html_url"],
        guard_passed=True, submission_authorized=True)
    result = {"schema": "wexp-github-submission-result-v1", "identity": config["identity"],
              "source_commit": env["GITHUB_SHA"], "run_id": attempt["run_id"], "release_id": release["id"],
              "attempt_sha256": sha256(Path(attempt_path).read_bytes()), "xml_sha256": request.xml_sha256,
              "attempt_artifact_id": int(artifact_id), "attempt_artifact_digest": artifact_digest,
              "recorded_at": utc_now(), "result": "OUTCOME_UNKNOWN", "publication_verified": False,
              "network_submission_performed": None,
              "next_action": "Inspect the result and Datatracker state; do not rerun or recreate the release to retry."}
    # The workflow must have successfully uploaded attempt.json before this call.
    # The existing client makes one POST, has no retry, and refuses redirects.
    try:
        response = transport.submit_request(request, live=True, environment=env)
    except (transport.SubmissionBlocked, transport.SubmissionRequestError) as exc:
        result.update(result="NOT_PERFORMED", network_submission_performed=False, error_type=type(exc).__name__)
    except Exception as exc:
        result["error_type"] = type(exc).__name__
    else:
        queued = accepted_response(response, config["identity"])
        result.update(result="SUBMISSION_QUEUED" if queued else "OUTCOME_UNKNOWN",
                      network_submission_performed=True, http_status=response.status_code,
                      response=public_response(response))
        if queued:
            result["next_action"] = "Follow the author's confirmation email and verify the official archive. Queued is not posted."
    write_json(Path(output) / "result.json", result)
    print(json.dumps(result, indent=2))
    if result["result"] == "SUBMISSION_QUEUED":
        status = observe_status(response.body, status_getter, status_sleeper)
        write_json(Path(output) / "status.json", status)
        print(json.dumps(status, indent=2))
    return 0 if result["result"] == "SUBMISSION_QUEUED" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("preflight", "submit"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--attempt", type=Path)
    args = parser.parse_args()
    if args.operation == "preflight":
        preflight(args.config, args.output)
        print("ATTEMPT_RESERVED — no Datatracker request in preflight")
        return 0
    require(args.attempt is not None, "Submission needs the retained attempt record")
    return submit(args.config, args.attempt, args.output)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, ET.ParseError) as exc:
        print(f"Submission refused: {exc}", file=sys.stderr)
        raise SystemExit(1)
