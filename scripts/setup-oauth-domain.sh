#!/bin/bash
# Automated OAuth Domain Setup Script for rSpotify
# Run this on a fresh VPS to set up DNS for OAuth
# Note: SSL is handled automatically by aiohttp + certbot (no Nginx needed)

set -e  # Exit on any error

echo "🚀 Starting OAuth domain setup for rspotify.shhvang.space..."

# Get VPS IP automatically
VPS_IP=$(hostname -I | awk '{print $1}')
PROD_DOMAIN="rspotify.shhvang.space"
TEST_DOMAIN="rspotifytest.shhvang.space"
ROOT_DOMAIN="shhvang.space"

echo "📍 Detected VPS IP: $VPS_IP"
echo "🌐 Setting up domains:"
echo "   Production: $PROD_DOMAIN"
echo "   Test: $TEST_DOMAIN"

# ===== Step 1: Install and Configure DNS Server =====
echo ""
echo "📦 Step 1: Installing BIND DNS server..."
apt update -qq
DEBIAN_FRONTEND=noninteractive apt install -y bind9 bind9utils bind9-doc

echo "⚙️  Configuring DNS zone for $ROOT_DOMAIN..."
cat > /etc/bind/named.conf.local << EOF
zone "$ROOT_DOMAIN" {
    type master;
    file "/etc/bind/zones/db.$ROOT_DOMAIN";
};
EOF

mkdir -p /etc/bind/zones

cat > /etc/bind/zones/db.$ROOT_DOMAIN << EOF
\$TTL    604800
@       IN      SOA     rspotify.$ROOT_DOMAIN. admin.$ROOT_DOMAIN. (
                              1         ; Serial
                         604800         ; Refresh
                          86400         ; Retry
                        2419200         ; Expire
                         604800 )       ; Negative Cache TTL
;
@       IN      NS      rspotify.$ROOT_DOMAIN.
rspotify IN     A       $VPS_IP
rspotifytest IN A       $VPS_IP
EOF

# Validate DNS config
named-checkconf
named-checkzone $ROOT_DOMAIN /etc/bind/zones/db.$ROOT_DOMAIN

# Start and enable BIND
systemctl restart bind9
systemctl enable bind9

# Configure firewall for DNS
ufw allow 53/tcp
ufw allow 53/udp

echo "✅ DNS server configured!"
echo "Checking DNS for production domain:"
dig @localhost $PROD_DOMAIN +short
echo "Checking DNS for test domain:"
dig @localhost $TEST_DOMAIN +short

# ===== Step 2: Open Firewall Ports =====
echo ""
echo "� Step 2: Configuring firewall..."
ufw allow 80/tcp   # HTTP (for certbot ACME challenge and production OAuth)
ufw allow 443/tcp  # HTTPS (for production OAuth callbacks)
ufw allow 8080/tcp # HTTP (for test OAuth)
ufw allow 8443/tcp # HTTPS (for test OAuth callbacks)

echo "✅ Firewall configured for OAuth services!"

echo ""
echo "🎉 Setup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Next Steps:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1️⃣  Wait for DNS propagation (5-60 minutes)"
echo "   Test production: dig $PROD_DOMAIN @8.8.8.8 +short"
echo "   Test staging: dig $TEST_DOMAIN @8.8.8.8 +short"
echo ""
echo "2️⃣  Deploy production and test environments:"
echo "   Production: ./scripts/deploy.sh"
echo "   Test: ./scripts/deploy-test.sh"
echo ""
echo "   ⚠️  IMPORTANT: The deployment scripts will:"
echo "      - Start aiohttp OAuth services on configured ports"
echo "      - Automatically obtain SSL certificates via certbot"
echo "      - No Nginx needed - aiohttp handles SSL directly!"
echo ""
echo "3️⃣  Update Spotify Developer App redirect URIs:"
echo "   https://$PROD_DOMAIN/spotify/callback"
echo "   https://$TEST_DOMAIN/spotify/callback"
echo ""
echo "4️⃣  Test OAuth flow:"
echo "   Production: Send /login to production bot"
echo "   Test: Send /login to test bot"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ DNS Server: Running on port 53"
echo "✅ Firewall: Ports 53, 80, 443, 8080, 8443 open"
echo ""
echo "📊 DNS Status:"
echo "Production:"
dig @localhost $PROD_DOMAIN +short
echo "Test:"
dig @localhost $TEST_DOMAIN +short
echo ""
echo "💡 Port Configuration:"
echo "   Production OAuth (aiohttp): Ports 80 (HTTP) / 443 (HTTPS)"
echo "   Test OAuth (aiohttp): Ports 8080 (HTTP) / 8443 (HTTPS)"
echo ""
echo "💡 Architecture Note:"
echo "   - aiohttp services bind directly to their ports (CAP_NET_BIND_SERVICE)"
echo "   - SSL certificates managed automatically by certbot integration"
echo "   - No reverse proxy needed - aiohttp serves HTTPS directly!"
echo ""
echo "💡 Save this script for reuse on future VPS migrations!"
