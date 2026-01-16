#!/usr/bin/env python3
"""
CRM Database Data Generator - SQL Output Mode

Generates synthetic CRM data using Faker and outputs SQL INSERT statements.
This can be imported via gcloud sql import sql.
"""

import os
import random
import sys
from datetime import datetime, timedelta
from decimal import Decimal

from faker import Faker

# Initialize Faker
fake = Faker()
Faker.seed(42)  # For reproducibility
random.seed(42)

# Configuration - record counts
CONFIG = {
    'companies': 100,
    'contacts': 500,
    'deals': 200,
    'products': 50,
    'deal_products': 300,
    'activities': 400,
    'notes': 300,
    'tasks': 150,
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


def escape_sql(value):
    """Escape a value for SQL."""
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, datetime):
        return f"'{value.strftime('%Y-%m-%d %H:%M:%S')}'"
    if hasattr(value, 'strftime'):  # date objects
        return f"'{value.strftime('%Y-%m-%d')}'"
    # String - escape single quotes
    return "'" + str(value).replace("'", "''") + "'"


def generate_companies(count):
    """Generate company INSERT statements."""
    print(f"-- Generating {count} companies", file=sys.stderr)
    print("\n-- Companies")

    for i in range(1, count + 1):
        name = escape_sql(fake.company())
        industry = escape_sql(random.choice(INDUSTRIES))
        website = escape_sql(fake.url())
        address = escape_sql(fake.street_address())
        city = escape_sql(fake.city())
        state = escape_sql(fake.state_abbr())
        country = escape_sql('USA')
        postal_code = escape_sql(fake.zipcode())
        phone = escape_sql(fake.phone_number())
        employee_count = random.randint(10, 10000)
        annual_revenue = f"{random.randint(100000, 100000000)}.00"
        created_at = escape_sql(fake.date_time_between(start_date='-3y', end_date='now'))

        print(f"INSERT INTO companies (id, name, industry, website, address, city, state, country, postal_code, phone, employee_count, annual_revenue, created_at) VALUES ({i}, {name}, {industry}, {website}, {address}, {city}, {state}, {country}, {postal_code}, {phone}, {employee_count}, {annual_revenue}, {created_at});")

    # Reset sequence
    print(f"SELECT setval('companies_id_seq', {count});")
    return list(range(1, count + 1))


def generate_contacts(company_ids, count):
    """Generate contact INSERT statements."""
    print(f"-- Generating {count} contacts", file=sys.stderr)
    print("\n-- Contacts")

    used_emails = set()
    contact_company_map = {}

    for i in range(1, count + 1):
        company_id = random.choice(company_ids)
        contact_company_map[i] = company_id
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

        is_primary = 'TRUE' if i % 5 == 0 else 'FALSE'
        created_at = escape_sql(fake.date_time_between(start_date='-2y', end_date='now'))
        linkedin = escape_sql(f"https://linkedin.com/in/{first_name.lower()}-{last_name.lower()}-{fake.uuid4()[:8]}")

        print(f"INSERT INTO contacts (id, company_id, first_name, last_name, email, phone, mobile, title, department, linkedin_url, is_primary, created_at) VALUES ({i}, {company_id}, {escape_sql(first_name)}, {escape_sql(last_name)}, {escape_sql(email)}, {escape_sql(fake.phone_number())}, {escape_sql(fake.phone_number())}, {escape_sql(title)}, {escape_sql(department)}, {linkedin}, {is_primary}, {created_at});")

    print(f"SELECT setval('contacts_id_seq', {count});")
    return list(range(1, count + 1)), contact_company_map


