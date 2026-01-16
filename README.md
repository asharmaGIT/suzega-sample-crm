# CRM Sample Database on GCP Cloud SQL

A sample CRM database with synthetic data for testing and development purposes. This project creates a PostgreSQL database on GCP Cloud SQL and populates it with realistic CRM data using Python/Faker.

## Database Schema

### Entity Relationship

```
companies (1) ──< (many) contacts
companies (1) ──< (many) deals
contacts (1) ──< (many) activities
contacts (1) ──< (many) notes
deals (1) ──< (many) products (via deal_products)
deals (1) ──< (many) tasks
```

### Tables

| Table | Description | Records |
|-------|-------------|---------|
| `companies` | Customer organizations | ~100 |
| `contacts` | People at companies | ~500 |
| `deals` | Sales opportunities | ~200 |
| `products` | Products/services offered | ~50 |
| `deal_products` | Products in each deal | ~300 |
| `activities` | Calls, emails, meetings | ~400 |
| `notes` | Notes about contacts | ~300 |
| `tasks` | Tasks related to deals | ~150 |

**Total: ~2,000 records**

## Project Structure

```
.
├── README.md                           # This file
├── .env.example                        # Environment template
├── src/                                # Application source code
│   ├── Dockerfile                      # Container image for data generator
│   ├── generate_data.py                # Python data generation script
│   ├── requirements.txt                # Python dependencies
│   └── schema.sql                      # PostgreSQL table definitions
└── infra/                              # Infrastructure deployment scripts
    ├── deploy-all.sh                   # Main orchestrator (runs all phases)
    ├── bootstrap/
    │   └── deploy-service-account.sh   # Phase 1: Deployer service account
    ├── sql/
    │   ├── deploy.sh                   # Phase 2: Cloud SQL instance & schema
    │   └── schema.sql                  # Schema file for deployment
    ├── secrets/
    │   └── deploy.sh                   # Phase 3: Secret Manager credentials
    └── cloudrun/
        └── deploy.sh                   # Phase 4: Cloud Run data generator job
```

## Prerequisites

- Google Cloud SDK (`gcloud`) installed and configured
- Access to a GCP project with billing enabled
- Required APIs will be enabled automatically by deployment scripts

## Deployment

### Quick Start (Full Deployment)

Run the main orchestrator to deploy all components:

```bash
cd infra
./deploy-all.sh --project=YOUR_PROJECT_ID --bootstrap --build --execute
```

This will:
1. Create a deployer service account with necessary IAM roles
2. Create/verify Cloud SQL instance and database
3. Deploy database schema
4. Create secrets in Secret Manager
5. Build and push Docker image
6. Create and execute Cloud Run job for data generation

### Step-by-Step Deployment

#### Phase 1: Bootstrap (Deployer Service Account)

Creates a service account with permissions to deploy all infrastructure:

```bash
./infra/bootstrap/deploy-service-account.sh YOUR_PROJECT_ID
```

Roles granted:
- `roles/cloudsql.admin` - Manage Cloud SQL
- `roles/secretmanager.admin` - Manage secrets
- `roles/run.admin` - Manage Cloud Run
- `roles/storage.admin` - Access Cloud Storage
- `roles/iam.serviceAccountUser` - Use service accounts
- `roles/artifactregistry.admin` - Push container images
- `roles/cloudbuild.builds.builder` - Run Cloud Build

#### Phase 2: Cloud SQL

Creates Cloud SQL instance, database, and deploys schema:

```bash
./infra/sql/deploy.sh --project=YOUR_PROJECT_ID
```

Options:
- `--instance=NAME` - Instance name (default: ithara-db)
- `--database=NAME` - Database name (default: crm_db)
- `--region=REGION` - Region (default: us-central1)
- `--skip-instance` - Skip instance creation check
- `--skip-database` - Skip database creation check

**Idempotent**: Checks for existing instance/database before creating.

#### Phase 3: Secrets

Creates/updates secrets in Secret Manager:

```bash
./infra/secrets/deploy.sh --project=YOUR_PROJECT_ID --db-password=YOUR_PASSWORD
```

Options:
- `--db-password=PASSWORD` - Database password (will prompt if not provided)
- `--env-file=FILE` - Load secrets from .env file

