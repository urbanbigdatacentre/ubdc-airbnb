FROM python:3.10 as python-builder
WORKDIR /tmp
RUN pip install poetry
COPY ./poetry.lock* ./pyproject.toml /tmp/
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

FROM osgeo/gdal:ubuntu-small-3.5.3 as runner
ENV PYTHONUNBUFFERED=1
RUN chmod -eox;\
    apt-get update;\
    apt-get install python3-pip -y -q

WORKDIR /app
COPY --from=python-builder /tmp/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

COPY ./src/ubdc_airbnb /app
COPY ./docker-entrypoint.sh /app/docker-entrypoint
RUN chmod +x docker-entrypoint

ENTRYPOINT ["docker-entrypoint"]
CMD ["bash"]
