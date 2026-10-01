# Security and malformed-input reporting

This repository contains binary parsers and patchers. They are intended for the verified
`SLPM-65882` game revision and for project-generated test fixtures, not as hardened parsers for
untrusted arbitrary files.

If a malformed archive/PPF/ISO causes an unexpected write outside the requested output, excessive
resource use, or another potentially security-relevant failure, open a GitHub Issue with:

- the tool/command used
- Python and OS version
- the smallest reproducible non-copyrighted fixture if possible
- the exact error/traceback

Do not attach commercial game ISOs or extracted copyrighted assets to public issues.

Hash/revision mismatches are expected safety failures and should not be bypassed in release builds.
