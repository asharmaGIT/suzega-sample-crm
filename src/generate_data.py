#!/usr/bin/env python3
"""
CRM Database Data Generator

Generates synthetic CRM data using Faker and inserts it into a PostgreSQL database.
Maintains referential integrity across all tables.

Connection modes:
1. Cloud SQL Python Connector (INSTANCE_CONNECTION_NAME set) - for Cloud Run/Cloud Build
2. Direct connection (DB_HOST set) - for local development

Usage:
    # Generate all tables with default counts
    python generate_data.py

    # Generate all tables with custom count (applies to all tables)
    python generate_data.py --count 50

    # Generate specific tables only
    python generate_data.py --tables companies,contacts,deals

    # Generate specific tables with custom counts
    python generate_data.py --tables companies,contacts --count 200

    # Specify counts per table
    python generate_data.py --tables companies:50,contacts:100,deals:75

    # Mix: some with counts, some using default/--count
    python generate_data.py --tables companies:50,contacts,deals --count 100
"""

import argparse
import os
import random
import sys
from datetime import datetime, timedelta
from decimal import Decimal

from dotenv import load_dotenv
from faker import Faker
import sqlalchemy
from sqlalchemy import text

# Load environment variables
load_dotenv()

# Initialize Faker with time-based seed for unique data each run
import time
seed = int(time.time())
fake = Faker()
Faker.seed(seed)
random.seed(seed)

# Configuration - default record counts
DEFAULT_COUNTS = {
    'companies': 100,
    'contacts': 500,
    'deals': 200,
    'products': 50,
    'deal_products': 300,
    'activities': 400,
    'notes': 300,
    'tasks': 150,
}

# All available tables
ALL_TABLES = ['companies', 'contacts', 'deals', 'products', 'deal_products', 'activities', 'notes', 'tasks']

# Table dependencies - maps each table to the tables it depends on
TABLE_DEPENDENCIES = {
    'companies': [],
    'contacts': ['companies'],
    'deals': ['companies', 'contacts'],
    'products': [],
    'deal_products': ['deals', 'products'],
    'activities': ['contacts'],
    'notes': ['contacts'],
    'tasks': ['deals'],
}

# Industry options
INDUSTRIES = [
    'Technology', 'Healthcare', 'Finance', 'Manufacturing', 'Retail',
    'Education', 'Real Estate', 'Consulting', 'Marketing', 'Legal',
    'Energy', 'Transportation', 'Hospitality', 'Construction', 'Agriculture',
    'Telecommunications', 'Media', 'Insurance', 'Pharmaceutical', 'Automotive'
]

# Job titles by department
JOB_TITLES = {
    'Executive': ['CEO', 'CTO', 'CFO', 'COO', 'VP of Operations', 'President', 'Managing Director'],
    'Sales': ['Sales Director', 'Sales Manager', 'Account Executive', 'Sales Representative', 'Business Development Manager'],
    'Marketing': ['Marketing Director', 'Marketing Manager', 'Brand Manager', 'Digital Marketing Specialist', 'Content Manager'],
    'Engineering': ['Engineering Manager', 'Software Engineer', 'Senior Developer', 'Tech Lead', 'DevOps Engineer'],
    'Finance': ['Finance Director', 'Controller', 'Financial Analyst', 'Accountant', 'Treasurer'],
    'HR': ['HR Director', 'HR Manager', 'Recruiter', 'Talent Acquisition Specialist', 'HR Generalist'],
    'Operations': ['Operations Manager', 'Project Manager', 'Supply Chain Manager', 'Logistics Coordinator'],
}

DEAL_STAGES = {
    'prospecting': 10,
    'qualification': 25,
    'proposal': 50,
    'negotiation': 75,
    'closed_won': 100,
    'closed_lost': 0,
}

PRODUCT_CATEGORIES = [
    'Software', 'Hardware', 'Services', 'Support', 'Training',
    'Consulting', 'Subscription', 'License', 'Integration', 'Custom Development'
]

ACTIVITY_TYPES = ['call', 'email', 'meeting', 'demo', 'follow_up']
TASK_PRIORITIES = ['low', 'medium', 'high', 'urgent']
TASK_STATUSES = ['pending', 'in_progress', 'completed', 'cancelled']
DEAL_SOURCES = [
    'Website', 'Referral', 'Cold Call', 'Trade Show', 'Social Media',
    'Email Campaign', 'Partner', 'Advertisement', 'Inbound', 'Outbound'
]


