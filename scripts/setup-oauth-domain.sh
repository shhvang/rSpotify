#!/bin/bash
# Automated OAuth Domain Setup Script for rSpotify
# Run this on a fresh VPS to set up DNS, Nginx, and SSL for OAuth

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

# ===== Step 2: Install and Configure Nginx =====
echo ""
echo "📦 Step 2: Setting up Nginx..."
DEBIAN_FRONTEND=noninteractive apt install -y nginx

# Production OAuth configuration (ports 80/443)
cat > /etc/nginx/sites-available/rspotify-oauth << 'NGINXEOF'
server {
    listen 80;
    server_name rspotify.shhvang.space;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location /spotify/callback {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        return 404;
    }
}

server {
    listen 443 ssl;
    server_name rspotify.shhvang.space;

    # SSL certificates will be added by certbot
    
    location /spotify/callback {
        proxy_pass https://localhost:443;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        return 404;
    }
}
NGINXEOF

# Test OAuth configuration (ports 8080/8443)
cat > /etc/nginx/sites-available/rspotify-oauth-test << 'NGINXEOF'
server {
    listen 80;
    server_name rspotifytest.shhvang.space;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location /spotify/callback {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        return 404;
    }
}

server {
    listen 443 ssl;
    server_name rspotifytest.shhvang.space;

    # SSL certificates will be added by certbot
    
    location /spotify/callback {
        proxy_pass https://localhost:8443;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        return 404;
    }
}
NGINXEOF

ln -sf /etc/nginx/sites-available/rspotify-oauth /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/rspotify-oauth-test /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
systemctl enable nginx

ufw allow 80/tcp
ufw allow 443/tcp

echo "✅ Nginx configured for both production and test domains!"

# ===== Step 3: Install Certbot =====
echo ""
echo "📦 Step 3: Installing Certbot for SSL..."
DEBIAN_FRONTEND=noninteractive apt install -y certbot python3-certbot-nginx

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
echo "2️⃣  Once DNS resolves, run SSL certificate setup:"
echo "   certbot --nginx -d $PROD_DOMAIN -d $TEST_DOMAIN"
echo ""
echo "3️⃣  Deploy production and test environments:"
echo "   Production: ./scripts/deploy.sh"
echo "   Test: ./scripts/deploy-test.sh"
echo ""
echo "4️⃣  Update Spotify Developer App redirect URIs:"
echo "   https://$PROD_DOMAIN/spotify/callback"
echo "   https://$TEST_DOMAIN/spotify/callback"
echo ""
echo "5️⃣  Test OAuth flow:"
echo "   Production: Send /login to production bot"
echo "   Test: Send /login to test bot"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ DNS Server: Running on port 53"
echo "✅ Nginx: Running on port 80/443"
echo "✅ Firewall: Ports 22, 53, 80, 443 open"
echo ""
echo "📊 DNS Status:"
echo "Production:"
dig @localhost $PROD_DOMAIN +short
echo "Test:"
dig @localhost $TEST_DOMAIN +short
echo ""
echo "💡 Port Configuration:"
echo "   Production OAuth: Ports 80 (HTTP) / 443 (HTTPS)"
echo "   Test OAuth: Ports 8080 (HTTP) / 8443 (HTTPS)"
echo ""
echo "💡 Save this script for reuse on future VPS migrations!"
