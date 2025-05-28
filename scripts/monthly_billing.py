#!/usr/bin/env python3
"""
Monthly Billing Management Script

This script provides CLI utilities for managing monthly billing cycles,
including generating invoices, processing billing periods, and generating reports.

Usage:
    python scripts/monthly_billing.py --help
    python scripts/monthly_billing.py generate --dry-run
    python scripts/monthly_billing.py generate --period 2024-01-01
    python scripts/monthly_billing.py process --admin-user 1
    python scripts/monthly_billing.py summary --period 2024-01-01
"""

import argparse
import sys
import os
from datetime import datetime, timedelta
from typing import Optional, List
import json

# Add the parent directory to the path to import from api
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services.billing_service import billing_service
from api.database.session import get_db
from api.core.audit_logger import log_billing_event


class DatabaseSession:
    """Context manager for database sessions"""

    def __init__(self):
        self.db = None

    def __enter__(self):
        self.db = next(get_db())
        return self.db

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()


def get_db_session():
    """Get database session context manager"""
    return DatabaseSession()


def generate_monthly_invoices(
    period_start: Optional[datetime] = None,
    admin_user_id: int = 1,
    dry_run: bool = False,
):
    """Generate monthly invoices for all offices"""
    print(f"🔄 {'[DRY RUN] ' if dry_run else ''}Generating monthly invoices...")
    if period_start:
        print(f"📅 Billing period start: {period_start.strftime('%Y-%m-%d')}")
    else:
        print("📅 Using current billing period")

    db = next(get_db_session())
    try:
        result = billing_service.generate_monthly_invoices_for_all_offices(
            db=db,
            billing_period_start=period_start,
            admin_user_id=admin_user_id,
            dry_run=dry_run,
        )

        print(f"✅ Monthly invoice generation completed!")
        print(f"📊 Results:")
        print(
            f"   • Billing period: {result['billing_period_start'].strftime('%Y-%m-%d')} to {result['billing_period_end'].strftime('%Y-%m-%d')}"
        )
        print(f"   • Offices processed: {result['offices_processed']}")
        print(f"   • Invoices created: {result['total_invoices_created']}")
        print(f"   • Patients billed: {result['total_patients_billed']}")
        print(f"   • Total amount: ${result['total_amount_cents']/100:.2f}")

        if dry_run:
            print("💡 This was a dry run - no data was actually created")

        # Show office-level details
        if result["office_results"]:
            print(f"\n📋 Office-level details:")
            for office_result in result["office_results"]:
                status = "✅" if office_result["success"] else "❌"
                print(
                    f"   {status} Office {office_result['office_id']}: {office_result.get('patients_billed', 0)} patients, ${office_result.get('total_amount_cents', 0)/100:.2f}"
                )
                if not office_result["success"]:
                    print(f"      Error: {office_result.get('error', 'Unknown error')}")

        return result

    except Exception as e:
        print(f"❌ Error generating monthly invoices: {e}")
        return None
    finally:
        db.close()


def process_billing_cycle(
    period_start: Optional[datetime] = None,
    admin_user_id: int = 1,
    dry_run: bool = False,
):
    """Process complete monthly billing cycle (generate invoices + update cycles)"""
    print(
        f"🔄 {'[DRY RUN] ' if dry_run else ''}Processing complete monthly billing cycle..."
    )

    db = next(get_db_session())
    try:
        result = billing_service.process_monthly_billing_cycle(
            db=db,
            billing_period_start=period_start,
            admin_user_id=admin_user_id,
            dry_run=dry_run,
        )

        print(f"✅ Monthly billing cycle completed!")
        print(f"📊 Summary:")

        # Invoice generation results
        invoice_results = result["invoice_generation"]
        print(f"   📄 Invoice Generation:")
        print(f"      • Offices processed: {invoice_results['offices_processed']}")
        print(f"      • Invoices created: {invoice_results['total_invoices_created']}")
        print(f"      • Patients billed: {invoice_results['total_patients_billed']}")
        print(f"      • Total amount: ${invoice_results['total_amount_cents']/100:.2f}")

        # Cycle updates (if not dry run)
        if not dry_run and "cycle_updates" in result:
            cycle_results = result["cycle_updates"]
            print(f"   🔄 Billing Cycle Updates:")
            print(f"      • Patients updated: {cycle_results['patients_updated']}")

        # Final summary
        if "final_summary" in result:
            final_summary = result["final_summary"]
            print(f"   📈 Final Totals:")
            print(f"      • Total offices: {final_summary['total_offices']}")
            print(f"      • Total invoices: {final_summary['total_invoices']}")
            print(
                f"      • Total patients billed: {final_summary['total_patients_billed']}"
            )
            print(
                f"      • Total amount: ${final_summary['total_amount_cents']/100:.2f}"
            )

        if dry_run:
            print("💡 This was a dry run - no data was actually created or updated")

        return result

    except Exception as e:
        print(f"❌ Error processing billing cycle: {e}")
        return None
    finally:
        db.close()


