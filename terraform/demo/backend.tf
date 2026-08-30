# Remote state for the DEMO environment — its own bucket, its own key, in the
# DEMO ACCOUNT.
#
# This is not an organisational preference. A separate state is what makes it
# STRUCTURALLY IMPOSSIBLE for a plan of this module to propose a change to a
# resource of the shop's production account: it has never read that state, so
# it does not know those resources exist. Sharing a bucket or a key with
# `terraform/backend.tf` would remove that guarantee, and no amount of care in
# review restores it.
#
# PREREQUISITE: create the bucket manually in the demo account BEFORE
# `terraform init`:
#
#   aws s3api create-bucket --bucket jbg-demo-terraform-state --region eu-west-1 \
#     --create-bucket-configuration LocationConstraint=eu-west-1
#
#   aws s3api put-bucket-versioning --bucket jbg-demo-terraform-state \
#     --versioning-configuration Status=Enabled
#
#   aws s3api put-public-access-block --bucket jbg-demo-terraform-state \
#     --public-access-block-configuration \
#     BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

terraform {
  backend "s3" {
    bucket  = "jbg-demo-terraform-state"
    key     = "demo/terraform.tfstate"
    region  = "eu-west-1"
    encrypt = true
  }
}
