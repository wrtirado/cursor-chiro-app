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
from datetime import datetime
from typing import Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.database.session import get_db
from api.services.billing_service import billing_service


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

    db = next(get_db())
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

    db = next(get_db())
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

    db = next(get_db())
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


def main():
    parser = argparse.ArgumentParser(
        description="Monthly Billing Management Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate invoices for current period (dry run)
    python scripts/monthly_billing.py generate --dry-run
    
    # Generate invoices for specific period
    python scripts/monthly_billing.py generate --period 2024-01-01
    
    # Process complete billing cycle
    python scripts/monthly_billing.py process --admin-user 1
    
    # Get billing summary for current period
    python scripts/monthly_billing.py summary
    
    # Get billing summary for specific period and office
    python scripts/monthly_billing.py summary --period 2024-01-01 --office 1
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Generate command
    generate_parser = subparsers.add_parser(
        "generate", help="Generate monthly invoices"
    )
    generate_parser.add_argument(
        "--period", type=parse_date, help="Billing period start date (YYYY-MM-DD)"
    )
    generate_parser.add_argument(
        "--admin-user", type=int, default=1, help="Admin user ID (default: 1)"
    )
    generate_parser.add_argument(
        "--dry-run", action="store_true", help="Simulate without creating data"
    )

    # Process command
    process_parser = subparsers.add_parser(
        "process", help="Process complete billing cycle"
    )
    process_parser.add_argument(
        "--period", type=parse_date, help="Billing period start date (YYYY-MM-DD)"
    )
    process_parser.add_argument(
        "--admin-user", type=int, default=1, help="Admin user ID (default: 1)"
    )
    process_parser.add_argument(
        "--dry-run", action="store_true", help="Simulate without creating data"
    )

    # Summary command
    summary_parser = subparsers.add_parser("summary", help="Get billing summary")
    summary_parser.add_argument(
        "--period", type=parse_date, help="Billing period start date (YYYY-MM-DD)"
    )
    summary_parser.add_argument("--office", type=int, help="Office ID to filter by")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    print(f"🚀 Monthly Billing Management")
    print(f"📅 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("")

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
        get_billing_summary(
            period_start=args.period,
            office_id=args.office,
        )


if __name__ == "__main__":
    main()
