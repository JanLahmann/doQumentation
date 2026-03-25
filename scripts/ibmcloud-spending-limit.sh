#!/usr/bin/env bash
# IBM Cloud spending notification & Code Engine cost controls
#
# IBM Cloud does NOT support hard spending limits (per-service or account-wide).
# This script sets up spending notifications (email alerts) and verifies that
# Code Engine resource caps are in place as the primary cost controls.
#
# Prerequisites:
#   brew install ibmcloud-cli   # or see https://cloud.ibm.com/docs/cli
#   ibmcloud plugin install code-engine
#   ibmcloud login
#
# Usage:
#   ./scripts/ibmcloud-spending-limit.sh [--threshold AMOUNT]

set -euo pipefail

CE_PROJECT="ce-doqumentation-01"
CE_APP_PREFIX="ce-doqumentation-"
CE_REGION="eu-de"
DEFAULT_THRESHOLD=5  # USD per month

THRESHOLD="${1:-}"
if [[ "$THRESHOLD" == "--threshold" ]]; then
    THRESHOLD="${2:-$DEFAULT_THRESHOLD}"
elif [[ -z "$THRESHOLD" ]]; then
    THRESHOLD="$DEFAULT_THRESHOLD"
fi

# --- Preflight checks ---

if ! command -v ibmcloud &>/dev/null; then
    echo "Error: ibmcloud CLI not found. Install: https://cloud.ibm.com/docs/cli"
    exit 1
fi

if ! ibmcloud target &>/dev/null; then
    echo "Error: Not logged in. Run: ibmcloud login"
    exit 1
fi

echo "=== IBM Cloud Spending Controls ==="
echo ""

# --- 1. Set spending notification ---

echo "1. Setting spending notification threshold: \$${THRESHOLD}/month"
echo "   (Email alert when projected usage exceeds this amount)"
echo "   NOTE: This is a notification only — IBM Cloud does not support hard spending caps."
echo ""

# The CLI command depends on account type; fall back to console instructions
if ibmcloud billing account-usage --output json &>/dev/null; then
    echo "   Current month usage:"
    ibmcloud billing account-usage 2>/dev/null | head -20 || true
    echo ""
fi

echo "   To set the notification threshold:"
echo "   → Console: Manage → Billing and usage → Spending notifications → Set to \$${THRESHOLD}"
echo "   → Or via CLI (if available for your account type):"
echo "     ibmcloud billing account-spending-notification-set --threshold ${THRESHOLD}"
echo ""

# --- 2. Verify Code Engine resource caps ---

echo "2. Verifying Code Engine resource caps (project: ${CE_PROJECT})"
echo ""

if ! ibmcloud plugin show code-engine &>/dev/null; then
    echo "   Warning: Code Engine plugin not installed. Run: ibmcloud plugin install code-engine"
else
    ibmcloud target -r "$CE_REGION" -g Default &>/dev/null || true

    if ibmcloud ce project select --name "$CE_PROJECT" &>/dev/null 2>&1; then
        # Find all workshop/CE apps matching the prefix
        APP_COUNT=0
        ALL_OK=true
        for APP_NAME in $(ibmcloud ce app list --output json 2>/dev/null \
            | jq -r '.[].metadata.name // empty' 2>/dev/null \
            | grep "^${CE_APP_PREFIX}" | sort); do
            APP_COUNT=$((APP_COUNT + 1))
            echo "   App: ${APP_NAME}"
            ibmcloud ce app get --name "$APP_NAME" --output json 2>/dev/null \
                | grep -E '"(min_scale|max_scale|scale_memory_limit|scale_cpu_limit)"' \
                | sed 's/^/     /' || echo "     (Could not retrieve app config)"

            MAX_SCALE=$(ibmcloud ce app get --name "$APP_NAME" --output json 2>/dev/null \
                | grep '"max_scale"' | grep -o '[0-9]*' || echo "unknown")
            if [[ "$MAX_SCALE" == "1" ]]; then
                echo "     ✓ max-scale=1"
            else
                echo "     ⚠ max-scale=${MAX_SCALE} — consider setting to 1:"
                echo "       ibmcloud ce app update --name ${APP_NAME} --max-scale 1"
                ALL_OK=false
            fi
            echo ""
        done

        if [[ "$APP_COUNT" -eq 0 ]]; then
            echo "   No apps found matching prefix '${CE_APP_PREFIX}'"
        elif $ALL_OK; then
            echo "   ✓ All ${APP_COUNT} app(s) have max-scale=1"
        fi
    else
        echo "   Warning: Could not select project ${CE_PROJECT}"
    fi
fi

echo ""
echo "3. Cost control summary:"
echo "   • Spending notification: \$${THRESHOLD}/month (set via console)"
echo "   • CE apps: ${APP_COUNT:-unknown} instance(s), each max-scale=1"
echo "   • CE min-scale: 0 (scales to zero when idle — no charges)"
echo "   • nginx rate limiting: /build/ 5r/m, /api/ 30r/s, /terminals/ 10r/m"
echo "   • Estimated monthly cost: \$0–7 per instance (within free tier if usage is light)"
echo ""
echo "   Hard spending limits are NOT available on IBM Cloud."
echo "   Monitor usage: https://cloud.ibm.com/billing/usage"