def get_billing_summary(
    period_start: Optional[datetime] = None,
    office_id: Optional[int] = None,
):
    """Get billing summary for a specific period"""
    print(f"📊 Getting billing summary...")
    if period_start:
        print(f"📅 Period: {period_start.strftime('%Y-%m-%d')}")
    if office_id:
        print(f"🏢 Office: {office_id}")

    db = next(get_db_session())
    try:
        summary = billing_service.get_monthly_billing_summary(
            db=db,
            billing_period_start=period_start,
            office_id=office_id,
        )

        print(f"✅ Billing summary retrieved!")
        print(
            f"📊 Summary for {summary['billing_period_start'].strftime('%Y-%m-%d')} to {summary['billing_period_end'].strftime('%Y-%m-%d')}:"
        )
        print(f"   • Total offices: {summary['total_offices']}")
        print(f"   • Total invoices: {summary['total_invoices']}")
        print(f"   • Total patients billed: {summary['total_patients_billed']}")
        print(f"   • Total amount: ${summary['total_amount_cents']/100:.2f}")

        # Office-level summaries
        if summary["office_summaries"]:
            print(f"\n📋 Office summaries:")
            for office_summary in summary["office_summaries"]:
                print(f"   🏢 Office {office_summary['office_id']}:")
                print(f"      • Patients: {office_summary['total_patients']}")
                print(
                    f"      • Amount: ${office_summary['total_amount_cents']/100:.2f}"
                )
                print(f"      • Invoices: {len(office_summary['invoices'])}")

        return summary

    except Exception as e:
        print(f"❌ Error getting billing summary: {e}")
        return None
    finally:
        db.close()


def parse_date(date_string: str) -> datetime:
    """Parse date string in YYYY-MM-DD format"""
    try:
        return datetime.strptime(date_string, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date format: {date_string}. Use YYYY-MM-DD"
        )


def summary_command(args):
    """Generate billing summary report"""
    try:
        billing_period = None
        if args.period:
            billing_period = datetime.strptime(args.period, "%Y-%m-%d")

        with get_db_session() as db:
            summary = billing_service.get_billing_period_activations_summary(
                db=db,
                start_date=billing_period,
                end_date=(
                    billing_period + timedelta(days=30) if billing_period else None
                ),
                office_id=args.office_id,
            )

        if args.output == "json":
            print(json.dumps(summary, indent=2, default=str))
        else:
            print_formatted_summary(summary)

    except Exception as e:
        print(f"❌ Error generating summary: {e}")
        sys.exit(1)


def one_off_charge_command(args):
    """Create one-off charge invoice"""
    try:
        with get_db_session() as db:
            result = billing_service.create_one_off_invoice_for_office(
                db=db,
                office_id=args.office_id,
                charge_description=args.description,
                amount_cents=args.amount_cents,
                admin_user_id=args.admin_user or 1,
                charge_type=args.charge_type,
                metadata={"notes": args.notes} if args.notes else None,
                dry_run=args.dry_run,
            )

        if result["success"]:
            print(f"✅ {result['message']}")
            if not args.dry_run:
                print(f"   Invoice ID: {result['invoice']['id']}")
                print(f"   Amount: ${result['invoice']['total_amount_cents']/100:.2f}")
                print(f"   Status: {result['invoice']['status']}")
            else:
                print(f"   [DRY RUN] Amount: ${args.amount_cents/100:.2f}")
        else:
            print(f"❌ {result['message']}")
            print(f"   Error: {result.get('error', 'Unknown error')}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Error creating one-off charge: {e}")
        sys.exit(1)


def setup_fee_command(args):
    """Create setup fee invoice"""
    try:
        with get_db_session() as db:
            result = billing_service.create_setup_fee_invoice(
                db=db,
                office_id=args.office_id,
                setup_fee_cents=args.amount_cents,
                admin_user_id=args.admin_user or 1,
                dry_run=args.dry_run,
            )

        if result["success"]:
            print(f"✅ {result['message']}")
            if not args.dry_run:
                print(f"   Invoice ID: {result['invoice']['id']}")
                print(f"   Amount: ${result['invoice']['total_amount_cents']/100:.2f}")
                print(f"   Status: {result['invoice']['status']}")
            else:
                print(f"   [DRY RUN] Amount: ${args.amount_cents/100:.2f}")
        else:
            print(f"❌ {result['message']}")
            print(f"   Error: {result.get('error', 'Unknown error')}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Error creating setup fee: {e}")
        sys.exit(1)


