# -*- encoding: utf-8 -*-

import exifread
from datetime import datetime


def gps_to_float(ref, values):
    mult = 1 if ref in ("N", "E") else -1
    degrees, minutes, seconds = [float(v.num) / float(v.den) for v in values]
    return mult * (degrees + minutes/60.0 + seconds/3600.0)


def render_stream(stream):
    return render_tags(exifread.process_file(stream))


def render_tags(exif_tags):
    return {
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
