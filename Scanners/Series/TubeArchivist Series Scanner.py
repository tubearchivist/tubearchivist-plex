#!/usr/bin/env python

"""
Custom scanner plugin for Plex Media Server to integrate with TubeArchivist.
"""

import datetime
import inspect
import json
import logging
import logging.handlers
import os
import os.path
import re
import ssl
import sys

import Media
import Stack
import Utils
import VideoFiles

# from lxml import etree

try:
    from ssl import (
        PROTOCOL_TLS as SSL_PROTOCOL,  # Python >= 2.7.13 ##ssl.PROTOCOL_TLSv1
    )
except ImportError:
    from ssl import PROTOCOL_SSLv23 as SSL_PROTOCOL  # Python <  2.7.13
try:
    from urllib.error import HTTPError
    from urllib.request import Request as Request  # Python >= 3.0
    from urllib.request import urlopen
except ImportError:
    from urllib2 import HTTPError
    from urllib2 import Request as Request  # Python == 2.x
    from urllib2 import urlopen

SetupDone = False
Log = None
Handler = None
PLEX_ROOT = ""
PLEX_LIBRARY = {}
# Allow to get the library name to get a log per library https://support.plex.tv/hc/en-us/articles/204059436-Finding-your-account-token-X-Plex-Token  # noqa: E501
PLEX_LIBRARY_URL = "http://localhost:32400/library/sections/"
SOURCE = "TubeArchivist Scanner"
TA_CONFIG = None
LOG_RETENTION = 5


SSL_CONTEXT = ssl.SSLContext(SSL_PROTOCOL)
FILTER_CHARS = "\\/:*?<>|;"
TA_REGEXS = [
    "[0-9]{8}_[a-zA-Z0-9_-]{11}_*.*",
    "[a-zA-Z0-9_-]{11}.*",
]


def setup():
    global SetupDone
    if SetupDone:
        return True

    else:
        global PLEX_ROOT
        PLEX_ROOT = os.path.abspath(
            os.path.join(
                os.path.dirname(inspect.getfile(inspect.currentframe())),
                "..",
                "..",
            )
        )
        if not os.path.isdir(PLEX_ROOT):
            path_location = {
                "Windows": "%LOCALAPPDATA%\\Plex Media Server",
                "MacOSX": "$HOME/Library/Application Support/Plex Media Server",  # noqa: E501
                "Linux": "$PLEX_HOME/Library/Application Support/Plex Media Server",  # noqa: E501
                "Android": "/storage/emulated/0/Plex Media Server",
            }
            PLEX_ROOT = os.path.expandvars(
                path_location[Platform.OS.lower()]  # type: ignore # noqa: F821
                if Platform.OS.lower() in path_location  # type: ignore # noqa: F821, E501
                else "~"
            )  # Platform.OS:  Windows, MacOSX, or Linux

        if sys.version[0] == "2":
            from imp import reload

            reload(sys)
            sys.setdefaultencoding("utf-8")

        global Log
        Log = logging.getLogger(SOURCE)
        Log.setLevel(logging.DEBUG)
        set_logging()

        Log.info(
            "TubeArchivist scanner started: {}".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")
            )
        )
        Log.debug("Plex Python environment: ")
        Log.debug("\tPython version: %s" % (sys.version))
        # Log.debug("\tPython argv: %s" % (sys.argv))
        Log.debug("\tPython platform: %s" % (sys.platform))
        Log.debug("\tPython prefix: %s" % (sys.prefix))
        # Log.debug("\tPython thread info: %s" % (sys.thread_info))
        SetupDone = True
        return True


def read_url(url, data=None):
    url_content = ""
    try:
        if data is None:
            url_content = urlopen(url, context=SSL_CONTEXT).read()
        else:
            url_content = urlopen(url, context=SSL_CONTEXT, data=data).read()
        return url_content
    except Exception as e:
        Log.error(
            "Error reading or accessing url '%s', Exception: '%s'"
            % (
                (
                    url.get_full_url()
                    if any(
                        x in str(type(url)) for x in ["Request", "instance"]
                    )
                    else url
                ),
                e,
            )
        )
        raise e


