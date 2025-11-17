#!/bin/bash

###############################################################################
# Test Script for Manual Research API Endpoint
###############################################################################
#
# This script tests the /execute/manual endpoint in both sync and async modes
#
# USAGE:
#   ./test_manual_research.sh sync    # Synchronous execution (get results immediately)
#   ./test_manual_research.sh async   # Asynchronous execution (webhook callback)
#
###############################################################################

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
API_KEY="${API_SECRET_KEY}"

if [ -z "$API_KEY" ]; then
    echo -e "${RED}❌ Error: API_SECRET_KEY environment variable not set${NC}"
    exit 1
fi

# Check mode
MODE="${1:-sync}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🧪 Testing Manual Research API${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "API URL: ${API_URL}"
echo -e "Mode: ${MODE}"
echo -e "${BLUE}========================================${NC}\n"

# Test research topic
RESEARCH_TOPIC="Latest developments in quantum computing"

if [ "$MODE" = "sync" ]; then
    echo -e "${YELLOW}📤 Testing SYNCHRONOUS execution...${NC}\n"

    # Synchronous request (no callback_url)
    PAYLOAD=$(cat <<EOF
{
    "research_topic": "${RESEARCH_TOPIC}",
    "email": "test@example.com"
}
EOF
)

    echo -e "${BLUE}Request:${NC}"
    echo "$PAYLOAD" | jq '.'
    echo ""

    echo -e "${YELLOW}⏳ Sending request (this may take a few minutes)...${NC}\n"

    RESPONSE=$(curl -s -X POST "${API_URL}/execute/manual" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: ${API_KEY}" \
        -d "$PAYLOAD")

    echo -e "${GREEN}✅ Response received:${NC}\n"
    echo "$RESPONSE" | jq '.'

    # Check status
    STATUS=$(echo "$RESPONSE" | jq -r '.status')

    if [ "$STATUS" = "completed" ]; then
        echo -e "\n${GREEN}========================================${NC}"
        echo -e "${GREEN}✅ Research completed successfully!${NC}"
        echo -e "${GREEN}========================================${NC}"

        # Extract key metrics
        SECTIONS=$(echo "$RESPONSE" | jq -r '.result.sections | length')
        CITATIONS=$(echo "$RESPONSE" | jq -r '.result.citations | length')
        STRATEGY=$(echo "$RESPONSE" | jq -r '.result.metadata.strategy_slug')

        echo -e "Strategy: ${BLUE}${STRATEGY}${NC}"
        echo -e "Sections: ${BLUE}${SECTIONS}${NC}"
        echo -e "Citations: ${BLUE}${CITATIONS}${NC}"
    elif [ "$STATUS" = "failed" ]; then
        echo -e "\n${RED}========================================${NC}"
        echo -e "${RED}❌ Research failed${NC}"
        echo -e "${RED}========================================${NC}"
        ERROR=$(echo "$RESPONSE" | jq -r '.error')
        echo -e "Error: ${RED}${ERROR}${NC}"
    fi

elif [ "$MODE" = "async" ]; then
    echo -e "${YELLOW}📤 Testing ASYNCHRONOUS execution...${NC}\n"

    # Async request (with callback_url)
    WEBHOOK_URL="https://defaulte29fc699127e425da75fed341dc328.38.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/05a44fcda78f472d9943dc52d3e66641/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=2l-aB7LtZ7hDnyqUdZg4lccHzr0H_favXxG-VZqSmd8"  # Power Automate webhook URL

    PAYLOAD=$(cat <<EOF
{
    "research_topic": "${RESEARCH_TOPIC}",
    "email": "test@example.com",
    "callback_url": "${WEBHOOK_URL}"
}
EOF
)

    echo -e "${BLUE}Request:${NC}"
    echo "$PAYLOAD" | jq '.'
    echo ""

    echo -e "${YELLOW}⏳ Triggering async research...${NC}\n"

    RESPONSE=$(curl -s -X POST "${API_URL}/execute/manual" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: ${API_KEY}" \
        -d "$PAYLOAD")

    echo -e "${GREEN}✅ Response received:${NC}\n"
    echo "$RESPONSE" | jq '.'

    # Check status
    STATUS=$(echo "$RESPONSE" | jq -r '.status')

    if [ "$STATUS" = "running" ]; then
        echo -e "\n${GREEN}========================================${NC}"
        echo -e "${GREEN}✅ Research started in background!${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo -e "Results will be sent to: ${BLUE}${WEBHOOK_URL}${NC}"
        echo -e "\n${YELLOW}💡 Tip: Check your webhook URL for results${NC}"
    else
        echo -e "\n${RED}========================================${NC}"
        echo -e "${RED}⚠️  Unexpected status: ${STATUS}${NC}"
        echo -e "${RED}========================================${NC}"
    fi

else
    echo -e "${RED}❌ Invalid mode: ${MODE}${NC}"
    echo -e "Usage: $0 [sync|async]"
    exit 1
fi

echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}🏁 Test complete${NC}"
echo -e "${BLUE}========================================${NC}"
