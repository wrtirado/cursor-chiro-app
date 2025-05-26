# Billing API and Data Model Alignment Assessment

## Executive Summary

This document provides a comprehensive assessment of the current billing API and data model implementation against the specifications in `docs/payment-plan.md`. It identifies gaps, misalignments, and provides specific recommendations for achieving full compliance with the payment plan requirements.

## Current State Analysis

### ✅ **Well-Aligned Components**

1. **Office Model Subscription Fields**

   - ✅ `subscription_status` with proper enum values (active, past_due, canceled, trialing, inactive)
   - ✅ `payment_provider_customer_id` for Stripe customer references
   - ✅ `payment_provider_subscription_id` for Stripe subscription references
   - ✅ `current_plan_id` for plan tracking
   - ✅ `billing_cycle_anchor_date` for billing cycle management

2. **Security Infrastructure**

   - ✅ Payment reference encryption and validation (PaymentReferenceSecurity)
   - ✅ Stripe ID format validation for customer and subscription IDs
   - ✅ TLS enforcement and secure headers middleware
   - ✅ Comprehensive data minimization system (api/core/data_minimization.py)

3. **ePHI Isolation Framework**
   - ✅ ePHI detection and classification system
   - ✅ Billing data sanitization for Stripe integration
   - ✅ Anonymous reference generation system
   - ✅ External data validation framework

### ❌ **Critical Gaps Identified**

1. **Missing Database Tables**

   - ❌ Invoice table for monthly and one-off billing
   - ❌ Invoice Line Item table for detailed charge breakdown
   - ❌ Payment tracking and status management

2. **User Model Billing Fields Missing**

   - ❌ `is_active_for_billing` boolean field
   - ❌ `activated_at` timestamp
   - ❌ `deactivated_at` timestamp
   - ❌ `last_billed_cycle` tracking

3. **Billing API Endpoints Missing**

   - ❌ No billing router or module exists
   - ❌ No invoice management endpoints
   - ❌ No payment status endpoints
   - ❌ No patient activation billing integration

4. **Business Logic Missing**

   - ❌ Patient activation billing automation ($2 per activation)
   - ❌ Monthly invoice generation logic
   - ❌ One-off charge handling (setup fees)
   - ❌ Billing cycle management

5. **Stripe Integration Missing**
   - ❌ Customer creation and management
   - ❌ Invoice transmission to Stripe
   - ❌ Payment status synchronization
   - ❌ Webhook handling for payment events

## Detailed Alignment Analysis

### 1. Data Model Alignment

#### Payment Plan Requirement:

> "Invoices are generated and tracked in a dedicated invoices table or via the payment provider's system (e.g., Stripe)."

**Current State**: ❌ **Missing**

- No Invoice table exists
- No Line Item table exists
- Only Office table has billing references

**Required Implementation**:

```sql
-- Invoice table (monthly and one-off)
CREATE TABLE invoices (
    invoice_id INTEGER PRIMARY KEY,
    office_id INTEGER REFERENCES offices(office_id),
    billing_period_start DATETIME,
    billing_period_end DATETIME,
    total_amount DECIMAL(10,2),
    status VARCHAR(50), -- draft, sent, paid, failed, canceled
    stripe_invoice_id VARCHAR(255),
    invoice_type VARCHAR(50), -- monthly, setup_fee, one_off
    created_at DATETIME,
    updated_at DATETIME
);

-- Invoice Line Items (with ePHI isolation)
CREATE TABLE invoice_line_items (
    line_item_id INTEGER PRIMARY KEY,
    invoice_id INTEGER REFERENCES invoices(invoice_id),
    description VARCHAR(255),
    quantity INTEGER,
    unit_price DECIMAL(10,2),
    total_price DECIMAL(10,2),
    item_type VARCHAR(50), -- patient_activation, setup_fee, etc.
    anonymous_patient_ref VARCHAR(255), -- For internal tracking only
    created_at DATETIME
);
```

#### Payment Plan Requirement:

> "Track which patients are billable" with fields like `is_active_for_billing, activated_at, deactivated_at, last_billed_cycle`

**Current State**: ❌ **Missing**

- User model has no billing status fields
- No patient activation/deactivation tracking

**Required Implementation**:

```sql
-- Patient Billing Status (Internal ePHI tracking)
ALTER TABLE users ADD COLUMN is_active_for_billing BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN activated_at DATETIME;
ALTER TABLE users ADD COLUMN deactivated_at DATETIME;
ALTER TABLE users ADD COLUMN last_billed_cycle VARCHAR(50);
```

### 2. API Endpoint Alignment

#### Payment Plan Requirement:

> "Create endpoints for offices to view their invoices, line items, and payment status"

**Current State**: ❌ **Completely Missing**

- No billing module or router exists
- No API endpoints for billing operations

**Required Endpoints**:

```
GET    /api/v1/billing/offices/{office_id}/invoices
GET    /api/v1/billing/invoices/{invoice_id}
GET    /api/v1/billing/invoices/{invoice_id}/line-items
POST   /api/v1/billing/patients/{patient_id}/activate
POST   /api/v1/billing/charges/one-off
GET    /api/v1/billing/payment-status/{invoice_id}
POST   /api/v1/billing/invoices/generate-monthly
```

### 3. Business Logic Alignment

#### Payment Plan Requirement:

