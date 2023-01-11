FROM python:3.10 as python-builder
WORKDIR /tmp
RUN pip install poetry
COPY ./poetry.lock* ./pyproject.toml /tmp/
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes


FROM osgeo/gdal@sha256:452da485c574fe040a5748b73932d3ec7334913197744b550d13ce80493ef3c4 as runner
ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY --from=python-builder /tmp/requirements.txt /app/requirements.txt
ADD https://bootstrap.pypa.io/pip/pip.pyz pip.pyz
ADD https://docs.zyte.com/_static/zyte-smartproxy-ca.crt /usr/local/share/ca-certificates/zyte-smartproxy-ca.crt
RUN update-ca-certificates

RUN python pip.pyz install --no-cache-dir --upgrade -r /app/requirements.txt

COPY ./src/ubdc_airbnb /app
COPY ./docker-entrypoint.sh /app/docker-entrypoint
RUN chmod +x docker-entrypoint
ENV PYTHONPATH=/app
#ENV DJANGO_SETTINGS_MODULE="core.settings"
ENTRYPOINT ["/app/docker-entrypoint"]
CMD ["manange"]
