# AWS target environment for ClaimLens (docs/diagrams/deployment.md).
# Written as a reference module; it has not been applied.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

resource "aws_s3_bucket" "documents" {
  bucket = "${var.name}-documents"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_sqs_queue" "claim_jobs_dlq" {
  name                      = "${var.name}-claim-jobs-dlq"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "claim_jobs" {
  name                       = "${var.name}-claim-jobs"
  visibility_timeout_seconds = 300
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.claim_jobs_dlq.arn
    maxReceiveCount     = 3
  })
}

# Roadmap: VPC, RDS PostgreSQL with pgvector, ECS Fargate services for api and worker,
# ALB, CloudFront, Secrets Manager and queue-depth autoscaling for the worker.
