#!/usr/bin/env python

"""
Custom scanner plugin for Plex Media Server to integrate with TubeArchivist.
"""

import re, os, os.path
import sys
import inspect
import ssl
import datetime
import json
import logging, logging.handlers
from lxml import etree

try:
    from ssl import PROTOCOL_TLS as SSL_PROTOCOL # Python >= 2.7.13 ##ssl.PROTOCOL_TLSv1
except ImportError:  
  from ssl import PROTOCOL_SSLv23 as SSL_PROTOCOL # Python <  2.7.13
try:
  from urllib.request import urlopen, Request     # Python >= 3.0
except ImportError:
  from urllib2 import urlopen, Request     # Python == 2.x

SetupDone         = False
Log               = None
Handler           = None
PLEX_ROOT         = ""
PLEX_LIBRARY      = {}
PLEX_LIBRARY_URL  = "http://localhost:32400/library/sections/" # Allow to get the library name to get a log per library https://support.plex.tv/hc/en-us/articles/204059436-Finding-your-account-token-X-Plex-Token
SOURCE            = "TubeArchivist Scanner"
TA_CONFIG         = None
LOG_RETENTION     = 5

import Media, VideoFiles, Stack, Utils

SSL_CONTEXT       = ssl.SSLContext(SSL_PROTOCOL)
FILTER_CHARS      = "\\/:*?<>|;"
TA_REGEXS         = [
                    '[0-9]{8}_[a-zA-Z0-9_-]{11}_*.*',
                    '[a-zA-Z0-9_-]{11}.*',
                    ]


def setup():
   global SetupDone
   if SetupDone:
      return
   
   else:
       
      global PLEX_ROOT
      PLEX_ROOT = os.path.abspath(os.path.join(os.path.dirname(inspect.getfile(inspect.currentframe())), "..", ".."))
      if not os.path.isdir(PLEX_ROOT):
        path_location = {
          'Windows': '%LOCALAPPDATA%\\Plex Media Server',
          'MacOSX' : '$HOME/Library/Application Support/Plex Media Server',
          'Linux'  : '$PLEX_HOME/Library/Application Support/Plex Media Server',
          'Android': '/storage/emulated/0/Plex Media Server',
        }
        PLEX_ROOT = os.path.expandvars(path_location[Platform.OS.lower()] if Platform.OS.lower() in path_location else '~')  # Platform.OS:  Windows, MacOSX, or Linux

      if sys.version[0] == '2':
        from imp import reload
        reload(sys)
        sys.setdefaultencoding("utf-8")
      
      global Log
      Log = logging.getLogger(SOURCE)
      Log.setLevel(logging.DEBUG)
      set_logging()

      Log.info(u"TubeArchivist scanner started: {}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")))
      # try:
      #   library_xml = etree.fromstring(read_url(Request(PLEX_LIBRARY_URL, headers={"X-Plex-Token": read_file(os.path.join(PLEX_ROOT, "X-Plex-Token.id")).strip() if os.path.isfile(os.path.join(PLEX_ROOT, "X-Plex-Token.id")) else Dict(os.environ, 'PLEXTOKEN')})))
      #   for directory in library_xml.iterchildren("Directory"):
      #     for location in directory.iterchildren("Location"):
      #       PLEX_LIBRARY[location.get('path')] = {
      #         'title'  : directory.get('title'),
      #         'scanner': directory.get('scanner'),
      #         'agent'  : directory.get('agent'),
      #       }
      # except Exception as e:
      #   Log.error("Exception: '%s', library_xml could not be loaded. Is the X-Plex-Token file present and accessible?" % (e))
      
      SetupDone = True


def read_url(url, data=None):
  url_content = ""
  try:
    if data is None:
      url_content = urlopen(url,context=SSL_CONTEXT).read()
    else:
      url_content = urlopen(url,context=SSL_CONTEXT, data=data).read()
    return url_content
  except Exception as e:
    Log.error("Error reading or accessing url '%s', Exception: '%s'" % (url, e))
    raise e


def read_file(localfile):
  file_content = ""
  try:
    with open(localfile, 'r') as file:
      file_content = file.read()
    return file_content
  except Exception as e:
    Log.error("Error reading or accessing file '%s', Exception: '%s'" % (localfile, e))
    raise e


