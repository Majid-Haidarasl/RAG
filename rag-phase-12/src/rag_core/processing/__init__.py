"""Cyclic Node Processing bounded context (Phase 11).

Once per processing cycle (e.g. the quarter closing ``1403-Q2``) every active
node is processed bottom-up — leaves first, the CEO last — and sends one
TransferPackage to its parent. The package itself is built by the Knowledge
Transfer context; this context owns the cycle, the order and the run report.
"""