def read_file(localfile):
    file_content = ""
    try:
        with open(localfile, "r") as file:
            file_content = file.read()
        return file_content
    except Exception as e:
        Log.error(
            "Error reading or accessing file '%s', Exception: '%s'"
            % (localfile, e)
        )
        raise e


def set_logging(
    root="",
    foldername="",
    filename="",
    backup_count=LOG_RETENTION,
    format="%(asctime)s [%(name)s] %(levelname)s - %(message)s",
    mode="a",
):
    log_path = os.path.join(PLEX_ROOT, "Logs", SOURCE)
    if not os.path.exists(log_path):
        os.makedirs(log_path)
    if not foldername:
        foldername = Dict(PLEX_LIBRARY, root, "title")
    if foldername:
        log_path = os.path.join(log_path, os_filename_clean_string(foldername))
    if not os.path.exists(log_path):
        os.makedirsr(log_path)

    filename = (
        os_filename_clean_string(filename)
        if filename
        else "_root_.scanner.log"
    )
    log_file = os.path.join(log_path, filename)

    # Bypass DOS path MAX_PATH limitation (260 Bytes=> 32760 Bytes, 255 Bytes per folder unless UDF 127B ytes max)  # noqa: E501
    if os.sep == "\\":
        dos_path = (
            os.path.abspath(log_file)
            if isinstance(log_file, unicode)  # type: ignore # noqa: F821
            else os.path.abspath(log_file.decode("utf-8"))
        )
        log_file = (
            "\\\\?\\UNC\\" + dos_path[2:]
            if dos_path.startswith("\\\\")
            else "\\\\?\\" + dos_path
        )

    # if not mode:  mode = 'a' if os.path.exists(log_file) and os.stat(log_file).st_mtime + 3600 > time.time() else 'w' # Override mode for repeat manual scans or immediate rescans  # noqa: E501

    global Handler
    if Handler:
        Log.removeHandler(Handler)
    if backup_count:
        Handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=backup_count,
            encoding="utf-8",
        )
    else:
        Handler = logging.FileHandler(log_file, mode=mode, encoding="utf-8")
    Handler.setFormatter(logging.Formatter(format))
    Handler.setLevel(logging.DEBUG)
    Log.addHandler(Handler)


def Dict(var, *arg, **kwarg):
    for key in arg:
        if isinstance(var, dict) and key and key in var:
            var = var[key]
        else:
            return (
                kwarg["default"] if kwarg and "default" in kwarg else ""
            )  # Allow Dict(var, tvdbid).isdigit() for example
    return (
        kwarg["default"]
        if var in (None, "", "N/A", "null") and kwarg and "default" in kwarg
        else "" if var in (None, "", "N/A", "null") else var
    )


def os_filename_clean_string(in_string):
    for ch, subst in zip(
        list(FILTER_CHARS),
        [" " for x in range(len(FILTER_CHARS)) + [("`", "'"), ('"', "'")]],
    ):
        if ch in in_string:
            in_string = in_string.replace(ch, subst)
    return in_string


def filter_chars(in_string):
    for ch, subst in zip(
        list(FILTER_CHARS), [" " for x in range(len(FILTER_CHARS))]
    ):
        if ch in in_string:
            in_string = in_string.replace(ch, subst)
    return in_string


def set_date_to_utc(date):
    tsymbolplus = False
    if "+" in date:
        dt, tz = date.split("+")
        tsymbolplus = True
    else:
        sd = date.split("-")
        dt = "".join(sd[:-1])
        tz = (
            sd[-1] if len(sd) > 3 else "00:00"
        )  # (Year, Month, Datetime, [timezone])  # noqa: E501
    tz = datetime.datetime.strptime(tz, "%H:%M")
    tztd = datetime.timedelta(hours=tz.hour, minutes=tz.minute)
    date_out = datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S")
    if tsymbolplus:
        date_out = date_out + tztd
    else:
        date_out = date_out - tztd
    return date_out


