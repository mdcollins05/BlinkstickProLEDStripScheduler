FROM python:3.9-slim AS builder

RUN apt-get update && \
  apt-get install -y --no-install-recommends build-essential wget ca-certificates gcc python3-dev && \
  pip install pipenv

WORKDIR /app

COPY Pipfile Pipfile.lock ./

RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy

COPY . ./

FROM python:3.9-slim

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
  apt-get install -y --no-install-recommends tini nano supervisor libusb-1.0-0 && \
  pip3 install pipenv && \
  apt-get autoremove -y && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

RUN useradd -u 911 -U -d /app/config -s /bin/false runner && \
  usermod -G users runner && \
  mkdir -p /app/config

COPY --from=builder /app/ ./

CMD ["/usr/bin/tini", "--", "/app/start.sh"]
