#!/bin/sh
# Runs inside LocalStack once it is ready: creates the bucket and queues used locally.
set -e

awslocal s3 mb s3://claimlens-documents
# The browser uploads directly to presigned URLs, so the bucket needs CORS for the web app.
awslocal s3api put-bucket-cors --bucket claimlens-documents --cors-configuration '{
  "CORSRules": [{
    "AllowedOrigins": ["http://localhost:5173"],
    "AllowedMethods": ["GET", "PUT"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3000
  }]
}'

awslocal sqs create-queue --queue-name claim-jobs-dlq
awslocal sqs create-queue --queue-name claim-jobs \
  --attributes '{"VisibilityTimeout":"300","RedrivePolicy":"{\"deadLetterTargetArn\":\"arn:aws:sqs:us-east-1:000000000000:claim-jobs-dlq\",\"maxReceiveCount\":\"3\"}"}'
