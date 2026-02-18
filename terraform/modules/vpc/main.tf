variable "project_name" { type = string }
variable "environment" { type = string }
variable "vpc_cidr" { type = string }
variable "availability_zones" { type = list(string) }

# When false (default) a single NAT gateway is created in the first AZ.
# All private subnets share it — cheapest option, suitable for dev/staging.
#
# When true, one NAT gateway is created per AZ so that outbound traffic from
# each private subnet stays within its AZ. This eliminates cross-AZ data
# transfer costs and removes the NAT as a single point of failure.
# Recommended for production. Cost: ~$32/month per additional NAT gateway.
variable "enable_multi_az_nat" {
  type        = bool
  default     = false
  description = "Create one NAT gateway per AZ (true) or a single shared NAT (false)."
}

# ---------------------------------------------------------------------------
# VPC
# ---------------------------------------------------------------------------
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.project_name}-vpc" }
}

# ---------------------------------------------------------------------------
# Subnets
# ---------------------------------------------------------------------------
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = { Name = "${var.project_name}-public-${count.index}" }
}

resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 100)
  availability_zone = var.availability_zones[count.index]

  tags = { Name = "${var.project_name}-private-${count.index}" }
}

# ---------------------------------------------------------------------------
# Internet Gateway
# ---------------------------------------------------------------------------
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.project_name}-igw" }
}

# ---------------------------------------------------------------------------
# NAT Gateways + Elastic IPs
#
# enable_multi_az_nat = false → 1 EIP + 1 NAT in the first public subnet.
#   All private subnets share this gateway (single point of failure per AZ,
#   lower cost — appropriate for dev/staging).
#
# enable_multi_az_nat = true  → 1 EIP + 1 NAT per AZ, each placed in that
#   AZ's public subnet. Each private subnet routes through its local NAT
#   (no cross-AZ traffic, no single point of failure — required for prod).
#
# NOTE: If you are applying this change to an existing deployment that was
# created with enable_multi_az_nat = false, Terraform will rename the
# existing resources (aws_eip.nat → aws_eip.nat[0], etc.). Run:
#   terraform state mv aws_eip.nat aws_eip.nat[0]
#   terraform state mv aws_nat_gateway.main aws_nat_gateway.main[0]
#   terraform state mv aws_route_table.private aws_route_table.private[0]
#   terraform state mv aws_route.private_nat aws_route.private_nat[0]
# before applying to avoid resource recreation.
# ---------------------------------------------------------------------------
resource "aws_eip" "nat" {
  count  = var.enable_multi_az_nat ? length(var.availability_zones) : 1
  domain = "vpc"
  tags   = { Name = "${var.project_name}-nat-eip-${count.index}" }
}

resource "aws_nat_gateway" "main" {
  count         = var.enable_multi_az_nat ? length(var.availability_zones) : 1
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = { Name = "${var.project_name}-nat-${count.index}" }

  depends_on = [aws_internet_gateway.main]
}

# ---------------------------------------------------------------------------
# Route tables
# ---------------------------------------------------------------------------
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.project_name}-public-rt" }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# One private route table per NAT gateway.
# Single-NAT mode:    1 route table shared by all private subnets.
# Multi-AZ-NAT mode: N route tables, one per AZ, each pointing at its local NAT.
resource "aws_route_table" "private" {
  count  = var.enable_multi_az_nat ? length(var.availability_zones) : 1
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.project_name}-private-rt-${count.index}" }
}

resource "aws_route" "private_nat" {
  count                  = var.enable_multi_az_nat ? length(var.availability_zones) : 1
  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.main[count.index].id
}

# Each private subnet is associated with its AZ's route table.
# In single-NAT mode all subnets resolve to index 0 (the one shared table).
resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[var.enable_multi_az_nat ? count.index : 0].id
}

# ---------------------------------------------------------------------------
# VPC Flow Logs (security best practice)
# ---------------------------------------------------------------------------
resource "aws_flow_log" "main" {
  vpc_id               = aws_vpc.main.id
  traffic_type         = "ALL"
  log_destination_type = "cloud-watch-logs"
  log_destination      = aws_cloudwatch_log_group.flow_log.arn
  iam_role_arn         = aws_iam_role.flow_log.arn
}

resource "aws_cloudwatch_log_group" "flow_log" {
  name              = "/aws/vpc/${var.project_name}-flow-logs"
  retention_in_days = 30
}

resource "aws_iam_role" "flow_log" {
  name = "${var.project_name}-flow-log-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "vpc-flow-logs.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "flow_log" {
  name = "${var.project_name}-flow-log-policy"
  role = aws_iam_role.flow_log.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
      ]
      Resource = "*"
    }]
  })
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}
