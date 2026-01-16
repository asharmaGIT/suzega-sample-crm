#!/bin/bash
# Deploy Cloud Run Job for data generation
# This script is idempotent - it checks for existing resources before creating
#
# Usage: ./deploy.sh [options]
#   --project=PROJECT_ID    GCP project ID (default: rnd-dev-asheesh)
#   --region=REGION         Region (default: us-central1)
#   --instance=INSTANCE     Cloud SQL instance name (default: ithara-db)
#   --database=DATABASE     Database name (default: crm_db)
#   --build                 Build and push Docker image
#   --execute               Execute the job after deployment

set -e

# Default configuration
PROJECT_ID="rnd-dev-asheesh"
REGION="us-central1"
INSTANCE_NAME="ithara-db"
DATABASE_NAME="crm_db"
JOB_NAME="crm-data-generator"
IMAGE_NAME="gcr.io/${PROJECT_ID}/crm-data-generator"
BUILD_IMAGE=false
EXECUTE_JOB=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --project=*)
            PROJECT_ID="${arg#*=}"
            IMAGE_NAME="gcr.io/${PROJECT_ID}/crm-data-generator"
            ;;
        --region=*)
            REGION="${arg#*=}"
            ;;
        --instance=*)
            INSTANCE_NAME="${arg#*=}"
            ;;
        --database=*)
            DATABASE_NAME="${arg#*=}"
            ;;
        --build)
            BUILD_IMAGE=true
            ;;
        --execute)
            EXECUTE_JOB=true
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/../.."
CONNECTION_NAME="${PROJECT_ID}:${REGION}:${INSTANCE_NAME}"

echo "=============================================="
echo "Cloud Run Job Deployment"
echo "=============================================="
echo "Project:    ${PROJECT_ID}"
echo "Region:     ${REGION}"
echo "Job Name:   ${JOB_NAME}"
echo "Image:      ${IMAGE_NAME}"
echo "Connection: ${CONNECTION_NAME}"
echo ""

# Set project
gcloud config set project "${PROJECT_ID}" --quiet

# Enable required APIs
echo "Ensuring required APIs are enabled..."
gcloud services enable run.googleapis.com --quiet
gcloud services enable artifactregistry.googleapis.com --quiet
echo "✓ APIs enabled"

# ============================================
# Step 1: Check for VPC Connector
# ============================================
echo ""
echo "--- Step 1: VPC Connector ---"

VPC_CONNECTOR=$(gcloud compute networks vpc-access connectors list \
    --region="${REGION}" \
    --format="value(name)" \
    --limit=1 2>/dev/null || echo "")

if [[ -n "${VPC_CONNECTOR}" ]]; then
    echo "✓ Found VPC connector: ${VPC_CONNECTOR}"
else
    echo "⚠ No VPC connector found in ${REGION}"
    echo "  Cloud Run may not be able to connect to private Cloud SQL"
    VPC_CONNECTOR=""
fi

# ============================================
# Step 2: Build Docker Image (optional)
# ============================================
echo ""
echo "--- Step 2: Docker Image ---"

if [[ "${BUILD_IMAGE}" == "true" ]]; then
    echo "Building Docker image..."

    # Check for Dockerfile in src directory
    DOCKERFILE="${PROJECT_ROOT}/src/Dockerfile"
    if [[ ! -f "${DOCKERFILE}" ]]; then
        echo "ERROR: Dockerfile not found at ${DOCKERFILE}"
        exit 1
    fi

    gcloud builds submit "${PROJECT_ROOT}/src" \
        --tag "${IMAGE_NAME}" \
        --quiet

    echo "✓ Image built and pushed: ${IMAGE_NAME}"
else
    # Check if image exists
    if gcloud container images describe "${IMAGE_NAME}:latest" &>/dev/null; then
        echo "✓ Image exists: ${IMAGE_NAME}"
    else
        echo "⚠ Image not found. Run with --build to create it."
        echo "  Or manually: gcloud builds submit src/ --tag ${IMAGE_NAME}"
    fi
fi

# ============================================
# Step 3: Check for Secret
# ============================================
echo ""
echo "--- Step 3: Database Secret ---"

