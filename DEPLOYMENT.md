# Deployment Guide for Commuteapp

This guide covers deploying the updated Commuteapp with accurate bus tracking to Fly.io.

## What's New

The latest version includes:
- **Accurate stop predictions** using getStopPredictions API
- **Official NJ Transit ETAs** (no more GPS distance calculations)
- **Only buses serving your stop** (no false positives)
- **Playwright integration** for bypassing Cloudflare protection
- **Real-time vs scheduled indicators**
- **Timezone-aware auto-trigger** (Eastern Time)

## Prerequisites

1. **Fly.io CLI installed**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Fly.io account and authentication**
   ```bash
   flyctl auth login
   ```

## Quick Deploy

Simply run the deployment script:

```bash
./deploy.sh
```

## Manual Deployment Steps

If you prefer to deploy manually:

### 1. Build and Deploy

```bash
flyctl deploy --remote-only
```

The `--remote-only` flag builds the Docker image on Fly.io's servers, which is recommended for images with Playwright/Chromium.

### 2. Set Environment Variables (First Time Only)

```bash
flyctl secrets set \
  NJT_USERNAME="your_username" \
  NJT_PASSWORD="your_password" \
  NJT_BUS_BASE_URL="https://pcsdata.njtransit.com" \
  NJT_RAIL_BASE_URL="https://raildata.njtransit.com" \
  TWILIO_ACCOUNT_SID="your_sid" \
  TWILIO_AUTH_TOKEN="your_token" \
  TWILIO_PHONE_FROM="whatsapp:+14155238886" \
  TWILIO_PHONE_TO="whatsapp:+your_number" \
  WEATHER_KEY="your_weather_key" \
  TELEGRAM_TOKEN="your_telegram_token" \
  TELEGRAM_CHAT_ID="your_chat_id"
```

## Monitoring

### Check Status
```bash
flyctl status
```

### View Logs
```bash
flyctl logs
```

### Live Log Streaming
```bash
flyctl logs -f
```

### SSH into Machine
```bash
flyctl ssh console
```

## Docker Image Details

The updated Dockerfile includes:

- **Base Image**: `python:3.11-slim`
- **Timezone**: Configured to America/New_York
- **Security**: Runs as non-root user (appuser)
- **Health Checks**: Built-in health endpoint monitoring
- **Playwright**: Chromium browser with all dependencies
- **System packages**: Required libraries for headless browser operation
- **Optimizations**:
  - Multi-stage caching for faster builds
  - `.dockerignore` excludes test files and dev dependencies
  - Only Chromium installed (not all browsers) for smaller image size

## Troubleshooting

### Build fails with Playwright installation
The Dockerfile uses `playwright install chromium --with-deps` which should handle all dependencies. If it fails, check:
- Memory allocation (increase in `fly.toml` if needed)
- Fly.io builder resources

### GPS tracking not working
Check logs for Playwright errors:
```bash
flyctl logs | grep "Playwright"
```

Common issues:
- Cloudflare blocking: The Playwright setup should handle this
- Missing dependencies: Verify all system packages are installed in Dockerfile

### Application crashes with "event loop" errors
The code uses `nest_asyncio` to handle nested event loops. If issues persist:
- Check that `nest-asyncio` is in `requirements.txt`
- Verify the package is installed in the container

## Rollback

To rollback to a previous version:
```bash
flyctl releases
flyctl rollback <version_number>
```

## Resources

- [Fly.io Documentation](https://fly.io/docs/)
- [Playwright Python Docs](https://playwright.dev/python/docs/intro)
- [MyBusNow API](https://mybusnow.njtransit.com)

## Support

For issues with:
- **GPS tracking logic**: Check `agent/clients/bus_client.py:93` (get_bus_live_trips_from_stop)
- **Playwright setup**: Check Dockerfile lines 9-40
- **Environment variables**: Check `.env` file format and Fly.io secrets
