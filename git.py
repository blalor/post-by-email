# -*- encoding: utf-8 -*-

import logging
logger = logging.getLogger(__name__)

import os
import subprocess
import tempfile
from file_lock import file_lock
from contextlib import contextmanager


class Git(object):
    """wrapper for git commands"""
    def __init__(self, repo_url, repo_path):
        super(Git, self).__init__()
        self.repo_url = repo_url
        self.repo_path = repo_path
        self._lock_file = os.path.join(self.repo_path, ".git", "render_post.lock")

    def clone(self):
        logger.info("cloning")
        
        subprocess.check_call(
            [
                "git", "clone",
                "--depth", "1",
                "--quiet",
                self.repo_url,
                self.repo_path,
            ],
            env={
                ## disable template; my pre-commit hook checks for user.{email,name}
                "GIT_TEMPLATE_DIR": "",
            },
        )
    
    @contextmanager
    def lock(self):
        with file_lock(self._lock_file):
            logger.debug("acquired lock")
            yield

    def clean_sweep(self):
        logger.info("cleaning")
        
        subprocess.check_call(["git", "fetch"], cwd=self.repo_path)
        subprocess.check_call(
            [
                "git", "reset",
                "--quiet",
                "--hard", "origin/master",
            ],
            cwd=self.repo_path,
        )
        
        ## make it squeaky clean
        subprocess.check_call(
            ["git", "clean", "-f", "-d", "-x"],
            cwd=self.repo_path,
        )

    def add_file(self, path):
        logger.info("adding %s", path)
        
        subprocess.check_call(
            ["git", "add", path],
            cwd=self.repo_path,
        )

    def commit(self, author_name, author_email, date, message):
        logger.info("committing")
        
        # @todo ensure there are actual changes to be made
        
        ## write commit message to temp file
        with tempfile.TemporaryFile() as tf:
            tf.write(message.encode("utf-8"))
            tf.seek(0)
            
            subprocess.check_call(
                [
                    "git", "commit",
                    "--file=-",
                    "--quiet",
                ],
                stdin=tf,
                cwd=self.repo_path,
                env={
                    "GIT_AUTHOR_NAME":     author_name,
                    "GIT_AUTHOR_EMAIL":    author_email,
                    "GIT_AUTHOR_DATE":     date,
                    
                    ## adding delivered-to exposes the email address used to create posts!
                    # "GIT_COMMITTER_NAME":  config.GIT_COMMITTER_NAME,
                    # "GIT_COMMITTER_EMAIL": msg["delivered-to"],
                },
            )
    
    def push(self):
        logger.info("pushing")
        
        subprocess.check_call(
            [
                "git", "push", "--quiet"
            ],
            cwd=self.repo_path,
        )