SECRET_NAME="crm-db-password"
if gcloud secrets describe "${SECRET_NAME}" &>/dev/null; then
    # Get latest version
    SECRET_VERSION=$(gcloud secrets versions list "${SECRET_NAME}" \
        --filter="state=ENABLED" \
        --format="value(name)" \
        --limit=1 | tail -1)
    echo "✓ Secret '${SECRET_NAME}' exists (version: ${SECRET_VERSION})"
else
    echo "ERROR: Secret '${SECRET_NAME}' not found"
    echo "  Run: ./infra/secrets/deploy.sh first"
    exit 1
fi

# ============================================
# Step 4: Determine Service Account
# ============================================
echo ""
echo "--- Step 4: Service Account ---"

# Try to find a suitable service account
RUNTIME_SA=""
for sa in "ithara-runtime" "crm-runtime" "default"; do
    SA_EMAIL="${sa}@${PROJECT_ID}.iam.gserviceaccount.com"
    if [[ "${sa}" == "default" ]]; then
        SA_EMAIL="${PROJECT_ID}@appspot.gserviceaccount.com"
    fi

    if gcloud iam service-accounts describe "${SA_EMAIL}" &>/dev/null; then
        RUNTIME_SA="${SA_EMAIL}"
        echo "✓ Using service account: ${RUNTIME_SA}"
        break
    fi
done

if [[ -z "${RUNTIME_SA}" ]]; then
    echo "⚠ No suitable service account found, using default compute"
    RUNTIME_SA=""
fi

# ============================================
# Step 5: Create or Update Cloud Run Job
# ============================================
echo ""
echo "--- Step 5: Cloud Run Job ---"

# Build the gcloud command
CMD="gcloud run jobs"

if gcloud run jobs describe "${JOB_NAME}" --region="${REGION}" &>/dev/null; then
    echo "Job '${JOB_NAME}' exists, updating..."
    CMD="${CMD} update ${JOB_NAME}"
else
    echo "Creating job '${JOB_NAME}'..."
    CMD="${CMD} create ${JOB_NAME} --image=${IMAGE_NAME}"
fi

# Add common options
CMD="${CMD} --region=${REGION}"
CMD="${CMD} --set-env-vars=INSTANCE_CONNECTION_NAME=${CONNECTION_NAME}"
CMD="${CMD} --set-env-vars=DB_NAME=${DATABASE_NAME}"
CMD="${CMD} --set-env-vars=DB_USER=postgres"
CMD="${CMD} --set-env-vars=IP_TYPE=PRIVATE"
CMD="${CMD} --set-secrets=DB_PASSWORD=${SECRET_NAME}:${SECRET_VERSION}"
CMD="${CMD} --task-timeout=1800"
CMD="${CMD} --max-retries=1"

# Add VPC connector if available
if [[ -n "${VPC_CONNECTOR}" ]]; then
    CMD="${CMD} --vpc-connector=${VPC_CONNECTOR}"
fi

# Add service account if available
if [[ -n "${RUNTIME_SA}" ]]; then
    CMD="${CMD} --service-account=${RUNTIME_SA}"
fi

# Execute the command
eval "${CMD}"
echo "✓ Job deployed"

# ============================================
# Step 6: Execute Job (optional)
# ============================================
if [[ "${EXECUTE_JOB}" == "true" ]]; then
    echo ""
    echo "--- Step 6: Execute Job ---"
    echo "Executing job..."
    gcloud run jobs execute "${JOB_NAME}" --region="${REGION}" --wait
    echo "✓ Job executed"
fi

# ============================================
# Summary
# ============================================
echo ""
echo "=============================================="
echo "Cloud Run Job Deployment Complete"
echo "=============================================="
echo ""
echo "Job Name: ${JOB_NAME}"
echo "Region:   ${REGION}"
echo "Image:    ${IMAGE_NAME}"
echo ""
echo "To execute the job:"
echo "  gcloud run jobs execute ${JOB_NAME} --region=${REGION}"
echo ""
echo "To view logs:"
echo "  gcloud logging read 'resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${JOB_NAME}\"' --limit=50"
echo ""