def get_db_engine():
    """Create and return a SQLAlchemy engine."""
    instance_connection_name = os.getenv('INSTANCE_CONNECTION_NAME')

    if instance_connection_name:
        # Use Cloud SQL Python Connector
        from google.cloud.sql.connector import Connector

        connector = Connector()

        def getconn():
            return connector.connect(
                instance_connection_name,
                "pg8000",
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', ''),
                db=os.getenv('DB_NAME', 'crm_db'),
                ip_type=os.getenv('IP_TYPE', 'PRIVATE')
            )

        engine = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=getconn,
        )
    else:
        # Direct connection
        db_url = f"postgresql://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', '')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'crm_db')}"
        engine = sqlalchemy.create_engine(db_url)

    return engine


def generate_companies(conn, count):
    """Generate company records."""
    print(f"Generating {count} companies...")
    company_ids = []

    for _ in range(count):
        result = conn.execute(
            text("""
            INSERT INTO companies (name, industry, website, address, city, state, country, postal_code, phone, employee_count, annual_revenue, created_at)
            VALUES (:name, :industry, :website, :address, :city, :state, :country, :postal_code, :phone, :employee_count, :annual_revenue, :created_at)
            RETURNING id
            """),
            {
                'name': fake.company(),
                'industry': random.choice(INDUSTRIES),
                'website': fake.url(),
                'address': fake.street_address(),
                'city': fake.city(),
                'state': fake.state_abbr(),
                'country': 'USA',
                'postal_code': fake.zipcode(),
                'phone': fake.phone_number(),
                'employee_count': random.randint(10, 10000),
                'annual_revenue': Decimal(random.randint(100000, 100000000)),
                'created_at': fake.date_time_between(start_date='-3y', end_date='now'),
            }
        )
        company_ids.append(result.fetchone()[0])

    print(f"  Created {len(company_ids)} companies")
    return company_ids


def generate_contacts(conn, company_ids, count):
    """Generate contact records."""
    print(f"Generating {count} contacts...")
    contact_ids = []
    contact_company_map = {}
    used_emails = set()

    for i in range(count):
        company_id = random.choice(company_ids)
        department = random.choice(list(JOB_TITLES.keys()))
        title = random.choice(JOB_TITLES[department])

        first_name = fake.first_name()
        last_name = fake.last_name()

        base_email = f"{first_name.lower()}.{last_name.lower()}@{fake.domain_name()}"
        email = base_email
        counter = 1
        while email in used_emails:
            email = f"{first_name.lower()}.{last_name.lower()}{counter}@{fake.domain_name()}"
            counter += 1
        used_emails.add(email)

        result = conn.execute(
            text("""
            INSERT INTO contacts (company_id, first_name, last_name, email, phone, mobile, title, department, linkedin_url, is_primary, created_at)
            VALUES (:company_id, :first_name, :last_name, :email, :phone, :mobile, :title, :department, :linkedin_url, :is_primary, :created_at)
            RETURNING id
            """),
            {
                'company_id': company_id,
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'phone': fake.phone_number(),
                'mobile': fake.phone_number(),
                'title': title,
                'department': department,
                'linkedin_url': f"https://linkedin.com/in/{first_name.lower()}-{last_name.lower()}-{fake.uuid4()[:8]}",
                'is_primary': i % 5 == 0,
                'created_at': fake.date_time_between(start_date='-2y', end_date='now'),
            }
        )
        contact_id = result.fetchone()[0]
        contact_ids.append(contact_id)
        contact_company_map[contact_id] = company_id

    print(f"  Created {len(contact_ids)} contacts")
    return contact_ids, contact_company_map


