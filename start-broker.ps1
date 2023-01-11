docker run --rm -p 8080:15672 -p 5672:5672 -e RABBITMQ_DEFAULT_USER=rabbit -e RABBITMQ_DEFAULT_PASS=carrot rabbitmq:3-management
