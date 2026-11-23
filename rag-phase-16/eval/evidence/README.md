# فهرست شواهد

هر عدد گزارش نهایی (`docs/final-report.md`) از یک فایل نتیجه می‌آید. این فایل‌ها در هر اجرای
`bash scripts/setup_and_test.sh` با برچسب زمان UTC ساخته می‌شوند و در مخزن نگه داشته نمی‌شوند؛ برای دیدن شواهد،
اسکریپت را اجرا کنید و تازه‌ترین فایل هر ردیف را باز کنید. بررسی فاز ۱۶ (`evidence_present`) نگاه می‌کند که برای
هر ردیف دست‌کم یک فایل باشد.

| فاز | الگوی فایل | خط خلاصه | چه عددی از آن می‌آید |
|---|---|---|---|
| ۴ | `results/phase-04/ingest-*.json` | `PHASE 4 INGEST SUMMARY` | تعداد فایل‌ها و نوعشان، تعداد تکه‌ها |
| ۵ | `results/phase-05/dedup-*.json` | `PHASE 5 SUMMARY` | موارد دانش، نسخه‌ها، تکه‌های فعال، تکراری‌ها |
| ۶ | `results/phase-06/hierarchy-*.json` | `PHASE 6 SUMMARY` | گره‌ها و سندهای وصل‌شده |
| ۷ | `results/phase-07/issue-check-*.json` | `PHASE 7 SUMMARY` | ایشوها، زیرایشوها و مقایسه‌ها |
| ۸ | `results/phase-08/rag-demo-*.json` | `PHASE 8 SUMMARY` | hit@5، MRR، واقعیت‌ها و ارجاع‌ها |
| ۹ | `results/phase-09/ike-check-*.json` | `PHASE 9 SUMMARY` | توافق تطبیق مجری، precision و recall |
| ۱۰ | `results/phase-10/judge-check-*.json` | `PHASE 10 SUMMARY` | کالیبراسیون داور قاعده‌ای و داور مدل |
| ۱۱ | `results/phase-11/transfer-check-*.json` | `PHASE 11 SUMMARY` | بسته‌ها، کنترل‌های منفی، پیشنهادهای مدل |
| ۱۲ | `results/phase-12/project-check-*.json` | `PHASE 12 SUMMARY` | ایشوهای کلیدی و آزمون حساسیت |
| ۱۳ | `results/phase-13/rfp-check-*.json` | `PHASE 13 SUMMARY` | امتیاز پیشنهادها و متن‌های مدل |
| ۱۴ | `eval/results/phase-14-check-*.json` | `PHASE 14 SUMMARY` | جست‌وجو، پرامپت پاسخ، داور، شناسه‌ها و انتخاب‌ها |
| ۱۵ | `results/phase-15/quality-check-*.json` | `PHASE 15 SUMMARY` | تست‌ها، پوشش، چک‌لیست و آمادگی |
| ۱۵ | `results/phase-15/coverage.json` | `coverage:` در بلوک فاز ۱۵ | پوشش خط و شاخه هر ماژول |
| ۱۶ | `results/phase-16/release-check-*.json` | `PHASE 16 SUMMARY` | بررسی انتشار و تأیید زندهٔ چهار انتخاب |

کنار بعضی از فایل‌های JSON یک فایل `.md` هم با همان نام هست (مثل `eval/results/updated-metrics-*.md`) که جدول‌ها را
خواناتر نشان می‌دهد. جدول‌های ثابت هر فاز با عددهای اجرای مرجع در `docs/phase-NN/` و `README-phase-NN.md` آمده‌اند.

## اجرای مرجع

| فاز | اجرا (UTC) | کجا ثبت شده |
|---|---|---|
| ۱۲ | 20261123T185733Z | `results/phase-12/project-check-20261123T185733Z.json`، `README-phase-12.md` |
| ۱۵ | 20261123T215647Z | `README-phase-15.md`، `docs/phase-15/unit-test-report.md` |
| ۱۶ | 20261123T224140Z | `results/phase-16/release-check-20261123T224140Z.json`، `README-phase-16.md` |

فایل‌های فاز ۸ به بعد کلیدهای `status` و `checks` دارند؛ با یک نگاه معلوم است اجرا قبول شده یا نه.
