FROM python:3.11-slim-bullseye
# RUN apk update
# RUN apk add gcc g++
# RUN apk add openssh
# # aiokafka
# RUN apk add zlib-dev geos-dev geos
# RUN apk add build-base make cmake

RUN apt-get update
RUN apt-get install -y openssh-client
RUN apt-get install -y build-essential make cmake
RUN apt-get install -y zlib1g-dev libgeos-dev libgeos-c1v5

RUN cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo 'Asia/Shanghai' >/etc/timezone

ADD ./pyproject.toml /base/pyproject.toml
ADD ./poetry.lock /base/poetry.lock
WORKDIR /base

RUN pip install poetry
ENV POETRY_VIRTUALENVS_CREATE=false
RUN poetry config installer.max-workers 10
RUN poetry install --all-extras --only main -vvv
