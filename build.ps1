Write-Output "Building Images"
$Env:UBDC_DOCKER_REGISTRY = "172.20.67.71/"
Invoke-Expression -Command `
    "docker compose build worker"
