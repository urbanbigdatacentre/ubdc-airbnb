FROM continuumio/miniconda3
ENV PROJ_LIB=/opt/conda/share/proj
ENV PYTHONUNBUFFERED=1

RUN chmod -eox;\
    apt-get update;\
    conda install mkl-service gdal=3


ADD ./src/dj_airbnb /code/dj_airbnb
ADD ./docker-entrypoint.sh /code/docker-entrypoint.sh
ADD ./requirements.txt /code/requirements.txt

WORKDIR /code
RUN chmod +x docker-entrypoint.sh
RUN pip install -r requirements.txt

ENV PYTHONPATH=/code/dj_airbnb

ENTRYPOINT ["./docker-entrypoint.sh"]