def set_logging(root='', foldername='', filename='', backup_count=LOG_RETENTION, format='%(asctime)s [%(name)s] %(levelname)s - %(message)s', mode='a'):
  log_path = os.path.join(PLEX_ROOT, 'Logs', SOURCE)
  if not os.path.exists(log_path):
    os.makedirs(log_path)
  if not foldername:
    foldername = Dict(PLEX_LIBRARY, root, 'title')
  if foldername:
    log_path = os.path.join(log_path, os_filename_clean_string(foldername))
  if not os.path.exists(log_path):
    os.makedirsr(log_path)

  filename = os_filename_clean_string(filename) if filename else '_root_.scanner.log'
  log_file = os.path.join(log_path, filename)

  # Bypass DOS path MAX_PATH limitation (260 Bytes=> 32760 Bytes, 255 Bytes per folder unless UDF 127B ytes max)
  if os.sep=="\\":
    dos_path = os.path.abspath(log_file) if isinstance(log_file, unicode) else os.path.abspath(log_file.decode('utf-8'))
    log_file = u"\\\\?\\UNC\\" + dos_path[2:] if dos_path.startswith(u"\\\\") else u"\\\\?\\" + dos_path

  #if not mode:  mode = 'a' if os.path.exists(log_file) and os.stat(log_file).st_mtime + 3600 > time.time() else 'w' # Override mode for repeat manual scans or immediate rescans

  global Handler
  if Handler:       Log.removeHandler(Handler)
  if backup_count:  Handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=backup_count, encoding='utf-8')
  else:             Handler = logging.FileHandler                 (log_file, mode=mode, encoding='utf-8')
  Handler.setFormatter(logging.Formatter(format))
  Handler.setLevel(logging.DEBUG)
  Log.addHandler(Handler)


def Dict(var, *arg, **kwarg):
  for key in arg:
    if isinstance(var, dict) and key and key in var:
      var = var[key]
    else:
      return kwarg['default'] if kwarg and 'default' in kwarg else ""  # Allow Dict(var, tvdbid).isdigit() for example
  return kwarg['default'] if var in (None, '', 'N/A', 'null') and kwarg and 'default' in kwarg else "" if var in (None, '', 'N/A', 'null') else var


def os_filename_clean_string(in_string):
  for ch, subst in zip(list(FILTER_CHARS), [" " for x in range(len(FILTER_CHARS)) + [("`", "'"), ('"', "'")]]):
    if ch in in_string:
      in_string = in_string.replace(ch, subst)
  return in_string


def filter_chars(in_string):
  for ch, subst in zip(list(FILTER_CHARS), [" " for x in range(len(FILTER_CHARS))]):
    if ch in in_string:
      in_string = in_string.replace(ch, subst)
  return in_string


def load_ta_config():
  global TA_CONFIG
  if TA_CONFIG:
    return
  else:
    TA_CONFIG = get_ta_config()


def get_ta_config():
  SCANNER_LOCATION = "Scanners/Series/"
  CONFIG_NAME = "ta_config.json"
  response = {}
  config_file = os.path.join(PLEX_ROOT, SCANNER_LOCATION, CONFIG_NAME)
  try:
    response = json.loads(read_file(config_file) if os.path.isfile(config_file) else "{}")
  except ValueError as e:
    Log.error("Check to see if `{}` has proper JSON formatting. Exception: {}".format(config_file, e))
    raise e
  except IOError as e:
    Log.error("Check to see if `{}` has correct permissions. Exception: {}".format(config_file, e))
    raise e
  except Exception as e:
    Log.error("Issue with loading `{}` Scanner config file. Check to see if the file exists, is accessible, and is properly formatted. Exception: {}".format(config_file, e))
    raise e
  if not response:
    if os.path.isfile(config_file):
      Log.error("Check to see if `{}` Scanner config file is accessible and has configuration data.".format(config_file))
    else:
      Log.error("Check to see if the Scanner config file `{}` exists.".format(config_file))
  for key in ['ta_url', 'ta_api_key']:
    if key not in response:
      Log.error("Configuration is missing key '{}'.".format(key))
  if not response['ta_url'].startswith("http") and response['ta_url'].find("://") == -1:
    response['ta_url'] = "http://" + response['ta_url']
  Log.debug("TA URL: %s" % (response['ta_url']))
  return response