def generate_products(conn, count):
    """Generate product records."""
    print(f"Generating {count} products...")
    product_data = {}

    product_prefixes = ['Pro', 'Enterprise', 'Basic', 'Premium', 'Ultimate', 'Starter', 'Business', 'Team']
    product_types = ['Suite', 'Platform', 'Solution', 'Package', 'Service', 'Module', 'Add-on', 'License']
    used_skus = set()

    for i in range(count):
        prefix = random.choice(product_prefixes)
        prod_type = random.choice(product_types)
        category = random.choice(PRODUCT_CATEGORIES)
        name = f"{prefix} {category} {prod_type}"

        sku = f"{category[:3].upper()}-{random.randint(1000, 9999)}"
        while sku in used_skus:
            sku = f"{category[:3].upper()}-{random.randint(1000, 9999)}"
        used_skus.add(sku)

        price = Decimal(random.randint(99, 99999)) + Decimal(random.randint(0, 99)) / 100

        result = conn.execute(
            text("""
            INSERT INTO products (name, description, price, sku, category, is_active, created_at)
            VALUES (:name, :description, :price, :sku, :category, :is_active, :created_at)
            RETURNING id
            """),
            {
                'name': name,
                'description': fake.paragraph(nb_sentences=2),
                'price': price,
                'sku': sku,
                'category': category,
                'is_active': random.random() > 0.1,
                'created_at': fake.date_time_between(start_date='-2y', end_date='now'),
            }
        )
        product_id = result.fetchone()[0]
        product_data[product_id] = price

    print(f"  Created {len(product_data)} products")
    return product_data


def generate_deals(conn, company_ids, contact_ids, contact_company_map, count):
    """Generate deal records."""
    print(f"Generating {count} deals...")
    deal_ids = []

    for _ in range(count):
        company_id = random.choice(company_ids)
        company_contacts = [cid for cid, comp_id in contact_company_map.items() if comp_id == company_id]
        contact_id = random.choice(company_contacts) if company_contacts else None

        stage = random.choice(list(DEAL_STAGES.keys()))
        probability = DEAL_STAGES[stage]
        if stage not in ('closed_won', 'closed_lost'):
            probability = max(0, min(100, probability + random.randint(-10, 10)))

        value = Decimal(random.randint(1000, 500000))
        expected_close = fake.date_between(start_date='-6m', end_date='+6m')

        actual_close = None
        if stage in ('closed_won', 'closed_lost'):
            actual_close = fake.date_between(start_date='-6m', end_date='today')

        result = conn.execute(
            text("""
            INSERT INTO deals (company_id, contact_id, title, description, value, stage, probability, expected_close_date, actual_close_date, source, created_at)
            VALUES (:company_id, :contact_id, :title, :description, :value, :stage, :probability, :expected_close_date, :actual_close_date, :source, :created_at)
            RETURNING id
            """),
            {
                'company_id': company_id,
                'contact_id': contact_id,
                'title': f"{fake.bs().title()} Project",
                'description': fake.paragraph(nb_sentences=2),
                'value': value,
                'stage': stage,
                'probability': probability,
                'expected_close_date': expected_close,
                'actual_close_date': actual_close,
                'source': random.choice(DEAL_SOURCES),
                'created_at': fake.date_time_between(start_date='-1y', end_date='now'),
            }
        )
        deal_ids.append(result.fetchone()[0])

    print(f"  Created {len(deal_ids)} deals")
    return deal_ids


def generate_deal_products(conn, deal_ids, product_data, count):
    """Generate deal-product associations."""
    print(f"Generating {count} deal-product associations...")
    deal_products = []
    used_pairs = set()
    product_ids = list(product_data.keys())

    while len(deal_products) < count:
        deal_id = random.choice(deal_ids)
        product_id = random.choice(product_ids)

        pair = (deal_id, product_id)
        if pair in used_pairs:
            continue
        used_pairs.add(pair)

        base_price = product_data[product_id]
        unit_price = base_price * Decimal(random.uniform(0.8, 1.2))

        deal_products.append({
            'deal_id': deal_id,
            'product_id': product_id,
            'quantity': random.randint(1, 20),
            'unit_price': round(unit_price, 2),
            'discount_percent': Decimal(random.choice([0, 0, 0, 5, 10, 15, 20])),
        })

    conn.execute(
        text("""
        INSERT INTO deal_products (deal_id, product_id, quantity, unit_price, discount_percent)
        VALUES (:deal_id, :product_id, :quantity, :unit_price, :discount_percent)
        """),
        deal_products
    )
    print(f"  Created {len(deal_products)} deal-product associations")


