#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import logging
import logging.handlers

log_format = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(format=log_format, level=logging.WARN)

# syslog_handler = logging.handlers.SysLogHandler()
# syslog_handler.setLevel(logging.INFO)
# syslog_handler.setFormatter(logging.Formatter(log_format))

import config
from lib.EmailHandler import EmailHandler

import itsdangerous
import hashlib

import geopy
import tinys3
from lib.git import Git

from flask import Flask, request
app = Flask(__name__)
logger = app.logger
logger.setLevel(logging.DEBUG)

geocoder = geopy.geocoders.OpenCage(config.OPENCAGE_API_KEY, timeout=5)
git = Git(config.GIT_REPO, config.GIT_WORKING_COPY)
s3 = tinys3.Connection(
    config.AWS_ACCESS_KEY_ID,
    config.AWS_SECRET_ACCESS_KEY,
    default_bucket=config.S3_IMAGE_BUCKET,
    tls=True,
)

mail_handler = EmailHandler(s3, config.S3_IMAGE_PATH_PREFIX, geocoder, git, config.COMMIT_CHANGES)
signer = itsdangerous.Signer(config.ADDR_VALIDATION_HMAC_KEY, sep="^", digest_method=hashlib.sha256)


@app.route("/email/<sender>/<addr_hash>", methods=["POST"])
def upload_email(sender, addr_hash):
    logger.info("processing request from %s with hash %s", sender, addr_hash)
    
    if not signer.validate("^".join([sender, addr_hash])):
        logger.warn("invalid hash from %s", sender)
        
        return "invalid hash", 403, {"Content-Type": "text/plain; charset=utf-8"}
    
    post_path = mail_handler.process_stream(request.stream)

    logger.info("successfully created %s", post_path)
    return post_path, 201, {"Content-Type": "text/plain; charset=utf-8"}


if __name__ == "__main__":
    logger.info("ready")
    app.run()
