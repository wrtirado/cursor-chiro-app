# Payment Plan and Billing Structure

This document outlines the payment and billing structure for the SaaS platform used by chiropractic offices. It is intended for developers and business stakeholders to understand how payments, invoicing, and billing logic are designed and implemented.

## 1. Onboarding and Setup

- **Free Onboarding:**
  - Chiropractors can sign up and create an account for free.
  - They can set up their company, add sub-offices, create roles, and configure users without any initial charge.
- **Optional Setup Fee:**
  - For chiropractors who prefer not to self-onboard, an optional setup service is available for a one-time fee.
  - This setup fee is handled as a one-off invoice or charge, separate from recurring billing.
  - **Rationale:** The setup fee is not tracked on the Office table. Instead, it is managed as a special invoice/charge in the billing system or payment provider. This keeps the Office table clean and allows for flexible handling of other one-off charges in the future.

## 2. Patient Activation and Usage-Based Billing

- **Core Billing Model:**
  - Offices are billed based on the number of active patient accounts each month.
  - When a chiropractor creates a patient account, builds a plan, and activates the account (by sending the plan to the patient), a fixed amount of $2 is added to the office's invoice for the month.
- **Monthly Billing Cycle:**
  - At the start of each billing cycle, all active patient accounts from the previous cycle are automatically included in the new cycle's invoice at $2 per account.
  - Deactivated accounts that were already billed in a previous cycle do not reduce the invoice for that cycle, but will not be included in future cycles unless reactivated.
  - Reactivated accounts are billed in the current cycle if they had not already been active in that cycle.

## 3. Invoicing and Payments

- **Invoices:**
  - Each office receives a monthly invoice that includes charges for all active patient accounts and any one-off fees (such as setup, if applicable).
  - Invoices are generated and tracked in a dedicated invoices table or via the payment provider's system (e.g., Stripe).
- **Payments:**
  - Payments will be processed through Stripe, with each office having a unique customer record in the provider's system.
  - Payment status, invoice references, and payment method details are stored in the billing/invoice tables, not on the Office table.

## 4. Data Model Rationale

- **Office Table:**
  - Contains only fields relevant to ongoing subscription and billing status (e.g., subscription status, current plan, payment provider customer ID).
  - Does **not** include setup fee status or invoice references for one-off charges.
- **Invoices Table:**
  - Stores all invoice records, including monthly recurring and one-off charges (such as setup fees).
  - Allows for flexible reporting, auditing, and future expansion of billing features.
- **Payments Table (optional):**
  - Tracks payment attempts and records, linked to invoices.

## 5. Summary Table Structure

| Table         | Field(s)                                                                               | Purpose                                     |
| ------------- | -------------------------------------------------------------------------------------- | ------------------------------------------- |
| Office        | billing_status, current_plan_id, payment_provider_customer_id, ...                     | Track office billing state and payment info |
| Patient/User  | is_active_for_billing, activated_at, deactivated_at, last_billed_cycle                 | Track which patients are billable           |
| Invoice       | invoice_id, office_id, billing_period_start/end, total_amount, status, line_items, ... | Store invoice details per office/cycle      |
| Line Item     | line_item_id, invoice_id, description, quantity, unit_price, total_price, patient_id   | Detailed breakdown of invoice charges       |
| Audit/History | event_id, office_id, patient_id, event_type, event_time, details                       | Compliance and troubleshooting              |

## 6. Compliance and Security

- All payment and billing data handling must adhere to HIPAA and security best practices as outlined in `developer-compliance-guide.md`.
- Sensitive payment data (e.g., card numbers) is never stored in the application database; only references (IDs) from the payment provider are stored.
- Audit logging, encryption, and secure data handling are required for all billing-related operations.