def generate_products(count):
    """Generate product INSERT statements."""
    print(f"-- Generating {count} products", file=sys.stderr)
    print("\n-- Products")

    product_prefixes = ['Pro', 'Enterprise', 'Basic', 'Premium', 'Ultimate', 'Starter', 'Business', 'Team']
    product_types = ['Suite', 'Platform', 'Solution', 'Package', 'Service', 'Module', 'Add-on', 'License']
    used_skus = set()
    product_prices = {}

    for i in range(1, count + 1):
        prefix = random.choice(product_prefixes)
        prod_type = random.choice(product_types)
        category = random.choice(PRODUCT_CATEGORIES)
        name = f"{prefix} {category} {prod_type}"

        sku = f"{category[:3].upper()}-{random.randint(1000, 9999)}"
        while sku in used_skus:
            sku = f"{category[:3].upper()}-{random.randint(1000, 9999)}"
        used_skus.add(sku)

        price = Decimal(random.randint(99, 99999)) + Decimal(random.randint(0, 99)) / 100
        product_prices[i] = price
        is_active = 'TRUE' if random.random() > 0.1 else 'FALSE'
        created_at = escape_sql(fake.date_time_between(start_date='-2y', end_date='now'))

        print(f"INSERT INTO products (id, name, description, price, sku, category, is_active, created_at) VALUES ({i}, {escape_sql(name)}, {escape_sql(fake.paragraph(nb_sentences=2))}, {price}, {escape_sql(sku)}, {escape_sql(category)}, {is_active}, {created_at});")

    print(f"SELECT setval('products_id_seq', {count});")
    return list(range(1, count + 1)), product_prices


def generate_deals(company_ids, contact_ids, contact_company_map, count):
    """Generate deal INSERT statements."""
    print(f"-- Generating {count} deals", file=sys.stderr)
    print("\n-- Deals")

    for i in range(1, count + 1):
        company_id = random.choice(company_ids)
        company_contacts = [cid for cid, comp_id in contact_company_map.items() if comp_id == company_id]
        contact_id = random.choice(company_contacts) if company_contacts else 'NULL'

        stage = random.choice(list(DEAL_STAGES.keys()))
        probability = DEAL_STAGES[stage]
        if stage not in ('closed_won', 'closed_lost'):
            probability = max(0, min(100, probability + random.randint(-10, 10)))

        value = Decimal(random.randint(1000, 500000))
        expected_close = escape_sql(fake.date_between(start_date='-6m', end_date='+6m'))

        actual_close = 'NULL'
        if stage in ('closed_won', 'closed_lost'):
            actual_close = escape_sql(fake.date_between(start_date='-6m', end_date='today'))

        title = escape_sql(f"{fake.bs().title()} Project")
        description = escape_sql(fake.paragraph(nb_sentences=2))
        source = escape_sql(random.choice(DEAL_SOURCES))
        created_at = escape_sql(fake.date_time_between(start_date='-1y', end_date='now'))

        print(f"INSERT INTO deals (id, company_id, contact_id, title, description, value, stage, probability, expected_close_date, actual_close_date, source, created_at) VALUES ({i}, {company_id}, {contact_id}, {title}, {description}, {value}, {escape_sql(stage)}, {probability}, {expected_close}, {actual_close}, {source}, {created_at});")

    print(f"SELECT setval('deals_id_seq', {count});")
    return list(range(1, count + 1))


def generate_deal_products(deal_ids, product_ids, product_prices, count):
    """Generate deal_products INSERT statements."""
    print(f"-- Generating {count} deal-product associations", file=sys.stderr)
    print("\n-- Deal Products")

    used_pairs = set()
    dp_id = 0

    while dp_id < count:
        deal_id = random.choice(deal_ids)
        product_id = random.choice(product_ids)

        pair = (deal_id, product_id)
        if pair in used_pairs:
            continue
        used_pairs.add(pair)
        dp_id += 1

        base_price = product_prices[product_id]
        unit_price = round(base_price * Decimal(random.uniform(0.8, 1.2)), 2)
        quantity = random.randint(1, 20)
        discount = random.choice([0, 0, 0, 5, 10, 15, 20])

        print(f"INSERT INTO deal_products (id, deal_id, product_id, quantity, unit_price, discount_percent) VALUES ({dp_id}, {deal_id}, {product_id}, {quantity}, {unit_price}, {discount});")

    print(f"SELECT setval('deal_products_id_seq', {dp_id});")


