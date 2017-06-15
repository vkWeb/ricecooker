
"""Usage: ricecooker uploadchannel [-huv] <file_path> [--warn] [--compress] [--token=<t>] [--thumbnails] [--download-attempts=<n>] [--resume [--step=<step>] | --reset] [--prompt] [--publish] [--daemon] [[OPTIONS] ...]

Arguments:
  file_path        Path to file with channel data

Options:
  -h                          Help documentation
  -v                          Verbose mode
  -u                          Re-download files from file paths
  --warn                      Print out warnings to stderr
  --compress                  Compress high resolution videos to low resolution videos
  --thumbnails                Automatically generate thumbnails for topics
  --token=<t>                 Authorization token (can be token or path to file with token) [default: #]
  --download-attempts=<n>     Maximum number of times to retry downloading files [default: 3]
  --resume                    Resume from ricecooker step (cannot be used with --reset flag)
  --step=<step>               Step to resume progress from (must be used with --resume flag) [default: last]
  --reset                     Restart session, overwriting previous session (cannot be used with --resume flag)
  --prompt                    Receive prompt to open the channel once it's uploaded
  --publish                   Automatically publish channel once it's been created
  --daemon                    Runs in daemon mode
  [OPTIONS]                   Extra arguments to add to command line (e.g. key='field')

Steps (for restoring session):
  LAST (default):       Resume where the session left off
  INIT:                 Resume at beginning of session
  CONSTRUCT_CHANNEL:    Resume with call to construct channel
  CREATE_TREE:          Resume at set tree relationships
  DOWNLOAD_FILES:       Resume at beginning of download process
  GET_FILE_DIFF:        Resume at call to get file diff from Kolibri Studio
  START_UPLOAD:         Resume at beginning of uploading files to Kolibri Studio
  UPLOADING_FILES:      Resume at last upload request
  UPLOAD_CHANNEL:       Resume at beginning of uploading tree to Kolibri Studio
  PUBLISH_CHANNEL:      Resume at option to publish channel
  DONE:                 Resume at prompt to open channel

"""

from .commands import uploadchannel
from . import config
from .exceptions import InvalidUsageException
from .managers.progress import Status
from daemonize import Daemonize
from docopt import docopt
import json
import threading
import time
import websocket

commands = ["uploadchannel"]


class WebSocketHandler(threading.Thread):
    """WebSocket with re-connection logic."""

    def __init__(self, url):
        threading.Thread.__init__(self)
        self.url = url
        self.ws_opened = False
        self.ws = None
        self._stop_event = threading.Event()

    def __connect(self):
        print('########### CONNECTING ##############')
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self.__on_open,
            on_close=self.__on_close,
            on_message=self.on_message
        )
        #print('waiting')
        #while not self.ws_opened:
        #    pass
        #print('done')

    def __on_open(self, message):
        self.ws_opened = True

    def __on_close(self, message):
        self.ws_opened = False

    def run(self):
        while not self.stopped():
            self.__connect()
            self.ws.run_forever()

    def on_message(self, ws, message):
        pass

    def send(self, data):
        if self.ws_opened:
            self.ws.send(data)

    def stop(self):
        self._stop_event.set()
        self.ws.close()

    def stopped(self):
        return self._stop_event.is_set()


class ControlWebSocket(WebSocketHandler):
    def __init__(self):
        WebSocketHandler.__init__(self, 'ws://127.0.0.1:8000/control/12345')

    def on_message(self, ws, message):
        message = json.loads(message)
        print(message['command'])


def single_run(arguments, **kwargs):
    try:
        uploadchannel(arguments["<file_path>"],
                      verbose=arguments["-v"],
                      update=arguments['-u'],
                      thumbnails=arguments["--thumbnails"],
                      download_attempts=arguments['--download-attempts'],
                      resume=arguments['--resume'],
                      reset=arguments['--reset'],
                      token=arguments['--token'],
                      step=arguments['--step'],
                      prompt=arguments['--prompt'],
                      publish=arguments['--publish'],
                      warnings=arguments['--warn'],
                      compress=arguments['--compress'],
                      **kwargs)
        config.SUSHI_BAR_CLIENT.report_stage('COMPLETED', 0)
    except Exception as e:
        config.SUSHI_BAR_CLIENT.report_stage('FAILURE', 0)
        config.LOGGER.critical(e)
        raise
    finally:
        config.SUSHI_BAR_CLIENT.close()


def daemon_mode(arguments, **kwargs):
    cws = ControlWebSocket()
    cws.start()
    cws.join()


if __name__ == '__main__':
    arguments = docopt(__doc__)

    # Parse OPTIONS for keyword arguments
    kwargs = {}
    for arg in arguments['OPTIONS']:
      try:
        kwarg = arg.split('=')
        kwargs.update({kwarg[0].strip(): kwarg[1].strip()})
      except IndexError:
        raise InvalidUsageException("Invalid kwarg '{0}' found: Must format as [key]=[value] (no whitespace)".format(arg))

    # Check if step is valid (if provided)
    step = arguments['--step']
    all_steps = [s.name for s in Status]
    if step.upper() not in all_steps:
      raise InvalidUsageException("Invalid step '{0}': Valid steps are {1}".format(step, all_steps))
    arguments['--step'] = step

    # Make sure max-retries can be cast as an integer
    try:
      int(arguments['--download-attempts'])
    except ValueError:
      raise InvalidUsageException("Invalid argument: Download-attempts must be an integer.")

    if arguments['--daemon']:
        #daemon = Daemonize(app='sushi_chef', pid='chef.pid', action=lambda : daemon_mode(arguments,**kwargs), chdir='.')
        #daemon.start()
        daemon_mode(arguments,**kwargs)
    else:
        single_run(arguments, **kwargs)
