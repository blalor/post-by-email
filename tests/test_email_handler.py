# -*- encoding: utf-8 -*-

from post_by_email.lib.EmailHandler import EmailHandler

import mock
import os
import shutil
import tempfile
import gzip
import email.header
import rtyaml as yaml
import io
import geopy
from email.mime.text import MIMEText
from email.utils import formatdate


def parse_post(fn):
    buf = io.StringIO()

    with open(fn, "r", encoding="utf-8") as ifp:
        ## must start with ---\n
        line = ifp.readline()
        assert line == "---\n"

        while True:
            line = ifp.readline()
            if line == "---\n":
                break

            buf.write(line)

        buf.seek(0)
        return yaml.load(buf), ifp.read()


class TestEmailHandler:
    FIXTURE_DIR = os.path.abspath(os.path.join(__file__, "../../test-fixtures"))

    def setup_method(self):
        self.git_repo_dir = tempfile.mkdtemp()

        ## mock of tinys3.Connection
        self.mock_s3_bucket = mock.Mock()

        ## mock of geopy.geocoders.OpenCage
        self.mock_geocoder = mock.Mock()

        ## mock of lib.git.Git
        self.mock_git = mock.Mock()
        self.mock_git.repo_path = self.git_repo_dir
        self.mock_git.lock = mock.MagicMock()

        self.handler = EmailHandler(self.mock_s3_bucket, "img", self.mock_geocoder, self.mock_git, commit_changes=True)

    def teardown_method(self):
        shutil.rmtree(self.git_repo_dir)

    def test_parseMessage(self):
        self.mock_s3_bucket.objects.filter.return_value = []

        lat, lon = 42.347011111111115, -71.09632222222221
        location = geopy.location.Location(
            "the park",
            point=geopy.location.Point(lat, lon, 0),
            raw={
                'annotations': {'DMS': {'lat': "42\xb0 20' 49.39584'' N",
                                          'lng': "71\xb0 5' 47.26752'' W"},
                                 'FIPS': {'county': '25025', 'state': '25'},
                                 'MGRS': '19TCG2731890439',
                                 'Maidenhead': 'FN42ki83kh',
                                 'Mercator': {'x': -7914422.081, 'y': 5184317.945},
                                 'OSM': {'edit_url': 'https://www.openstreetmap.org/edit?node=1712242950#map=17/42.34705/-71.09646',
                                          'url': 'https://www.openstreetmap.org/?mlat=42.34705&mlon=-71.09646#map=17/42.34705/-71.09646'},
                                 'callingcode': 1,
                                 'currency': {'alternate_symbols': ['US$'],
                                               'decimal_mark': '.',
                                               'disambiguate_symbol': 'US$',
                                               'html_entity': '$',
                                               'iso_code': 'USD',
                                               'iso_numeric': 840,
                                               'name': 'United States Dollar',
                                               'smallest_denomination': 1,
                                               'subunit': 'Cent',
                                               'subunit_to_unit': 100,
                                               'symbol': '$',
                                               'symbol_first': 1,
                                               'thousands_separator': ','},
                                 'flag': '\U0001f1fa\U0001f1f8',
                                 'geohash': 'drt2yjj1kr4ej6jr10s8',
                                 'qibla': 60.4,
                                 'sun': {'rise': {'apparent': 1536055980,
                                                    'astronomical': 1536050040,
                                                    'civil': 1536054240,
                                                    'nautical': 1536052200},
                                          'set': {'apparent': 1536102660,
                                                   'astronomical': 1536022140,
                                                   'civil': 1536104400,
                                                   'nautical': 1536020040}},
                                 'timezone': {'name': 'America/New_York',
                                               'now_in_dst': 1,
                                               'offset_sec': -14400,
                                               'offset_string': -400,
                                               'short_name': 'EDT'},
                                 'what3words': {'words': 'tour.humans.sport'}},
                'bounds': {'northeast': {'lat': 42.3471544, 'lng': -71.0963632},
                            'southwest': {'lat': 42.3469544, 'lng': -71.0965632}},
                'components': {'ISO_3166-1_alpha-2': 'US',
                                '_type': 'bar',
                                'bar': 'Bleacher Bar',
                                'city': 'Boston',
                                'country': 'USA',
                                'country_code': 'us',
                                'county': 'Suffolk County',
                                'house_number': '82A',
                                'neighbourhood': 'Roxbury Crossing',
                                'postcode': '02114',
                                'road': 'Lansdowne Street',
                                'state': 'Massachusetts',
                                'state_code': 'MA',
                                'suburb': 'Fenway'},
                'confidence': 9,
                'formatted': 'Bleacher Bar, 82A Lansdowne Street, Boston, MA 02114, United States of America',
                'geometry': {'lat': 42.3470544, 'lng': -71.0964632}
            }
        )
        self.mock_geocoder.reverse.return_value = location

        self.mock_s3_bucket.put_object.return_value = None

        with gzip.open(os.path.join(self.FIXTURE_DIR, "photo-1.msg.gz"), "rt", encoding="utf-8") as ifp:
            post_path = self.handler.process_stream(ifp)

        assert post_path == "2015-07-05-fenway-fireworks.md"
        post_fn = os.path.join(self.git_repo_dir, "_posts", "blog", post_path)

        self.mock_s3_bucket.objects.filter.assert_called_once_with(Prefix="img/email/2015-07-05-fenway-fireworks/IMG_5810.JPG")
        assert self.mock_s3_bucket.put_object.call_args[1]["Key"] == "img/email/2015-07-05-fenway-fireworks/IMG_5810.JPG"
        assert self.mock_s3_bucket.put_object.call_args[1]["ContentType"] == "image/jpeg"

        self.mock_git.clean_sweep.assert_called_once_with()
        self.mock_git.add_file.assert_called_once_with(post_fn)
        self.mock_git.commit.called_once_with("Brian Lalor", "blalor@bravo5.org", "Sun, 5 Jul 2015 07:28:43 -0400", "Fenway fireworks")
        self.mock_git.push.called_once_with()

        ## bet those float comparisons will bite me later!
        self.mock_geocoder.reverse.assert_called_once_with((lat, lon), exactly_one=True)

        frontmatter, body = parse_post(post_fn)
        # {'author': 'blalor@bravo5.org',
        #  'categories': 'blog',
        #  'date': '2015-07-05T07:28:43-04:00',
        #  'images': {'img_5810_jpg': OrderedDict([('path', 'img/email/2015-07-05-fenway-fireworks/IMG_5810.JPG'), ('exif', OrderedDict([('cameraMake', 'Apple'), ('cameraModel', 'iPhone 6'), ('cameraSWVer', '8.4'), ('dateTimeOriginal', '2015-07-03T23:39:33'), ('lensModel', 'iPhone 6 back camera 4.15mm f/2.2'), ('location', OrderedDict([('latitude', 42.347011111111115), ('longitude', -71.09632222222221)]))]))])},
        #  'layout': 'post',
        #  'tags': ['photo'],
        #  'title': 'Fenway fireworks'}
        assert frontmatter["author"] == "blalor@bravo5.org"
        assert frontmatter["categories"] == "blog"
        assert "photo" in frontmatter["tags"]

        assert len(frontmatter["images"]) == 1
        img = frontmatter["images"]["img_5810_jpg"]
        assert img["exif"]["location"]["latitude"] == lat
        assert img["exif"]["location"]["longitude"] == lon
        assert img["exif"]["location"]["name"] == "Bleacher Bar, Boston, MA 🇺🇸"

        assert r"{% include exif-image.html img=page.images.img_5810_jpg %}" in body

    def test_parseMessagePreservingEmoji(self):
        msg = MIMEText("""Foo 👍🔫""".encode("utf-8"), "plain", "UTF-8")

        msg["Message-ID"] = "7351da42-12a8-41a1-9b60-25ee7b784720"
        msg["From"] = "Brian Lalor <blalor@bravo5.org>"
        msg["To"] = "photos@localhost"
        msg["Subject"] = email.header.make_header([
            ("just some 💬".encode("utf-8"), "utf-8")
        ])
        msg["Date"] = formatdate(1436782211)

        post_path = self.handler.process_message(msg)

        assert post_path == "2015-07-13-just-some-u0001f4ac.md"
        post_fn = os.path.join(self.git_repo_dir, "_posts", "blog", post_path)

        _, body = parse_post(post_fn)
        assert body == "\nFoo 👍🔫"

    def test_handleNoPhotos(self):
        msg = MIMEText("""Just a test; no photos.""")
        msg["Message-ID"] = "7351da42-12a8-41a1-9b60-25ee7b784720"
        msg["From"] = "Brian Lalor <blalor@bravo5.org>"
        msg["To"] = "photos@localhost"
        msg["Subject"] = "just some text"
        msg["Date"] = formatdate(1436782211)

        post_path = self.handler.process_message(msg)

        assert post_path == "2015-07-13-just-some-text.md"
        post_fn = os.path.join(self.git_repo_dir, "_posts", "blog", post_path)

        assert not self.mock_s3_bucket.objects.filter.called
        assert not self.mock_geocoder.reverse.called

        frontmatter, _ = parse_post(post_fn)
        # {'author': 'blalor@bravo5.org',
        #  'categories': 'blog',
        #  'date': '2015-07-05T07:28:43-04:00',
        #  'layout': 'post',
        #  'tags': ['photo'],
        #  'title': 'Fenway fireworks'}
        assert frontmatter["author"] == "blalor@bravo5.org"
        assert "photo" not in frontmatter["tags"]
        assert "images" not in frontmatter

    def test_stripSignature(self):
        msg = MIMEText("""some text ramble ramble bla bla bla

--
Nobody
nobody@home.com
""")

        msg["Message-ID"] = "7351da42-12a8-41a1-9b60-25ee7b784720"
        msg["From"] = "Brian Lalor <blalor@bravo5.org>"
        msg["To"] = "photos@localhost"
        msg["Subject"] = "just some text"
        msg["Date"] = formatdate(1436782211)

        post_path = self.handler.process_message(msg)

        assert post_path == "2015-07-13-just-some-text.md"
        post_fn = os.path.join(self.git_repo_dir, "_posts", "blog", post_path)

        _, body = parse_post(post_fn)
        assert body.startswith("\nsome text ramble ramble")
        assert "-- \nNobody\nnobody@home.com" not in body, "found signature"

    def test_stripSignature2(self):
        msg = MIMEText("""some text ramble ramble bla bla bla

Sent from my iPhone""")

        msg["Message-ID"] = "7351da42-12a8-41a1-9b60-25ee7b784720"
        msg["From"] = "Brian Lalor <blalor@bravo5.org>"
        msg["To"] = "photos@localhost"
        msg["Subject"] = "just some text"
        msg["Date"] = formatdate(1436782211)

        post_path = self.handler.process_message(msg)

        assert post_path == "2015-07-13-just-some-text.md"
        post_fn = os.path.join(self.git_repo_dir, "_posts", "blog", post_path)

        _, body = parse_post(post_fn)
        assert body.startswith("\nsome text ramble ramble")
        assert "Sent from my iPhone" not in body, "found signature"

    def test_addTagsFromMsg(self):
        msg = MIMEText("""tags: foo, baz bap
some text ramble ramble bla bla bla
""")

        msg["Message-ID"] = "7351da42-12a8-41a1-9b60-25ee7b784720"
        msg["From"] = "Brian Lalor <blalor@bravo5.org>"
        msg["To"] = "photos@localhost"
        msg["Subject"] = "just some text"
        msg["Date"] = formatdate(1436782211)

        post_path = self.handler.process_message(msg)

        assert post_path == "2015-07-13-just-some-text.md"
        post_fn = os.path.join(self.git_repo_dir, "_posts", "blog", post_path)

        frontmatter, body = parse_post(post_fn)
        assert "foo" in frontmatter["tags"]
        assert "baz bap" in frontmatter["tags"]

        assert body.startswith("\nsome text ramble ramble")

    def test_addTagsFromMsgUppercase(self):
        msg = MIMEText("""Tags: foo, baz bap""")

        msg["Message-ID"] = "7351da42-12a8-41a1-9b60-25ee7b784720"
        msg["From"] = "Brian Lalor <blalor@bravo5.org>"
        msg["To"] = "photos@localhost"
        msg["Subject"] = "just some text"
        msg["Date"] = formatdate(1436782211)

        post_fn = os.path.join(self.git_repo_dir, "_posts", "blog", self.handler.process_message(msg))

        frontmatter, _ = parse_post(post_fn)
        assert "foo" in frontmatter["tags"]
        assert "baz bap" in frontmatter["tags"]

    def test_extractsGPSTimestamp(self):
        self.mock_s3_bucket.objects.filter.return_value = []
        self.mock_geocoder.reverse.return_value = None
        self.mock_s3_bucket.upload.return_value = None

        with gzip.open(os.path.join(self.FIXTURE_DIR, "photo-1.msg.gz"), "rt", encoding="utf-8") as ifp:
            post_path = self.handler.process_stream(ifp)

        post_fn = os.path.join(self.git_repo_dir, "_posts", "blog", post_path)

        frontmatter, body = parse_post(post_fn)
        # {'author': 'blalor@bravo5.org',
        #  'categories': 'blog',
        #  'date': '2015-07-05T07:28:43-04:00',
        #  'images': {'img_5810_jpg': OrderedDict([('path', 'img/email/2015-07-05-fenway-fireworks/IMG_5810.JPG'), ('exif', OrderedDict([('cameraMake', 'Apple'), ('cameraModel', 'iPhone 6'), ('cameraSWVer', '8.4'), ('dateTimeOriginal', '2015-07-03T23:39:33'), ('lensModel', 'iPhone 6 back camera 4.15mm f/2.2'), ('location', OrderedDict([('latitude', 42.347011111111115), ('longitude', -71.09632222222221)]))]))])},
        #  'layout': 'post',
        #  'tags': ['photo'],
        #  'title': 'Fenway fireworks'}
        assert len(frontmatter["images"]) == 1
        img = frontmatter["images"]["img_5810_jpg"]
        assert img["exif"]["dateTimeOriginal"] == "2015-07-03T23:39:33"
        assert img["exif"]["dateTimeGps"] ==      "2015-07-04T03:39:33+00:00"

        assert r"{% include exif-image.html img=page.images.img_5810_jpg %}" in body
