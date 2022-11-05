Service for posting to a [Jekyll](http://jekyllrb.com) blog via email

With a particular focus on posting images.  Intended to run in a Docker container, exposing an HTTP endpoint for submitting emails to be processed.  Integrates with your/a email account via procmail:

    ## set ADDR_EXT to "Bar" of "foo+Bar@whatever.com"
    ## postfix turns this into "bar", which breaks HMAC validation. :-(
    ADDR_EXT=` formail -z -xTo: | sed -r -e 's#^.*\+(.*)@.*$#\1#g' `
    
    ## figure out who actually sent the message
    SENDER = `formail -rtz -xTo:`
    
    :0 w
    | curl -s -f -H 'Content-Type: message/rfc822' --data-binary @- localhost:5000/email/$SENDER/$ADDR_EXT

Stores any image attachments in S3 and adds a new post to your Jekyll repository.  References to the images are captured in the frontmatter.

### example frontmatter

```yaml
---
title: '<email Subject>'
date: '<email Date>'
layout: post
categories: blog
tags:
- photo
author: '<email From>'
images:
- path: path/to/image/in/S3/bucket.jpg
  exif:
    cameraMake: Apple
    cameraModel: iPhone 6
    cameraSWVer: '8.4'
    dateTimeOriginal: '2015-07-03T23:39:33'
    lensModel: iPhone 6 back camera 4.15mm f/2.2
    location:
      latitude: 42.347011111111115
      longitude: -71.09632222222221
      name: Bleachers, Riverway, Lansdowne Street, Boston MA, United States of America
---
```

See [`config.py`](post_by_email/config.py) for configuration.

## developing and testing

```
$ pip install -e '.[tests]'
$ pytest
```
