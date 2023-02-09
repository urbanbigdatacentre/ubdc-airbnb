import os
import warnings
from logging import getLogger
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

logger = getLogger(__name__)


def config_env_for_app():
    docker_configuration_path = Path('/config/')
    docker_secrets_path = Path('/run/secrets/')

    dev_mode = os.getenv('DJANGO_ENV') == 'DEV'
    test_mode = os.getenv('DJANGO_ENV') == 'TEST'
    prod_mode = os.getenv('DJANGO_ENV') == 'PROD'
    load_env = False

    if load_dotenv(find_dotenv('.env'), override=False):
        logger.info('Loaded .env file')

    # DEVELOPMENT load  .env.devel
    if dev_mode:
        if load_dotenv(find_dotenv('.env.local'), override=True):
            logger.info('Loaded .env.local file')
            load_env = True
        else:
            logger.info('Dev mode enabled but .env.devel was not found. Skipping')

    # PRODUCTION mode load .env.devel
    elif prod_mode:
        if load_dotenv(find_dotenv('.env.prod'), override=True):
            logger.info('Loaded .env.prod file')
            load_env = True

        else:
            logger.info('Prod mode enabled but .env.prod was not found. Skipping')

    # TEST mode load .env.test
    elif test_mode:
        if load_dotenv(find_dotenv('.env.test'), override=True):
            logger.info('Loaded .env.test file')
            load_env = True
        else:
            logger.info('Test mode enabled but .env.prod was not found. Skipping')

    # DOCKER SECRETS
    if docker_secrets_path.exists():
        for f in docker_secrets_path.glob('*'):
            if f.is_file():
                logger.info(f'Secrets: Sourcing {f.name}')
                load_dotenv(f, override=True, verbose=True)
                load_env = True
    else:
        logger.info('docker secrets folder does not exits, skipping')

    # DOCKER CONFIGURATIONS
    if docker_configuration_path.exists():
        for f in docker_configuration_path.glob('*'):
            if f.is_file():
                logger.info(f'Config: Sourcing {f.name}')
                load_dotenv(f, override=True, verbose=True)
                load_env = True
    else:
        logger.info('docker configuration folder does not exits, skipping')

    if not load_env:
        logger.warning('No environment files were loaded.')

    # Check if AIRBNB_PROXY is loaded
    if os.getenv('AIRBNB_PROXY') is None:
        message = f"No proxy is set. Not using a proxy could lead Airbnb QoS to be activated."
        warnings.warn(message)
    else:
        print(f'proxy set: {os.getenv("AIRBNB_PROXY")} dsf')


config_env_for_app()
# from .celery import app
