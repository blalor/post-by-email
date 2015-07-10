# -*- encoding: utf-8 -*-

import os

COMMIT_CHANGES = os.environ.get("COMMIT_CHANGES", "False").lower() == "true"

## tr -dc A-Za-z0-9 < /dev/urandom | head -c 40
ADDR_VALIDATION_HMAC_KEY = os.environ["ADDR_VALIDATION_HMAC_KEY"]

## like "https://<token>:x-oauth-basic@github.com/<owner>/<repo>.git"
## yeah, includes the auth; should make it fairly simple, if a bit cumbersome…
GIT_REPO = os.environ["GIT_REPO"]
GIT_WORKING_COPY = os.environ["GIT_WORKING_COPY"]

GIT_COMMITTER_NAME = os.environ.get("GIT_COMMITTER_NAME", "post by email")

## http://hipsterdevblog.com/blog/2014/06/22/lazy-processing-images-using-s3-and-redirection-rules/
## https://github.com/thumbor/thumbor/wiki
## http://www.dadoune.com/blog/best-thumbnailing-solution-set-up-thumbor-on-aws/

S3_IMAGE_BUCKET = os.environ["S3_IMAGE_BUCKET"]
S3_IMAGE_PATH_PREFIX = os.environ["S3_IMAGE_PATH_PREFIX"]

AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]

## reverse geocoding service
## http://geocoder.opencagedata.com/demo.html
OPENCAGE_API_KEY = os.environ["OPENCAGE_API_KEY"]
