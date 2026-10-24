# License and provenance map

The specification source and renderings under `drafts/` retain their embedded
IETF notices and the applicable [IETF Trust Legal Provisions](https://trustee.ietf.org/documents/trust-legal-provisions/).
The tooling license does not replace those document notices or the terms for
Code Components in an IETF document. The source declares `trust200902`.

The separately authored repository tooling below uses the BSD-3-Clause terms
in [LICENSE-CODE](LICENSE-CODE):

- `scripts/check_draft.py`
- `scripts/datatracker_submit.py`
- `scripts/github_release_submit.py`
- `tests/test_github_release_submit.py`
- `.github/workflows/draft-ci.yml`
- `.github/workflows/ietf-submit-coverage-00.yml`
- `publication/submission/coverage-00.json`
- `tools/requirements-build.txt`
- `tools/node/package.json`
- root-project metadata in `tools/node/package-lock.json`

`LICENSE-CODE` preserves the public WEXP project's existing copyright and BSD
notice, obtained from [wexp-spec at 86e548782e652254c0a3fe6020b4ecc3659ecca5](https://github.com/WEXP-dev/wexp-spec/blob/86e548782e652254c0a3fe6020b4ecc3659ecca5/LICENSE-CODE).
The check script is newly authored for this standalone package. GitHub Action
commit pins were checked against that same public repository's draft CI.
`scripts/datatracker_submit.py` is copied without changes from that pinned
public WEXP repository, retaining its BSD license. The release adapter,
offline refusal tests and revision-specific workflow are repository tooling.

The lock file records the selected idnits 3.3.0 registry package and transitive
dependency integrities. Dependency records and package installation do not
relicense third-party software. Python/Node packages and GitHub Actions retain
their own licenses. No dependency source or binary is vendored here.

This explicit tooling list does not apply a general license to the manuscript,
manifest, other repository prose or third-party material merely because those
files are stored together. Preserve applicable notices when adding material.