def generate_activities(contact_ids, count):
    """Generate activity INSERT statements."""
    print(f"-- Generating {count} activities", file=sys.stderr)
    print("\n-- Activities")

    activity_subjects = {
        'call': ['Initial discovery call', 'Follow-up call', 'Product discussion', 'Pricing call', 'Check-in call', 'Support call'],
        'email': ['Introduction email', 'Proposal sent', 'Follow-up email', 'Meeting confirmation', 'Thank you email', 'Contract sent'],
        'meeting': ['Product demo', 'Strategy meeting', 'Kickoff meeting', 'Quarterly review', 'Executive presentation', 'Technical deep-dive'],
        'demo': ['Product walkthrough', 'Feature demonstration', 'Technical demo', 'POC presentation', 'Solution overview'],
        'follow_up': ['Post-meeting follow-up', 'Proposal follow-up', 'Contract follow-up', 'Decision check-in', 'Next steps discussion'],
    }

    for i in range(1, count + 1):
        contact_id = random.choice(contact_ids)
        activity_type = random.choice(ACTIVITY_TYPES)
        subject = escape_sql(random.choice(activity_subjects[activity_type]))
        notes = escape_sql(fake.paragraph(nb_sentences=3)) if random.random() > 0.3 else 'NULL'
        duration = random.randint(5, 120) if activity_type in ('call', 'meeting', 'demo') else 'NULL'
        activity_date = escape_sql(fake.date_time_between(start_date='-1y', end_date='now'))

        print(f"INSERT INTO activities (id, contact_id, type, subject, notes, duration_minutes, activity_date) VALUES ({i}, {contact_id}, {escape_sql(activity_type)}, {subject}, {notes}, {duration}, {activity_date});")

    print(f"SELECT setval('activities_id_seq', {count});")


def generate_notes(contact_ids, count):
    """Generate note INSERT statements."""
    print(f"-- Generating {count} notes", file=sys.stderr)
    print("\n-- Notes")

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

    for i in range(1, count + 1):
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

        created_at = escape_sql(fake.date_time_between(start_date='-1y', end_date='now'))
        print(f"INSERT INTO notes (id, contact_id, content, created_at) VALUES ({i}, {contact_id}, {escape_sql(content)}, {created_at});")

    print(f"SELECT setval('notes_id_seq', {count});")


def generate_tasks(deal_ids, count):
    """Generate task INSERT statements."""
    print(f"-- Generating {count} tasks", file=sys.stderr)
    print("\n-- Tasks")

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

    for i in range(1, count + 1):
        deal_id = random.choice(deal_ids)
        title, description = random.choice(task_templates)

        status = random.choices(TASK_STATUSES, weights=[30, 20, 40, 10], k=1)[0]
        priority = random.choice(TASK_PRIORITIES)
        due_date = fake.date_between(start_date='-30d', end_date='+60d')

        completed_at = 'NULL'
        if status == 'completed':
            completed_at = escape_sql(fake.date_time_between(
                start_date=due_date - timedelta(days=7),
                end_date=min(due_date + timedelta(days=3), datetime.now().date())
            ))

        created_at = escape_sql(fake.date_time_between(start_date='-2m', end_date='now'))

        print(f"INSERT INTO tasks (id, deal_id, title, description, due_date, status, priority, completed_at, created_at) VALUES ({i}, {deal_id}, {escape_sql(title)}, {escape_sql(description)}, {escape_sql(due_date)}, {escape_sql(status)}, {escape_sql(priority)}, {completed_at}, {created_at});")

    print(f"SELECT setval('tasks_id_seq', {count});")


def main():
    """Generate SQL insert statements for all CRM data."""
    print("-- CRM Sample Data")
    print("-- Generated by generate_data_sql.py")
    print(f"-- Generated at: {datetime.now().isoformat()}")
    print("")
    print("BEGIN;")

    # Generate data in dependency order
    company_ids = generate_companies(CONFIG['companies'])
    contact_ids, contact_company_map = generate_contacts(company_ids, CONFIG['contacts'])
    product_ids, product_prices = generate_products(CONFIG['products'])
    deal_ids = generate_deals(company_ids, contact_ids, contact_company_map, CONFIG['deals'])
    generate_deal_products(deal_ids, product_ids, product_prices, CONFIG['deal_products'])
    generate_activities(contact_ids, CONFIG['activities'])
    generate_notes(contact_ids, CONFIG['notes'])
    generate_tasks(deal_ids, CONFIG['tasks'])

    print("")
    print("COMMIT;")
    print(f"-- Generation complete", file=sys.stderr)


if __name__ == '__main__':
    main()
