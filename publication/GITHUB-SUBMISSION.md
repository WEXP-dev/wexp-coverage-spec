# Submit draft-sergeev-wexp-coverage-00 through GitHub

This repository uses the IETF's documented submission API from a GitHub
release workflow. The [IETF author resources](https://authors.ietf.org/collaborative-editing)
recommend the community `i-d-template`, whose [submission procedure](https://github.com/martinthomson/i-d-template/blob/ee7503164995688f720b2cc9e55099e5c74216e5/doc/SUBMITTING.md)
uses tags/releases and GitHub Actions. This repository uses that release/API
process with a small adapter for already reviewed RFCXML: no make target,
xml2rfc invocation, redating or source transformation occurs during submission.
It is not an IETF-maintained GitHub Action or a claim of IETF approval.

## The operator's sequence

1. Review and authorize the exact XML and manifest identified by
   [`submission/coverage-00.json`](submission/coverage-00.json). Preserve
   the author decision and review evidence in appropriate controlled storage.
   Do not copy private review correspondence into a public release.
2. Merge the reviewed source and workflow into `main`. Wait for `check`
   to succeed on that exact main commit. No release is published by PR/push CI.
3. In GitHub Releases, create a **prerelease** with the exact tag
   `draft-sergeev-wexp-coverage-00`, selecting that reviewed main commit. The release body should
   identify the source commit and XML hash and state **submission requested;
   official posting not yet verified**. Publishing this release requests one
   live submission. A bare tag push does not.
4. Inspect the `Submit Coverage -00 to IETF` workflow. Preserve its
   attempt and outcome artifacts and copy them to a durable project archive
   before the 90-day Actions retention limit. Record the actual submission ID
   and status; do not infer posting from a green GitHub job.
5. Follow the author's Datatracker confirmation email. The API always requires
   that author confirmation; no API key, PAT or Datatracker password is used.
   The workflow records up to six status GETs, five seconds apart while the
   submission is validating. A later state must be checked separately.
6. After posting, retrieve official XML/TXT and compare their identities with
   the submitted package. Preserve server-rendering differences explicitly.
   Update the release status and evidence; do not move its tag or overwrite the
   approved XML. A submission tag identifies source selection, not posting.

This draft and `draft-sergeev-wexp-core-02` are one coordinated submission pair, with separate
GitHub runs and separate Datatracker submission IDs. There is no atomic two-draft
API transaction. Record any partial outcome honestly and do not resubmit the
successful half of the pair.

## What is checked and retained

The revision-specific workflow only accepts `release: published` for the exact
canonical repository and tag. GitHub's `published` event also covers a published
prerelease. The adapter checks repository numeric identity, event/ref/revision,
first run attempt, current main commit, latest successful required GitHub checks,
XML and manifest digests, XML metadata and the current document-date window.
The submitter address is the author address declared in the manuscript.

A per-revision concurrency group does not cancel an existing attempt. The
adapter inspects earlier release jobs, including their previous run attempts,
and refuses if an earlier job successfully retained an attempt record or is
unresolved. It writes `attempt.json`, and the workflow uploads that record
**before** the POST. The sender verifies the retained artifact's ID, digest,
run and commit before sending the unchanged XML exactly once.

`result.json` records `NOT_PERFORMED`, `OUTCOME_UNKNOWN`, or a matching
`SUBMISSION_QUEUED` receipt. A timeout or unexpected response never triggers a
POST retry. Known response identifiers, safe status URLs and bounded validation
messages are retained; unknown response fields are not republished. A separate
`status.json` records observed API states. `auth`/`aut-appr` concern confirmation;
even `posted` does not establish official-file byte equality.

The GitHub token has only `contents: read`, `actions: read`, and `checks: read`.
No workflow writes repository files, tags, releases or settings. The
Datatracker POST carries only the public XML and declared submitter email.

## When to stop

Do not use **Re-run jobs**, delete/recreate the release, move the revision tag,
or start a manual upload to retry an uncertain outcome. Inspect the retained
run, any receipt/status URL and actual Datatracker state first. If an earlier
attempt failed before sending, any new attempt still needs an explicit
operator decision based on that evidence.

History inspection and retained artifacts prevent repeats within the observed
GitHub history. They are not a global exactly-once guarantee: deleting runs,
release history or artifacts can remove evidence, and Actions artifacts expire.
Preserve that history and the separate durable archive. No test or CI badge
proves delivery, confirmation-email receipt, IETF posting or standardization.

The manuscript date must remain within Datatracker's current accepted window.
If it is too old, prepare and review a new candidate; do not edit these frozen
bytes inside the submission workflow.

References: [IETF submission guidance](https://authors.ietf.org/submitting-your-internet-draft)
· [Datatracker API](https://datatracker.ietf.org/api/submission)
· [GitHub release events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#release).
