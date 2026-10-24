# WEXP Coverage

**Prepared for submission; posting has not yet been verified.**

This repository contains the selected source and review renderings of
`draft-sergeev-wexp-coverage-00`, *WEXP Coverage: Claims, Evidence, and Evaluation*.
Its intended status is Experimental. The document date is 23 October 2026;
the draft expires on 26 April 2027.

- [Standalone RFCXML source](drafts/coverage/00/draft-sergeev-wexp-coverage-00.xml)
- [Text rendering](drafts/coverage/00/draft-sergeev-wexp-coverage-00.txt)
- [HTML rendering](drafts/coverage/00/draft-sergeev-wexp-coverage-00.html)
- [Exact artifact manifest](manifests/coverage-00.json)

Coverage specifies evaluation and reporting of bounded claims about action
records, delivery, source coverage and supplied-record correspondence. Its
claim outcomes are distinct from WEXP Core verdicts and application decisions.
The planned submission is coordinated with `draft-sergeev-wexp-core-02`;
neither document's bibliography is evidence that the other has been posted.

The XML is the manuscript source. TXT and HTML are fixed review renderings.
The three selected files are preserved exactly; a changed manuscript requires
a new reviewed package and manifest. The IETF archive becomes authoritative
for an officially posted revision. No official archive snapshot is claimed here.

## Local checks

Use CPython 3.12.14 and Node 24.19.0. Install the declared dependencies, then run:

```sh
python -m pip install -r tools/requirements-build.txt
npm ci --prefix tools/node --ignore-scripts --no-audit --no-fund
python scripts/check_draft.py
python scripts/check_draft.py --render --idnits tools/node/node_modules/.bin/idnits --output-dir build/qa
```

The checker verifies the three hashes and byte counts, document metadata,
internal references and text width. Rendering uses xml2rfc 3.34.1 offline in a
temporary directory and compares its outputs to the selected renderings.
It never writes over the selected XML/TXT/HTML. idnits 3.3.0 runs offline in
submission and normal modes; original diagnostics are retained in the report.
The manifest records package versions, not a complete OS or binary-image lock.

CI has read-only repository permissions and no submission operation. Checks
do not establish independent interoperability, deployment conformance or IETF
posting. See the document's Implementation and Validation Status section for
its implementation limits.

Use [the publication procedure](PUBLICATION-PROCESS.md) for submission and
official-file readback. [The license map](LICENSE-MAP.md) distinguishes
document notices, repository tooling and third-party components.
