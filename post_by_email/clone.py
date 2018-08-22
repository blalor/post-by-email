#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from lib.git import Git
import config


def main():
    git = Git(config.GIT_REPO, config.GIT_WORKING_COPY)
    git.clone()


if __name__ == "__main__":
    main()