def load_ta_config():
    global TA_CONFIG
    if TA_CONFIG:
        return TA_CONFIG
    else:
        TA_CONFIG = get_ta_config()


def read_ta_config():
    SCANNER_LOCATION = "Scanners/Series/"
    CONFIG_NAME = "ta_config.json"
    response = {}

    config_file = os.path.join(PLEX_ROOT, SCANNER_LOCATION, CONFIG_NAME)
    try:
        response = json.loads(
            read_file(config_file) if os.path.isfile(config_file) else "{}"
        )
    except ValueError as e:
        Log.error(
            "Check to see if `{}` has proper JSON formatting. Exception: {}".format(  # noqa: E501
                config_file, e
            )
        )
        raise e
    except IOError as e:
        Log.error(
            "Check to see if `{}` has correct permissions. Exception: {}".format(  # noqa: E501
                config_file, e
            )
        )
        raise e
    except Exception as e:
        Log.error(
            "Issue with loading `{}` Scanner config file. Check to see if the file exists, is accessible, and is properly formatted. Exception: {}".format(  # noqa: E501
                config_file, e
            )
        )
        raise e
    if not response:
        if os.path.isfile(config_file):
            Log.error(
                "Check to see if `{}` Scanner config file is accessible and has configuration data.".format(  # noqa: E501
                    config_file
                )
            )
        else:
            Log.error(
                "Check to see if the Scanner config file `{}` exists.".format(
                    config_file
                )
            )
    return response


def get_ta_config():
    response = {}
    response = read_ta_config()
    for key in ["ta_url", "ta_api_key"]:
        if key not in response:
            Log.error("Configuration is missing key '{}'.".format(key))
    if (
        not response["ta_url"].startswith("http")
        and response["ta_url"].find("://") == -1
    ):
        response["ta_url"] = "http://" + response["ta_url"]
    if response["ta_url"].endswith("/"):
        response["ta_url"] = response["ta_url"][:-1]
    Log.debug("TA URL: %s" % (response["ta_url"]))
    return response


def check_ta_version_in_response(response):
    ta_version = []
    try:
        if "version" in response:
            try:
                if "v" in response["version"]:
                    ta_version = [
                        int(x)
                        for x in response["version"][1:]
                        .rstrip("-unstable")
                        .split(".")
                    ]
                else:
                    ta_version = [
                        int(x)
                        for x in response["version"]
                        .rstrip("-unstable")
                        .split(".")
                    ]
            except (AttributeError, TypeError):
                ta_version = response["version"]
            Log.info(
                "TubeArchivist is running version v{}".format(
                    ".".join(str(x) for x in ta_version)
                )
            )
        else:
            ta_version = [0, 3, 6]
            Log.info(
                "TubeArchivist did not respond with a version. Assuming v{} for interpretation.".format(  # noqa: E501
                    ".".join(str(x) for x in ta_version)
                )
            )
    except Exception as e:
        Log.error(
            "Unable to set the `ta_version`. Check the connection via `ta_ping`. "  # noqa: E501
        )
        Log.debug("Response: %s\nException details: %s" % (response, e))
    return ta_version