> "When a chiropractor creates a patient account, builds a plan, and activates the account (by sending the plan to the patient), a fixed amount of $2 is added to the office's invoice for the month."

**Current State**: ❌ **Missing**

- No integration between patient activation and billing
- No automatic line item creation
- No billing logic in patient workflows

#### Payment Plan Requirement:

> "At the start of each billing cycle, all active patient accounts from the previous cycle are automatically included in the new cycle's invoice at $2 per account."

**Current State**: ❌ **Missing**

- No monthly invoice generation automation
- No billing cycle management
- No active patient aggregation

### 4. ePHI Isolation Alignment

#### Payment Plan Requirement:

> "All payment and billing data handling must adhere to HIPAA and security best practices"

**Current State**: ✅ **Well-Aligned**

- Comprehensive data minimization system implemented
- ePHI detection and sanitization working
- Anonymous reference generation in place
- Stripe integration security framework established

## Implementation Priority Matrix

### Phase 1: Core Data Models (HIGH PRIORITY)

**Dependencies**: None
**Estimated Effort**: 2-3 days

1. **Create Invoice Table**

   - Monthly and one-off invoice storage
   - Stripe reference integration
   - Status tracking and indexing

2. **Create Invoice Line Item Table**

   - Dual-purpose schema (internal ePHI + external anonymous)
   - Data sanitization integration
   - Aggregation support

3. **Update User Model for Billing**
   - Add billing status tracking fields
   - Activation/deactivation timestamps
   - Billing cycle tracking

### Phase 2: API Endpoints (HIGH PRIORITY)

**Dependencies**: Phase 1 complete
**Estimated Effort**: 3-4 days

1. **Create Billing Router Module**

   - `api/billing/router.py`
   - Full endpoint implementation
   - RBAC integration

2. **Billing Schemas**

   - `api/schemas/billing.py`
   - Request/response models
   - Validation rules

3. **Billing CRUD Operations**
   - `api/crud/billing.py`
   - Database operations
   - ePHI-safe queries

### Phase 3: Business Logic Integration (CRITICAL PRIORITY)

**Dependencies**: Phase 2 complete
**Estimated Effort**: 4-5 days

1. **Patient Activation Billing**

   - Integration with existing patient workflows
   - Automatic line item creation
   - Billing status updates

2. **Monthly Invoice Generation**

   - Automated billing cycle management
   - Active patient aggregation
   - Stripe-ready data preparation

3. **One-Off Charge Handling**
   - Setup fee implementation
   - Flexible charge system
   - Manual charge creation

### Phase 4: Stripe Integration (HIGH PRIORITY)

**Dependencies**: Phase 3 complete
**Estimated Effort**: 3-4 days

1. **Stripe Customer Management**

   - Customer creation automation
   - Reference synchronization
   - Error handling

2. **Invoice Transmission**
   - Sanitized data transmission
   - Payment status tracking
   - Webhook integration

## Compliance Considerations

### ePHI Isolation Requirements

- ✅ Data minimization framework implemented
- ✅ Anonymous reference system working
- ❌ Integration with billing workflows needed
- ❌ Real-time validation checkpoints needed

### Audit Requirements

- ✅ Foundation audit logging established
- ❌ Billing-specific audit events needed
- ❌ Integration with billing workflows needed

### Security Requirements

- ✅ TLS enforcement implemented
- ✅ Payment reference encryption working
- ✅ Stripe ID validation in place
- ❌ End-to-end security testing needed

## Risk Assessment

### High Risk Issues

1. **Patient Billing Integration Gap**: No connection between patient activation and billing could lead to revenue loss
2. **Invoice Generation Missing**: No automated billing could cause significant operational burden
3. **Payment Status Tracking**: No synchronization with Stripe could cause payment discrepancies

### Medium Risk Issues

1. **API Endpoint Security**: Need RBAC integration for billing endpoints
2. **Data Model Performance**: Need proper indexing for billing queries
3. **Error Handling**: Need comprehensive error handling for payment failures

### Low Risk Issues

1. **Documentation Updates**: API documentation needs updating
2. **Test Coverage**: Comprehensive testing needed for billing workflows
3. **Monitoring**: Payment processing monitoring needed

## Recommended Implementation Sequence

1. **Start with Task 9.10**: Create Invoice Table
2. **Continue with Task 9.11**: Create Invoice Line Item Table
3. **Then Task 9.12**: Update User Model for Billing
4. **Move to Task 9.17**: Implement API Endpoints
5. **Complete Task 9.13**: Patient Activation Billing Logic
6. **Finish with Task 9.16**: Stripe Integration

This sequence ensures database foundation is solid before building business logic and API layers.

## Success Criteria

### Technical Criteria

- ✅ All payment-plan.md data model requirements implemented
- ✅ All API endpoints functional and secure
- ✅ Patient activation automatically creates billing entries
- ✅ Monthly invoice generation working
- ✅ Stripe integration functional with ePHI isolation

### Compliance Criteria

- ✅ No ePHI transmitted to Stripe under any circumstances
- ✅ All billing operations properly audited
- ✅ Security validation passes for all billing workflows
- ✅ Payment reference encryption working correctly

### Business Criteria

- ✅ $2 per patient activation billing working
- ✅ Monthly recurring billing operational
- ✅ One-off charges (setup fees) supported
- ✅ Payment status tracking accurate
- ✅ Revenue recognition automated
