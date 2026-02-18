aws_region         = "us-east-1"
project_name       = "devsecops-pipeline"
environment        = "dev"
vpc_cidr           = "10.0.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b"]
container_image    = "devsecops-pipeline-app:latest"
container_port     = 8080
task_cpu           = 256
task_memory        = 512
desired_count      = 1
db_instance_class  = "db.t3.micro"
db_name            = "appdb"

# Single NAT gateway intentionally kept for dev to minimise cost.
# A NAT gateway costs ~$32/month plus ~$0.045/GB data processed.
# Dev traffic is low and AZ-level HA is not required outside production.
# Set to true only if you need to test multi-AZ routing locally.
enable_multi_az_nat = false
