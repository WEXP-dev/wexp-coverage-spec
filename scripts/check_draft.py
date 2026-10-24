#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Mikhail Anatolievich Sergeev
"""Check the selected standalone artifacts; never submit or overwrite them."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile

from lxml import etree, html

ROOT = Path(__file__).resolve().parents[1]
STEM = "draft-sergeev-wexp-coverage-00"
PAYLOAD = Path("drafts/coverage/00")
MANIFEST = Path("manifests/coverage-00.json")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check_artifacts(root):
    manifest = json.loads((root / MANIFEST).read_text())
    require(manifest["format"] == "wexp-coverage-artifact-manifest/1", "Manifest format")
    require(manifest["document"] == STEM, "Document identity")
    expected = {str(PAYLOAD / (STEM + suffix)) for suffix in (".xml", ".txt", ".html")}
    require(set(manifest["files"]) == expected, "Exactly three selected artifact paths required")
    require(manifest["canonical_source"] == str(PAYLOAD / (STEM + ".xml")), "Source path")
    require({str(p.relative_to(root)) for p in (root / PAYLOAD).iterdir()} == expected,
            "Unexpected selected-artifact directory entry")
    for name, declared in manifest["files"].items():
        path = root / name
        require(not path.is_symlink() and path.is_file(), "Artifact must be a regular file: " + name)
        require(identity(path) == declared, "Artifact identity mismatch: " + name)
        raw = path.read_text()
        require(all(marker not in raw for marker in
                    ("Private Working Revision", "VALIDATION-RECORD", "/workspace/")),
                "Private preparation marker in " + name)
    source = root / manifest["canonical_source"]
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
    tree = etree.parse(str(source), parser)
    require(not tree.docinfo.doctype, "Standalone XML must not use a DOCTYPE")
    doc = tree.getroot()
    require(doc.tag == "rfc" and doc.get("version") == "3", "RFCXML v3 required")
    require(doc.get("docName") == STEM and doc.get("category") == "exp", "Document metadata")
    require(doc.get("submissionType") == "IETF" and doc.get("ipr") == "trust200902", "Document notices")
    require(not doc.findall('.//{http://www.w3.org/2001/XInclude}include'), "Standalone XML required")
    date = doc.find("./front/date")
    require(date is not None and dict(date.attrib) == {"year": "2026", "month": "October", "day": "23"},
            "Document date")
    require(doc.findtext("./front/title") == manifest["title"], "Document title")
    anchors = [n.get("anchor") for n in doc.iter() if n.get("anchor")]
    require(len(anchors) == len(set(anchors)), "Duplicate XML anchors")
    xrefs = [n.get("target") for n in doc.iter("xref")]
    require(all(target in anchors for target in xrefs), "Unresolved XML reference")
    rendered = html.parse(str(root / PAYLOAD / (STEM + ".html")))
    ids = rendered.xpath("//@id")
    require(len(ids) == len(set(ids)), "Duplicate HTML identifiers")
    fragments = [link[1:] for link in rendered.xpath("//a/@href") if link.startswith("#") and len(link) > 1]
    require(all(fragment in ids for fragment in fragments), "Unresolved HTML fragment")
    width = max(map(len, (root / PAYLOAD / (STEM + ".txt")).read_text().splitlines()))
    require(width <= 72, "Text exceeds 72 columns")
    return manifest, {"artifact_count": 3, "xml_references": len(xrefs),
                      "html_fragments": len(fragments), "maximum_text_columns": width,
                      "files": manifest["files"]}


def check_environment(root, manifest):
    require(platform.python_version() == manifest["build"]["python"], "Selected Python version required")
    packages = {}
    for line in (root / manifest["build"]["requirements"]).read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, expected = line.split("==")
        actual = importlib.metadata.version(name)
        require(actual == expected, "Selected package version differs: " + name)
        packages[name] = actual
    return {"python": platform.python_version(), "platform": platform.platform(), "packages": packages,
            "limit": "Selected package versions, not a complete operating-system or wheel-byte lock."}


def run(argv, report):
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    report["commands"].append({"argv": argv, "exit_code": result.returncode,
                               "stdout": result.stdout, "stderr": result.stderr})
    require(result.returncode == 0, "Command failed: " + argv[0])
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", action="store_true", help="Render into a temporary directory and compare")
    parser.add_argument("--idnits", type=Path, help="Installed idnits 3.3.0 executable")
    parser.add_argument("--output-dir", type=Path, help="Write an original QA report outside the selected artifacts")
    args = parser.parse_args()
    if args.output_dir:
        output = args.output_dir.resolve()
        selected = (ROOT / "drafts").resolve()
        require(output != selected and selected not in output.parents, "Reports must stay outside drafts/")
    report = {"document": STEM, "started_utc": datetime.now(timezone.utc).isoformat(),
              "commands": [], "submission_performed": False}
    try:
        manifest, report["integrity"] = check_artifacts(ROOT)
        if args.render or args.idnits:
            report["environment"] = check_environment(ROOT, manifest)
        if args.render:
            with tempfile.TemporaryDirectory(prefix="coverage-render-") as temporary:
                for kind, suffix in (("text", ".txt"), ("html", ".html")):
                    target = Path(temporary) / (STEM + suffix)
                    run([sys.executable, "-m", "xml2rfc.run", str(ROOT / manifest["canonical_source"]),
                         "--" + kind, "--no-network", "--date", manifest["build"]["render_date"],
                         "--out", str(target)], report)
                    require(identity(target) == manifest["files"][str(PAYLOAD / target.name)],
                            "Re-render differs from selected artifact: " + target.name)
            report["rendered_files_match"] = 2
        if args.idnits:
            executable = str(args.idnits.resolve())
            version = run([executable, "--version"], report).strip()
            require(version == manifest["build"]["idnits"], "Selected idnits version required")
            node_version = run(["node", "--version"], report).strip().removeprefix("v")
            require(node_version == manifest["build"]["node"], "Selected Node version required")
            report["idnits"] = []
            for suffix in (".xml", ".txt"):
                for mode in ("submission", "normal"):
                    output = run([executable, "--offline", "--mode", mode, "--output", "json",
                                  "--fail-on", "errors", str(ROOT / PAYLOAD / (STEM + suffix))], report)
                    result = json.loads(output)
                    require(result["nitsBySeverity"]["error"] == 0, "idnits errors")
                    report["idnits"].append({"format": suffix[1:], "mode": mode,
                                             "counts": result["nitsBySeverity"]})
        check_artifacts(ROOT)
        report["status"] = "PASS_BOUNDED_DOCUMENT_CHECKS"
    except Exception as error:
        report["status"] = "FAIL"
        report["error"] = str(error)
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    report["limits"] = ["No IETF submission or posting is established.",
                        "No independent review or deployment conformance is established."]
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "qa-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