def test_ta_connection(try_legacy_api=False):
    if not TA_CONFIG:
        return False, []
    try:
        Log.info(
            "Attempting to connect to TubeArchivist at {} with provided token from `ta_config.json` file.".format(  # noqa: E501
                TA_CONFIG["ta_url"]
            )
        )
        ping_url = "{}/api/ping/".format(TA_CONFIG["ta_url"])
        if try_legacy_api:
            ping_url = "{}/api/ping".format(TA_CONFIG["ta_url"])
        response = json.loads(
            read_url(
                Request(
                    ping_url,
                    headers={
                        "Authorization": "Token {}".format(
                            TA_CONFIG["ta_api_key"]
                        )
                    },
                )
            )
        )
        ta_ping = response["response"]
        ta_version = []
        ta_version = check_ta_version_in_response(response)
        if ta_ping == "pong":
            return True, ta_version
    except HTTPError as e:
        Log.error(  # type: ignore # noqa: F821
            "HTTP Error connecting to TubeArchivist with URL '%s', HTTPError: '%s'"  # noqa: E501
            % (TA_CONFIG["ta_url"], e)
        )
        if try_legacy_api:
            return False, []
        Log.debug(  # type: ignore # noqa: F821
            "Attempting with legacy API for ping response."
        )
        return test_ta_connection(try_legacy_api=True)
    except Exception as e:
        Log.error(
            "Error connecting to TubeArchivist with URL '%s', Exception: '%s'"
            % (TA_CONFIG["ta_url"], e)
        )
        raise e


def get_ta_metadata(id, mtype="video"):
    request_url = ""
    # Currently, the API endpoint is identical. However, we should have this here for a future version in case the API changes.  # noqa: E501
    # if TA_CONFIG["version"] < [0, 5, 0]:
    #     request_url = "{}/api/{}/{}/".format(TA_CONFIG["ta_url"], mtype, id)
    # else:
    #     request_url = "{}/api/{}/{}/".format(TA_CONFIG["ta_url"], mtype, id)
    request_url = "{}/api/{}/{}/".format(TA_CONFIG["ta_url"], mtype, id)
    if not TA_CONFIG:
        return None
    try:
        Log.info(
            "Attempting to connect to TubeArchivist to lookup YouTube {}: {}".format(  # noqa: E501
                mtype, id
            )
        )
        response = json.loads(
            read_url(
                Request(
                    request_url,
                    headers={
                        "Authorization": "Token {}".format(
                            TA_CONFIG["ta_api_key"]
                        )
                    },
                )
            )
        )
        return response
    except Exception as e:
        Log.error(
            "Error connecting to TubeArchivist with URL '{}', Exception: '{}'".format(  # noqa: E501
                request_url, e
            )
        )
        raise e


def get_ta_video_metadata(ytid):
    mtype = "video"
    if not TA_CONFIG:
        Log.error("No configurations in TA_CONFIG.")
        return None
    if not ytid:
        Log.error("No {} ID present.".format(mtype))
        return None
    try:
        vid_response = get_ta_metadata(ytid)
        Log.info(
            "Response from TubeArchivist received for YouTube {}: {}".format(
                mtype, ytid
            )
        )
        if vid_response:
            if TA_CONFIG["version"] < [0, 5, 0]:
                Log.debug(
                    "Processing response with pre-v0.5.0 TA API response format."  # noqa: E501
                )
                vid_response = vid_response["data"]
            metadata = {}
            metadata["show"] = "{} [{}]".format(
                vid_response["channel"]["channel_name"],
                vid_response["channel"]["channel_id"],
            )
            metadata["ytid"] = vid_response["youtube_id"]
            metadata["title"] = vid_response["title"]
            if TA_CONFIG["version"] < [0, 3, 7]:
                Log.debug(
                    "Processing response with initial TA API response format."
                )
                metadata["processed_date"] = datetime.datetime.strptime(
                    vid_response["published"], "%d %b, %Y"
                )
                video_refresh = datetime.datetime.strptime(
                    vid_response["vid_last_refresh"], "%d %b, %Y"
                )
            elif TA_CONFIG["version"] < [0, 5, 3]:
                metadata["processed_date"] = datetime.datetime.strptime(
                    vid_response["published"], "%Y-%m-%d"
                )
                video_refresh = datetime.datetime.strptime(
                    vid_response["vid_last_refresh"], "%Y-%m-%d"
                )
            else:
                metadata["processed_date"] = set_date_to_utc(
                    vid_response["published"]
                )
                video_refresh = set_date_to_utc(
                    vid_response["vid_last_refresh"]
                )
            # With the additional metadata, we can be more specific with the season ordering for v0.2.0 # noqa: E501
            metadata["refresh_date"] = video_refresh.strftime("%Y%m%d")
            metadata["season"] = metadata["processed_date"].year
            # With the additional metadata, we can be more specific with the season ordering for v0.2.0 # noqa: E501
            metadata["episode"] = metadata["processed_date"].strftime("%Y%m%d")
            metadata["description"] = vid_response["description"]
            metadata["thumb_url"] = vid_response["vid_thumb_url"]
            metadata["type"] = vid_response["vid_type"]
            metadata["has_subtitles"] = (
                True if "subtitles" in vid_response else False
            )
            if metadata["has_subtitles"]:
                metadata["subtitle_metadata"] = vid_response["subtitles"]
            return metadata
        else:
            Log.error(
                "Empty response returned from %s when requesting data about %s."  # noqa: E501
                % (TA_CONFIG["ta_url"], mtype)
            )
    except Exception as e:
        Log.error(
            "Error processing %s response from TubeArchivist at location '%s', Exception: '%s'"  # noqa: E501
            % (mtype, TA_CONFIG["ta_url"], e)
        )
        raise e


