"""Quality bounded context (Phases 15 and 16): tests, coverage and the release.

* ``domain``         — coverage numbers per module and per bounded context, the
                       coverage gate, the release checklist (deliverables per
                       phase and their status) and the release rules (one
                       version, complete documents, phrase scan, changelog,
                       slide deck);
* ``application``    — the release-readiness report built from those parts;
* ``infrastructure`` — ``coverage.json`` (coverage.py), ``config/quality.yaml``,
                       ``config/release-checklist.yaml``, ``config/release.yaml``,
                       the kit's text files and a static test inventory (AST,
                       nothing is imported or run).
"""
