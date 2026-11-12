# SOP-004: Internal Dispute Operations, Representment & PII Controls

**Document ID:** `sop-provisional-credit-and-representment`  
**Version:** `2026.1`  
**Category:** `internal_operations`  
**Effective Date:** 2026-01-15  
**Owner:** Dispute Operations & Information Security

## 1. Small-Dollar Auto-Write-Off vs. Chargeback Pursuit Thresholds

To balance operational cost against network chargeback fees:
- **Transactions under $25.00 USD:** Eligible for **Automated Low-Value Write-Off** without filing a network chargeback, provided the cardholder has **fewer than 3 disputes in the trailing 90 days** and no velocity-abuse flags.
- **Transactions $25.00 USD to $499.99 USD:** Process via standard automated chargeback workflow once mandatory evidence checklist is complete.
- **Transactions $500.00 USD or greater:** Require **Senior Dispute Analyst peer review** before issuing provisional credit on accounts opened less than 90 days, or before filing Pre-Arbitration.

## 2. Merchant Representment & Pre-Arbitration SLA

When a merchant contests a chargeback via **Representment** (Second Presentment):
1. **Analyst Review SLA:** Review incoming merchant representment evidence within **5 business days** of receipt.
2. **Cardholder Rebuttal Window:** If the merchant supplies credible evidence (e.g., signed proof of delivery to billing address, CE 3.0 device match, or recurring subscription terms), notify the cardholder and allow **10 calendar days** for rebuttal evidence before reversing provisional credit (observing Reg E 5-business-day advance debit notice where applicable).
3. **Pre-Arbitration Escalation:** Only file Pre-Arbitration if the merchant failed to address the original reason code requirements, the dispute amount is **>= $150.00 USD** (network arbitration fee risk threshold), and Senior Analyst approval is logged.

## 3. Mandatory PII & PCI-DSS Data Handling in AI & Support Tools

Under PCI-DSS and internal Information Security Policy:
- **Never** submit full 16-digit Primary Account Numbers (PANs), CVV/CVC security codes, full SSNs, or raw bank account/routing numbers into external LLM prompts, chat logs, or unencrypted tickets.
- **Required Masking Format:** Mask PANs to show at most the first 6 (BIN) or last 4 digits (e.g., `****-****-****-1234`), redact emails and SSNs, and reference disputes solely by **Case ID** (e.g., `DSP-2026-004812`).
- **Audit Logging:** Every AI-assisted compliance lookup must log a sanitized query, the exact policy chunk IDs retrieved, the outcome (`answered`, `refused`, or `blocked`), and latency in the immutable `audit_logs` table.
