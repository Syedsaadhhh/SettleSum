# SettleSum — three-minute pitch and live demo

Target: about **3 minutes**, leaving room under the **5-minute maximum**. The narration below is roughly 280 words; rehearse once with the actual clicks. If the judging rubric requires more detail, use one or both optional scenes. The rubric itself has not been supplied, so the core covers the problem, product, working demo, technical distinction, accounting proof, and limits.

Live app: **https://settlesum.vercel.app**

## Submission schedule — Pakistan time (PKT, UTC+5)

Hard deadline: **2:00 AM PKT**. Aim to finish submitting by **1:30 AM**, leaving a 30-minute buffer.

| Target | Work |
| --- | --- |
| By 12:15 AM | App release frozen, production verified, script ready |
| 12:15–1:00 AM | Rehearse, record the three-minute demo, trim mistakes, export video |
| 1:00–1:30 AM | Upload video, complete submission fields, verify playable video and public app link, submit |
| 1:30–2:00 AM | Buffer for upload, processing, or form issues; avoid starting new app features |

Do not wait for 1:30 AM to begin uploading. Start as soon as a good export is ready. Keep the app commit stable while recording so labels and results match this script.

## Recording setup

- Record at 1920×1080 or 1440×1000. Keep browser zoom at 100%; zoom the recording crop for the equation and journal instead of shrinking the app.
- Start on the clean welcome screen. Close personal tabs, notifications, and downloads with private information. Keep the cursor still while explaining a number.
- Use the real deployed app. Sample records are synthetic; matches and telemetry are calculated live. Do not replace API output, speed claims, or accounting results in editing.
- Do one rehearsal to confirm the sample still matches 7/8 and the mixed-discount payment flags $164. Timing changes across runs and is not a fixed benchmark claim.
- Keep the custom case values below ready to copy. Shorten typing in the edit if needed, but show the actual submission, response, and changed result. No claims that a draft chargeback has been sent or money collected.

## Core film: say / show / do

| Time | What to say | What to show and do |
| --- | --- | --- |
| **0:00–0:20** | “A business receives one bank payment for several invoices. The amount is short. Is it a bank fee, a valid discount, or money the customer still owes? SettleSum turns that unclear payment into an exact explanation and a balanced accounting entry.” | Start on the welcome screen. Let viewers read **Match payments. Find missing margin.** Point briefly to **Build a live case**, **Import CSV files**, and **Load sample ledger**. No scrolling yet. |
| **0:20–0:40** | “Start with your own data, or explore this clearly labeled synthetic ledger. Every result is calculated by the same engine. Seven of eight payments reconcile. The remaining payment stays in review instead of being forced into a match.” | Click **Load sample ledger**. Show **87.5%** and **$164.00 recoverable margin**. Click **Exceptions** to show the unmatched payment, then return to **All deposits**. |
| **0:40–1:15** | “Here’s the important case. This payment covers three invoices. One early-payment discount is valid. Another was taken after its deadline. SettleSum matches the exact payment and separates the two: the valid discount is an expense, while the expired discount becomes 164 dollars of recoverable receivables. Below it, every debit equals every credit.” | Select **Kestrel Freight & Logistics**. It is usually selected automatically because recovery was found. Show the **$18,412** payment, the invoice-state badges, **$124 valid discount**, and **$164 expired discount**. Scroll to **Accounting journal**. Point to **GL 4910**, **GL 1215**, and equal debit/credit totals. Show **Generate debit memo** as a draft export, not an external posting. |
| **1:15–1:55** | “This also works with a completely new customer. I’ll create a ten-thousand-dollar invoice with two-percent, ten-day terms, and a ninety-eight-hundred-dollar payment. Paid within the window, that discount is valid. Nothing here depends on a sample customer or transaction ID.” | Click **Build a live case**, choose **Start a fresh ledger**, and enter the custom case below. Keep the generated customer/invoice/deposit IDs or edit them. Click **Sum minus 2% Discount**, then **Reconcile this ledger**. Show **Valid discount**, **GL 4910**, and **$0 recoverable margin**. |
| **1:55–2:25** | “Now I’ll change only the clearing date. The arithmetic still matches, but the discount has expired. The system recalculates and moves the same two hundred dollars into chargeback receivables. That’s the difference between matching a number and understanding a payment.” | Click **Try a change**. Change clearing date to **2026-10-22** and click **RE-SOLVE LEDGER**. Show **$200 recoverable margin**, **Expired discount**, and **GL 1215**. Keep the net payment amount visible. |
| **2:25–2:45** | “Add one cent, and there is no exact solution under these rules. SettleSum leaves the payment unapplied. It never invents an allocation to make a demo look successful.” | Open **Try a change** again. Set payment to **9800.01**. Re-solve. Show **No exact reconciliation found** and the absence of a journal for that payment. |
| **2:45–3:05** | “Underneath, an inspectable Python branch-and-bound solver chooses invoice states using integer cents. The app also accepts CSVs and remittance claims, and exports journals and audit evidence. SettleSum makes cash application explainable—and gives finance teams a clear starting point to recover lost margin.” | Open **Solver details** to show actual nodes and measured timing; do not read a fixed millisecond figure. Briefly show **Import data** and its CSV/PDF/text paths, then close it. End on the app and its URL. If you want a successful journal export on screen, return to the sample ledger before opening **Export journal**. |

