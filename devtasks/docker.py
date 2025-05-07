import os


def generate_docker_compose():
    github_sha = os.environ.get("GITHUB_SHA")
    print("Generating docker-compose.yml: hash: ", github_sha)
