#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import logging
import logging.handlers

log_format = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(format=log_format, level=logging.WARN)

# syslog_handler = logging.handlers.SysLogHandler()
# syslog_handler.setLevel(logging.INFO)
# syslog_handler.setFormatter(logging.Formatter(log_format))

import os
import shutil
import email
import email.header
from slugify import slugify

import json
import subprocess
import tempfile
from file_lock import file_lock
from time_util import parse_date, UTC
from datetime import datetime

from collections import OrderedDict
import codecs
import StringIO
import exifread

import config
import tinys3


from flask import Flask, request
app = Flask(__name__)
logger = app.logger
logger.setLevel(logging.DEBUG)

s3 = tinys3.Connection(
    config.AWS_ACCESS_KEY_ID,
    config.AWS_SECRET_ACCESS_KEY,
    default_bucket=config.S3_IMAGE_BUCKET,
    tls=True,
)


def decode_header(hdr, default_charset="us-ascii"):
    ## decode_header returns (string, encoding)
    val, charset = email.header.decode_header(hdr)[0]
    return unicode(val, charset if charset else default_charset)


def gps_to_float(ref, values):
    mult = 1 if ref in ("N", "E") else -1
    degrees, minutes, seconds = [float(v.num) / float(v.den) for v in values]
    return mult * (degrees + minutes/60.0 + seconds/3600.0)


