#!/usr/bin/env python3

import os
import sys
import json
import yaml
import time
import logging
import subprocess
import multiprocessing
from itertools import repeat
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

try:
    from pyradios import RadioBrowser
    has_radio_browser = True
except ImportError:
    logger.warning(
        "Could not load pyradios to use radio-browser. Channels will have " \
        "to specify the stream URL inside the config file!"
    )
    has_radio_browser = False

def resource_path(relative_path):
    if relative_path.startswith('/'):
        return relative_path
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def wait_until(until):
    while until > datetime.now(timezone.utc):
        time.sleep(60) # wait for 60s until next retry

def seconds_to_hhmmss(seconds):
    seconds = int(seconds)
    hours = seconds // 3600
    seconds = seconds % 3600
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def get_url(channel):
    prefix = f"[{channel['name']}] "

    if 'url' in channel:
        # you can directly specify the url to the stream
        return {'url': channel['url']}, channel['url']

    if not has_radio_browser:
        raise ValueError(
            "RadioBrowser (pyradios) is not installed, and I don't know the " \
            "URL to that radio."
        )
    rb = RadioBrowser()
    if 'uuid' in channel:
        result = rb.station_by_uuid(channel['uuid'])
    else:
        result = rb.search(name=channel['name'], name_exact=True, order='votes')

    logger.info(f"{prefix}Found {len(result)} stations.")
    if len(result) == 0:
        raise ValueError(
            "No stations found, not recording!"
        )
    elif len(result) > 1:
        logger.warning(f"{prefix}Multiple stations available, will take the one with the most votes.")

    result = result[-1]
    url = result['url']

    return result, url

def record_channel(channel, args):
    prefix = f"[{channel['name']}] "

    if 'start' not in channel or 'stop' not in channel:
        logger.info(f"{prefix}Not start/stop, ignoring.")
        return False

    until = channel['start'] - timedelta(seconds=args.collar_seconds)
    logger.info(f"{prefix}Waiting until {until}...")
    wait_until(until)

    try:
        result, url = get_url(channel)
    except ValueError as e:
        logger.error(f"{prefix}{e.args[0]}")
        return False
    logger.info(f"{prefix}Selected the broadcast with UUID={result.get('stationuuid', '')} and URL={url}.")

    now = datetime.now(timezone.utc)
    duration = int(
        (channel['stop'] - now).total_seconds() \
        + args.collar_seconds
    )
    if duration < 0:
        logger.error(f"{prefix}Requested duration is < 0 seconds. Are we running late?")
        return False
    hhmmss = seconds_to_hhmmss(duration)
    name = f"{channel['name'].replace(' ', '-')}_{now.strftime('%Y%m%dT%H%M%S')}_{duration}"
    target_file = os.path.join(args.save_dir, f"{name}.wav")

    with open(os.path.join(args.log_dir, f"{name}.json"), 'w') as f:
        json.dump(result, fp=f, indent=True, ensure_ascii=False)

    logging.info(f"{prefix}[Recording] Starting saving into {target_file}. Will run for {hhmmss}.")
    command = [
        resource_path(args.ffmpeg_binary),
        "-loglevel", "warning",
        "-y",
        "-i", url,
        "-to", hhmmss,
        target_file
    ]
    with open(os.path.join(args.log_dir, f"{name}.log"), 'w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=log)
        process.communicate()
    logger.info(f"{prefix}Done!")
    return True

if __name__ == "__main__":
    multiprocessing.freeze_support()
    import argparse

    parser = argparse.ArgumentParser(
        description='Script used to automatically download a broadcast radio ' \
        'at a given time.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--ffmpeg_binary', type=str, default='ffmpeg',
        help='Path to the ffmpeg binary used to download.'
    )
    parser.add_argument(
        '--config', type=argparse.FileType('r'), default='config.yaml',
        help='File containing the configuration (channels and required times).'
    )
    parser.add_argument(
        '--collar_seconds', type=int, default=600,
        help='How many seconds before and after the required times should we ' \
        'start / stop the recording.'
    )
    parser.add_argument(
        '--save_dir', type=str, default='recordings',
        help='Specify a downloading directory for the recordings.'
    )
    parser.add_argument(
        '--log_dir', type=str, default='logs',
        help='Specify a directory for the logs.'
    )
    parser.add_argument(
        '--debug', action='store_true',
        help='If set, will only download recordings for maximum 10s.'
    )

    args = parser.parse_args()
    logger.info(args)

    config = yaml.safe_load(args.config)
    channels = config['channels']
    logger.info(config)

    if args.debug:
        logger.info("Enabled debug mode! Will record 10s for each channel.")
        for c in channels:
            if 'start' in c and 'stop' in c:
                c['start'] = datetime.now(timezone.utc)
                c['stop'] = datetime.now(timezone.utc) + timedelta(seconds=10)
        args.collar_seconds = 0

    os.makedirs(args.save_dir, exist_ok=True)
    os.makedirs(args.log_dir, exist_ok=True)

    logger.info("Starting the workers!")
    safe_args = argparse.Namespace(**{k: getattr(args, k) for k in ['ffmpeg_binary', 'collar_seconds', 'save_dir', 'log_dir', 'debug']})
    with multiprocessing.Pool(processes=len(channels)) as p:
        correct = p.starmap(record_channel, zip(channels, repeat(safe_args)))

    logger.info(
        f"All processes have finished. Correct? "\
        f"{dict(zip((x['name'] for x in channels), correct))}"
    )