def generate_activities(conn, contact_ids, count):
    """Generate activity records."""
    print(f"Generating {count} activities...")
    activities = []

    activity_subjects = {
        'call': ['Initial discovery call', 'Follow-up call', 'Product discussion', 'Pricing call', 'Check-in call', 'Support call'],
        'email': ['Introduction email', 'Proposal sent', 'Follow-up email', 'Meeting confirmation', 'Thank you email', 'Contract sent'],
        'meeting': ['Product demo', 'Strategy meeting', 'Kickoff meeting', 'Quarterly review', 'Executive presentation', 'Technical deep-dive'],
        'demo': ['Product walkthrough', 'Feature demonstration', 'Technical demo', 'POC presentation', 'Solution overview'],
        'follow_up': ['Post-meeting follow-up', 'Proposal follow-up', 'Contract follow-up', 'Decision check-in', 'Next steps discussion'],
    }

    for _ in range(count):
        contact_id = random.choice(contact_ids)
        activity_type = random.choice(ACTIVITY_TYPES)

        activities.append({
            'contact_id': contact_id,
            'type': activity_type,
            'subject': random.choice(activity_subjects[activity_type]),
            'notes': fake.paragraph(nb_sentences=3) if random.random() > 0.3 else None,
            'duration_minutes': random.randint(5, 120) if activity_type in ('call', 'meeting', 'demo') else None,
            'activity_date': fake.date_time_between(start_date='-1y', end_date='now'),
        })

    conn.execute(
        text("""
        INSERT INTO activities (contact_id, type, subject, notes, duration_minutes, activity_date)
        VALUES (:contact_id, :type, :subject, :notes, :duration_minutes, :activity_date)
        """),
        activities
    )
    print(f"  Created {count} activities")


def generate_notes(conn, contact_ids, count):
    """Generate note records."""
    print(f"Generating {count} notes...")
    notes = []

    note_templates = [
        "Spoke with {name} about their current challenges. They mentioned {topic}.",
        "Key decision maker is {role}. Budget approval needed from {dept}.",
        "Follow up required regarding {topic}. Best time to call is {time}.",
        "Competitor {competitor} is also in discussions. We need to highlight {feature}.",
        "Customer expressed interest in {product}. Schedule demo for next week.",
        "Contract negotiations ongoing. Legal review expected by {date}.",
        "Technical requirements gathered: {requirements}.",
        "Budget: {budget}. Timeline: {timeline}.",
    ]

    for _ in range(count):
        contact_id = random.choice(contact_ids)
        template = random.choice(note_templates)

        content = template.format(
            name=fake.name(),
            topic=fake.bs(),
            role=random.choice(['CEO', 'CTO', 'CFO', 'VP', 'Director']),
            dept=random.choice(['Finance', 'IT', 'Operations', 'Executive']),
            time=random.choice(['morning', 'afternoon', 'after 3pm']),
            competitor=fake.company(),
            feature=fake.bs(),
            product=f"{random.choice(['Pro', 'Enterprise'])} {random.choice(['Suite', 'Platform'])}",
            date=fake.date_between(start_date='today', end_date='+30d').strftime('%B %d'),
            requirements=fake.bs(),
            budget=f"${random.randint(10, 500)}K",
            timeline=f"{random.randint(1, 6)} months",
        )

        notes.append({
            'contact_id': contact_id,
            'content': content,
            'created_at': fake.date_time_between(start_date='-1y', end_date='now'),
        })

    conn.execute(
        text("""
        INSERT INTO notes (contact_id, content, created_at)
        VALUES (:contact_id, :content, :created_at)
        """),
        notes
    )
    print(f"  Created {count} notes")


