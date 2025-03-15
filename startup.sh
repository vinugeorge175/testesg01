#!/bin/bash
cd /home/site/wwwroot
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
