variable "name" {
  description = "Prefix for all resource names"
  type        = string
  default     = "claimlens"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}