def generate_tasks(conn, deal_ids, count):
    """Generate task records."""
    print(f"Generating {count} tasks...")
    tasks = []

    task_templates = [
        ('Send proposal to client', 'Prepare and send detailed proposal with pricing'),
        ('Schedule follow-up call', 'Arrange call to discuss next steps'),
        ('Prepare demo environment', 'Set up demo instance with sample data'),
        ('Review contract terms', 'Legal review of contract amendments'),
        ('Send pricing breakdown', 'Detailed cost analysis for customer'),
        ('Update CRM records', 'Ensure all contact info is current'),
        ('Prepare executive summary', 'Summary document for leadership review'),
        ('Technical requirements review', 'Validate technical specifications'),
        ('Coordinate with implementation team', 'Align on delivery timeline'),
        ('Follow up on outstanding questions', 'Address customer concerns'),
    ]

    for _ in range(count):
        deal_id = random.choice(deal_ids)
        title, description = random.choice(task_templates)

        status = random.choices(TASK_STATUSES, weights=[30, 20, 40, 10], k=1)[0]
        due_date = fake.date_between(start_date='-30d', end_date='+60d')

        completed_at = None
        if status == 'completed':
            completed_at = fake.date_time_between(
                start_date=due_date - timedelta(days=7),
                end_date=min(due_date + timedelta(days=3), datetime.now().date())
            )

        tasks.append({
            'deal_id': deal_id,
            'title': title,
            'description': description,
            'due_date': due_date,
            'status': status,
            'priority': random.choice(TASK_PRIORITIES),
            'completed_at': completed_at,
            'created_at': fake.date_time_between(start_date='-2m', end_date='now'),
        })

    conn.execute(
        text("""
        INSERT INTO tasks (deal_id, title, description, due_date, status, priority, completed_at, created_at)
        VALUES (:deal_id, :title, :description, :due_date, :status, :priority, :completed_at, :created_at)
        """),
        tasks
    )
    print(f"  Created {count} tasks")


