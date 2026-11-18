# Sample Corpus — ArmanRayan IT (Phase 1)

Fictional, bilingual knowledge corpus used as the case-study data for the offline hierarchical RAG core. Everything in it is invented; no real company, person or customer data.

## Contents

| Item | Count |
|---|---|
| Persian documents (`fa/`, RTL DOCX) | 26 |
| English documents (`en/`, LTR DOCX) | 26 |
| Manifest (`manifest.md`, Persian) | 1 |
| **Total files** | **53** |

Every document exists in both languages with the same ID, structure and content. Header of every document: knowledge class, owner layer and node, version 1.0, date Mehr 1403 / October 2024, status Approved. Size: about 2,000 words per language version (1,600–3,300), 1–15 tables each.

## Document list

| ID | Title (EN) | Persian file | English file |
|---|---|---|---|
| AR-ORG-001 | Company introduction, mission, history, services, and layer map | `fa/AR-ORG-001-معرفی-شرکت.docx` | `en/AR-ORG-001-company-introduction.docx` |
| AR-ORG-002 | Full organizational structure | `fa/AR-ORG-002-ساختار-سازمانی.docx` | `en/AR-ORG-002-organizational-structure.docx` |
| AR-BRD-003 | Board of directors bylaws | `fa/AR-BRD-003-آیین-نامه-هیئت-مدیره.docx` | `en/AR-BRD-003-board-bylaws.docx` |
| AR-HR-004 | Hiring policy | `fa/AR-HR-004-آیین-نامه-استخدام.docx` | `en/AR-HR-004-hiring-policy.docx` |
| AR-HR-005 | Leave and attendance policy | `fa/AR-HR-005-مرخصی-و-حضور.docx` | `en/AR-HR-005-leave-and-attendance.docx` |
| AR-HR-006 | Compensation and raise policy | `fa/AR-HR-006-جبران-خدمات.docx` | `en/AR-HR-006-compensation-policy.docx` |
| AR-HR-007 | Talent acquisition and retention | `fa/AR-HR-007-استعدادیابی-و-نگهداشت.docx` | `en/AR-HR-007-talent-and-retention.docx` |
| AR-FIN-008 | Sample quarterly financial report for the board | `fa/AR-FIN-008-گزارش-مالی-فصلی.docx` | `en/AR-FIN-008-quarterly-financial-report.docx` |
| AR-LEG-009 | Legal unit procedure | `fa/AR-LEG-009-رویه-حقوقی.docx` | `en/AR-LEG-009-legal-procedure.docx` |
| AR-FIN-010 | Project accounting and financial workflow | `fa/AR-FIN-010-حسابداری-پروژه.docx` | `en/AR-FIN-010-project-accounting.docx` |
| AR-HR-011 | Code of professional ethics and internal rules | `fa/AR-HR-011-منشور-اخلاق-حرفه-ای.docx` | `en/AR-HR-011-code-of-conduct.docx` |
| AR-HW-012 | Hardware repair instruction | `fa/AR-HW-012-دستورالعمل-تعمیرات.docx` | `en/AR-HW-012-hardware-repair.docx` |
| AR-HW-013 | Hardware procurement advisory guide | `fa/AR-HW-013-مشاوره-خرید.docx` | `en/AR-HW-013-procurement-advisory.docx` |
| AR-HW-014 | Hardware sales process | `fa/AR-HW-014-فرآیند-فروش.docx` | `en/AR-HW-014-hardware-sales.docx` |
| AR-HW-015 | Assembly, test, and delivery standard | `fa/AR-HW-015-اسمبل-تست-تحویل.docx` | `en/AR-HW-015-assembly-test-delivery.docx` |
| AR-SW-016 | Software engineering and architecture standards | `fa/AR-SW-016-استاندارد-مهندسی.docx` | `en/AR-SW-016-engineering-standards.docx` |
| AR-SW-017 | Web development team guide | `fa/AR-SW-017-راهنمای-تیم-وب.docx` | `en/AR-SW-017-web-team-guide.docx` |
| AR-SW-018 | Mobile development team guide | `fa/AR-SW-018-راهنمای-تیم-موبایل.docx` | `en/AR-SW-018-mobile-team-guide.docx` |
| AR-SW-019 | Windows desktop software team guide | `fa/AR-SW-019-نرم-افزار-ویندوز.docx` | `en/AR-SW-019-windows-software-guide.docx` |
| AR-SW-020 | UI/UX design guide | `fa/AR-SW-020-راهنمای-UI-UX.docx` | `en/AR-SW-020-uiux-guide.docx` |
| AR-SW-021 | Visual identity and logo design guide | `fa/AR-SW-021-هویت-بصری-و-لوگو.docx` | `en/AR-SW-021-visual-identity.docx` |
| AR-SW-022 | Software SLA and support | `fa/AR-SW-022-SLA-پشتیبانی.docx` | `en/AR-SW-022-software-sla.docx` |
| AR-EXE-023 | Sample executor profiles | `fa/AR-EXE-023-پروفایل-مجریان.docx` | `en/AR-EXE-023-executor-profiles.docx` |
| AR-ISS-024 | Azarpakhsh organizational issue file | `fa/AR-ISS-024-پرونده-مسئله-آذرپخش.docx` | `en/AR-ISS-024-azarpakhsh-issue-file.docx` |
| AR-RFP-025 | Sample RFP and proposal evaluation sheet | `fa/AR-RFP-025-نمونه-RFP-ارزیابی.docx` | `en/AR-RFP-025-rfp-and-evaluation.docx` |
| AR-TRN-026 | Multi-layer knowledge transfer report and annual knowledge scorecard | `fa/AR-TRN-026-انتقال-دانش-و-کارنامه.docx` | `en/AR-TRN-026-knowledge-transfer-report.docx` |

