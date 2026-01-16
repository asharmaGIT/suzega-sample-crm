#!/bin/bash
# Deploy secrets to Secret Manager
# This script is idempotent - it checks for existing secrets before creating
#
# Usage: ./deploy.sh [options]
#   --project=PROJECT_ID    GCP project ID (default: rnd-dev-asheesh)
#   --db-password=PASSWORD  Database password to store
#   --env-file=FILE         Load secrets from .env file

set -e

# Default configuration
PROJECT_ID="rnd-dev-asheesh"
DB_PASSWORD=""
ENV_FILE=""

# Parse arguments
for arg in "$@"; do
    case $arg in
        --project=*)
            PROJECT_ID="${arg#*=}"
            ;;
        --db-password=*)
            DB_PASSWORD="${arg#*=}"
            ;;
        --env-file=*)
            ENV_FILE="${arg#*=}"
            ;;
    esac
done

# Load from env file if provided
if [[ -n "${ENV_FILE}" && -f "${ENV_FILE}" ]]; then
    echo "Loading secrets from ${ENV_FILE}..."
    source "${ENV_FILE}"
    DB_PASSWORD="${DB_PASSWORD:-${DB_PASSWORD}}"
fi

echo "=============================================="
echo "Secret Manager Deployment"
echo "=============================================="
echo "Project: ${PROJECT_ID}"
echo ""

# Set project
gcloud config set project "${PROJECT_ID}" --quiet

# Enable Secret Manager API
echo "Ensuring Secret Manager API is enabled..."
gcloud services enable secretmanager.googleapis.com --quiet
echo "✓ Secret Manager API enabled"

# ============================================
# Function to create or update a secret
# ============================================
create_or_update_secret() {
    local SECRET_NAME="$1"
    local SECRET_VALUE="$2"
    local DESCRIPTION="$3"

    if [[ -z "${SECRET_VALUE}" ]]; then
        echo "  ⚠ Skipping '${SECRET_NAME}' - no value provided"
        return 0
    fi

    echo ""
    echo "Processing secret: ${SECRET_NAME}"

    # Check if secret exists
    if gcloud secrets describe "${SECRET_NAME}" &>/dev/null; then
        echo "  ✓ Secret '${SECRET_NAME}' already exists"

        # Check if we should update the value
        read -p "  Update secret value? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -n "${SECRET_VALUE}" | gcloud secrets versions add "${SECRET_NAME}" --data-file=-
            echo "  ✓ Secret version added"
        else
            echo "  ✓ Keeping existing secret value"
        fi
    else
        echo "  Creating secret '${SECRET_NAME}'..."
        gcloud secrets create "${SECRET_NAME}" \
            --replication-policy="automatic" \
            --labels="app=crm,managed-by=infra-scripts" \
            2>/dev/null || true

        echo -n "${SECRET_VALUE}" | gcloud secrets versions add "${SECRET_NAME}" --data-file=-
        echo "  ✓ Secret created with initial version"
    fi
}

# ============================================
# Function to grant access to a secret
# ============================================
grant_secret_access() {
    local SECRET_NAME="$1"
    local SERVICE_ACCOUNT="$2"

    echo "  Granting access to ${SERVICE_ACCOUNT}..."

    # Check if binding already exists
    existing=$(gcloud secrets get-iam-policy "${SECRET_NAME}" \
        --format="value(bindings.members)" 2>/dev/null | grep "${SERVICE_ACCOUNT}" || true)

    if [[ -n "${existing}" ]]; then
        echo "    ✓ Access already granted"
    else
        gcloud secrets add-iam-policy-binding "${SECRET_NAME}" \
            --member="serviceAccount:${SERVICE_ACCOUNT}" \
            --role="roles/secretmanager.secretAccessor" \
            --quiet >/dev/null
        echo "    ✓ Access granted"
    fi
}

# ============================================
# Deploy secrets
# ============================================
echo ""
echo "--- Deploying Secrets ---"

# Database password
if [[ -z "${DB_PASSWORD}" ]]; then
    echo ""
    read -sp "Enter database password (or press Enter to skip): " DB_PASSWORD
    echo ""
fi

create_or_update_secret "crm-db-password" "${DB_PASSWORD}" "CRM database password"

# Grant access to runtime service accounts
echo ""
echo "--- Granting Access ---"

# Common service accounts that need secret access
SERVICE_ACCOUNTS=(
    "ithara-runtime@${PROJECT_ID}.iam.gserviceaccount.com"
    "crm-deployer@${PROJECT_ID}.iam.gserviceaccount.com"
)

for sa in "${SERVICE_ACCOUNTS[@]}"; do
    # Check if service account exists
    if gcloud iam service-accounts describe "${sa}" &>/dev/null; then
        grant_secret_access "crm-db-password" "${sa}"
    fi
done

# ============================================
# Summary
# ============================================
echo ""
echo "=============================================="
echo "Secret Manager Deployment Complete"
echo "=============================================="
echo ""
echo "Secrets created/updated:"
gcloud secrets list --filter="labels.app=crm" --format="table(name,createTime)" 2>/dev/null || \
    gcloud secrets list --format="table(name,createTime)" | head -5
echo ""
