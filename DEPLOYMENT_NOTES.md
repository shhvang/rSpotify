# Deployment Notes - Web App Bots Integration

## What Changed

The rSpotify repository now includes two optional web app bots that deploy alongside the main Spotify bot:

1. **Better Than Very Bot** - @BetterThanVeryBot
2. **Perfect Circle Bot** - @PerfectCircleBot

## GitHub Secrets to Add

Go to: https://github.com/shhvang/rSpotify/settings/secrets/actions

Add these two new secrets:

```
BETTERTHANVERY_BOT_TOKEN = 8417744876:AAH8C5J33VWu8SneS1tCUWdKdRNWL85kHZo
PERFECTCIRCLE_BOT_TOKEN = 8163239474:AAGAXqC8U4nZINVHCrUjKYl9BulGy6OR7hY
```

## What Happens After Adding Secrets

The next deployment will:
1. Deploy rSpotify bot (as before)
2. Deploy Better Than Very bot (new)
3. Deploy Perfect Circle bot (new)

All three bots will run as independent supervisor processes under the same infrastructure.

## Architecture

```
/opt/rspotify-bot/
├── repo/
│   ├── rspotify.py              # Main Spotify bot
│   ├── web_apps/
│   │   ├── betterthanvery/
│   │   │   └── bot.py           # Better Than Very bot
│   │   └── perfectcircle/
│   │       └── bot.py           # Perfect Circle bot
│   └── .env                     # Shared environment file
├── venv/                        # Shared Python environment
└── logs/
    ├── bot_output.log           # rSpotify logs
    ├── bot_error.log
    ├── betterthanvery_output.log
    ├── betterthanvery_error.log
    ├── perfectcircle_output.log
    └── perfectcircle_error.log
```

## Supervisor Processes

After deployment, you'll have:
- `rspotify-bot` - Main Spotify bot
- `betterthanvery-bot` - Better Than Very web app bot
- `perfectcircle-bot` - Perfect Circle web app bot

Check status:
```bash
ssh -i ~/.ssh/rspotify_deploy root@178.128.48.130 "supervisorctl status"
```

## Bot Features

### Better Than Very Bot
- **Start Message**: "Hi [Name]! 👋\n\nReplace weak phrases with stronger words.\nExample: 'very good' → 'excellent'"
- **Button**: Inline "Open App" button → https://betterthanvery.netlify.app
- **Commands**: /start, /help

### Perfect Circle Bot
- **Start Message**: "Hi [Name]! 👋\n\nDraw a circle and see how perfect it is.\nCan you score 100%?"
- **Button**: Inline "Open App" button → https://perfectcircle.netlify.app
- **Commands**: /start, /help

## Testing After Deployment

1. Message @BetterThanVeryBot with `/start`
2. Message @PerfectCircleBot with `/start`
3. Verify they respond with subtle messages and inline buttons
4. Click "Open App" to verify web apps load

## Optional: Remove Old Standalone Bots

If you deployed the bots previously on the same VPS, you can remove them:

```bash
ssh -i ~/.ssh/rspotify_deploy root@178.128.48.130

# Stop and remove old standalone bots (if they exist)
supervisorctl stop betterthanvery-bot perfectcircle-bot
rm /etc/supervisor/conf.d/betterthanvery-bot.conf
rm /etc/supervisor/conf.d/perfectcircle-bot.conf
supervisorctl reread
supervisorctl update

# Remove old directory (if exists)
rm -rf /opt/telegram-bots
```

The new bots will now be managed through the rSpotify deployment pipeline.
