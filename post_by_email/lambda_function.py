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
    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(format=log_format, level=logging.INFO)

    email_evt_payload = json.dumps({
        "notificationType": "Received",
        "receipt": {
            "timestamp": "2015-09-11T20:32:33.936Z",
            "processingTimeMillis": 406,
            "recipients": [
                "post+JFFtVp-uPMYXWvzIThlJVEDgsW6MAxH6jqlFIO7T0Ok@example.com"
            ],
            "spamVerdict": {
                "status": "PASS"
            },
            "virusVerdict": {
                "status": "PASS"
            },
            "spfVerdict": {
                "status": "PASS"
            },
            "dkimVerdict": {
                "status": "PASS"
            },
            "action": {
                "type": "S3",
                "topicArn": "arn:aws:sns:us-east-1:012345678912:example-topic",
                "bucketName": "beta5.org-20180818131208298800000001",
                "objectKey": "emails/u8vm5b2jqkm6k1ktbl2b5959j1si1t81s11d1rg1"
            }
        },
        "mail": {
            "timestamp": "2015-09-11T20:32:33.936Z",
            "source": "0000014fbe1c09cf-7cb9f704-7531-4e53-89a1-5fa9744f5eb6-000000@amazonses.com",
            "messageId": "d6iitobk75ur44p8kdnnp7g2n800",
            "destination": [
                "post+JFFtVp-uPMYXWvzIThlJVEDgsW6MAxH6jqlFIO7T0Ok@example.com"
            ],
            "headersTruncated": False,
            "headers": [
                {
                    "name": "Return-Path",
                    "value": "<0000014fbe1c09cf-7cb9f704-7531-4e53-89a1-5fa9744f5eb6-000000@amazonses.com>"
                },
                {
                    "name": "Received",
                    "value": "from a9-183.smtp-out.amazonses.com (a9-183.smtp-out.amazonses.com [54.240.9.183]) by inbound-smtp.us-east-1.amazonaws.com with SMTP id d6iitobk75ur44p8kdnnp7g2n800 for post+JFFtVp-uPMYXWvzIThlJVEDgsW6MAxH6jqlFIO7T0Ok@example.com; Fri, 11 Sep 2015 20:32:33 +0000 (UTC)"
                },
                {
                    "name": "DKIM-Signature",
                    "value": "v=1; a=rsa-sha256; q=dns/txt; c=relaxed/simple; s=ug7nbtf4gccmlpwj322ax3p6ow6yfsug; d=amazonses.com; t=1442003552; h=From:To:Subject:MIME-Version:Content-Type:Content-Transfer-Encoding:Date:Message-ID:Feedback-ID; bh=DWr3IOmYWoXCA9ARqGC/UaODfghffiwFNRIb2Mckyt4=; b=p4ukUDSFqhqiub+zPR0DW1kp7oJZakrzupr6LBe6sUuvqpBkig56UzUwc29rFbJF hlX3Ov7DeYVNoN38stqwsF8ivcajXpQsXRC1cW9z8x875J041rClAjV7EGbLmudVpPX 4hHst1XPyX5wmgdHIhmUuh8oZKpVqGi6bHGzzf7g="
                },
                {
                    "name": "From",
                    "value": "sender@example.com"
                },
                {
                    "name": "To",
                    "value": "post+JFFtVp-uPMYXWvzIThlJVEDgsW6MAxH6jqlFIO7T0Ok@example.com"
                },
                {
                    "name": "Subject",
                    "value": "Example subject"
                },
                {
                    "name": "MIME-Version",
                    "value": "1.0"
                },
                {
                    "name": "Content-Type",
                    "value": "text/plain; charset=UTF-8"
                },
                {
                    "name": "Content-Transfer-Encoding",
                    "value": "7bit"
                },
                {
                    "name": "Date",
                    "value": "Fri, 11 Sep 2015 20:32:32 +0000"
                },
                {
                    "name": "Message-ID",
                    "value": "<61967230-7A45-4A9D-BEC9-87CBCF2211C9@example.com>"
                },
                {
                    "name": "X-SES-Outgoing",
                    "value": "2015.09.11-54.240.9.183"
                },
                {
                    "name": "Feedback-ID",
                    "value": "1.us-east-1.Krv2FKpFdWV+KUYw3Qd6wcpPJ4Sv/pOPpEPSHn2u2o4=:AmazonSES"
                }
            ],
            "commonHeaders": {
                "returnPath": "0000014fbe1c09cf-7cb9f704-7531-4e53-89a1-5fa9744f5eb6-000000@amazonses.com",
                "from": [
                    "sender@example.com"
                ],
                "date": "Fri, 11 Sep 2015 20:32:32 +0000",
                "to": [
                    "post+JFFtVp-uPMYXWvzIThlJVEDgsW6MAxH6jqlFIO7T0Ok@example.com"
                ],
                "messageId": "<61967230-7A45-4A9D-BEC9-87CBCF2211C9@example.com>",
                "subject": "Example subject"
            }
        }
    })

    lambda_handler(
        {
            "Records": [
                {
                    "EventSource": "aws:sns",
                    "Sns": {
                        "Message": email_evt_payload
                    }
                }
            ]
        },
        None,
    )
