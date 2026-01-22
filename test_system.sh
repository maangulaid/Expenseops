#!/bin/bash
#
# ExpenseOps System Test Script
#
# This script demonstrates the complete receipt processing flow:
# 1. Login to get JWT token
# 2. Upload a test receipt
# 3. Check receipt status
# 4. View audit trail
#
# Usage: ./test_system.sh
#

set -e  # Exit on error

BASE_URL="http://localhost:8000/api/v1"
ADMIN_EMAIL="admin@expenseops.local"
ADMIN_PASSWORD="Admin123!"

echo "========================================="
echo "ExpenseOps System Test"
echo "========================================="
echo ""

# Check if API is running
echo "1. Checking API health..."
HEALTH=$(curl -s ${BASE_URL%/api/v1}/health)
if [[ $HEALTH == *"healthy"* ]]; then
    echo "   ✅ API is healthy"
else
    echo "   ❌ API is not running. Start with: docker compose up -d"
    exit 1
fi
echo ""

# Login
echo "2. Logging in as admin..."
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$ADMIN_EMAIL&password=$ADMIN_PASSWORD")

TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
    echo "   ❌ Login failed. Response:"
    echo "   $LOGIN_RESPONSE"
    exit 1
fi

echo "   ✅ Login successful"
echo "   Token: ${TOKEN:0:20}..."
echo ""

# Create a test receipt image (1x1 pixel PNG)
echo "3. Creating test receipt image..."
TEST_IMAGE="/tmp/test_receipt_$(date +%s).png"
echo "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==" | base64 -d > "$TEST_IMAGE"
echo "   ✅ Test image created: $TEST_IMAGE"
echo ""

# Upload receipt
echo "4. Uploading receipt..."
UPLOAD_RESPONSE=$(curl -s -X POST "$BASE_URL/receipts" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$TEST_IMAGE")

RECEIPT_ID=$(echo $UPLOAD_RESPONSE | jq -r '.receipt_id')
RECEIPT_STATUS=$(echo $UPLOAD_RESPONSE | jq -r '.status')
CORRELATION_ID=$(echo $UPLOAD_RESPONSE | jq -r '.correlation_id')

if [ "$RECEIPT_ID" == "null" ] || [ -z "$RECEIPT_ID" ]; then
    echo "   ❌ Upload failed. Response:"
    echo "   $UPLOAD_RESPONSE"
    exit 1
fi

echo "   ✅ Upload successful"
echo "   Receipt ID: $RECEIPT_ID"
echo "   Status: $RECEIPT_STATUS"
echo "   Correlation ID: $CORRELATION_ID"
echo ""

# Wait for processing
echo "5. Waiting for worker to process receipt..."
echo "   (This may take 10-30 seconds for OCR...)"
sleep 5

MAX_WAIT=60  # seconds
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    DETAIL_RESPONSE=$(curl -s "$BASE_URL/receipts/$RECEIPT_ID" \
      -H "Authorization: Bearer $TOKEN")

    CURRENT_STATUS=$(echo $DETAIL_RESPONSE | jq -r '.status')

    if [ "$CURRENT_STATUS" == "COMPLETED" ] || [ "$CURRENT_STATUS" == "FLAGGED" ] || [ "$CURRENT_STATUS" == "FAILED" ]; then
        echo "   ✅ Processing complete: $CURRENT_STATUS"
        break
    fi

    echo "   ⏳ Still processing ($CURRENT_STATUS)... ${ELAPSED}s elapsed"
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo "   ⚠️  Processing timeout. Status: $CURRENT_STATUS"
fi
echo ""

# Get receipt details
echo "6. Fetching receipt details..."
DETAIL_RESPONSE=$(curl -s "$BASE_URL/receipts/$RECEIPT_ID" \
  -H "Authorization: Bearer $TOKEN")

echo "   Receipt Details:"
echo "$DETAIL_RESPONSE" | jq '{
  id,
  status,
  merchant_name,
  total_amount,
  transaction_date,
  uploaded_at,
  processed_at
}'
echo ""

# Get audit trail
echo "7. Fetching audit trail..."
EVENTS_RESPONSE=$(curl -s "$BASE_URL/receipts/$RECEIPT_ID/events" \
  -H "Authorization: Bearer $TOKEN")

EVENT_COUNT=$(echo $EVENTS_RESPONSE | jq 'length')
echo "   ✅ Found $EVENT_COUNT events"
echo ""
echo "   Event Timeline:"
echo "$EVENTS_RESPONSE" | jq -r '.[] | "   \(.created_at | fromdate | strftime("%H:%M:%S")) | \(.event_type) | \(.from_status // "N/A") → \(.to_status)"'
echo ""

# Summary
echo "========================================="
echo "Test Summary"
echo "========================================="
echo "Receipt ID:       $RECEIPT_ID"
echo "Final Status:     $CURRENT_STATUS"
echo "Events Logged:    $EVENT_COUNT"
echo "Correlation ID:   $CORRELATION_ID"
echo ""

if [ "$CURRENT_STATUS" == "COMPLETED" ]; then
    echo "✅ TEST PASSED - Receipt processed successfully!"
elif [ "$CURRENT_STATUS" == "FLAGGED" ]; then
    echo "⚠️  TEST PASSED - Receipt flagged by policy"
elif [ "$CURRENT_STATUS" == "FAILED" ]; then
    echo "❌ TEST FAILED - Receipt processing failed"
else
    echo "⏳ TEST INCOMPLETE - Receipt still processing"
fi
echo ""

# Cleanup
rm -f "$TEST_IMAGE"

echo "Logs:"
echo "  API:    docker compose logs api"
echo "  Worker: docker compose logs worker"
echo "  All:    docker compose logs -f"
echo ""
echo "API Documentation: http://localhost:8000/docs"