def get_ta_channel_metadata(chid):
    mtype = "channel"
    if not TA_CONFIG:
        Log.error("No configurations in TA_CONFIG.")
        return None
    if not chid:
        Log.error("No {} ID present.".format(mtype))
        return None
    try:
        ch_response = get_ta_metadata(chid, mtype=mtype)
        Log.info(
            "Response from TubeArchivist received for YouTube {}: {}".format(
                mtype, chid
            )
        )
        if ch_response:
            if TA_CONFIG["version"] < [0, 5, 0]:
                Log.debug(
                    "Processing response with pre-v0.5.0 TA API response format."  # noqa: E501
                )
                ch_response = ch_response["data"]
            metadata = {}
            metadata["show"] = "{} [{}]".format(
                ch_response["channel_name"],
                ch_response["channel_id"],
            )
            if TA_CONFIG["version"] < [0, 3, 7]:
                Log.debug(
                    "Processing response with initial TA API response format."
                )
                channel_refresh = datetime.datetime.strptime(
                    ch_response["channel_last_refresh"], "%d %b, %Y"
                )
            elif TA_CONFIG["version"] < [0, 5, 3]:
                channel_refresh = datetime.datetime.strptime(
                    ch_response["channel_last_refresh"], "%Y-%m-%d"
                )
            else:
                channel_refresh = set_date_to_utc(
                    ch_response["channel_last_refresh"]
                )
            metadata["refresh_date"] = channel_refresh.strftime("%Y%m%d")
            metadata["description"] = ch_response["channel_description"]
            metadata["banner_url"] = ch_response["channel_banner_url"]
            metadata["thumb_url"] = ch_response["channel_thumb_url"]
            metadata["tvart_url"] = ch_response["channel_tvart_url"]
            return metadata
        else:
            Log.error(
                "Empty response returned from %s when requesting data about %s."  # noqa: E501
                % (TA_CONFIG["ta_url"], mtype)
            )
    except Exception as e:
        Log.error(
            "Error processing %s response from TubeArchivist at location '%s', Exception: '%s'"  # noqa: E501
            % (mtype, TA_CONFIG["ta_url"], e)
        )
        raise e


