#!/bin/bash
# Bootstrap: Deploy the deployer service account
# This service account will be used to deploy all other infrastructure
#
# Usage: ./deploy-service-account.sh <project_id>
#
# This script is idempotent - it checks for existing resources before creating

set -e

# Configuration
PROJECT_ID="${1:-rnd-dev-asheesh}"
SA_NAME="crm-deployer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=============================================="
echo "Bootstrap: Deployer Service Account Setup"
echo "=============================================="
echo "Project: ${PROJECT_ID}"
echo "Service Account: ${SA_EMAIL}"
echo ""

# Set project
gcloud config set project "${PROJECT_ID}" --quiet

# Check if service account already exists
echo "Checking if service account exists..."
if gcloud iam service-accounts describe "${SA_EMAIL}" &>/dev/null; then
    echo "✓ Service account '${SA_NAME}' already exists, skipping creation"
else
    echo "Creating service account '${SA_NAME}'..."
    gcloud iam service-accounts create "${SA_NAME}" \
        --display-name="CRM Infrastructure Deployer" \
        --description="Service account for deploying CRM infrastructure resources"
    echo "✓ Service account created"
fi

# Define required roles for the deployer
# These roles allow the deployer to manage Cloud SQL, Secret Manager, Cloud Run, and related resources
REQUIRED_ROLES=(
    "roles/cloudsql.admin"           # Manage Cloud SQL instances and databases
    "roles/secretmanager.admin"      # Manage secrets in Secret Manager
    "roles/run.admin"                # Manage Cloud Run jobs and services
    "roles/storage.admin"            # Access Cloud Storage for SQL imports
    "roles/iam.serviceAccountUser"   # Use service accounts for Cloud Run
    "roles/artifactregistry.admin"   # Push container images
    "roles/cloudbuild.builds.builder" # Run Cloud Build
)

echo ""
echo "Granting IAM roles to deployer service account..."

for role in "${REQUIRED_ROLES[@]}"; do
    echo "  Checking role: ${role}"

    # Check if binding already exists
    existing=$(gcloud projects get-iam-policy "${PROJECT_ID}" \
        --flatten="bindings[].members" \
        --filter="bindings.role:${role} AND bindings.members:serviceAccount:${SA_EMAIL}" \
        --format="value(bindings.members)" 2>/dev/null || true)

    if [[ -n "${existing}" ]]; then
        echo "    ✓ Role already granted"
    else
        gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
            --member="serviceAccount:${SA_EMAIL}" \
            --role="${role}" \
            --quiet >/dev/null
        echo "    ✓ Role granted"
    fi
done

# Create and download key (optional - for CI/CD pipelines)
KEY_FILE="./deployer-key.json"
if [[ "${2}" == "--create-key" ]]; then
    echo ""
    echo "Creating service account key..."
    if [[ -f "${KEY_FILE}" ]]; then
        echo "  Key file already exists at ${KEY_FILE}"
        read -p "  Overwrite? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            gcloud iam service-accounts keys create "${KEY_FILE}" \
                --iam-account="${SA_EMAIL}"
            echo "  ✓ Key created at ${KEY_FILE}"
        fi
    else
        gcloud iam service-accounts keys create "${KEY_FILE}" \
            --iam-account="${SA_EMAIL}"
        echo "  ✓ Key created at ${KEY_FILE}"
    fi
    echo ""
    echo "  WARNING: Keep this key secure and add it to .gitignore"
fi

echo ""
echo "=============================================="
echo "Bootstrap Complete"
echo "=============================================="
echo ""
echo "Deployer Service Account: ${SA_EMAIL}"
echo ""
echo "To use this service account for deployments:"
echo "  1. Impersonate: gcloud config set auth/impersonate_service_account ${SA_EMAIL}"
echo "  2. Or use key:  export GOOGLE_APPLICATION_CREDENTIALS=./deployer-key.json"
echo ""
echo "Next steps:"
echo "  1. Run: ./infra/sql/deploy.sh"
echo "  2. Run: ./infra/secrets/deploy.sh"
echo "  3. Run: ./infra/cloudrun/deploy.sh"
echo ""
