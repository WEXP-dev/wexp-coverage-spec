"""Offline release/submission failure controls; no live HTTP requests."""
from datetime import date, datetime, timezone
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import github_release_submit as release


class FakeGitHub:
    def __init__(self, config, head, run_id):
        self.values = {
            "": {"id": config["repository_id"]},
            "/branches/main": {"commit": {"sha": head}},
            "/actions/artifacts/555": {
                "workflow_run": {"id": run_id, "head_sha": head}, "expired": False,
                "name": f"{config['identity']}-attempt-{run_id}", "size_in_bytes": 1234,
                "digest": "sha256:" + "d" * 64,
            },
        }
        self.runs = []
        self.jobs = []
        self.checks = [{"id": n + 1, "name": name, "status": "completed", "conclusion": "success",
                        "app": {"slug": "github-actions"}, "html_url": "https://github.com/example/check"}
                       for n, name in enumerate(config["required_checks"])]

    def get(self, suffix):
        return self.values[suffix]

    def pages(self, suffix, key):
        if key == "workflow_runs":
            return iter(self.runs)
        if key == "jobs":
            assert "filter=all" in suffix
            return iter(self.jobs)
        if key == "check_runs":
            return iter(self.checks)
        raise AssertionError(suffix)


class GitHubReleaseSubmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        original = next((ROOT / "publication/submission").glob("*.json"))
        self.config = json.loads(original.read_text())
        self.config_path = self.root / "config.json"
        self.config_path.write_bytes(original.read_bytes())
        for kind in ("xml", "manifest"):
            relative = self.config[kind]["path"]
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        self.head = "a" * 40
        self.run_id = 200
        self.env = {
            "GITHUB_EVENT_NAME": "release", "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_REPOSITORY": self.config["repository"],
            "GITHUB_REPOSITORY_ID": str(self.config["repository_id"]),
            "GITHUB_REF": "refs/tags/" + self.config["identity"], "GITHUB_SHA": self.head,
            "GITHUB_RUN_ID": str(self.run_id), "GITHUB_ACTOR": "example-editor",
            "GITHUB_EVENT_PATH": str(self.root / "event.json"),
            "WEXP_DATATRACKER_SUBMIT": "PUBLISH",
            "ATTEMPT_ARTIFACT_ID": "555", "ATTEMPT_ARTIFACT_DIGEST": "d" * 64,
        }
        self.event = {"action": "published", "release": {"id": 12, "draft": False, "prerelease": True,
            "tag_name": self.config["identity"],
            "html_url": "https://github.com/" + self.config["repository"] + "/releases/tag/" + self.config["identity"]}}
        Path(self.env["GITHUB_EVENT_PATH"]).write_text(json.dumps(self.event))
        self.api = FakeGitHub(self.config, self.head, self.run_id)
        self.clock = self.enterContext(mock.patch.object(release, "datetime", wraps=datetime))
        self.clock.now.return_value = datetime(2026, 10, 24, tzinfo=timezone.utc)

    def reserve(self):
        with mock.patch.object(release.subprocess, "check_output", return_value=self.head + "\n"):
            return release.preflight(self.config_path, self.root / "out", self.env, self.api, self.root)

    def send(self, response=None, exception=None):
        if response is None:
            name, rev = self.config["identity"].rsplit("-", 1)
            response = release.transport.SubmissionResponse(201, {"id": 123, "name": name, "rev": rev,
                "status_url": "https://datatracker.ietf.org/api/submission/123/status"})
        with mock.patch.object(release.transport, "submit_request", return_value=response, side_effect=exception) as sender, mock.patch("builtins.print"):
            code = release.submit(self.config_path, self.root / "out/attempt.json", self.root / "out",
                                  self.env, self.root, self.api,
                                  status_getter=lambda url: {"id": "123", "state": "auth", "state_desc": "Awaiting author confirmation"},
                                  status_sleeper=lambda seconds: self.fail("Unexpected status wait"))
            return code, sender.call_count, json.loads((self.root / "out/result.json").read_text())

    def test_preflight_uses_no_datatracker_transport(self):
        with mock.patch.object(release.transport, "submit_request", side_effect=AssertionError("must not send")):
            record = self.reserve()
        self.assertEqual(record["state"], "ATTEMPT_RESERVED")
        self.assertIsNone(record["network_submission_performed"])

    def test_reject_wrong_event_repository_revision_and_rerun(self):
        for key, value in [("GITHUB_EVENT_NAME", "push"), ("GITHUB_REPOSITORY_ID", "1"),
                           ("GITHUB_RUN_ATTEMPT", "2"), ("GITHUB_REF", "refs/heads/main")]:
            with self.subTest(key=key):
                wrong = dict(self.env, **{key: value})
                with self.assertRaises(ValueError):
                    release.validate_event(self.config, self.event, wrong)
        wrong = copy.deepcopy(self.event)
        wrong["release"]["tag_name"] += "-other"
        with self.assertRaises(ValueError):
            release.validate_event(self.config, wrong, self.env)

    def test_mutated_xml_and_expired_date_refused(self):
        with self.assertRaisesRegex(ValueError, "date"):
            release.validate_files(self.config, self.root, date(2026, 10, 27))
        path = self.root / self.config["xml"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "digest"):
            release.validate_files(self.config, self.root, date(2026, 10, 24))

    def test_wrong_submitter_refused(self):
        wrong = dict(self.config, submitter="other@example.org")
        with self.assertRaisesRegex(ValueError, "authors"):
            release.validate_files(wrong, self.root, date(2026, 10, 24))

    def test_later_failed_check_overrides_earlier_success(self):
        self.api.checks.append({**self.api.checks[0], "id": 999, "conclusion": "failure"})
        with self.assertRaisesRegex(ValueError, "latest required"):
            self.reserve()

    def test_main_move_refused(self):
        self.api.values["/branches/main"]["commit"]["sha"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "main commit"):
            self.reserve()

    def test_prior_original_attempt_blocks_even_if_later_rerun_failed(self):
        self.api.runs = [{"id": 100, "run_attempt": 2}]
        self.api.jobs = [
            {"name": self.config["job_name"], "status": "completed", "steps": [
                {"name": release.RESERVATION_STEP, "conclusion": "success"}]},
            {"name": self.config["job_name"], "status": "completed", "steps": []},
        ]
        with self.assertRaisesRegex(ValueError, "prior run"):
            self.reserve()

    def test_prior_unresolved_job_refused(self):
        self.api.runs = [{"id": 100}]
        self.api.jobs = [{"name": self.config["job_name"], "status": "in_progress", "steps": []}]
        with self.assertRaisesRegex(ValueError, "unresolved"):
            self.reserve()

    def test_wrong_release_skipped_job_does_not_claim_an_attempt(self):
        self.api.runs = [{"id": 100}]
        self.api.jobs = [{"name": self.config["job_name"], "status": "completed", "conclusion": "skipped", "steps": []}]
        self.reserve()

    def test_existing_reservation_is_never_overwritten(self):
        self.reserve()
        with self.assertRaises(FileExistsError):
            self.reserve()

    def test_retained_artifact_required_before_any_post(self):
        self.reserve()
        self.env.pop("ATTEMPT_ARTIFACT_ID")
        with mock.patch.object(release.transport, "submit_request") as sender:
            with self.assertRaisesRegex(ValueError, "retained"):
                release.submit(self.config_path, self.root / "out/attempt.json", self.root / "out",
                               self.env, self.root, self.api)
            sender.assert_not_called()

    def test_artifact_digest_or_run_mismatch_blocks_post(self):
        self.reserve()
        self.api.values["/actions/artifacts/555"]["digest"] = "sha256:" + "e" * 64
        with self.assertRaisesRegex(ValueError, "Retained attempt"):
            self.send()

    def test_changed_xml_after_reservation_blocks_post(self):
        self.reserve()
        path = self.root / self.config["xml"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "digest"):
            self.send()

    def test_one_post_matching_response_is_queued_not_posted(self):
        self.reserve()
        code, count, result = self.send()
        self.assertEqual((code, count, result["result"]), (0, 1, "SUBMISSION_QUEUED"))
        self.assertFalse(result["publication_verified"])
        self.assertEqual(result["xml_sha256"], self.config["xml"]["sha256"])

    def test_timeout_is_unknown_without_retry(self):
        self.reserve()
        code, count, result = self.send(exception=TimeoutError())
        self.assertEqual((code, count, result["result"]), (1, 1, "OUTCOME_UNKNOWN"))
        self.assertIsNone(result["network_submission_performed"])

    def test_wrong_identity_response_is_not_accepted(self):
        self.reserve()
        response = release.transport.SubmissionResponse(201, {"id": 123, "name": "draft-other", "rev": "00",
            "status_url": "https://datatracker.ietf.org/api/submission/123/status"})
        self.assertEqual(self.send(response=response)[2]["result"], "OUTCOME_UNKNOWN")

    def test_unknown_response_fields_not_republished(self):
        result = release.public_response(release.transport.SubmissionResponse(201, {"id": 1, "confirmation_secret": "do-not-publish"}))
        self.assertNotIn("do-not-publish", json.dumps(result))
        self.assertIn("confirmation_secret", result["unretained_response_fields"])

    def test_response_link_with_future_access_token_is_not_republished(self):
        result = release.public_response(release.transport.SubmissionResponse(201,
            {"submission_url": "https://datatracker.ietf.org/submit/status/123/?access_token=private"}))
        self.assertNotIn("private", json.dumps(result))
        self.assertIn("submission_url", result["unretained_response_fields"])

    def test_documented_error_messages_are_retained_with_bounds(self):
        result = release.public_response(release.transport.SubmissionResponse(400,
            {"error": "Validation failed", "messages": ["Bad document date"]}))
        self.assertEqual(result["messages"], ["Bad document date"])
        self.assertNotIn("messages", result["unretained_response_fields"])

    def test_status_poll_is_bounded_and_stops_at_author_confirmation(self):
        getter = mock.Mock(side_effect=[
            {"id": "123", "state": "validating", "state_desc": "Validating"},
            {"id": "123", "state": "auth", "state_desc": "Waiting for confirmation"}])
        sleeper = mock.Mock()
        result = release.observe_status({"id": 123, "status_url": "https://datatracker.ietf.org/api/submission/123/status"}, getter, sleeper)
        self.assertEqual(len(result["observations"]), 2)
        self.assertEqual(result["observations"][-1]["state"], "auth")
        sleeper.assert_called_once_with(5)
        self.assertFalse(result["publication_verified"])

    def test_status_read_failure_is_recorded_without_retry(self):
        getter = mock.Mock(side_effect=TimeoutError())
        result = release.observe_status({"id": 123, "status_url": "https://datatracker.ietf.org/api/submission/123/status"}, getter, mock.Mock())
        self.assertEqual(getter.call_count, 1)
        self.assertEqual(result["observations"][0]["state"], "UNKNOWN")

    def test_live_workflow_retains_attempt_before_send_and_has_no_push_trigger(self):
        text = (ROOT / ".github/workflows" / self.config["workflow_file"]).read_text()
        self.assertLess(text.index("name: Retain attempt before submission"), text.index("name: Submit the exact existing XML once"))
        self.assertNotIn("  push:", text)
        self.assertNotIn("  pull_request:", text)
        self.assertIn("types: [published]", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertNotIn("contents: write", text)


if __name__ == "__main__":
    unittest.main()
