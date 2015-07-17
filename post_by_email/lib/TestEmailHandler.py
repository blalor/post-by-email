# -*- encoding: utf-8 -*-

from EmailHandler import EmailHandler

from nose.tools import eq_, ok_
import mock
import os
import shutil
import tempfile
import gzip
import rtyaml as yaml
import StringIO
import geopy
from email.mime.text import MIMEText
from email.utils import formatdate


def parse_post(fn):
    buf = StringIO.StringIO()
    
    with open(fn, "r") as ifp:
        ## must start with ---\n
        line = ifp.readline().decode("utf-8")
        eq_(line, u"---\n")
        
        while True:
            line = ifp.readline().decode("utf-8")
            if line == u"---\n":
                break
            
            buf.write(line)
    
        buf.seek(0)
        return yaml.load(buf), ifp.read().decode("utf-8")
        

class TestEmailHandler:
    FIXTURE_DIR = os.path.abspath(os.path.join(__file__, "../../test-fixtures"))
    
    def setup(self):
        self.git_repo_dir = tempfile.mkdtemp()
        
        ## mock of tinys3.Connection
        self.mock_s3 = mock.Mock()

        ## mock of geopy.geocoders.OpenCage
        self.mock_geocoder = mock.Mock()

        ## mock of lib.git.Git
        self.mock_git = mock.Mock()
        self.mock_git.repo_path = self.git_repo_dir
        self.mock_git.lock = mock.MagicMock()

        self.handler = EmailHandler(self.mock_s3, "img/email", self.mock_geocoder, self.mock_git, commit_changes=True)
    
    def teardown(self):
        shutil.rmtree(self.git_repo_dir)
    
    def test_parseMessage(self):
        self.mock_s3.list.return_value = []
        
        lat, lon = 42.347011111111115, -71.09632222222221
        location = geopy.location.Location("the park", geopy.location.Point(lat, lon, 0))
        self.mock_geocoder.reverse.return_value = location
        
        self.mock_s3.upload.return_value = None
        
        with gzip.open(os.path.join(self.FIXTURE_DIR, "photo-1.msg.gz"), "r") as ifp:
            post_path = self.handler.process_stream(ifp)
        
        eq_(post_path, "2015-07-05-fenway-fireworks.md")
        post_fn = os.path.join(self.git_repo_dir, "_posts", "blog", post_path)
        
        self.mock_s3.list.assert_called_once_with("img/email/2015-07-05-fenway-fireworks/IMG_5810.JPG")
        eq_(self.mock_s3.upload.call_args[0][0], "img/email/2015-07-05-fenway-fireworks/IMG_5810.JPG")
        eq_(self.mock_s3.upload.call_args[1]["content_type"], "image/jpeg")

        self.mock_git.clean_sweep.assert_called_once_with()
        self.mock_git.add_file.assert_called_once_with(post_fn)
        self.mock_git.commit.called_once_with("Brian Lalor", "blalor@bravo5.org", "Sun, 5 Jul 2015 07:28:43 -0400", "Fenway fireworks")
        self.mock_git.push.called_once_with()
        
        ## bet those float comparisons will bite me later!
        self.mock_geocoder.reverse.assert_called_once_with([lat, lon], exactly_one=True)
        
        frontmatter, body = parse_post(post_fn)
        # {'author': 'blalor@bravo5.org',
        #  'categories': 'blog',
        #  'date': '2015-07-05T07:28:43-04:00',
        #  'images': [OrderedDict([('path', 'img/email/2015-07-05-fenway-fireworks/IMG_5810.JPG'), ('exif', OrderedDict([('cameraMake', 'Apple'), ('cameraModel', 'iPhone 6'), ('cameraSWVer', '8.4'), ('dateTimeOriginal', '2015-07-03T23:39:33'), ('lensModel', 'iPhone 6 back camera 4.15mm f/2.2'), ('location', OrderedDict([('latitude', 42.347011111111115), ('longitude', -71.09632222222221)]))]))])],
        #  'layout': 'post',
        #  'tags': ['photo'],
        #  'title': 'Fenway fireworks'}
        eq_(frontmatter["author"], "blalor@bravo5.org")
        eq_(frontmatter["categories"], "blog")
        ok_("photo" in frontmatter["tags"])
        
        eq_(len(frontmatter["images"]), 1)
        img = frontmatter["images"][0]
        eq_(img["exif"]["location"]["latitude"], lat)
        eq_(img["exif"]["location"]["longitude"], lon)
        eq_(img["exif"]["location"]["name"], location.address)

    def test_parseMessagePreservingEmoji(self):
        msg = MIMEText(u"""Foo 👍🔫""".encode("utf-8"), "plain", "UTF-8")

        msg["Message-ID"] = "7351da42-12a8-41a1-9b60-25ee7b784720"
        msg["From"] = "Brian Lalor <blalor@bravo5.org>"
        msg["To"] = "photos@localhost"
        msg["Subject"] = "just some text"
        msg["Date"] = formatdate(1436782211)
        
        post_path = self.handler.process_message(msg)
        
        eq_(post_path, "2015-07-13-just-some-text.md")
        post_fn = os.path.join(self.git_repo_dir, "_posts", "blog", post_path)
        
        _, body = parse_post(post_fn)
        eq_(body, u"\nFoo 👍🔫")

    def test_handleNoPhotos(self):
        msg = MIMEText("""Just a test; no photos.""")
        msg["Message-ID"] = "7351da42-12a8-41a1-9b60-25ee7b784720"
        msg["From"] = "Brian Lalor <blalor@bravo5.org>"
        msg["To"] = "photos@localhost"
        msg["Subject"] = "just some text"
        msg["Date"] = formatdate(1436782211)
        
        post_path = self.handler.process_message(msg)
        
        eq_(post_path, "2015-07-13-just-some-text.md")
        post_fn = os.path.join(self.git_repo_dir, "_posts", "blog", post_path)
        
        ok_(not self.mock_s3.list.called)
        ok_(not self.mock_geocoder.reverse.called)

        frontmatter, body = parse_post(post_fn)
        # {'author': 'blalor@bravo5.org',
        #  'categories': 'blog',
        #  'date': '2015-07-05T07:28:43-04:00',
        #  'layout': 'post',
        #  'tags': ['photo'],
        #  'title': 'Fenway fireworks'}
        eq_(frontmatter["author"], "blalor@bravo5.org")
        ok_("photo" not in frontmatter["tags"])
        ok_("images" not in frontmatter)

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
        
        eq_(post_path, "2015-07-13-just-some-text.md")
        post_fn = os.path.join(self.git_repo_dir, "_posts", "blog", post_path)
        
        _, body = parse_post(post_fn)
        ok_(body.startswith("\nsome text ramble ramble"))
        ok_("-- \nNobody\nnobody@home.com" not in body, "found signature")

    def test_stripSignature2(self):
        msg = MIMEText("""some text ramble ramble bla bla bla

Sent from my iPhone""")

        msg["Message-ID"] = "7351da42-12a8-41a1-9b60-25ee7b784720"
        msg["From"] = "Brian Lalor <blalor@bravo5.org>"
        msg["To"] = "photos@localhost"
        msg["Subject"] = "just some text"
        msg["Date"] = formatdate(1436782211)
        
        post_path = self.handler.process_message(msg)
        
        eq_(post_path, "2015-07-13-just-some-text.md")
        post_fn = os.path.join(self.git_repo_dir, "_posts", "blog", post_path)
        
        _, body = parse_post(post_fn)
        ok_(body.startswith("\nsome text ramble ramble"))
        ok_("Sent from my iPhone" not in body, "found signature")

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
        
        eq_(post_path, "2015-07-13-just-some-text.md")
        post_fn = os.path.join(self.git_repo_dir, "_posts", "blog", post_path)
        
        frontmatter, body = parse_post(post_fn)
        ok_("foo" in frontmatter["tags"])
        ok_("baz bap" in frontmatter["tags"])
        
        ok_(body.startswith("\nsome text ramble ramble"))

    def test_extractsGPSTimestamp(self):
        self.mock_s3.list.return_value = []
        self.mock_geocoder.reverse.return_value = None
        self.mock_s3.upload.return_value = None
        
        with gzip.open(os.path.join(self.FIXTURE_DIR, "photo-1.msg.gz"), "r") as ifp:
            post_path = self.handler.process_stream(ifp)
        
        post_fn = os.path.join(self.git_repo_dir, "_posts", "blog", post_path)
        
        frontmatter, body = parse_post(post_fn)
        # {'author': 'blalor@bravo5.org',
        #  'categories': 'blog',
        #  'date': '2015-07-05T07:28:43-04:00',
        #  'images': [OrderedDict([('path', 'img/email/2015-07-05-fenway-fireworks/IMG_5810.JPG'), ('exif', OrderedDict([('cameraMake', 'Apple'), ('cameraModel', 'iPhone 6'), ('cameraSWVer', '8.4'), ('dateTimeOriginal', '2015-07-03T23:39:33'), ('lensModel', 'iPhone 6 back camera 4.15mm f/2.2'), ('location', OrderedDict([('latitude', 42.347011111111115), ('longitude', -71.09632222222221)]))]))])],
        #  'layout': 'post',
        #  'tags': ['photo'],
        #  'title': 'Fenway fireworks'}
        eq_(len(frontmatter["images"]), 1)
        img = frontmatter["images"][0]
        eq_(img["exif"]["dateTimeOriginal"], "2015-07-03T23:39:33")
        eq_(img["exif"]["dateTimeGps"],      "2015-07-04T03:39:33+00:00")