**Idempotent**: Checks for existing secrets and asks before updating.

#### Phase 4: Cloud Run

Deploys the data generator as a Cloud Run Job:

```bash
./infra/cloudrun/deploy.sh --project=YOUR_PROJECT_ID --build --execute
```

Options:
- `--region=REGION` - Region (default: us-central1)
- `--build` - Build and push Docker image
- `--execute` - Execute the job after deployment

**Idempotent**: Updates existing job if it already exists.

### Deployment Options

| Flag | Description |
|------|-------------|
| `--project=ID` | GCP project ID |
| `--bootstrap` | Run bootstrap phase first |
| `--skip-sql` | Skip Cloud SQL deployment |
| `--skip-secrets` | Skip Secret Manager deployment |
| `--skip-cloudrun` | Skip Cloud Run deployment |
| `--build` | Build Docker images |
| `--execute` | Execute Cloud Run job after deployment |
| `--db-password=PWD` | Database password |

## Local Development

### Environment Configuration

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your database credentials:
```
DB_HOST=<Cloud SQL public IP or 127.0.0.1 for proxy>
DB_PORT=5432
DB_NAME=crm_db
DB_USER=postgres
DB_PASSWORD=your_password_here
```

### Install Python Dependencies

```bash
pip install -r src/requirements.txt
```

### Run Data Generator Locally

```bash
python3 src/generate_data.py
```

## Verification

Connect to the database:
```bash
psql -h <DB_HOST> -U postgres -d crm_db
```

List tables:
```sql
\dt
```

Check record counts:
```sql
SELECT 'companies' as table_name, COUNT(*) FROM companies
UNION ALL SELECT 'contacts', COUNT(*) FROM contacts
UNION ALL SELECT 'deals', COUNT(*) FROM deals
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'deal_products', COUNT(*) FROM deal_products
UNION ALL SELECT 'activities', COUNT(*) FROM activities
UNION ALL SELECT 'notes', COUNT(*) FROM notes
UNION ALL SELECT 'tasks', COUNT(*) FROM tasks;
```

## Sample Queries

### Top companies by deal value
```sql
SELECT c.name, COUNT(d.id) as deal_count, SUM(d.value) as total_value
FROM companies c
LEFT JOIN deals d ON c.id = d.company_id
GROUP BY c.id
ORDER BY total_value DESC
LIMIT 10;
```

### Deals by stage
```sql
SELECT stage, COUNT(*) as count, SUM(value) as total_value
FROM deals
GROUP BY stage
ORDER BY count DESC;
```

### Recent activities by type
```sql
SELECT type, COUNT(*) as count
FROM activities
WHERE activity_date > NOW() - INTERVAL '30 days'
GROUP BY type
ORDER BY count DESC;
```

### Contacts with most activities
```sql
SELECT c.first_name, c.last_name, c.email, COUNT(a.id) as activity_count
FROM contacts c
JOIN activities a ON c.id = a.contact_id
GROUP BY c.id
ORDER BY activity_count DESC
LIMIT 10;
```

### Deal pipeline value
```sql
SELECT
    stage,
    COUNT(*) as deals,
    SUM(value) as total_value,
    AVG(probability) as avg_probability,
    SUM(value * probability / 100) as weighted_value
FROM deals
WHERE stage NOT IN ('closed_won', 'closed_lost')
GROUP BY stage
ORDER BY
    CASE stage
        WHEN 'prospecting' THEN 1
        WHEN 'qualification' THEN 2
        WHEN 'proposal' THEN 3
        WHEN 'negotiation' THEN 4
    END;
```

## Cost Estimate

- **db-f1-micro**: ~$7-10/month (smallest tier)
- Stop instance when not in use to reduce costs:
  ```bash
  gcloud sql instances patch ithara-db --activation-policy=NEVER
  ```
- Restart when needed:
  ```bash
  gcloud sql instances patch ithara-db --activation-policy=ALWAYS
  ```

## Cleanup

To delete all resources:
```bash
# Delete Cloud Run job
gcloud run jobs delete crm-data-generator --region=us-central1

# Delete secrets
gcloud secrets delete crm-db-password

# Delete Cloud SQL instance (WARNING: This deletes all data)
gcloud sql instances delete ithara-db
```

## License

This is sample code for demonstration purposes.
