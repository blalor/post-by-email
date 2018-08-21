FROM blalor/supervised:latest
MAINTAINER Brian Lalor <blalor@bravo5.org>

EXPOSE 5000

ADD src/ /tmp/src/
ADD post_by_email/ /post_by_email/
RUN /tmp/src/config.sh

ENV COMMIT_CHANGES True
ENV GIT_WORKING_COPY /tmp/git_work

## ENV ADDR_VALIDATION_HMAC_KEY
## ENV GIT_REPO
## ENV GIT_COMMITTER_NAME
## ENV S3_IMAGE_BUCKET
## ENV S3_IMAGE_PATH_PREFIX
## ENV AWS_ACCESS_KEY_ID
## ENV AWS_SECRET_ACCESS_KEY
## ENV OPENCAGE_API_KEY
