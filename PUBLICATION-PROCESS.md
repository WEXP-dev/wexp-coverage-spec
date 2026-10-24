# Submission and official snapshots

The selected manuscript and its review renderings are identified by
`manifests/coverage-00.json`. Repository checks verify those declared bytes;
they do not themselves submit a draft or establish posting.

1. Review the exact source, metadata, references, notices, manifest and check
   results. Record the author's decision for the selected package and actions.
   Existing authorization remains sufficient for unchanged files and scope.
2. Follow [the GitHub release submission procedure](publication/GITHUB-SUBMISSION.md).
   After merge and successful checks, explicitly publish the exact revision's
   prerelease to request a single API submission of the saved XML. The tag
   selects source bytes and does not claim IETF posting. Do not rebuild or redate
   at upload time. A bare tag push and ordinary PR/push CI cannot submit.
3. Preserve the pre-attempt artifact and actual response/status. Follow
   Datatracker's author-confirmation step. If the outcome is uncertain, inspect
   the existing submission before any new attempt; never use an automatic retry.
4. After posting, retrieve official XML and TXT, record their hashes and compare
   them with the selected package. Explain server rendering differences.
   Preserve the originally submitted package and official snapshot separately.
5. Update the existing release's status and evidence to identify the verified
   official files. Never move its revision tag or overwrite frozen files.

Manual upload through [Datatracker](https://datatracker.ietf.org/submit/) remains
an alternative for the same saved XML, but must not run in parallel with an
unresolved API attempt.

Coverage -00 and Core -02 are a coordinated pair with separate submission IDs.
Prior posting of Core -02 is not a prerequisite. Record each actual event rather
than inferring one document's outcome from the other.

Only the revision-specific `release: published` workflow can submit. It uses the
documented Datatracker API and a repository adapter that preserves the reviewed
XML bytes. Its token has read-only repository, check and Actions access; no PAT
or Datatracker password is required. Preserve run history and archive attempt
records beyond the 90-day Actions artifact retention. These bounded controls
are not a distributed exactly-once guarantee.

This procedure follows the [WEXP project publication policy](https://github.com/WEXP-dev/wexp-spec/blob/main/PUBLICATION-PROCESS.md)
and [IETF submission guidance](https://authors.ietf.org/submitting-your-internet-draft).
