#!/bin/bash

# Deployment script for Commuteapp to Fly.io
# This script builds and deploys the updated bus tracking with accurate predictions

set -e

echo "🚀 Deploying Commuteapp to Fly.io..."
echo ""

# Check if flyctl is installed
if ! command -v flyctl &> /dev/null; then
    echo "❌ flyctl is not installed. Install it with:"
    echo "   curl -L https://fly.io/install.sh | sh"
    exit 1
fi

# Check if logged in
if ! flyctl auth whoami &> /dev/null; then
    echo "❌ Not logged in to Fly.io. Run: flyctl auth login"
    exit 1
fi

echo "✅ flyctl found and authenticated"
echo ""

# Show current app status
echo "📊 Current app status:"
flyctl status || echo "App not yet deployed"
echo ""

# Confirm deployment
read -p "🤔 Deploy to production? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Deployment cancelled"
    exit 1
fi

# Build and deploy
echo "📦 Building and deploying Docker image..."
flyctl deploy --remote-only --ha=false

echo ""
echo "✅ Deployment complete!"
echo ""

# Check health
echo "🏥 Checking app health..."
sleep 5
flyctl checks list || echo "Health checks not available yet"

echo ""
echo "📊 Useful commands:"
echo "   flyctl status              - Check app status"
echo "   flyctl logs                - View application logs"
echo "   flyctl ssh console         - SSH into the machine"
echo "   flyctl secrets list        - View configured secrets"
echo "   flyctl checks list         - View health checks"
echo "   flyctl machine list        - View running machines"
echo ""
echo "🔐 Required secrets (set if not already configured):"
echo "   flyctl secrets set NJT_USERNAME=your_username"
echo "   flyctl secrets set NJT_PASSWORD=your_password"
echo "   flyctl secrets set NJT_BUS_BASE_URL=https://pcsdata.njtransit.com"
echo "   flyctl secrets set NJT_RAIL_BASE_URL=https://pcsdata.njtransit.com"
echo "   flyctl secrets set TWILIO_ACCOUNT_SID=your_sid"
echo "   flyctl secrets set TWILIO_AUTH_TOKEN=your_token"
echo "   flyctl secrets set TWILIO_PHONE_FROM=whatsapp:+14155238886"
echo "   flyctl secrets set TWILIO_PHONE_TO=whatsapp:+your_number"
echo ""
echo "📱 View logs in real-time:"
echo "   flyctl logs -f"
echo ""
