UBDC_DOCKER_REGISTRY="172.20.67.71/"

docker-compose -f docker-compose.yml build worker beat
docker-compose -f docker-compose.yml push worker beat