def Scan(path, files, mediaList, subdirs):  # noqa: C901
    setup()
    load_ta_config()
    TA_CONFIG["online"] = None
    TA_CONFIG["version"] = []
    TA_CONFIG["online"], TA_CONFIG["version"] = test_ta_connection()
    Log.info("Initiating scan of library files...")
    VideoFiles.Scan(path, files, mediaList, subdirs)

    paths = Utils.SplitPath(path)

    if len(paths) > 0 and len(paths[0]) > 0:
        done = False
        episode_counts = {}
        if not done:
            (show, year) = VideoFiles.CleanName(paths[0])

            for i in files:
                file = os.path.basename(i)
                Log.info("Processing file with scanner: {}".format(file))
                (file, ext) = os.path.splitext(file)
                episode = ""

                for rx in TA_REGEXS:
                    match = re.search(rx, file, re.IGNORECASE)
                    video_metadata = {}
                    if match:
                        Log.info("File matches expected filename layout.")
                        if TA_CONFIG["online"]:
                            if TA_CONFIG["version"] == []:
                                Log.error(
                                    "TubeArchivist instance version is unknown or unset. Please review the logs further and ensure that there is connectivity between Plex and TubeArchivist."  # noqa: E501
                                )
                                break
                            if TA_CONFIG["version"] < [0, 3, 7]:
                                Log.info(
                                    "Processing filename with legacy filename format."  # noqa: E501
                                )
                                originalAirDate = file[0:7]
                                ytid = file[9:20]
                                title = file[21:]
                                season = originalAirDate[0:4]
                                episode = originalAirDate[5:]
                            else:
                                ytid = file
                            try:
                                video_metadata = get_ta_video_metadata(ytid)
                                show = video_metadata["show"]
                                if "video" in video_metadata["type"]:
                                    title = video_metadata["title"]
                                    season = video_metadata["season"]
                                else:
                                    title = "[{}] {}".format(
                                        video_metadata["type"].upper(),
                                        video_metadata["title"],
                                    )
                                    season = 0
                                episode = video_metadata["episode"]
                            except Exception as e:
                                Log.error(
                                    "Issue with fetching or setting metadata from video using response metadata: '%s', Exception: '%s'"  # noqa: E501
                                    % (str(video_metadata), e)
                                )
                                continue
                        else:
                            Log.error(
                                "TubeArchivist instance is not accessible or not online. Unable to process video file."  # noqa: E501
                            )
                            break

                        if show not in episode_counts:
                            episode_counts[show] = {}
                        if season not in episode_counts[show]:
                            episode_counts[show][season] = {}
                        if episode not in episode_counts[show][season]:
                            episode_counts[show][season][episode] = 0
                        episode_counts[show][season][episode] += 1
                        episode_date = episode  # Preserve YYYYMMDD
                        episode = "{}{:02d}".format(
                            str(episode[4:]),
                            episode_counts[show][season][episode_date],
                        )

                        tv_show = Media.Episode(
                            str(show).encode("UTF-8"),
                            str(season).encode("UTF-8"),
                            episode,
                            str(title).encode("UTF-8"),
                            str(season).encode("UTF-8"),
                        )
                        Log.info(
                            "Identified episode '{} - {}' with TV Show {} under Season {}.".format(  # noqa: E501
                                episode, title, show, season
                            )
                        )
                        tv_show.released_at = str(
                            "{}-{}-{}".format(
                                episode_date[2:4],
                                episode_date[4:6],
                                episode_date[6:8],
                            )
                        ).encode("UTF-8")
                        tv_show.parts.append(i)
                        Log.info(
                            "Adding episode '{}' to TV show '{}' list of episodes.".format(  # noqa: E501
                                episode, show
                            )
                        )
                        mediaList.append(tv_show)
                        break

    Stack.Scan(path, files, mediaList, subdirs)
    Log.info("Scan completed for library files.")


if __name__ == "__main__":
    print("{} for Plex!".format(SOURCE))
    path = sys.argv[1]
    files = [os.path.join(path, file) for file in os.listdir(path)]
    media = []
    Scan(path[1:], files, media, [])
    print("Files detected: ", media)
