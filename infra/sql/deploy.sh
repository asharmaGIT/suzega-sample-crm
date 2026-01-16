#!/bin/bash
# Deploy Cloud SQL instance, database, and schema
# This script is idempotent - it checks for existing resources before creating
#
# Usage: ./deploy.sh [options]
#   --project=PROJECT_ID    GCP project ID (default: rnd-dev-asheesh)
#   --instance=INSTANCE     Cloud SQL instance name (default: ithara-db)
#   --database=DATABASE     Database name (default: crm_db)
#   --region=REGION         Region (default: us-central1)
#   --skip-instance         Skip instance creation check
#   --skip-database         Skip database creation check

set -e

# Default configuration
PROJECT_ID="rnd-dev-asheesh"
INSTANCE_NAME="ithara-db"
DATABASE_NAME="crm_db"
REGION="us-central1"
SKIP_INSTANCE=false
SKIP_DATABASE=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --project=*)
            PROJECT_ID="${arg#*=}"
            ;;
        --instance=*)
            INSTANCE_NAME="${arg#*=}"
            ;;
        --database=*)
            DATABASE_NAME="${arg#*=}"
            ;;
        --region=*)
            REGION="${arg#*=}"
            ;;
        --skip-instance)
            SKIP_INSTANCE=true
            ;;
        --skip-database)
            SKIP_DATABASE=true
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEMA_FILE="${SCRIPT_DIR}/schema.sql"

echo "=============================================="
echo "Cloud SQL Deployment"
echo "=============================================="
echo "Project:  ${PROJECT_ID}"
echo "Instance: ${INSTANCE_NAME}"
echo "Database: ${DATABASE_NAME}"
echo "Region:   ${REGION}"
echo ""

# Set project
gcloud config set project "${PROJECT_ID}" --quiet

# Enable required APIs
echo "Ensuring required APIs are enabled..."
gcloud services enable sqladmin.googleapis.com --quiet
echo "✓ Cloud SQL Admin API enabled"

# ============================================
# Step 1: Check/Create Cloud SQL Instance
# ============================================
if [[ "${SKIP_INSTANCE}" == "false" ]]; then
    echo ""
    echo "--- Step 1: Cloud SQL Instance ---"

    if gcloud sql instances describe "${INSTANCE_NAME}" &>/dev/null; then
        echo "✓ Instance '${INSTANCE_NAME}' already exists, skipping creation"

        # Get instance details
        INSTANCE_INFO=$(gcloud sql instances describe "${INSTANCE_NAME}" \
            --format="value(connectionName,databaseVersion,settings.tier)")
        echo "  Connection: $(echo ${INSTANCE_INFO} | cut -d' ' -f1)"
        echo "  Version:    $(echo ${INSTANCE_INFO} | cut -d' ' -f2)"
        echo "  Tier:       $(echo ${INSTANCE_INFO} | cut -d' ' -f3)"
    else
        echo "Creating Cloud SQL instance '${INSTANCE_NAME}'..."
        echo "  This may take several minutes..."

        # Try with private IP first (org policy may require it)
        if gcloud sql instances create "${INSTANCE_NAME}" \
            --database-version=POSTGRES_15 \
            --tier=db-f1-micro \
            --region="${REGION}" \
            --no-assign-ip \
            --network=default \
            --quiet 2>/dev/null; then
            echo "✓ Instance created with private IP"
        else
            # Fall back to public IP if private IP fails
            gcloud sql instances create "${INSTANCE_NAME}" \
                --database-version=POSTGRES_15 \
                --tier=db-f1-micro \
                --region="${REGION}" \
                --quiet
            echo "✓ Instance created with public IP"
        fi
    fi
else
    echo "--- Step 1: Skipped (--skip-instance) ---"
fi

# ============================================
# Step 2: Check/Create Database
# ============================================
if [[ "${SKIP_DATABASE}" == "false" ]]; then
    echo ""
    echo "--- Step 2: Database ---"

    # Check if database exists
    if gcloud sql databases describe "${DATABASE_NAME}" --instance="${INSTANCE_NAME}" &>/dev/null; then
        echo "✓ Database '${DATABASE_NAME}' already exists, skipping creation"
    else
        echo "Creating database '${DATABASE_NAME}'..."
        gcloud sql databases create "${DATABASE_NAME}" --instance="${INSTANCE_NAME}" --quiet
        echo "✓ Database created"
    fi
else
    echo "--- Step 2: Skipped (--skip-database) ---"
fi

# ============================================
# Step 3: Deploy Schema (Tables)
# ============================================
echo ""
echo "--- Step 3: Schema Deployment ---"

if [[ ! -f "${SCHEMA_FILE}" ]]; then
    echo "ERROR: Schema file not found at ${SCHEMA_FILE}"
    exit 1
fi

# Get Cloud SQL service account for GCS access
SA_EMAIL=$(gcloud sql instances describe "${INSTANCE_NAME}" \
    --format='value(serviceAccountEmailAddress)')

# Create a temporary bucket path for schema upload
BUCKET_NAME="${PROJECT_ID}_cloudbuild"
GCS_PATH="gs://${BUCKET_NAME}/crm/schema.sql"

echo "Uploading schema to Cloud Storage..."
gsutil cp "${SCHEMA_FILE}" "${GCS_PATH}" 2>/dev/null || {
    echo "  Creating bucket and retrying..."
    gsutil mb -l "${REGION}" "gs://${BUCKET_NAME}" 2>/dev/null || true
    gsutil cp "${SCHEMA_FILE}" "${GCS_PATH}"
}

# Grant Cloud SQL service account access to bucket
echo "Granting Cloud SQL access to bucket..."
gsutil iam ch "serviceAccount:${SA_EMAIL}:objectViewer" "gs://${BUCKET_NAME}" 2>/dev/null || true

# Import schema
echo "Importing schema into database..."
gcloud sql import sql "${INSTANCE_NAME}" "${GCS_PATH}" \
    --database="${DATABASE_NAME}" \
    --user=postgres \
    --quiet

echo "✓ Schema deployed"

# ============================================
# Summary
# ============================================
echo ""
echo "=============================================="
echo "Cloud SQL Deployment Complete"
echo "=============================================="
echo ""
echo "Instance:    ${INSTANCE_NAME}"
echo "Database:    ${DATABASE_NAME}"
echo "Connection:  ${PROJECT_ID}:${REGION}:${INSTANCE_NAME}"
echo ""

# Check for public IP
PUBLIC_IP=$(gcloud sql instances describe "${INSTANCE_NAME}" \
    --format='value(ipAddresses[0].ipAddress)' 2>/dev/null || echo "None")
echo "Public IP:   ${PUBLIC_IP}"
echo ""
