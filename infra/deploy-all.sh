#!/bin/bash
# Main deployment orchestrator for CRM infrastructure
# Deploys all components in the correct order with idempotency checks
#
# Usage: ./deploy-all.sh [options]
#   --project=PROJECT_ID    GCP project ID (default: rnd-dev-asheesh)
#   --bootstrap             Run bootstrap (deployer service account) first
#   --skip-sql              Skip Cloud SQL deployment
#   --skip-secrets          Skip Secret Manager deployment
#   --skip-cloudrun         Skip Cloud Run deployment
#   --build                 Build Docker images
#   --execute               Execute Cloud Run job after deployment
#   --db-password=PASSWORD  Database password (will prompt if not provided)

set -e

# Default configuration
PROJECT_ID="rnd-dev-asheesh"
RUN_BOOTSTRAP=false
SKIP_SQL=false
SKIP_SECRETS=false
SKIP_CLOUDRUN=false
BUILD_IMAGES=false
EXECUTE_JOB=false
DB_PASSWORD=""

# Parse arguments
for arg in "$@"; do
    case $arg in
        --project=*)
            PROJECT_ID="${arg#*=}"
            ;;
        --bootstrap)
            RUN_BOOTSTRAP=true
            ;;
        --skip-sql)
            SKIP_SQL=true
            ;;
        --skip-secrets)
            SKIP_SECRETS=true
            ;;
        --skip-cloudrun)
            SKIP_CLOUDRUN=true
            ;;
        --build)
            BUILD_IMAGES=true
            ;;
        --execute)
            EXECUTE_JOB=true
            ;;
        --db-password=*)
            DB_PASSWORD="${arg#*=}"
            ;;
        --help)
            echo "Usage: ./deploy-all.sh [options]"
            echo ""
            echo "Options:"
            echo "  --project=PROJECT_ID    GCP project ID (default: rnd-dev-asheesh)"
            echo "  --bootstrap             Run bootstrap (deployer service account) first"
            echo "  --skip-sql              Skip Cloud SQL deployment"
            echo "  --skip-secrets          Skip Secret Manager deployment"
            echo "  --skip-cloudrun         Skip Cloud Run deployment"
            echo "  --build                 Build Docker images"
            echo "  --execute               Execute Cloud Run job after deployment"
            echo "  --db-password=PASSWORD  Database password"
            echo "  --help                  Show this help message"
            exit 0
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║       CRM Infrastructure Deployment                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Project: ${PROJECT_ID}"
echo ""
echo "Deployment Plan:"
[[ "${RUN_BOOTSTRAP}" == "true" ]] && echo "  1. [✓] Bootstrap (Deployer Service Account)" || echo "  1. [−] Bootstrap (skipped)"
[[ "${SKIP_SQL}" == "false" ]] && echo "  2. [✓] Cloud SQL (Instance, Database, Schema)" || echo "  2. [−] Cloud SQL (skipped)"
[[ "${SKIP_SECRETS}" == "false" ]] && echo "  3. [✓] Secret Manager (Credentials)" || echo "  3. [−] Secret Manager (skipped)"
[[ "${SKIP_CLOUDRUN}" == "false" ]] && echo "  4. [✓] Cloud Run (Data Generator Job)" || echo "  4. [−] Cloud Run (skipped)"
echo ""

# Confirm before proceeding
read -p "Proceed with deployment? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

# Track deployment status
DEPLOYMENT_STATUS=()

# ============================================
# Phase 1: Bootstrap (Optional)
# ============================================
if [[ "${RUN_BOOTSTRAP}" == "true" ]]; then
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "Phase 1: Bootstrap - Deployer Service Account"
    echo "═══════════════════════════════════════════════════════════"

    if bash "${SCRIPT_DIR}/bootstrap/deploy-service-account.sh" "${PROJECT_ID}"; then
        DEPLOYMENT_STATUS+=("Bootstrap: ✓ Success")
    else
        DEPLOYMENT_STATUS+=("Bootstrap: ✗ Failed")
        echo "ERROR: Bootstrap failed. Stopping deployment."
        exit 1
    fi
fi

# ============================================
# Phase 2: Cloud SQL
# ============================================
if [[ "${SKIP_SQL}" == "false" ]]; then
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "Phase 2: Cloud SQL Deployment"
    echo "═══════════════════════════════════════════════════════════"

    if bash "${SCRIPT_DIR}/sql/deploy.sh" --project="${PROJECT_ID}"; then
        DEPLOYMENT_STATUS+=("Cloud SQL: ✓ Success")
    else
        DEPLOYMENT_STATUS+=("Cloud SQL: ✗ Failed")
        echo "ERROR: Cloud SQL deployment failed. Stopping deployment."
        exit 1
    fi
fi

# ============================================
# Phase 3: Secret Manager
# ============================================
if [[ "${SKIP_SECRETS}" == "false" ]]; then
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "Phase 3: Secret Manager Deployment"
    echo "═══════════════════════════════════════════════════════════"

    SECRET_ARGS="--project=${PROJECT_ID}"
    if [[ -n "${DB_PASSWORD}" ]]; then
        SECRET_ARGS="${SECRET_ARGS} --db-password=${DB_PASSWORD}"
    fi

    if bash "${SCRIPT_DIR}/secrets/deploy.sh" ${SECRET_ARGS}; then
        DEPLOYMENT_STATUS+=("Secrets: ✓ Success")
    else
        DEPLOYMENT_STATUS+=("Secrets: ✗ Failed")
        echo "WARNING: Secret deployment failed. Continuing..."
    fi
fi

# ============================================
# Phase 4: Cloud Run
# ============================================
if [[ "${SKIP_CLOUDRUN}" == "false" ]]; then
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "Phase 4: Cloud Run Deployment"
    echo "═══════════════════════════════════════════════════════════"

    CLOUDRUN_ARGS="--project=${PROJECT_ID}"
    [[ "${BUILD_IMAGES}" == "true" ]] && CLOUDRUN_ARGS="${CLOUDRUN_ARGS} --build"
    [[ "${EXECUTE_JOB}" == "true" ]] && CLOUDRUN_ARGS="${CLOUDRUN_ARGS} --execute"

    if bash "${SCRIPT_DIR}/cloudrun/deploy.sh" ${CLOUDRUN_ARGS}; then
        DEPLOYMENT_STATUS+=("Cloud Run: ✓ Success")
    else
        DEPLOYMENT_STATUS+=("Cloud Run: ✗ Failed")
        echo "WARNING: Cloud Run deployment failed."
    fi
fi

# ============================================
# Summary
# ============================================
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║       Deployment Summary                                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
for status in "${DEPLOYMENT_STATUS[@]}"; do
    echo "  ${status}"
done
echo ""
echo "Deployment complete!"
echo ""
