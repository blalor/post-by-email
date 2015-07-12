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
import email
import email.header
from slugify import slugify

import rtyaml as yaml
from lib.git import Git
from lib.time_util import parse_date, UTC
from datetime import datetime

from collections import OrderedDict
import codecs
import StringIO
import exifread

import config
import tinys3

import itsdangerous
import hashlib

import geopy


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

geocoder = geopy.geocoders.OpenCage(config.OPENCAGE_API_KEY, timeout=5)

signer = itsdangerous.Signer(config.ADDR_VALIDATION_HMAC_KEY, sep="^", digest_method=hashlib.sha256)

git = Git(config.GIT_REPO, config.GIT_WORKING_COPY)


def decode_header(hdr, default_charset="us-ascii"):
    ## decode_header returns (string, encoding)
    val, charset = email.header.decode_header(hdr)[0]
    return unicode(val, charset if charset else default_charset)


def gps_to_float(ref, values):
    mult = 1 if ref in ("N", "E") else -1
    degrees, minutes, seconds = [float(v.num) / float(v.den) for v in values]
    return mult * (degrees + minutes/60.0 + seconds/3600.0)


@app.route("/email/<sender>/<addr_hash>", methods=["POST"])
def upload_email(sender, addr_hash):
    logger.info("processing request from %s with hash %s", sender, addr_hash)
    
    if not signer.validate("^".join([sender, addr_hash])):
        logger.warn("invalid hash from %s", sender)
        
        return "invalid hash", 403, {"Content-Type": "text/plain; charset=utf-8"}
    
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
    fm["title"] = post_title = decode_header(msg["Subject"])
    slug = "%s-%s" % (msg_date.astimezone(UTC).strftime("%Y-%m-%d"), slugify(fm["title"].encode("unicode_escape")))

    fm["layout"] = "post"
    
    fm["categories"] = "blog"
    fm["tags"] = ["photo"]
    
    author_name, fm["author"] = email.utils.parseaddr(decode_header(msg["From"]))
    
    ## message body, decoded
    body = unicode(
        msg_parts["text/plain"][0].get_payload(decode=True),
        msg_parts["text/plain"][0].get_content_charset("utf-8"),
    )

    post_rel_fn = slug + ".md"
    post_full_fn = os.path.join(config.GIT_WORKING_COPY, "_posts", "blog", post_rel_fn)
    
    if os.path.exists(post_full_fn):
        logger.error("post %s already exists", post_rel_fn)
        
        return "post %s exists" % post_rel_fn, 409, {"Content-Type": "text/plain; charset=utf-8"}

    # @todo strip signature from body
    
    fm["images"] = []
    for photo in msg_parts["image/jpeg"]:
        img_info = OrderedDict()
        s3_obj_name = os.path.join(config.S3_IMAGE_PATH_PREFIX, slug, photo.get_filename())

        ## abort if image already exists
        if [k for k in s3.list(s3_obj_name)]:
            logger.error("image %s already exists in S3", s3_obj_name)
            
            return "image %s exists in S3" % s3_obj_name, 409, {"Content-Type": "text/plain; charset=utf-8"}
        
        img_info["path"] = s3_obj_name

        logger.debug("processing %s", s3_obj_name)

        photo_io = StringIO.StringIO(photo.get_payload(decode=True))
        exif_tags = exifread.process_file(photo_io)

        img_info["exif"] = {
            ## use GPSDate, GPSTimeStamp if available
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
        
        ## get image location name with opencagedata
        loc = geocoder.reverse(
            [img_info["exif"]["location"]["latitude"], img_info["exif"]["location"]["longitude"]],
            exactly_one=True,
        )
        
        if loc:
            ## @todo set image timezone from location?
            img_info["exif"]["location"]["name"] = loc.address
        else:
            logger.warn("no reverse geocoding result found for %r", (img_info["exif"]["location"]["latitude"], img_info["exif"]["location"]["longitude"]))
        
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

    with git.lock():
        if config.COMMIT_CHANGES:
            ## make the current master the same as the origin's master
            git.clean_sweep()
        
        ## @todo consider making every change a PR and automatically approving them

        if not os.path.exists(os.path.dirname(post_full_fn)):
            os.makedirs(os.path.dirname(post_full_fn))
        
        with codecs.open(post_full_fn, "w", encoding="utf-8") as ofp:
            ## I *want* to use yaml, but I can't get it to properly to encode
            ## "Test 🔫"; kept getting "Test \uD83D\uDD2B" which the Go yaml parser
            ## bitched about.
            ## but I'm not hitched to hugo, yet, and yaml is what jekyll uses, so…
            ofp.write("---\n")
            
            ## hack for title which the yaml generator won't do properly
            ofp.write('title: "%s"\n' % fm["title"])
            del fm["title"]
            yaml.dump(frontmatter, ofp)

            ## we want an space between the frontmatter and the body
            ofp.write("---\n\n")
            ofp.write(body)
        
        logger.info("generated %s", post_rel_fn)
        
        if config.COMMIT_CHANGES:
            ## add the new file
            git.add_file(post_full_fn)
            
            ## commit the change
            git.commit(author_name, fm["author"], msg["date"], post_title)
            
            ## push the change
            git.push()

    logger.info("successfully created %s", post_rel_fn)
    return post_rel_fn, 201, {"Content-Type": "text/plain; charset=utf-8"}


if __name__ == "__main__":
    logger.info("ready")
    app.run()
