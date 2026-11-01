#!/bin/sh
# Runs inside LocalStack once it is ready: creates the bucket and queues used locally.
awslocal s3 mb s3://claimlens-documents
awslocal sqs create-queue --queue-name claim-jobs-dlq
awslocal sqs create-queue --queue-name claim-jobs \
  --attributes '{"RedrivePolicy":"{\"deadLetterTargetArn\":\"arn:aws:sqs:us-east-1:000000000000:claim-jobs-dlq\",\"maxReceiveCount\":\"3\"}"}'
