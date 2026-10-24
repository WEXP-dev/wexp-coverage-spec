# Submission and official snapshots

The selected manuscript and its review renderings are identified by
`manifests/coverage-00.json`. Repository checks verify those declared bytes;
they do not submit a draft or establish posting.

1. Review the exact source, metadata, references, notices, manifest and check
   results. Record the author's decision for the selected package and actions.
   Existing authorization remains sufficient for unchanged files and scope.
2. Verify the selected XML hash, then upload that saved XML through
   [Datatracker](https://datatracker.ietf.org/submit/). Do not rebuild at upload
   time. Follow Datatracker's confirmation steps. If the result is uncertain,
   inspect the existing submission before retrying.
3. Record the actual submission identity and its observed state. A successful
   upload, queued response or bibliography entry is not verified posting.
4. After posting, retrieve the official XML and TXT, record their hashes and
   compare them with the selected package. Explain server rendering differences.
   Preserve the originally submitted package and official snapshot separately.
5. Update the public status and, when authorized, create a GitHub release that
   identifies the public source commit and verified official files. Never
   overwrite an existing revision tag or historical snapshot.

Coverage −00 and Core −02 are planned as a simultaneous pair. Prior posting of
Core −02 is not a prerequisite. Record actual events for each document rather
than inferring one from the other.

Ordinary push/PR checks have no submission authority. This repository contains
no automated submission transport. Any future transport must consume the
already approved bytes and verify an externally pinned manifest digest.

This procedure follows the [WEXP project publication policy](https://github.com/WEXP-dev/wexp-spec/blob/86e548782e652254c0a3fe6020b4ecc3659ecca5/PUBLICATION-PROCESS.md).
See also the [Datatracker instructions](https://datatracker.ietf.org/submit/tool-instructions/).
