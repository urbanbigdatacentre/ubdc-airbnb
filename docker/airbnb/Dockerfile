FROM osgeo/gdal:ubuntu-small-3.2.3
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/code/dj_airbnb


RUN chmod -eox;\
    apt-get update;\
    apt-get install python3-pip -y -q

ADD ./requirements.txt /requirements.txt
RUN pip install -r requirements.txt


ADD ./src/dj_airbnb /code/dj_airbnb
ADD ./docker-entrypoint.sh /code/docker-entrypoint.sh

WORKDIR /code
RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]