def bulk_setup_fee_command(args):
    """Create setup fees for multiple offices"""
    try:
        office_ids = [int(id.strip()) for id in args.office_ids.split(",")]

        with get_db_session() as db:
            result = billing_service.bulk_create_setup_fees(
                db=db,
                office_ids=office_ids,
                setup_fee_cents=args.amount_cents,
                admin_user_id=args.admin_user or 1,
                dry_run=args.dry_run,
            )

        print(f"📊 Bulk Setup Fee Results:")
        print(f"   Total Offices: {result['total_offices']}")
        print(f"   Successful: {result['successful_count']}")
        print(f"   Failed: {result['failed_count']}")
        print(f"   Amount per office: ${result['setup_fee_cents']/100:.2f}")

        if args.verbose:
            print("\n📋 Individual Results:")
            for office_result in result["office_results"]:
                status = "✅" if office_result["success"] else "❌"
                print(
                    f"   {status} Office {office_result['office_id']}: {office_result.get('message', 'Unknown')}"
                )

    except Exception as e:
        print(f"❌ Error creating bulk setup fees: {e}")
        sys.exit(1)


def one_off_summary_command(args):
    """Generate one-off charges summary report"""
    try:
        start_date = None
        end_date = None

        if args.start_date:
            start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
        if args.end_date:
            end_date = datetime.strptime(args.end_date, "%Y-%m-%d")

        with get_db_session() as db:
            summary = billing_service.get_one_off_charges_summary(
                db=db,
                office_id=args.office_id,
                start_date=start_date,
                end_date=end_date,
                charge_type=args.charge_type,
            )

        if args.output == "json":
            print(json.dumps(summary, indent=2, default=str))
        else:
            print_one_off_charges_summary(summary)

    except Exception as e:
        print(f"❌ Error generating one-off charges summary: {e}")
        sys.exit(1)