Owner layer/node per document and Persian titles are in `manifest.md` and in `docs/phase-01/domain-discovery.md` section 6.

## ID families

| Prefix | Meaning | IDs |
|---|---|---|
| ORG | Organization | 001, 002 |
| BRD | Board | 003 |
| HR | Human resources | 004–007, 011 |
| FIN | Finance | 008, 010 |
| LEG | Legal | 009 |
| HW | Hardware deputy and teams | 012–015 |
| SW | Software deputy and teams | 016–022 |
| EXE | Executor profiles | 023 |
| ISS | Issue file | 024 |
| RFP | RFP and proposal evaluation | 025 |
| TRN | Knowledge transfer and scorecard | 026 |

Other identifiers used inside the documents: contract `AR-CNT-1402-118`, RFP `AR-RFP-1403-07`, sub-issues `AR-ISS-024/HW`, `/WIN`, `/LEG`, cost centres `CC-*`, team sub-codes `HW-*`/`SW-*`, project code `PRJ-AZP-118`.

## Known data-quality issues (kept on purpose as realistic noise)

1. Eight Persian files (FIN-008, LEG-009, FIN-010, HR-011, HW-012, HW-013, HW-014, HW-015) write document IDs with Persian digits (`AR-FIN-۰۰۸`). Ingestion must normalize digits in IDs.
2. The Windows programmer appears as “Roozbeh Mohseni” and “Rouzbeh Mohseni” in different English files; both refer to the same executor.
3. No DOC or PDF files yet; DOC/PDF variants of a subset will be generated in phase 4.

## Usage rules

- Treat FA/EN files of one ID as a linked pair, not as duplicates.
- Cite by document ID and section heading.
- Do not edit these files; corrections create a new version (spec 7.6).

## Phase 4 note

The 52 official DOCX files are unchanged. Ingestion normalizes Persian-digit IDs (finding D1) in memory. Format samples (DOC, text PDF, one scanned PDF) are in `derived/`.