@app.route("/email/<addr_extension>", methods=["POST"])
def upload_email(addr_extension):
    logger.info("processing request for %s", addr_extension)
    
    msg = email.message_from_file(request.stream)
    
    logger.debug("%s from %s to %s: %s", msg["message-id"], msg["from"], msg["to"], msg["subject"])
    
    msg_date = parse_date(msg["Date"])
    
    ## group the parts by type
    msg_parts = {}
    for content_type, part in [(p.get_content_type(), p) for p in msg.walk()]:
        if content_type not in msg_parts:
            msg_parts[content_type] = []
        
        msg_parts[content_type].append(part)
    
    assert "text/plain" in msg_parts, "can't find plain text body"
    assert "image/jpeg" in msg_parts, "can't find JPEG attachment(s)"
    
    ## start building post frontmatter from headers
    fm = frontmatter = OrderedDict()
    
    fm["date"] = msg_date.isoformat()
    fm["title"] = decode_header(msg["Subject"])
    fm["slug"] = "%s-%s" % (msg_date.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S"), slugify(fm["title"].encode("unicode_escape")))
    fm["addr_extension"] = addr_extension

    author = email.utils.parseaddr(decode_header(msg["From"]))
    fm["author"] = {
        "name": author[0],
        "email": author[1],
    }
    
    ## message body, decoded
    body = unicode(
        msg_parts["text/plain"][0].get_payload(decode=True),
        msg_parts["text/plain"][0].get_content_charset("utf-8"),
    )

    post_rel_fn = os.path.join("post", fm["slug"] + ".md")
    post_full_fn = os.path.join(config.GIT_WORKING_COPY, post_rel_fn)
    
    if os.path.exists(post_full_fn):
        logger.error("post %s already exists", post_rel_fn)
        
        return "post %s exists" % post_rel_fn, 409, {"Content-Type": "text/plain; charset=utf-8"}

    # @todo strip signature from body
    
    fm["images"] = []
    for photo in msg_parts["image/jpeg"]:
        img_info = {}
        s3_obj_name = os.path.join(config.S3_IMAGE_PATH_PREFIX, fm["slug"], photo.get_filename())

        img_info["path"] = s3_obj_name

        logger.debug("processing %s", s3_obj_name)

        photo_io = StringIO.StringIO(photo.get_payload(decode=True))
        exif_tags = exifread.process_file(photo_io)

        img_info["exif"] = {
            "dateTimeOriginal": datetime.strptime(exif_tags["EXIF DateTimeOriginal"].printable, "%Y:%m:%d %H:%M:%S").isoformat(),
            "cameraMake": exif_tags["Image Make"].printable,
            "cameraModel": exif_tags["Image Model"].printable,
            "lensModel": exif_tags["EXIF LensModel"].printable,
            "cameraSWVer": exif_tags["Image Software"].printable,
            "location": {
                "latitude": gps_to_float(exif_tags["GPS GPSLatitudeRef"].values, exif_tags["GPS GPSLatitude"].values),
                "longitude": gps_to_float(exif_tags["GPS GPSLongitudeRef"].values, exif_tags["GPS GPSLongitude"].values),
            }
        }
        
        ## @todo get image location name with opencagedata
        ## @todo get image timezone from location
        
        ## abort if image already exists
        if [k for k in s3.list(s3_obj_name)]:
            logger.error("image %s already exists in S3", s3_obj_name)
            
            return "image %s exists in S3" % s3_obj_name, 409, {"Content-Type": "text/plain; charset=utf-8"}
        
        ## upload image to s3
        logger.debug("uploading to S3: %s", s3_obj_name)

        s3.upload(
            s3_obj_name,
            photo_io,
            content_type="image/jpeg",  # @todo
            close=True,  # close file afterwards
            rewind=True,  # defaults to True, but just in case…
        )

        logger.info("uploaded %s to S3", s3_obj_name)

        fm["images"].append(img_info)
    
    logger.debug("generating %s", post_full_fn)

    with file_lock(os.path.join(config.GIT_WORKING_COPY, ".git", "render_post.lock")):
        ## make the current master the same as the origin's master
        subprocess.check_call(["git", "fetch"], cwd=config.GIT_WORKING_COPY)
        subprocess.check_call(
            [
                "git", "reset",
                "--quiet",
                "--hard", "origin/master",
            ],
            cwd=config.GIT_WORKING_COPY,
        )
        
        ## make it squeaky clean
        subprocess.check_call(
            ["git", "clean", "-f", "-d", "-x"],
            cwd=config.GIT_WORKING_COPY,
        )
        
        ## @todo consider making every change a PR and automatically approving them

        if not os.path.exists(os.path.dirname(post_full_fn)):
            os.makedirs(os.path.dirname(post_full_fn))
        
        with codecs.open(post_full_fn, "w", encoding="utf-8") as ofp:
            ## I *want* to use yaml, but I can't get it to properly to encode
            ## "Test 🔫"; kept getting "Test \uD83D\uDD2B" which the Go yaml parser
            ## bitched about.
            json.dump(frontmatter, ofp, indent=4)

            ## 2 extra newlines; json.dump doesn't write a newline and we want a
            ## space between the frontmatter and the body
            ofp.write("\n\n")
            ofp.write(body)
        
        logger.info("generated %s", post_rel_fn)
        
        ## add the new file
        subprocess.check_call(
            ["git", "add", post_rel_fn],
            cwd=config.GIT_WORKING_COPY,
        )
        
        ## commit the change
        # @todo ensure there are actual changes to be made
        ## write commit message to temp file
        with tempfile.TemporaryFile() as tf:
            tf.write(fm["title"].encode("utf-8"))
            tf.seek(0)
            
            subprocess.check_call(
                [
                    "git", "commit",
                    "--file=-",
                    "--quiet",
                ],
                stdin=tf,
                cwd=config.GIT_WORKING_COPY,
                env={
                    "GIT_AUTHOR_NAME":     fm["author"]["name"],
                    "GIT_AUTHOR_EMAIL":    fm["author"]["email"],
                    "GIT_AUTHOR_DATE":     msg["date"],
                    
                    ## adding delivered-to exposes the email address used to create posts!
                    # "GIT_COMMITTER_NAME":  config.GIT_COMMITTER_NAME,
                    # "GIT_COMMITTER_EMAIL": msg["delivered-to"],
                },
            )
        
        ## push the change
        subprocess.check_call(
            [
                "git", "push", "--quiet"
            ],
            cwd=config.GIT_WORKING_COPY,
        )

    logger.info("successfully created %s", post_rel_fn)
    return post_rel_fn, 201, {"Content-Type": "text/plain; charset=utf-8"}


if __name__ == "__main__":
    logger.info("cloning repository")
    
    shutil.rmtree(config.GIT_WORKING_COPY)
    
    subprocess.check_call(
        [
            "git", "clone",
            "--depth", "1",
            "--quiet",
            config.GIT_REPO,
            config.GIT_WORKING_COPY,
        ],
        env={
            ## disable template; my pre-commit hook checks for user.{email,name}
            "GIT_TEMPLATE_DIR": "",
        },
    )
    
    logger.info("ready")
    app.run()
