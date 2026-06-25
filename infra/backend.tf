terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Get latest Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Security Group
resource "aws_security_group" "mii_backend" {
  name        = "mii-backend-sg"
  description = "MII Backend - allow HTTP 8000 and SSH"

  # Backend API
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Backend API"
  }

  # SSH (optional)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "SSH access"
  }

  # All outbound
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project = "MII"
  }
}

# IAM Role for EC2 (read-only IAM access for discovery)
resource "aws_iam_role" "mii_ec2" {
  name = "mii-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Project = "MII"
  }
}

resource "aws_iam_role_policy_attachment" "iam_read_only" {
  role       = aws_iam_role.mii_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/IAMReadOnlyAccess"
}

resource "aws_iam_instance_profile" "mii_ec2" {
  name = "mii-ec2-profile"
  role = aws_iam_role.mii_ec2.name
}

# EC2 Instance
resource "aws_instance" "mii_backend" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = "t3.micro"
  key_name               = var.key_name != "" ? var.key_name : null
  vpc_security_group_ids = [aws_security_group.mii_backend.id]
  iam_instance_profile   = aws_iam_instance_profile.mii_ec2.name

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = <<-EOF
#!/bin/bash
set -ex
exec > /var/log/user-data.log 2>&1

# Install Docker
yum update -y
yum install -y docker
systemctl start docker
systemctl enable docker

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Login to Container Registry
docker login -u ${var.container_registry_username} -p ${var.container_registry_password} ${var.container_registry_url}

# Create app directory
mkdir -p /opt/mii
cd /opt/mii

# Write docker-compose
cat > docker-compose.yml <<'COMPOSE'
version: "3.9"
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: mii
      POSTGRES_USER: mii
      POSTGRES_PASSWORD: ${var.db_password}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mii"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: always

  backend:
    image: ${var.container_image}
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://mii:${var.db_password}@db:5432/mii
      APP_ENV: production
      LOG_LEVEL: INFO
      AWS_REGION: ${var.aws_region}
      AWS_ACCOUNT_IDS: "${var.aws_account_ids}"
      GITLAB_URL: "https://gitlab.com"
      GITLAB_TOKEN: "${var.gitlab_token}"
      OPENAI_API_KEY: "${var.openai_api_key}"
      OPENAI_MODEL: gpt-4o-mini
    depends_on:
      db:
        condition: service_healthy
    restart: always

volumes:
  pgdata:
COMPOSE

# Pull and start
docker-compose pull
docker-compose up -d

# Wait for DB then run migrations
sleep 15
docker-compose exec -T backend alembic upgrade head || true
EOF

  user_data_replace_on_change = true

  tags = {
    Name    = "mii-backend"
    Project = "MII"
  }
}

# Outputs
output "backend_public_ip" {
  value       = aws_instance.mii_backend.public_ip
  description = "Public IP of the MII backend EC2 instance"
}

output "backend_url" {
  value       = "http://${aws_instance.mii_backend.public_ip}:8000"
  description = "Backend API URL"
}

output "instance_id" {
  value       = aws_instance.mii_backend.id
  description = "EC2 instance ID"
}
