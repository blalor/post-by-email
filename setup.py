#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="post_by_email",
    version="0.0.1",
    author="Brian Lalor",
    author_email="blalor@bravo5.org",
    description="post to a jekyll blog via email, with photo support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/blalor/post-by-email",

    packages=find_packages(),
    install_requires=[
        "dulwich ~= 0.20", #  --global-option=--pure
        "boto3 ~= 1.26",
        "itsdangerous ~= 2.1",
        "rtyaml ~= 1.0",
        "markdownify ~= 0.11",

        "ExifRead ~= 3.0",
        "python-slugify ~= 6.1",
        "geopy ~= 2.2",
    ],
    extras_require={
        "tests": [
            "pytest ~= 7.2",
            "mock ~= 4.0",
        ]
    }
)
