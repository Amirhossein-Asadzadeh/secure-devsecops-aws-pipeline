package kubernetes.admission

import rego.v1

# -----------------------------------------------------------------------
# Deny containers running as root
# -----------------------------------------------------------------------
deny contains msg if {
    input.request.kind.kind == "Deployment"
    container := input.request.object.spec.template.spec.containers[_]
    not container.securityContext.runAsNonRoot
    msg := sprintf("Container '%s' must set securityContext.runAsNonRoot to true", [container.name])
}

# -----------------------------------------------------------------------
# Deny containers without resource limits
# -----------------------------------------------------------------------
deny contains msg if {
    input.request.kind.kind == "Deployment"
    container := input.request.object.spec.template.spec.containers[_]
    not container.resources.limits
    msg := sprintf("Container '%s' must define resource limits (cpu, memory)", [container.name])
}

# -----------------------------------------------------------------------
# Deny privilege escalation
# -----------------------------------------------------------------------
deny contains msg if {
    input.request.kind.kind == "Deployment"
    container := input.request.object.spec.template.spec.containers[_]
    container.securityContext.allowPrivilegeEscalation == true
    msg := sprintf("Container '%s' must not allow privilege escalation", [container.name])
}

# -----------------------------------------------------------------------
# Deny images from untrusted registries
# -----------------------------------------------------------------------
deny contains msg if {
    input.request.kind.kind == "Deployment"
    container := input.request.object.spec.template.spec.containers[_]
    not startswith(container.image, "AWS_ACCOUNT_ID.dkr.ecr.")
    not startswith(container.image, "docker.io/library/")
    msg := sprintf("Container '%s' uses untrusted image registry: %s", [container.name, container.image])
}

# -----------------------------------------------------------------------
# Deny containers with writable root filesystem
# -----------------------------------------------------------------------
deny contains msg if {
    input.request.kind.kind == "Deployment"
    container := input.request.object.spec.template.spec.containers[_]
    not container.securityContext.readOnlyRootFilesystem
    msg := sprintf("Container '%s' must set readOnlyRootFilesystem to true", [container.name])
}

# -----------------------------------------------------------------------
# Require liveness and readiness probes
# -----------------------------------------------------------------------
deny contains msg if {
    input.request.kind.kind == "Deployment"
    container := input.request.object.spec.template.spec.containers[_]
    not container.livenessProbe
    msg := sprintf("Container '%s' must define a livenessProbe", [container.name])
}

deny contains msg if {
    input.request.kind.kind == "Deployment"
    container := input.request.object.spec.template.spec.containers[_]
    not container.readinessProbe
    msg := sprintf("Container '%s' must define a readinessProbe", [container.name])
}
