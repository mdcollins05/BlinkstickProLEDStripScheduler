#!/bin/bash

pipenv run python /app/server.py -c /app/schedule.yml --ignore-failed --morph --verbose
