# -*- encoding: utf-8 -*-

import os
from .file_lock import file_lock
from contextlib import contextmanager
from dulwich import porcelain
from dulwich.repo import Repo
from dulwich.config import ConfigDict
from .time_util import parse_date
from datetime import datetime

import logging
logger = logging.getLogger(__name__)


class Git(object):
    """wrapper for git commands"""

    def __init__(self, repo_url, repo_path):
        super(Git, self).__init__()
        self.repo_url = repo_url
        self.repo_path = repo_path
        self._lock_file = os.path.join(self.repo_path, ".git", "render_post.lock")

        ## dulwich repo instance
        self._repo = None
        if os.path.exists(os.path.join(self.repo_path, ".git")):
            self._repo = Repo(self.repo_path)

        self.config = ConfigDict()

    def clone(self):
        logger.info("cloning")
        self._repo = porcelain.clone(
            self.repo_url,
            target=self.repo_path,
            config=self.config,
        )

    @contextmanager
    def lock(self):
        with file_lock(self._lock_file):
            logger.debug("acquired lock")
            yield

    def clean_sweep(self):
        logger.info("cleaning")

        ## make it squeaky clean
        index = self._repo.open_index()
        for untracked in porcelain.get_untracked_paths(self._repo.path, self._repo.path, index):
            os.unlink(os.path.join(self._repo.path, untracked))

        porcelain.reset(self._repo.path, "hard", treeish="HEAD")
        porcelain.pull(self._repo.path, remote_location=self.repo_url)

    def add_file(self, path):
        logger.info("adding %s", path)

        porcelain.add(self._repo.path, path)

    def commit(self, author_name, author_email, date, message):
        logger.info("committing")

        # @todo ensure there are actual changes to be made

        ## https://stackoverflow.com/a/8778548/53051
        dt = parse_date(date)
        utc_naive  = dt.replace(tzinfo=None) - dt.utcoffset()
        author_timestamp = (utc_naive - datetime(1970, 1, 1)).total_seconds()
        author_timezone = dt.utcoffset().total_seconds()

        try:
            self._repo.do_commit(
                message=message.encode("utf-8"),
                author=f"{author_name} <{author_email}>".encode("utf-8"),
                author_timestamp=author_timestamp,
                author_timezone=author_timezone,
                committer=b"Nobody <nobody@post-by-email>",
                encoding=b"utf-8",
            )
        finally:
            self._repo.close()

    def push(self):
        logger.info("pushing")

        current_branch = self._repo.refs.follow(b"HEAD")[0][1]
        porcelain.push(
            self._repo.path,
            remote_location=self.repo_url,
            refspecs=current_branch,
        )
