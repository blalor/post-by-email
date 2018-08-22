# -*- encoding: utf-8 -*-

import exifread
from datetime import datetime
from time_util import UTC


def gps_to_float(ref, values):
    mult = 1 if ref in ("N", "E") else -1
    degrees, minutes, seconds = [float(v.num) / float(v.den) for v in values]
    return mult * (degrees + minutes/60.0 + seconds/3600.0)


def gps_time_to_datetime(date, timestamp):
    hours, minutes, seconds = [float(v.num) / float(v.den) for v in timestamp.values]
    ts_str = "%s %02d:%02d:%02d" % (date.printable, hours, minutes, seconds)

    return datetime.strptime(ts_str, "%Y:%m:%d %H:%M:%S").replace(tzinfo=UTC)


def render_stream(stream):
    return render_tags(exifread.process_file(stream))


def render_tags(exif_tags):
    result = {}

    for rk, ek in [
        ("cameraMake", "Image Make"),
        ("cameraModel", "Image Model"),
        ("lensModel", "EXIF LensModel"),
        ("cameraSWVer", "Image Software"),
    ]:
        if ek in exif_tags:
            result[rk] = exif_tags[ek].printable

    if "EXIF DateTimeOriginal" in exif_tags:
        result["dateTimeOriginal"] = datetime.strptime(exif_tags["EXIF DateTimeOriginal"].printable, "%Y:%m:%d %H:%M:%S").isoformat()

    if "GPS GPSDate" in exif_tags and "GPS GPSTimeStamp" in exif_tags:
        result["dateTimeGps"] = gps_time_to_datetime(exif_tags["GPS GPSDate"], exif_tags["GPS GPSTimeStamp"]).isoformat()

    if "GPS GPSLatitudeRef" in exif_tags:
        result["location"] = {
            "latitude": gps_to_float(exif_tags["GPS GPSLatitudeRef"].values, exif_tags["GPS GPSLatitude"].values),
            "longitude": gps_to_float(exif_tags["GPS GPSLongitudeRef"].values, exif_tags["GPS GPSLongitude"].values),
        }

    return result
