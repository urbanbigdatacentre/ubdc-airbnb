# Python 3.10, Geos 3.10.2, proj 9.2.0, gdal 3.6.0
FROM osgeo/gdal@sha256:452da485c574fe040a5748b73932d3ec7334913197744b550d13ce80493ef3c4 AS runner
ENV PYTHONUNBUFFERED=1 \
    REQUESTS_CA_BUNDLE="/etc/ssl/certs/ca-certificates.crt" \
    POETRY_VERSION=1.7.1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/var/cache/pypoetry' \
    POETRY_HOME='/usr/local'

SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
    python3.10-distutils

RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /tmp
COPY ./poetry.lock ./pyproject.toml /tmp/
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root


ADD https://docs.zyte.com/_static/zyte-smartproxy-ca.crt /usr/local/share/ca-certificates/zyte-smartproxy-ca.crt
RUN update-ca-certificates

COPY ./src/ubdc_airbnb /app
WORKDIR /app
RUN chmod +x 'docker-entrypoint.sh'
ENV PYTHONPATH="/app"
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["manage"]
