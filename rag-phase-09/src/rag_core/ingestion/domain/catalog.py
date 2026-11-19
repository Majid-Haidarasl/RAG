"""Static catalog of the 26 ArmanRayan knowledge items (from Phase 1 manifest)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogEntry:
    document_id: str
    title_fa: str
    title_en: str
    owning_node: str
    additional_nodes: tuple[str, ...]
    doc_type: str
    confidentiality: str
    version: str = "1.0"
    version_status: str = "Approved"
    date_jalali: str = "1403-07"
    date_gregorian: str = "2024-10"


# Primary owning node is the most specific unit that holds the document.
# Additional nodes are other layers that officially share ownership.
CATALOG: dict[str, CatalogEntry] = {
    "AR-ORG-001": CatalogEntry(
        "AR-ORG-001",
        "معرفی شرکت، مأموریت، تاریخچه، خدمات و جایگاه لایه‌ها",
        "Company introduction, mission, history, services, and layer map",
        "N-BRD",
        ("N-CEO",),
        "policy_organization",
        "restricted",
    ),
    "AR-ORG-002": CatalogEntry(
        "AR-ORG-002",
        "ساختار سازمانی کامل",
        "Full organizational structure",
        "N-CEO",
        (),
        "policy_organization",
        "internal",
    ),
    "AR-BRD-003": CatalogEntry(
        "AR-BRD-003",
        "آیین‌نامه هیئت‌مدیره",
        "Board of directors bylaws",
        "N-BRD",
        (),
        "governance",
        "restricted",
    ),
    "AR-HR-004": CatalogEntry(
        "AR-HR-004",
        "آیین‌نامه استخدام",
        "Hiring policy",
        "N-ADM-HR",
        ("N-ADM",),
        "hr_policy",
        "restricted",
    ),
    "AR-HR-005": CatalogEntry(
        "AR-HR-005",
        "آیین‌نامه مرخصی و حضور",
        "Leave and attendance policy",
        "N-ADM-HR",
        ("N-ADM",),
        "hr_policy",
        "restricted",
    ),
    "AR-HR-006": CatalogEntry(
        "AR-HR-006",
        "آیین‌نامه جبران خدمات و افزایش حقوق",
        "Compensation and raise policy",
        "N-ADM-HR",
        ("N-ADM",),
        "hr_policy",
        "restricted",
    ),
    "AR-HR-007": CatalogEntry(
        "AR-HR-007",
        "آیین‌نامه استعدادیابی و نگهداشت",
        "Talent acquisition and retention",
        "N-ADM-HR",
        ("N-ADM",),
        "hr_policy",
        "restricted",
    ),
    "AR-FIN-008": CatalogEntry(
        "AR-FIN-008",
        "نمونه گزارش مالی فصلی برای هیئت‌مدیره",
        "Sample quarterly financial report for the board",
        "N-ADM-FIN",
        ("N-BRD", "N-CEO"),
        "financial_report",
        "restricted",
    ),
    "AR-LEG-009": CatalogEntry(
        "AR-LEG-009",
        "رویه واحد حقوقی و قراردادها",
        "Legal unit procedure",
        "N-ADM-LEG",
        ("N-ADM",),
        "legal_procedure",
        "restricted",
    ),
    "AR-FIN-010": CatalogEntry(
        "AR-FIN-010",
        "رویه حسابداری و گردش مالی پروژه",
        "Project accounting and financial workflow",
        "N-ADM-FIN",
        ("N-ADM",),
        "financial_procedure",
        "restricted",
    ),
    "AR-HR-011": CatalogEntry(
        "AR-HR-011",
        "منشور اخلاق حرفه‌ای و مقررات داخلی",
        "Code of professional ethics and internal rules",
        "N-ADM-HR",
        ("N-ADM",),
        "hr_policy",
        "restricted",
    ),
    "AR-HW-012": CatalogEntry(
        "AR-HW-012",
        "دستورالعمل تعمیرات سخت‌افزار",
        "Hardware repair instruction",
        "N-HW-REP",
        ("N-HW",),
        "hardware_procedure",
        "internal",
    ),
    "AR-HW-013": CatalogEntry(
        "AR-HW-013",
        "راهنمای مشاوره خرید سخت‌افزار",
        "Hardware procurement advisory guide",
        "N-HW-ADV",
        ("N-HW",),
        "hardware_procedure",
        "internal",
    ),
    "AR-HW-014": CatalogEntry(
        "AR-HW-014",
        "فرآیند فروش سخت‌افزار",
        "Hardware sales process",
        "N-HW-SAL",
        ("N-HW",),
        "hardware_procedure",
        "internal",
    ),
    "AR-HW-015": CatalogEntry(
        "AR-HW-015",
        "استاندارد اسمبل، تست و تحویل",
        "Assembly, test, and delivery standard",
        "N-HW-ASM",
        ("N-HW",),
        "hardware_procedure",
        "internal",
    ),
    "AR-SW-016": CatalogEntry(
        "AR-SW-016",
        "استانداردهای مهندسی و معماری نرم‌افزار",
        "Software engineering and architecture standards",
        "N-SW",
        (),
        "software_standard",
        "internal",
    ),
    "AR-SW-017": CatalogEntry(
        "AR-SW-017",
        "راهنمای تیم توسعه وب",
        "Web development team guide",
        "N-SW-WEB",
        ("N-SW",),
        "team_guide",
        "internal",
    ),
    "AR-SW-018": CatalogEntry(
        "AR-SW-018",
        "راهنمای تیم توسعه موبایل",
        "Mobile development team guide",
        "N-SW-MOB",
        ("N-SW",),
        "team_guide",
        "internal",
    ),
    "AR-SW-019": CatalogEntry(
        "AR-SW-019",
        "راهنمای تیم نرم‌افزار ویندوز",
        "Windows desktop software team guide",
        "N-SW-WIN",
        ("N-SW",),
        "team_guide",
        "internal",
    ),
    "AR-SW-020": CatalogEntry(
        "AR-SW-020",
        "راهنمای طراحی UI/UX",
        "UI/UX design guide",
        "N-SW-UX",
        ("N-SW",),
        "team_guide",
        "internal",
    ),
    "AR-SW-021": CatalogEntry(
        "AR-SW-021",
        "راهنمای هویت بصری و طراحی لوگو",
        "Visual identity and logo design guide",
        "N-SW-VIS",
        ("N-SW",),
        "team_guide",
        "internal",
    ),
    "AR-SW-022": CatalogEntry(
        "AR-SW-022",
        "توافق سطح خدمات و پشتیبانی نرم‌افزار",
        "Software SLA and support",
        "N-SW-SUP",
        ("N-SW",),
        "service_level",
        "internal",
    ),
    "AR-EXE-023": CatalogEntry(
        "AR-EXE-023",
        "پروفایل مجریان نمونه",
        "Sample executor profiles",
        "N-LIB",
        ("N-HW-REP", "N-SW-WIN"),
        "executor_knowledge",
        "restricted",
    ),
    "AR-ISS-024": CatalogEntry(
        "AR-ISS-024",
        "پرونده مسئله سازمانی آذرپخش",
        "Azarpakhsh organizational issue file",
        "N-LIB",
        (),
        "issue_file",
        "internal",
    ),
    "AR-RFP-025": CatalogEntry(
        "AR-RFP-025",
        "نمونه اعلام نیاز (RFP) و برگه ارزیابی پیشنهاد",
        "Sample RFP and proposal evaluation sheet",
        "N-SW",
        ("N-ADM-LEG",),
        "rfp_evaluation",
        "internal",
    ),
    "AR-TRN-026": CatalogEntry(
        "AR-TRN-026",
        "گزارش انتقال دانش به لایه بالاتر و کارنامه سالانه دانش",
        "Multi-layer knowledge transfer report and annual knowledge scorecard",
        "N-LIB",
        ("N-BRD", "N-CEO", "N-SW", "N-SW-WEB"),
        "knowledge_transfer",
        "internal",
    ),
}

# Eight Persian files that write document IDs with Persian digits (Phase 1 finding D1).
PERSIAN_DIGIT_ID_DOCUMENTS = frozenset(
    {
        "AR-FIN-008",
        "AR-LEG-009",
        "AR-FIN-010",
        "AR-HR-011",
        "AR-HW-012",
        "AR-HW-013",
        "AR-HW-014",
        "AR-HW-015",
    }
)


def lookup(document_id: str) -> CatalogEntry | None:
    return CATALOG.get(document_id)
