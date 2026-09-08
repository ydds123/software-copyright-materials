# Repository Agent Instructions

## Automatic Git synchronization

After completing any adjustment to this skill repository:

1. Run the relevant tests; for cross-cutting changes, run the full test suite.
2. Check `git diff --check` and confirm no credentials, tokens, private keys, task artifacts, or generated temporary files are being committed.
3. Commit all intended repository changes with a concise descriptive message.
4. Push the commit to `origin/main` automatically without waiting for an additional reminder.
5. Verify the local `HEAD` matches `origin/main` and the working tree is clean.

Safety constraints:

- Never force-push.
- If tests fail, secret scanning finds a problem, authentication fails, or the remote rejects the push, stop and report the blocker instead of bypassing it.
- Do not commit software-copyright task outputs or user project files located outside this repository.
