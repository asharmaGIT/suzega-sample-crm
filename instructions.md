# Project Instructions: CRM Sample Database on GCP

This document provides comprehensive instructions for creating a sample CRM database project on Google Cloud Platform. Use this as a reference or prompt for future similar projects.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Target Environment](#target-environment)
3. [Application Specifications](#application-specifications)
4. [Folder Structure](#folder-structure)
5. [Database Schema Design](#database-schema-design)
6. [Code Implementation](#code-implementation)
7. [Infrastructure Deployment](#infrastructure-deployment)
8. [Cloud Run Job Configuration](#cloud-run-job-configuration)
9. [Scheduling with Cloud Scheduler](#scheduling-with-cloud-scheduler)
10. [Common Issues and Solutions](#common-issues-and-solutions)
11. [Best Practices](#best-practices)
12. [Useful Commands Reference](#useful-commands-reference)

---

## Project Overview

### Objective
Create a sample CRM (Customer Relationship Management) database populated with synthetic data for testing, development, and demonstration purposes.

### Key Components
- **Database**: PostgreSQL on GCP Cloud SQL
- **Data Generator**: Python script using Faker library
- **Execution**: Cloud Run Job (serverless)
- **Scheduling**: Cloud Scheduler for automated runs
- **Infrastructure**: Idempotent deployment scripts

### Data Volume
- ~2,000+ records across 8 tables
- Configurable record counts per table
- Supports incremental data generation

---

## Target Environment

### Google Cloud Platform Services
| Service | Purpose |
|---------|---------|
| Cloud SQL (PostgreSQL 15) | Database hosting |
| Cloud Run Jobs | Serverless job execution |
| Cloud Build | Docker image building |
| Container Registry (GCR) | Docker image storage |
| Secret Manager | Credential storage |
| Cloud Scheduler | Job scheduling |
| VPC Connector | Private network access |

### Instance Specifications
```
Cloud SQL:
  - Instance type: db-f1-micro (smallest, ~$7-10/month)
  - Database version: PostgreSQL 15
  - Region: us-central1
  - Network: Private IP preferred (org policy may require)

Cloud Run Job:
  - Memory: 512Mi (default)
  - CPU: 1
  - Timeout: 1800 seconds (30 minutes)
  - Max retries: 1
  - VPC Connector: Required for private Cloud SQL access
```

### Network Configuration
- Cloud SQL with private IP requires VPC connector for Cloud Run
- If using public IP, whitelist specific IPs for security
- Cloud SQL Auth Proxy available for local development

---

## Application Specifications

### Data Model - CRM Entities

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│  companies  │───┬───│  contacts   │───┬───│ activities  │
└─────────────┘   │   └─────────────┘   │   └─────────────┘
                  │          │          │
                  │          │          └───│   notes     │
                  │          │              └─────────────┘
                  │          │
                  └───│    deals    │───┬───│   tasks     │
                      └─────────────┘   │   └─────────────┘
                             │          │
                      ┌──────┴──────┐   │
                      │             │   │
                ┌─────────────┐     │   │
                │  products   │─────┴───┘
                └─────────────┘
                      │
              ┌───────────────┐
              │ deal_products │
              └───────────────┘
```

### Table Specifications

| Table | Description | Default Count | Key Fields |
|-------|-------------|---------------|------------|
| companies | Customer organizations | 100 | name, industry, website, employee_count, annual_revenue |
| contacts | People at companies | 500 | first_name, last_name, email (unique), title, department |
| deals | Sales opportunities | 200 | title, value, stage, probability, expected_close_date |
| products | Products/services | 50 | name, price, sku (unique), category |
| deal_products | Products in deals (junction) | 300 | deal_id, product_id, quantity, unit_price |
| activities | Interactions (calls, emails, meetings) | 400 | type, subject, activity_date, duration_minutes |
| notes | Notes about contacts | 300 | content, created_at |
| tasks | Tasks for deals | 150 | title, due_date, status, priority |

### Deal Stages & Probabilities
```python
DEAL_STAGES = {
    'prospecting': 10,
    'qualification': 25,
    'proposal': 50,
    'negotiation': 75,
    'closed_won': 100,
    'closed_lost': 0,
}
```

---

## Folder Structure

```
project-root/
├── README.md                      # Project documentation
├── .env.example                   # Environment template
├── .gitignore                     # Git ignore rules
├── cloudbuild.yaml               # Cloud Build config (optional)
│
├── src/                          # Application source code
│   ├── Dockerfile                # Container definition
│   ├── generate_data.py          # Main data generator script
│   ├── requirements.txt          # Python dependencies
│   └── schema.sql                # Database schema
│
└── infra/                        # Infrastructure deployment
    ├── deploy-all.sh             # Main orchestrator
    │
    ├── bootstrap/                # Phase 1: Service accounts
    │   └── deploy-service-account.sh
    │
    ├── sql/                      # Phase 2: Database
    │   ├── deploy.sh
    │   └── schema.sql
    │
    ├── secrets/                  # Phase 3: Credentials
    │   └── deploy.sh
    │
    └── cloudrun/                 # Phase 4: Job deployment
        └── deploy.sh
```

### File Purposes

| File | Purpose |
|------|---------|
| `src/generate_data.py` | Python script with CLI for generating synthetic CRM data |
| `src/Dockerfile` | Container image definition using python:3.11-slim base |
| `src/requirements.txt` | Python dependencies (faker, sqlalchemy, pg8000, cloud-sql-python-connector) |
| `src/schema.sql` | PostgreSQL DDL for all tables, indexes, and triggers |
| `infra/deploy-all.sh` | Orchestrates all deployment phases with skip options |
| `infra/bootstrap/deploy-service-account.sh` | Creates deployer service account with IAM roles |
| `infra/sql/deploy.sh` | Creates Cloud SQL instance, database, imports schema |
| `infra/secrets/deploy.sh` | Creates/updates secrets in Secret Manager |
| `infra/cloudrun/deploy.sh` | Deploys Cloud Run Job with proper configuration |

---

## Database Schema Design

### Schema File Structure (schema.sql)

```sql
-- 1. Drop existing tables (for clean deploys)
DROP TABLE IF EXISTS table_name CASCADE;

-- 2. Create tables with proper types and constraints
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    -- ... other fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Create indexes on frequently queried columns
CREATE INDEX idx_companies_industry ON companies(industry);
CREATE INDEX idx_contacts_company_id ON contacts(company_id);
CREATE INDEX idx_deals_stage ON deals(stage);

-- 4. Add trigger for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### Key Constraints
- Use `SERIAL` or `BIGSERIAL` for auto-increment IDs
- Add `UNIQUE` constraints on natural keys (email, sku)
- Use `REFERENCES` for foreign keys with `ON DELETE CASCADE` where appropriate
- Add `NOT NULL` on required fields
- Use appropriate data types (`DECIMAL` for money, `TIMESTAMP` for dates)

---

## Code Implementation

### Python Data Generator Structure

```python
#!/usr/bin/env python3
"""
Data Generator with CLI support and environment variable configuration.
"""

import argparse
import os
import time
from faker import Faker
import sqlalchemy
from sqlalchemy import text

# 1. Time-based seed for unique data each run
seed = int(time.time())
Faker.seed(seed)

# 2. Configuration with defaults
DEFAULT_COUNTS = {
    'companies': 100,
    'contacts': 500,
    # ...
}

# 3. Table dependencies for proper generation order
TABLE_DEPENDENCIES = {
    'companies': [],
    'contacts': ['companies'],
    'deals': ['companies', 'contacts'],
    # ...
}

# 4. Database connection supporting both Cloud SQL Connector and direct connection
def get_db_engine():
    instance_connection_name = os.getenv('INSTANCE_CONNECTION_NAME')

    if instance_connection_name:
        # Cloud SQL Python Connector (for Cloud Run)
        from google.cloud.sql.connector import Connector
        connector = Connector()
        def getconn():
            return connector.connect(
                instance_connection_name,
                "pg8000",
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                db=os.getenv('DB_NAME'),
                ip_type=os.getenv('IP_TYPE', 'PRIVATE')
            )
        engine = sqlalchemy.create_engine("postgresql+pg8000://", creator=getconn)
    else:
        # Direct connection (for local development)
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        engine = sqlalchemy.create_engine(db_url)

    return engine

# 5. CLI argument parsing with environment variable fallbacks
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tables', '-t', default=os.getenv('GENERATE_TABLES', 'all'))
    parser.add_argument('--count', '-c', type=int, default=os.getenv('GENERATE_COUNT'))
    parser.add_argument('--no-deps', action='store_true')
    return parser.parse_args()

# 6. Generate data with proper foreign key handling
def generate_contacts(conn, company_ids, count):
    for _ in range(count):
        company_id = random.choice(company_ids)
        result = conn.execute(
            text("""
                INSERT INTO contacts (company_id, first_name, ...)
                VALUES (:company_id, :first_name, ...)
                RETURNING id
            """),
            {'company_id': company_id, 'first_name': fake.first_name(), ...}
        )
        contact_ids.append(result.fetchone()[0])
    return contact_ids
```

### Key Implementation Points

1. **Use time-based seed** - Prevents duplicate key errors on repeated runs
2. **Support both connection methods** - Cloud SQL Connector for Cloud Run, direct for local
3. **Environment variables for Cloud Run** - Can't pass complex CLI args easily
4. **Single-row inserts with RETURNING** - SQLAlchemy's executemany doesn't support RETURNING
5. **Dependency resolution** - Generate parent tables before child tables
6. **Fetch existing IDs** - Support generating only specific tables using existing data

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY generate_data.py .
COPY schema.sql .

# Use ENTRYPOINT for argument passing
ENTRYPOINT ["python", "generate_data.py"]
CMD []
```

### requirements.txt

```
faker>=18.0.0
python-dotenv>=1.0.0
cloud-sql-python-connector[pg8000]>=1.0.0
pg8000>=1.30.0
sqlalchemy>=2.0.0
```

---

## Infrastructure Deployment

### Deployment Order (Bootstrap Model)

```
1. Bootstrap (Service Account)
   └── Creates deployer service account with IAM roles

2. Cloud SQL
   └── Creates instance, database, imports schema

3. Secret Manager
   └── Stores database credentials

4. Cloud Run
   └── Deploys job with proper configuration
```

### Service Account Roles Required

```bash
REQUIRED_ROLES=(
    "roles/cloudsql.admin"           # Manage Cloud SQL
    "roles/secretmanager.admin"      # Manage secrets
    "roles/run.admin"                # Manage Cloud Run
    "roles/storage.admin"            # Access GCS for SQL import
    "roles/iam.serviceAccountUser"   # Use service accounts
    "roles/artifactregistry.admin"   # Push container images
    "roles/cloudbuild.builds.builder" # Run Cloud Build
)
```

### Idempotent Deployment Pattern

```bash
# Check if resource exists before creating
if gcloud sql instances describe "${INSTANCE_NAME}" &>/dev/null; then
    echo "Instance exists, skipping creation"
else
    echo "Creating instance..."
    gcloud sql instances create "${INSTANCE_NAME}" \
        --database-version=POSTGRES_15 \
        --tier=db-f1-micro \
        --region="${REGION}"
fi
```

### Schema Import via GCS

```bash
# Direct psql connection often blocked by org policies
# Use GCS-based import instead

# 1. Upload schema to GCS
gsutil cp schema.sql gs://${BUCKET}/schema.sql

# 2. Grant Cloud SQL service account access
SA_EMAIL=$(gcloud sql instances describe ${INSTANCE} --format='value(serviceAccountEmailAddress)')
gsutil iam ch "serviceAccount:${SA_EMAIL}:objectViewer" "gs://${BUCKET}"

# 3. Import schema
gcloud sql import sql ${INSTANCE} gs://${BUCKET}/schema.sql \
    --database=${DATABASE} \
    --user=postgres
```

---

## Cloud Run Job Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `INSTANCE_CONNECTION_NAME` | Cloud SQL connection string | `project:region:instance` |
| `DB_NAME` | Database name | `crm_db` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | From Secret Manager | (secret reference) |
| `IP_TYPE` | Connection type | `PRIVATE` or `PUBLIC` |
| `GENERATE_TABLES` | Tables to generate | `companies:5,contacts,deals` |
| `GENERATE_COUNT` | Default record count | `100` |

### Job Creation Command

```bash
gcloud run jobs create ${JOB_NAME} \
    --image=${IMAGE} \
    --region=${REGION} \
    --set-env-vars="INSTANCE_CONNECTION_NAME=${CONNECTION_NAME}" \
    --set-env-vars="DB_NAME=${DATABASE}" \
    --set-env-vars="DB_USER=postgres" \
    --set-env-vars="IP_TYPE=PRIVATE" \
    --set-secrets="DB_PASSWORD=${SECRET_NAME}:latest" \
    --vpc-connector=${VPC_CONNECTOR} \
    --service-account=${SERVICE_ACCOUNT} \
    --task-timeout=1800 \
    --max-retries=1
```

### Setting Environment Variables with Special Characters

```bash
# Commas in values require special delimiter syntax
gcloud run jobs update ${JOB_NAME} \
    --update-env-vars="^@^GENERATE_TABLES=companies:5,contacts,deals@GENERATE_COUNT=100"
```

---

## Scheduling with Cloud Scheduler

### Create Scheduler Job

```bash
# Enable API
gcloud services enable cloudscheduler.googleapis.com

# Create scheduler
gcloud scheduler jobs create http ${SCHEDULER_NAME} \
    --location=${REGION} \
    --schedule="0 2 * * *" \
    --time-zone="UTC" \
    --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${JOB_NAME}:run" \
    --http-method=POST \
    --oauth-service-account-email="${SERVICE_ACCOUNT}"
```

### Common Cron Schedules

| Schedule | Cron Expression |
|----------|-----------------|
| Daily at 2 AM | `0 2 * * *` |
| Every hour | `0 * * * *` |
| Every 6 hours | `0 */6 * * *` |
| Weekly Sunday midnight | `0 0 * * 0` |
| Monthly 1st at midnight | `0 0 1 * *` |

### Grant Invoker Role

```bash
gcloud projects add-iam-policy-binding ${PROJECT} \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/run.invoker"
```

---

## Common Issues and Solutions

### 1. Duplicate Key Violation

**Problem:** Fixed Faker seed generates same data on each run.

**Solution:** Use time-based seed:
```python
import time
seed = int(time.time())
Faker.seed(seed)
random.seed(seed)
```

### 2. Organization Policy Blocks Public IP

**Problem:** `constraints/sql.restrictPublicIp` prevents public IP creation.

**Solution:**
- Use private IP with VPC connector
- Or modify org policy at project level (if permitted)

### 3. Cloud Run Can't Connect to Cloud SQL

**Problem:** Connection timeout or refused.

**Solution:**
- Ensure VPC connector is configured
- Use `IP_TYPE=PRIVATE` environment variable
- Verify service account has Cloud SQL Client role

### 4. CLI Arguments Not Parsing in Cloud Run

**Problem:** Commas in `--args` split incorrectly.

**Solution:** Use environment variables instead:
```bash
--set-env-vars="^@^GENERATE_TABLES=companies:5,contacts,deals@GENERATE_COUNT=100"
```

### 5. SQLAlchemy executemany with RETURNING

**Problem:** Batch inserts don't return generated IDs.

**Solution:** Use single-row inserts:
```python
for _ in range(count):
    result = conn.execute(text("INSERT ... RETURNING id"), params)
    ids.append(result.fetchone()[0])
```

### 6. Schema Import Fails

**Problem:** Direct psql connection blocked.

**Solution:** Use GCS-based import:
```bash
gsutil cp schema.sql gs://bucket/schema.sql
gcloud sql import sql instance gs://bucket/schema.sql --database=db
```

---

## Best Practices

### Security
- Store credentials in Secret Manager, never in code or env files
- Use service accounts with minimal required permissions
- Prefer private IP for Cloud SQL
- Whitelist specific IPs if using public IP
- Add sensitive files to .gitignore

### Code Quality
- Use type hints in Python
- Add docstrings to functions
- Implement proper error handling
- Log progress for debugging
- Make scripts idempotent

### Infrastructure
- Use Infrastructure as Code (deployment scripts)
- Make deployments idempotent (check before create)
- Use consistent naming conventions
- Tag resources for cost tracking
- Document all manual steps

### Data Generation
- Use time-based seeds for uniqueness
- Maintain referential integrity
- Generate realistic data distributions
- Support configurable record counts
- Handle existing data gracefully

---

## Useful Commands Reference

### Cloud SQL
```bash
# List instances
gcloud sql instances list

# Connect via proxy
cloud-sql-proxy PROJECT:REGION:INSTANCE

# Import schema
gcloud sql import sql INSTANCE gs://BUCKET/schema.sql --database=DB

# Reset password
gcloud sql users set-password postgres --instance=INSTANCE --password=PWD
```

### Cloud Run
```bash
# Deploy job
gcloud run jobs create JOB --image=IMAGE --region=REGION

# Execute job
gcloud run jobs execute JOB --region=REGION --wait

# View logs
gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="JOB"' --limit=50
```

### Cloud Build
```bash
# Build and push image
gcloud builds submit src/ --tag gcr.io/PROJECT/IMAGE
```

### Secret Manager
```bash
# Create secret
echo -n "value" | gcloud secrets create SECRET --data-file=-

# Access secret
gcloud secrets versions access latest --secret=SECRET
```

### Cloud Scheduler
```bash
# Create scheduler
gcloud scheduler jobs create http NAME --schedule="CRON" --uri=URL

# Trigger manually
gcloud scheduler jobs run NAME --location=REGION

# Pause/resume
gcloud scheduler jobs pause NAME
gcloud scheduler jobs resume NAME
```

---

## Example Prompt for Future Projects

Use this as a starting prompt for similar projects:

```
Create a sample [DOMAIN] database on GCP Cloud SQL (PostgreSQL) with the following:

1. Database Schema:
   - [List tables with relationships]
   - ~[X] total records

2. Data Generator:
   - Python script using Faker
   - CLI support for table selection and record counts
   - Environment variable support for Cloud Run

3. Infrastructure:
   - Idempotent deployment scripts
   - Bootstrap deployment model (service account first)
   - Cloud Run Job for execution
   - Cloud Scheduler for automation

4. Folder Structure:
   - src/ for application code
   - infra/ for deployment scripts

5. Target: GCP project [PROJECT_ID], region [REGION]

Please follow the patterns in instructions.md for implementation.
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-16 | Initial implementation |

---

*This document was created as part of the suzega-sample-crm project.*