def print_one_off_charges_summary(summary):
    """Print formatted one-off charges summary"""
    if not summary["success"]:
        print(f"❌ Error: {summary.get('message', 'Failed to retrieve summary')}")
        return

    s = summary["summary"]
    print("📊 One-Off Charges Summary")
    print("=" * 50)
    print(f"Total Charges: {s['total_charges']}")
    print(f"Total Amount: ${s['total_amount_cents']/100:.2f}")
    print(f"Unique Offices: {s['unique_offices']}")

    if s["date_range"]["start_date"] or s["date_range"]["end_date"]:
        print(
            f"Date Range: {s['date_range']['start_date'] or 'N/A'} to {s['date_range']['end_date'] or 'N/A'}"
        )

    print("\n📋 Charges by Type:")
    for charge_type, data in summary["charges_by_type"].items():
        print(
            f"  {charge_type}: {data['count']} charges, ${data['total_amount_cents']/100:.2f}"
        )

    print(f"\n📄 Invoices: {len(summary['invoices'])}")
    for invoice in summary["invoices"][:10]:  # Show first 10
        print(
            f"  Invoice {invoice['id']} (Office {invoice['office_id']}): ${invoice['total_amount_cents']/100:.2f} - {invoice['status']}"
        )

    if len(summary["invoices"]) > 10:
        print(f"  ... and {len(summary['invoices']) - 10} more invoices")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Monthly Billing Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/monthly_billing.py generate --dry-run
  python scripts/monthly_billing.py generate --period 2024-01-01
  python scripts/monthly_billing.py process --admin-user 1
  python scripts/monthly_billing.py summary --period 2024-01-01 --office-id 5
  python scripts/monthly_billing.py one-off --office-id 5 --amount 5000 --description "Setup Fee"
  python scripts/monthly_billing.py setup-fee --office-id 5 --amount 5000
  python scripts/monthly_billing.py bulk-setup --office-ids "1,2,3,4,5" --amount 5000
  python scripts/monthly_billing.py one-off-summary --charge-type setup_fee
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Generate command
    generate_parser = subparsers.add_parser(
        "generate", help="Generate monthly invoices"
    )
    generate_parser.add_argument(
        "--period", help="Billing period start date (YYYY-MM-DD)"
    )
    generate_parser.add_argument(
        "--office-id", type=int, help="Generate for specific office only"
    )
    generate_parser.add_argument(
        "--admin-user", type=int, help="Admin user ID (default: 1)"
    )
    generate_parser.add_argument(
        "--dry-run", action="store_true", help="Simulate without creating records"
    )

    # Process command
    process_parser = subparsers.add_parser(
        "process", help="Process complete monthly billing cycle"
    )
    process_parser.add_argument(
        "--period", help="Billing period start date (YYYY-MM-DD)"
    )
    process_parser.add_argument(
        "--admin-user", type=int, help="Admin user ID (default: 1)"
    )
    process_parser.add_argument(
        "--dry-run", action="store_true", help="Simulate without creating records"
    )

    # Summary command
    summary_parser = subparsers.add_parser("summary", help="Generate billing summary")
    summary_parser.add_argument("--period", help="Billing period date (YYYY-MM-DD)")
    summary_parser.add_argument("--office-id", type=int, help="Filter by office ID")
    summary_parser.add_argument(
        "--output", choices=["text", "json"], default="text", help="Output format"
    )

    # One-off charge command
    one_off_parser = subparsers.add_parser("one-off", help="Create one-off charge")
    one_off_parser.add_argument(
        "--office-id", type=int, required=True, help="Office ID to charge"
    )
    one_off_parser.add_argument(
        "--amount",
        type=int,
        dest="amount_cents",
        required=True,
        help="Amount in cents (e.g., 5000 for $50.00)",
    )
    one_off_parser.add_argument(
        "--description", required=True, help="Charge description"
    )
    one_off_parser.add_argument(
        "--charge-type", default="custom", help="Charge type (default: custom)"
    )
    one_off_parser.add_argument("--notes", help="Additional notes for metadata")
    one_off_parser.add_argument(
        "--admin-user", type=int, help="Admin user ID (default: 1)"
    )
    one_off_parser.add_argument(
        "--dry-run", action="store_true", help="Simulate without creating records"
    )

    # Setup fee command
    setup_fee_parser = subparsers.add_parser(
        "setup-fee", help="Create setup fee invoice"
    )
    setup_fee_parser.add_argument(
        "--office-id", type=int, required=True, help="Office ID to charge"
    )
    setup_fee_parser.add_argument(
        "--amount",
        type=int,
        dest="amount_cents",
        default=5000,
        help="Setup fee amount in cents (default: 5000 = $50.00)",
    )
    setup_fee_parser.add_argument(
        "--admin-user", type=int, help="Admin user ID (default: 1)"
    )
    setup_fee_parser.add_argument(
        "--dry-run", action="store_true", help="Simulate without creating records"
    )

    # Bulk setup fee command
    bulk_setup_parser = subparsers.add_parser(
        "bulk-setup", help="Create setup fees for multiple offices"
    )
    bulk_setup_parser.add_argument(
        "--office-ids",
        required=True,
        help="Comma-separated office IDs (e.g., '1,2,3,4,5')",
    )
    bulk_setup_parser.add_argument(
        "--amount",
        type=int,
        dest="amount_cents",
        default=5000,
        help="Setup fee amount in cents (default: 5000 = $50.00)",
    )
    bulk_setup_parser.add_argument(
        "--admin-user", type=int, help="Admin user ID (default: 1)"
    )
    bulk_setup_parser.add_argument(
        "--dry-run", action="store_true", help="Simulate without creating records"
    )
    bulk_setup_parser.add_argument(
        "--verbose", action="store_true", help="Show individual office results"
    )

    # One-off summary command
    one_off_summary_parser = subparsers.add_parser(
        "one-off-summary", help="Generate one-off charges summary"
    )
    one_off_summary_parser.add_argument(
        "--office-id", type=int, help="Filter by office ID"
    )
    one_off_summary_parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    one_off_summary_parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    one_off_summary_parser.add_argument(
        "--charge-type", help="Filter by charge type (e.g., setup_fee, consulting)"
    )
    one_off_summary_parser.add_argument(
        "--output", choices=["text", "json"], default="text", help="Output format"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Dispatch to appropriate command handler
    if args.command == "generate":
        generate_monthly_invoices(
            period_start=args.period,
            admin_user_id=args.admin_user,
            dry_run=args.dry_run,
        )
    elif args.command == "process":
        process_billing_cycle(
            period_start=args.period,
            admin_user_id=args.admin_user,
            dry_run=args.dry_run,
        )
    elif args.command == "summary":
        summary_command(args)
    elif args.command == "one-off":
        one_off_charge_command(args)
    elif args.command == "setup-fee":
        setup_fee_command(args)
    elif args.command == "bulk-setup":
        bulk_setup_fee_command(args)
    elif args.command == "one-off-summary":
        one_off_summary_command(args)
    else:
        print(f"❌ Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
