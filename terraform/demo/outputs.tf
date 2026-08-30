output "deploy_role_arn" {
  description = "Role the demo workflow assumes via OIDC. Store as the DEMO_DEPLOY_ROLE_ARN secret of the demo environment."
  value       = aws_iam_role.deploy.arn
}

output "instance_id" {
  description = "Demo host. Store as the DEMO_INSTANCE_ID secret of the demo environment."
  value       = aws_instance.host.id
}

output "public_ip" {
  description = "Elastic IP of the demo host"
  value       = aws_eip.host.public_ip
}

output "demo_hostname" {
  description = "Hostname the environment is served under, and the name on its certificate"
  value       = local.demo_hostname
}

output "demo_url" {
  description = "Public entry point"
  value       = "https://${local.demo_hostname}"
}

output "ecr_registry" {
  description = "Registry host for both demo images"
  value       = split("/", aws_ecr_repository.api.repository_url)[0]
}

output "api_repository_url" {
  description = "Repository for the bundled API + interface image"
  value       = aws_ecr_repository.api.repository_url
}

output "ai_repository_url" {
  description = "Repository for the AI service image"
  value       = aws_ecr_repository.ai.repository_url
}