def parse_args():
    """Parse command-line arguments (also supports environment variables)."""
    parser = argparse.ArgumentParser(
        description='Generate synthetic CRM data for PostgreSQL database.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Generate all tables with defaults
  %(prog)s --count 50                         # All tables, 50 records each
  %(prog)s --tables companies,contacts        # Only companies and contacts
  %(prog)s --tables companies:50,contacts:100 # Specific counts per table
  %(prog)s --tables all                       # Explicitly generate all tables
  %(prog)s --tables deals --count 75          # Only deals, 75 records

Environment variables (useful for Cloud Run):
  GENERATE_TABLES   - Same as --tables (e.g., "companies:5,contacts,deals")
  GENERATE_COUNT    - Same as --count (e.g., "100")
  GENERATE_NO_DEPS  - Same as --no-deps (set to "true" to enable)

Available tables: companies, contacts, deals, products, deal_products, activities, notes, tasks

Note: Dependencies are automatically included. For example, --tables deals will also
generate companies and contacts (unless --no-deps is specified).
        """
    )

    # Get defaults from environment variables
    env_tables = os.getenv('GENERATE_TABLES', 'all')
    env_count = os.getenv('GENERATE_COUNT')
    env_no_deps = os.getenv('GENERATE_NO_DEPS', '').lower() in ('true', '1', 'yes')

    parser.add_argument(
        '--tables', '-t',
        type=str,
        default=env_tables,
        help='Comma-separated list of tables to generate (or "all"). '
             'Can include counts: "companies:50,contacts:100" (default: all). '
             'Env: GENERATE_TABLES'
    )

    parser.add_argument(
        '--count', '-c',
        type=int,
        default=int(env_count) if env_count else None,
        help='Number of records to generate per table (overrides defaults, '
             'but not table-specific counts in --tables). Env: GENERATE_COUNT'
    )

    parser.add_argument(
        '--no-deps',
        action='store_true',
        default=env_no_deps,
        help='Do not auto-include dependent tables. Use existing data for dependencies. '
             'Env: GENERATE_NO_DEPS'
    )

    parser.add_argument(
        '--list-tables',
        action='store_true',
        help='List available tables and their dependencies, then exit'
    )

    return parser.parse_args()


def resolve_dependencies(tables, include_deps=True):
    """
    Resolve table dependencies and return ordered list of tables to generate.

    Args:
        tables: List of table names to generate
        include_deps: If True, automatically include dependent tables

    Returns:
        Ordered list of tables to generate (dependencies first)
    """
    if not include_deps:
        return tables

    # Build full set including dependencies
    to_generate = set(tables)
    added = True
    while added:
        added = False
        for table in list(to_generate):
            for dep in TABLE_DEPENDENCIES.get(table, []):
                if dep not in to_generate:
                    to_generate.add(dep)
                    added = True

    # Order by dependency (tables with no dependencies first)
    ordered = []
    remaining = to_generate.copy()

    while remaining:
        # Find tables whose dependencies are all in ordered
        for table in ALL_TABLES:
            if table in remaining:
                deps = TABLE_DEPENDENCIES.get(table, [])
                if all(d in ordered or d not in to_generate for d in deps):
                    ordered.append(table)
                    remaining.remove(table)
                    break

    return ordered


def parse_table_spec(tables_arg, default_count=None):
    """
    Parse the --tables argument into a dict of {table: count}.

    Args:
        tables_arg: String like "all", "companies,contacts", or "companies:50,contacts:100"
        default_count: Default count to use if not specified per-table

    Returns:
        Dict mapping table names to record counts
    """
    if tables_arg.lower() == 'all':
        tables_list = ALL_TABLES
    else:
        tables_list = [t.strip() for t in tables_arg.split(',')]

    result = {}
    for spec in tables_list:
        if ':' in spec:
            table, count_str = spec.split(':', 1)
            table = table.strip()
            count = int(count_str.strip())
        else:
            table = spec.strip()
            count = default_count if default_count else DEFAULT_COUNTS.get(table, 100)

        if table not in ALL_TABLES:
            print(f"Error: Unknown table '{table}'")
            print(f"Available tables: {', '.join(ALL_TABLES)}")
            sys.exit(1)

        result[table] = count

    return result


def fetch_existing_ids(conn, table):
    """Fetch existing IDs from a table."""
    result = conn.execute(text(f"SELECT id FROM {table}"))
    return [row[0] for row in result.fetchall()]


def fetch_contact_company_map(conn):
    """Fetch mapping of contact_id to company_id from existing data."""
    result = conn.execute(text("SELECT id, company_id FROM contacts"))
    return {row[0]: row[1] for row in result.fetchall()}


def fetch_product_prices(conn):
    """Fetch mapping of product_id to price from existing data."""
    result = conn.execute(text("SELECT id, price FROM products"))
    return {row[0]: row[1] for row in result.fetchall()}


def verify_data(conn, tables=None):
    """Verify data was inserted correctly."""
    print("\n--- Data Verification ---")

    check_tables = tables if tables else ALL_TABLES

    for table in check_tables:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
        count = result.fetchone()[0]
        print(f"  {table}: {count} records")

    print("\n--- Sample Query: Top 10 Companies by Deal Value ---")
    result = conn.execute(text("""
        SELECT c.name, COUNT(d.id) as deal_count, COALESCE(SUM(d.value), 0) as total_value
        FROM companies c
        LEFT JOIN deals d ON c.id = d.company_id
        GROUP BY c.id, c.name
        ORDER BY total_value DESC
        LIMIT 10
    """))

    for row in result.fetchall():
        print(f"  {row[0][:40]:<40} | Deals: {row[1]:>3} | Value: ${float(row[2]):>12,.2f}")


def list_tables():
    """Print available tables and their dependencies."""
    print("Available tables and dependencies:")
    print("-" * 50)
    for table in ALL_TABLES:
        deps = TABLE_DEPENDENCIES.get(table, [])
        deps_str = ', '.join(deps) if deps else '(none)'
        default = DEFAULT_COUNTS.get(table, 0)
        print(f"  {table:<15} default: {default:>4}  deps: {deps_str}")
    print("-" * 50)


def main():
    """Main function to generate CRM data."""
    args = parse_args()

    # Handle --list-tables
    if args.list_tables:
        list_tables()
        sys.exit(0)

    print("=" * 60)
    print("CRM Database Data Generator")
    print("=" * 60)

    # Parse table specifications
    table_counts = parse_table_spec(args.tables, args.count)
    requested_tables = list(table_counts.keys())

    # Resolve dependencies
    tables_to_generate = resolve_dependencies(requested_tables, include_deps=not args.no_deps)

    # Build final counts dict (use defaults for auto-included dependencies)
    final_counts = {}
    for table in tables_to_generate:
        if table in table_counts:
            final_counts[table] = table_counts[table]
        elif args.count:
            final_counts[table] = args.count
        else:
            final_counts[table] = DEFAULT_COUNTS.get(table, 100)

    engine = get_db_engine()
    print("\nConnected to database successfully!")

    # Show what will be generated
    print(f"\nTables to generate:")
    for table in tables_to_generate:
        count = final_counts[table]
        marker = "*" if table not in requested_tables else " "
        print(f"  {marker} {table}: {count} records")

    if any(t not in requested_tables for t in tables_to_generate):
        print("\n  * = auto-included dependency")

    if args.no_deps:
        # Check that dependencies exist in database
        missing_deps = []
        for table in tables_to_generate:
            for dep in TABLE_DEPENDENCIES.get(table, []):
                if dep not in tables_to_generate:
                    missing_deps.append((table, dep))
        if missing_deps:
            print("\nNote: Using existing data for dependencies:")
            for table, dep in missing_deps:
                print(f"  {table} requires existing {dep} records")

    print("\n--- Generating Data ---")

    with engine.connect() as conn:
        # Data structures to hold generated/fetched IDs
        company_ids = []
        contact_ids = []
        contact_company_map = {}
        product_data = {}
        deal_ids = []

        # Generate each table in dependency order
        for table in tables_to_generate:
            count = final_counts[table]

            if table == 'companies':
                company_ids = generate_companies(conn, count)

            elif table == 'contacts':
                # Need company_ids
                if not company_ids:
                    company_ids = fetch_existing_ids(conn, 'companies')
                    if not company_ids:
                        print("Error: No companies found. Generate companies first.")
                        sys.exit(1)
                    print(f"  Using {len(company_ids)} existing companies")
                contact_ids, contact_company_map = generate_contacts(conn, company_ids, count)

            elif table == 'products':
                product_data = generate_products(conn, count)

            elif table == 'deals':
                # Need company_ids and contact_ids
                if not company_ids:
                    company_ids = fetch_existing_ids(conn, 'companies')
                    if not company_ids:
                        print("Error: No companies found. Generate companies first.")
                        sys.exit(1)
                    print(f"  Using {len(company_ids)} existing companies")
                if not contact_ids:
                    contact_ids = fetch_existing_ids(conn, 'contacts')
                    contact_company_map = fetch_contact_company_map(conn)
                    if not contact_ids:
                        print("Error: No contacts found. Generate contacts first.")
                        sys.exit(1)
                    print(f"  Using {len(contact_ids)} existing contacts")
                deal_ids = generate_deals(conn, company_ids, contact_ids, contact_company_map, count)

            elif table == 'deal_products':
                # Need deal_ids and product_data
                if not deal_ids:
                    deal_ids = fetch_existing_ids(conn, 'deals')
                    if not deal_ids:
                        print("Error: No deals found. Generate deals first.")
                        sys.exit(1)
                    print(f"  Using {len(deal_ids)} existing deals")
                if not product_data:
                    product_data = fetch_product_prices(conn)
                    if not product_data:
                        print("Error: No products found. Generate products first.")
                        sys.exit(1)
                    print(f"  Using {len(product_data)} existing products")
                generate_deal_products(conn, deal_ids, product_data, count)

            elif table == 'activities':
                # Need contact_ids
                if not contact_ids:
                    contact_ids = fetch_existing_ids(conn, 'contacts')
                    if not contact_ids:
                        print("Error: No contacts found. Generate contacts first.")
                        sys.exit(1)
                    print(f"  Using {len(contact_ids)} existing contacts")
                generate_activities(conn, contact_ids, count)

            elif table == 'notes':
                # Need contact_ids
                if not contact_ids:
                    contact_ids = fetch_existing_ids(conn, 'contacts')
                    if not contact_ids:
                        print("Error: No contacts found. Generate contacts first.")
                        sys.exit(1)
                    print(f"  Using {len(contact_ids)} existing contacts")
                generate_notes(conn, contact_ids, count)

            elif table == 'tasks':
                # Need deal_ids
                if not deal_ids:
                    deal_ids = fetch_existing_ids(conn, 'deals')
                    if not deal_ids:
                        print("Error: No deals found. Generate deals first.")
                        sys.exit(1)
                    print(f"  Using {len(deal_ids)} existing deals")
                generate_tasks(conn, deal_ids, count)

        # Commit all changes
        conn.commit()
        print("\nAll data committed successfully!")

        # Verify data
        verify_data(conn, tables_to_generate)

    print("\n" + "=" * 60)
    print("Data generation complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
