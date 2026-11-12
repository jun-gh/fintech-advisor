# SOP-003: Visa & Mastercard Chargeback Reason Codes & Evidence Matrix

**Document ID:** `sop-visa-mastercard-reason-codes`  
**Version:** `2026.2`  
**Category:** `card_network_chargebacks`  
**Effective Date:** 2026-02-01  
**Owner:** Chargeback & Network Arbitration Desk

## 1. Chargeback Filing Timeframes & Reason Code Selection

Analysts must select the exact network reason code matching the cardholder's claim and verify that the filing date falls within the network's strict calendar-day window from the transaction processing date (or expected delivery date for goods/services).

| Network | Reason Code | Category & Description | Filing Time Limit | Mandatory Cardholder / Case Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **Visa** | **10.4** | Other Fraud — Card-Absent Environment | **120 calendar days** from transaction processing date | Cardholder written/recorded attestation denying authorization or benefit; verify no prior EMV/3DS liability shift applies. |
| **Visa** | **13.1** | Merchandise / Services Not Received | **120 calendar days** from expected delivery/service date (max 540 days from processing) | Expected delivery date, proof of attempt to contact merchant (if goods delayed/cancelled), and confirmation item was never received. |
| **Visa** | **13.3** | Not as Described or Defective Merchandise/Services | **120 calendar days** from receipt date (or service cancellation date) | Specific description of defect/mismatch, proof of merchant contact, and proof goods were returned or return was attempted/refused. |
| **Mastercard** | **4837** | No Cardholder Authorization | **120 calendar days** from central site business date | Cardholder statement confirming non-authorization; confirm transaction was not authenticated via valid 3-D Secure 2.0 liability-shift flow. |
| **Mastercard** | **4853** | Cardholder Dispute — Goods or Services Not Provided / Not as Described | **120 calendar days** from expected delivery or cancellation date | Proof of merchant resolution attempt, cancellation confirmation (for recurring/travel), or photographic/written evidence of defect. |

## 2. Visa Compelling Evidence 3.0 (CE 3.0) — Defending Visa 10.4 Fraud Claims

Under **Visa Compelling Evidence 3.0**, a merchant can overturn a **Visa 10.4** card-absent fraud chargeback by supplying **two prior undisputed transactions** with the same payment credential that occurred between **120 and 365 days** before the disputed transaction, **AND** proving at least **two matching data elements** across the prior undisputed transactions and the disputed transaction (one of which must be **IP address** or **Device ID / Device Fingerprint**, alongside Account ID, Shipping Address, or Email).

- **Analyst Action on CE 3.0 Representment:** Before accepting a merchant's CE 3.0 representment, verify that neither of the two historical transactions was previously reported as fraudulent or disputed, and confirm the timestamp gap falls strictly within **120 to 365 days**. If valid, close the chargeback against the merchant and escalate to the **First-Party Misuse / Friendly Fraud Review Queue**.

## 3. Mandatory Pre-Filing Checks

Before submitting any chargeback to the card network:
1. Confirm no **merchant refund or credit** has already posted in the last 14 calendar days.
2. Verify the transaction was not an **authenticated 3-D Secure (3DS2) full liability-shift** purchase for fraud codes (Visa 10.4 / Mastercard 4837), unless network rules provide an issuer override (e.g., lost/stolen reported prior to auth).
3. Ensure all cardholder attachments omit unmasked Primary Account Numbers (PANs).
