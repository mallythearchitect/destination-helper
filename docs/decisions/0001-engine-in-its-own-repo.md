# 1. The engine lives in its own repo (2026-09-27)

**Chose:** a new repo, `mindscape-app`, beside the old `malachis-workspace`.

**Why:** the old repo once went public with bills, customer data and a Google
key in it. The new one is built so that can't happen: the data folder and the
keys file are ignored from the first commit, and a scanner refuses commits
that look like they contain a key. It also lets any single app be released
later without dragging personal data or 35 old pages with it.

**Cost:** two servers for a while (:8765 old, :8770 new). Pages move over one
at a time; the old code is deleted only after the new version has worked for
two weeks (the strangler-fig pattern).