def test_ta_connection():
  if not TA_CONFIG:
    return
  try:
    Log.info("Attempting to connect to TubeArchivist at {} with provided token from `ta_config.json` file.".format(TA_CONFIG['ta_url']))
    response = json.loads(read_url(Request("{}/api/ping".format(TA_CONFIG['ta_url']), headers={"Authorization": "Token {}".format(TA_CONFIG['ta_api_key'])})))
    ta_ping = response['response']
    ta_version = []
    try:
      if "version" in response:
        try:
          if "v" in response['version'][0]:
            ta_version = [int(x) for x in response['version'][1:].split(".")]
          else:
            ta_version = [int(x) for x in response['version'].split(".")]
        except AttributeError:
          ta_version = response['version']
        Log.info("TubeArchivist is running version v{}".format('.'.join(str(x) for x in ta_version)))
      else:
        ta_version = [0,3,6]
        Log.info("TubeArchivist did not respond with a version. Assuming v{} for interpretation.".format('.'.join(str(x) for x in ta_version)))
    except:
      Log.error("Unable to set the `ta_version`. Check the connection via `ta_ping`.")
      Log.debug("Response: %s" % (response))
    if ta_ping == 'pong':
      return True, ta_version
  except Exception as e:
    Log.error("Error connecting to TubeArchivist with URL '%s', Exception: '%s'" % (TA_CONFIG['ta_url'], e))
    raise e


def get_ta_metadata(id, mtype="video"):
  request_url = ""
  request_url = "{}/api/{}/{}/".format(TA_CONFIG['ta_url'], mtype, id)
  if not TA_CONFIG:
    return
  try:
    Log.info("Attempting to connect to TubeArchivist to lookup YouTube {}: {}".format(mtype, id))
    response = json.loads(read_url(Request(request_url, headers={"Authorization": "Token {}".format(TA_CONFIG['ta_api_key'])})))
    return response
  except Exception as e:
    Log.error("Error connecting to TubeArchivist with URL '{}', Exception: '{}'".format(request_url, e))
    raise e


def get_ta_video_metadata(ytid):
  mtype = "video"
  if not TA_CONFIG:
    Log.error("No configurations in TA_CONFIG.")
    return
  if not ytid:
    Log.error("No {} ID present.".format(mtype))
    return
  try:
    vid_response = get_ta_metadata(ytid)
    Log.info("Response from TubeArchivist received for YouTube {}: {}".format(mtype, ytid))
    if vid_response:
      metadata = {}
      metadata['show'] = "{} [{}]".format(vid_response['data']['channel']['channel_name'], vid_response['data']['channel']['channel_id'])
      metadata['ytid'] = vid_response['data']['youtube_id']
      metadata['title'] = vid_response['data']['title']
      if TA_CONFIG['version'] < [0,3,7]:
        metadata['processed_date'] = datetime.datetime.strptime(vid_response['data']['published'],"%d %b, %Y")
        video_refresh = datetime.datetime.strptime(vid_response['data']['vid_last_refresh'],"%d %b, %Y")
      else:
        metadata['processed_date'] = datetime.datetime.strptime(vid_response['data']['published'],"%Y-%m-%d")
        video_refresh = datetime.datetime.strptime(vid_response['data']['vid_last_refresh'],"%Y-%m-%d")
      metadata['refresh_date'] = video_refresh.strftime("%Y%m%d")
      metadata['season'] = metadata['processed_date'].year
      metadata['episode'] = metadata['processed_date'].strftime("%Y%m%d")
      metadata['description'] = vid_response['data']['description']
      metadata['thumb_url'] = vid_response['data']['vid_thumb_url']
      metadata['type'] = vid_response['data']['vid_type']
      metadata['has_subtitles'] = True if 'subtitles' in vid_response['data'] else False
      if metadata['has_subtitles']:
        metadata['subtitle_metadata'] = vid_response['data']['subtitles']
      return metadata
    else:
      Log.error("Empty response returned from %s when requesting data about %s." % (TA_CONFIG['ta_url'], mtype))
  except Exception as e:
    Log.error("Error processing %s response from TubeArchivist at URL '%s', Exception: '%s'" % (mtype, TA_CONFIG['ta_url'], e))
    raise e