## Custom case: exact values to enter

This is input data for the demo, not special application logic.

| Field | Value |
| --- | --- |
| Workspace action | Start a fresh ledger |
| Customer name | Horizon Hardware Co |
| Customer ID | Keep the generated ID, or enter a new unique ID |
| Invoice ID | Keep generated ID, or use your own unique reference |
| Invoice date | **2026-10-01** |
| Due date | **2026-10-31** |
| Invoice amount ($) | **10000.00** |
| Discount terms | **2/10 Net 30** |
| Deposit ID | Keep generated ID |
| Clearing date, first run | **2026-10-08** |
| Raw bank memo | Automatically fills with the customer name; keep it |
| Deposit amount | Click **Sum minus 2% Discount** → **9800.00** |
| Remittance note | Leave empty for this scene |
| Clearing date, changed run | **2026-10-22** |
| Amount, failure run | **9800.01** |

Expected results under default rules: early payment → **$200 GL 4910**; late payment → **$200 GL 1215**; extra cent → **unmatched exception**, no fabricated journal. Fresh ledger retains the current fee/discount rules, so load the sample ledger before creating this case or use **New blank ledger** to restore default rules.

## Optional scene A: remittance evidence (+35–45 seconds)

Use if the rubric asks about unstructured documents or AI/offline behavior.

**Say:** “Not every deduction is a discount. This payment includes a damaged-goods claim documented in a remittance note. The parser extracts the invoice and deduction, and the solver books the claim separately for review. Text and text-based PDFs work offline; Gemini extraction is optional.”

**Show:** Load the sample ledger and select **Northstar Precision Manufacturing**. Show the **$340 Short-pay claim**, then **Source details** and the attached remittance text. Scroll to **GL 1220**. To prove new ingestion, use **Import data → PDF / text remittance** and paste a claim referencing an actual invoice ID in your current ledger. Click **Extract remittance references** and review the extracted reference before applying. Do not claim OCR for image-only PDFs.

## Optional scene B: CSV round-trip (+30–40 seconds)

Use if the rubric asks whether custom files really work.

**Say:** “These are real source records, not a fixed demo. I can download them, clear the workspace, and import them again through the same reconciliation pipeline.”

**Show:** With a successful ledger, open **Import data → CSV templates & downloads → Download Current Ledger as CSV**. Extract the ZIP. Click **New blank ledger**, then import `open_invoices.csv` and `bank_deposits.csv` separately. The first file is staged; the second runs reconciliation. Show the restored exact result. For the clearest recording, prepare the extracted files during rehearsal and tell viewers they came from the displayed export.

Core plus both optional scenes is approximately **4:15–4:30**, leaving margin under five minutes. Do not include every optional detail if it makes the screen hard to follow.

## Delivery notes

- Lead with the finance problem and result; explain the algorithm after the viewer has seen it work.
- Pause on **$164**, **$200**, and the unmatched one-cent result. Those are three distinct proofs.
- Say **“recoverable margin identified”**, not “cash recovered.” Debit memos and journals are drafts for controller review.
- Say **“calculated live”**, not “always under five milliseconds.” Show real measured execution time when useful.
- The synthetic benchmark is a labeled source dataset. There is no database, external posting, forced matching, or guaranteed match for arbitrary inputs.
- Recommended final frame: **SettleSum — match payments, explain deductions, identify recoverable margin.**
