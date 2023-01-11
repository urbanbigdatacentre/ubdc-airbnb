Write-Output "Building Images"
$Env:UBDC_DOCKER_REGISTRY = "ubdc"
Invoke-Expression -Command `
    "docker compose build worker"