def get_ta_channel_metadata(chid):
  mtype = "channel"
  if not TA_CONFIG:
    Log.error("No configurations in TA_CONFIG.")
    return
  if not chid:
    Log.error("No {} ID present.".format(mtype))
    return
  try:
    ch_response = get_ta_metadata(chid, mtype=mtype)
    Log.info("Response from TubeArchivist received for YouTube {}: {}".format(mtype, chid))
    if ch_response:
      metadata = {}
      metadata['show'] = "{} [{}]".format(ch_response['data']['channel_name'], ch_response['data']['channel_id'])
      if TA_CONFIG['version'] < [0,3,7]:
        channel_refresh = datetime.datetime.strptime(ch_response['data']['channel_last_refresh'],"%d %b, %Y")
      else:
        channel_refresh = datetime.datetime.strptime(ch_response['data']['channel_last_refresh'],"%Y-%m-%d")
      metadata['refresh_date'] = channel_refresh.strftime("%Y%m%d")
      metadata['description'] = ch_response['data']['channel_description']
      metadata['banner_url'] = ch_response['data']['channel_banner_url']
      metadata['thumb_url'] = ch_response['data']['channel_thumb_url']
      metadata['tvart_url'] = ch_response['data']['channel_tvart_url']
      return metadata
    else:
      Log.error("Empty response returned from %s when requesting data about %s." % (TA_CONFIG['ta_url'], mtype))
  except Exception as e:
    Log.error("Error processing %s response from TubeArchivist at URL '%s', Exception: '%s'" % (mtype, TA_CONFIG['ta_url'], e))
    raise e


def Scan(path, files, mediaList, subdirs):
  setup()
  load_ta_config()
  TA_CONFIG['online'] = None
  TA_CONFIG['version'] = []
  TA_CONFIG['online'], TA_CONFIG['version'] = test_ta_connection()
  VideoFiles.Scan(path, files, mediaList, subdirs)

  paths = Utils.SplitPath(path)
  
  if len(paths) > 0 and len(paths[0]) > 0:
    done = False
    episode_counts = {}
    if done == False:
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
            if TA_CONFIG['online']:
              if TA_CONFIG['version'] < [0,3,7]:
                Log.info("Processing filename with legacy filename format.")
                originalAirDate = file[0:7]
                ytid = file[9:20]
                title = file[21:]
                season = originalAirDate[0:4]
                episode = originalAirDate[5:]
              else:
                ytid = file
              try:
                video_metadata = get_ta_video_metadata(ytid)
                show = video_metadata['show']
                if "video" in video_metadata['type']:
                  title = video_metadata['title']
                  season = video_metadata['season']
                else:
                  title = "[{}] {}".format(video_metadata['type'].upper(), video_metadata['title'])
                  season = 0
                episode = video_metadata['episode']
              except Exception as e:
                Log.error("Issue with setting metadata from video using response metadata: '%s', Exception: '%s'" % (str(video_metadata), e))
            else:
              Log.error("TubeArchivist instance is not accessible or not online. Unable to process video file.")
              break
            
            if show not in episode_counts:
              episode_counts[show] = {}
            if season not in episode_counts[show]:
              episode_counts[show][season] = {}
            if episode not in episode_counts[show][season]:
              episode_counts[show][season][episode] = 0
            episode_counts[show][season][episode] += 1
            episode = "{}{:02d}".format(str(episode[2:]), episode_counts[show][season][episode])

            tv_show = Media.Episode(str(show).encode("UTF-8"), str(season).encode("UTF-8"), episode, str(title).encode("UTF-8"), str(season).encode("UTF-8"))
            Log.info("Identified episode '{} - {}' with TV Show {} under Season {}.".format(episode, title, show, season))

            tv_show.released_at = str("{}-{}-{}".format(str(episode)[:3],str(episode)[4:5],str(episode)[6:7])).encode("UTF-8")
            tv_show.parts.append(i)
            Log.info("Adding episode '{}' to TV show '{}' list of episodes.".format(episode, show))
            mediaList.append(tv_show)
            break

  Stack.Scan(path, files, mediaList, subdirs)            
              

if __name__ == '__main__':
  print("{} for Plex!".format(SOURCE))
  path = sys.argv[1]
  files = [os.path.join(path, file) for file in os.listdir(path)]
  media = []
  Scan(path[1:], files, media, [])
  print("Files detected: ", media)