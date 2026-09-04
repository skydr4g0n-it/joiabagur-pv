#!/bin/bash
set -euo pipefail

# ─── System packages ─────────────────────────────────────────────────────────
yum update -y
yum install -y docker nginx python3-pip

# ─── Docker ──────────────────────────────────────────────────────────────────
systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user
# SSM Start Session logs in as ssm-user, not ec2-user — same Docker socket access.
if id ssm-user &>/dev/null; then
  usermod -aG docker ssm-user
fi

# ─── SSM Agent (pre-installed on AL2023, ensure it's running) ────────────────
systemctl enable amazon-ssm-agent
systemctl start amazon-ssm-agent

# ─── Certbot (Let's Encrypt) ─────────────────────────────────────────────────
pip3 install certbot certbot-nginx

# pip installs certbot to /usr/local/bin; cron PATH does not include it — use full path.
cat > /etc/cron.d/certbot-jpv << 'CRON_EOF'
0 3,15 * * * root PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /usr/local/bin/certbot renew -q --deploy-hook "systemctl reload nginx" >> /var/log/certbot-cron.log 2>&1
CRON_EOF
chmod 644 /etc/cron.d/certbot-jpv

# ─── nginx (HTTP only — run certbot manually after DNS update) ───────────────
cat > /etc/nginx/conf.d/jpv.conf << 'NGINX_EOF'
server {
    listen 80;
    server_name ${domain_name};

    location / {
        proxy_pass         http://localhost:8080;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        client_max_body_size 50M;
        proxy_read_timeout   120s;
    }
}
NGINX_EOF

systemctl enable nginx
systemctl start nginx

# ─── Deploy script (called by GitHub Actions via SSM send-command) ────────────
cat > /usr/local/bin/jpv-deploy.sh << 'DEPLOY_EOF'
#!/bin/bash
set -euo pipefail

ECR_URI="$1"
IMAGE_TAG="$2"
REGION="eu-west-3"
SSM_PREFIX="/jpv/prod"

get_secure() { aws ssm get-parameter --name "$SSM_PREFIX/$1" --with-decryption --region "$REGION" --query 'Parameter.Value' --output text; }
get_plain()  { aws ssm get-parameter --name "$SSM_PREFIX/$1" --region "$REGION" --query 'Parameter.Value' --output text; }

# Login to ECR
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$ECR_URI"

# Pull new image
docker pull "$ECR_URI:$IMAGE_TAG"

# Read configuration from SSM Parameter Store (Mejora 2)
DB_CONN=$(get_secure "ConnectionStrings__DefaultConnection")
JWT_KEY=$(get_secure "Jwt__SecretKey")
JWT_ISSUER=$(get_plain "Jwt__Issuer")
JWT_AUDIENCE=$(get_plain "Jwt__Audience")
S3_BUCKET=$(get_plain "Aws__S3__BucketName")
S3_PRESIGNED=$(get_plain "Aws__S3__PresignedUrlExpirationMinutes")
CORS_ORIGIN=$(get_plain "Cors__AllowedOrigins__0")

# Graceful stop of old container
docker stop jpv-api 2>/dev/null || true
docker rm   jpv-api 2>/dev/null || true

# Start new container
docker run -d \
  --name jpv-api \
  --restart unless-stopped \
  -p 8080:8080 \
  -e ASPNETCORE_ENVIRONMENT=Production \
  -e "ConnectionStrings__DefaultConnection=$DB_CONN" \
  -e "Jwt__SecretKey=$JWT_KEY" \
  -e "Jwt__Issuer=$JWT_ISSUER" \
  -e "Jwt__Audience=$JWT_AUDIENCE" \
  -e "FileStorage__Provider=s3" \
  -e "Aws__S3__BucketName=$S3_BUCKET" \
  -e "Aws__S3__PresignedUrlExpirationMinutes=$S3_PRESIGNED" \
  -e "Cors__AllowedOrigins__0=$CORS_ORIGIN" \
  -e "AWS_REGION=$REGION" \
  "$ECR_URI:$IMAGE_TAG"

# Free up disk space
docker image prune -f

echo "Deployment complete: $IMAGE_TAG"
DEPLOY_EOF

chmod +x /usr/local/bin/jpv-deploy.sh
