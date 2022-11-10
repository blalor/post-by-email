#!/usr/bin/env python
# -*- encoding: utf-8 -*-

## https://docs.aws.amazon.com/ses/latest/DeveloperGuide/receiving-email-notifications-examples.html


import json
import logging
import tempfile

import boto3
import itsdangerous
import hashlib
import geopy

## this module is not on the path, so imports must be relative
from . import config
from .lib.EmailHandler import EmailHandler, PostExistsException
from .lib.git import Git

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.resource("s3")
image_bucket = s3.Bucket(config.S3_IMAGE_BUCKET)

geocoder = geopy.geocoders.OpenCage(config.OPENCAGE_API_KEY, timeout=5)

signer = itsdangerous.Signer(
    config.ADDR_VALIDATION_HMAC_KEY,
    sep="^",
    digest_method=hashlib.sha256,
)


def lambda_handler(event, context):
    logger.info("got event: %r", event)

    for rec in event["Records"]:
        assert rec["EventSource"] == "aws:sns"

        message = json.loads(rec["Sns"]["Message"])
        assert message["notificationType"] == "Received"

        action = message["receipt"]["action"]
        assert action["type"] == "S3"

        # sender = message["mail"]["source"]["from"][0]  ## contains name <addr>
        sender = message["mail"]["source"]
        sender_validated = False
        for recipient in message["receipt"]["recipients"]:
            recip, domain = recipient.split("@", 1)

            if domain.lower() == config.RECEIVING_DOMAIN:
                target, addr_hash = recip.split(config.EXTENSION_DELIMITER, 1)
                print((target, addr_hash))

                logger.info("processing request for %s from %s with hash %s", target, sender, addr_hash)

                if not signer.validate("^".join([sender, addr_hash])):
                    logger.warn("invalid hash from %s", sender)
                else:
                    sender_validated = True

        if sender_validated:
            ## retrieve message body from s3
            email_bucket = s3.Bucket(action["bucketName"])
            emailObj = email_bucket.Object(action["objectKey"])

            git = Git(config.GIT_REPO, tempfile.mkdtemp())
            git.clone()

            mail_handler = EmailHandler(
                image_bucket,
                config.S3_IMAGE_PATH_PREFIX,
                geocoder,
                git,
                commit_changes=config.COMMIT_CHANGES,
                jekyll_prefix=config.JEKYLL_PREFIX,
            )

            do_remove_object = False
            try:
                post_path = mail_handler.process_stream(emailObj.get()["Body"])
                logger.info("successfully created %s", post_path)
                do_remove_object = True

            except PostExistsException:
                logger.error("email has already been processed (hopefully)", exc_info=True)
                do_remove_object = True

            if do_remove_object:
                logger.info("deleting %s", emailObj.key)
                emailObj.delete()

        else:
            logger.error("no valid senders found")


if __name__ == "__main__":
    import sys

    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(format=log_format, level=logging.INFO)

    email_evt_payload = json.load(open(sys.argv[1]))

    lambda_handler(email_evt_payload, None)
