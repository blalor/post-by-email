# -*- encoding: utf-8 -*-

import logging
import os
import email.header
import StringIO
import codecs
import re

from slugify import slugify
import rtyaml as yaml

from time_util import parse_date, UTC
import exif_renderer
from collections import OrderedDict


def decode_header(hdr, default_charset="us-ascii"):
    ## decode_header returns (string, encoding)
    val, charset = email.header.decode_header(hdr)[0]
    return unicode(val, charset if charset else default_charset)


class PostExistsException(Exception):
    pass


class ImageExistsException(Exception):
    pass


class EmailHandler(object):
    """Generates Jekyll post from an email, possibly with attachments"""

    SIG_DELIMITER = re.compile(r"""^(--\s*|Sent from my iPhone)$""", re.IGNORECASE)

    def __init__(self, s3_bucket, s3_prefix, geocoder, git, commit_changes=False, jekyll_prefix=""):
        super(EmailHandler, self).__init__()

        self.logger = logging.getLogger(self.__class__.__name__)

        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.geocoder = geocoder
        self.git = git
        self.commit_changes = commit_changes
        self.jekyll_prefix = jekyll_prefix

    def __process_image(self, slug, photo):
        img_info = OrderedDict()

        img_path = os.path.join("email", "slug", photo.get_filename())
        s3_obj_name = os.path.join(self.s3_prefix, img_path)

        ## abort if image already exists
        if [k for k in self.s3_bucket.objects.filter(Prefix=s3_obj_name)]:
            raise ImageExistsException(s3_obj_name)

        img_info["path"] = img_path

        self.logger.debug("processing %s", s3_obj_name)

        photo_io = StringIO.StringIO(photo.get_payload(decode=True))
        img_info["exif"] = exif_renderer.render_stream(photo_io)

        ## get image location name with opencagedata
        loc = self.geocoder.reverse(
            [img_info["exif"]["location"]["latitude"], img_info["exif"]["location"]["longitude"]],
            exactly_one=True,
        )

        if loc:
            ## @todo set image timezone from location?
            img_info["exif"]["location"]["name"] = loc.address
        else:
            self.logger.warn("no reverse geocoding result found for %r", (img_info["exif"]["location"]["latitude"], img_info["exif"]["location"]["longitude"]))

        ## upload image to s3
        self.logger.debug("uploading to S3: %s", s3_obj_name)

        ## seek to the beginning of the file, so the entire thing is uploaded.
        ## exif_renderer seeks into the stream.
        photo_io.seek(0)
        self.s3_bucket.put_object(
            Key=s3_obj_name,
            Body=photo_io,
            ContentType="image/jpeg",  # @todo
        )

        self.logger.info("uploaded %s to S3", s3_obj_name)

        return img_info

    def process_stream(self, stream):
        return self.process_message(email.message_from_file(stream))

    def process_message(self, msg):
        self.logger.debug("%s from %s to %s: %s", msg["message-id"], msg["from"], msg["to"], msg["subject"])

        msg_date = parse_date(msg["Date"])

        ## group the parts by type
        msg_parts = {}
        for content_type, part in [(p.get_content_type(), p) for p in msg.walk()]:
            if content_type not in msg_parts:
                msg_parts[content_type] = []

            msg_parts[content_type].append(part)

        assert "text/plain" in msg_parts, "can't find plain text body"

        ## start building post frontmatter from headers
        fm = frontmatter = OrderedDict()

        fm["date"] = msg_date.isoformat()
        fm["title"] = post_title = decode_header(msg["Subject"])
        slug = "%s-%s" % (msg_date.astimezone(UTC).strftime("%Y-%m-%d"), slugify(fm["title"].encode("unicode_escape")))

        fm["layout"] = "post"

        fm["categories"] = "blog"
        fm["tags"] = []

        author_name, fm["author"] = email.utils.parseaddr(decode_header(msg["From"]))

        ## message body, decoded
        body = unicode(
            msg_parts["text/plain"][0].get_payload(decode=True),
            msg_parts["text/plain"][0].get_content_charset("utf-8"),
        )

        post_rel_fn = slug + ".md"
        post_full_fn = os.path.join(
            self.git.repo_path,
            self.jekyll_prefix,
            "_posts",
            "blog",
            post_rel_fn,
        )

        if os.path.exists(post_full_fn):
            raise PostExistsException(post_rel_fn)

        ## strip signature from body
        ## find last occurrence of the regex and drop everything else
        body_lines = body.split("\n")

        ## reverse list so we look from the end
        body_lines.reverse()

        sig_start_ind = 0
        for line in body_lines:
            sig_start_ind += 1

            if self.SIG_DELIMITER.match(line):
                break

        if sig_start_ind < len(body_lines):
            ## signature found
            body_lines = body_lines[sig_start_ind:]

        body_lines.reverse()

        if body_lines[0].lower().startswith("tags:"):
            fm["tags"].extend([t.strip() for t in body_lines[0][5:].strip().split(",")])
            del body_lines[0]

        ## recreate body
        body = u"\n".join(body_lines)

        if "image/jpeg" in msg_parts:
            fm["tags"].append("photo")
            fm["images"] = []
            for photo in msg_parts["image/jpeg"]:
                fm["images"].append(self.__process_image(slug, photo))

        self.logger.debug("generating %s", post_full_fn)

        with self.git.lock():
            if self.commit_changes:
                ## make the current master the same as the origin's master
                self.git.clean_sweep()

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

            self.logger.info("generated %s", post_rel_fn)

            if self.commit_changes:
                ## add the new file
                self.git.add_file(post_full_fn)

                ## commit the change
                self.git.commit(author_name, fm["author"], msg["date"], post_title)

                ## push the change
                self.git.push()
            else:
                self.logger.warn("not committing changes")

        return post_rel_fn
