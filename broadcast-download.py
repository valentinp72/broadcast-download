#!/usr/bin/env python3

import argparse

parser = argparse.ArgumentParser(
    description='Script used to automatically download a broadcast radio ' \
    'at a given time.'
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

args = parser.parse_args()

import os
import json
import yaml
import time
import logging
import subprocess
import multiprocessing
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger.info(args)

try:
    from pyradios import RadioBrowser
    has_radio_browser = True
except ImportError:
    logger.warning(
        "Could not load pyradios to use radio-browser. Channels will have " \
        "to specify the stream URL inside the config file!"
    )
    has_radio_browser = False

config = yaml.safe_load(args.config)
logger.info(config)

os.makedirs(args.save_dir, exist_ok=True)
os.makedirs(args.log_dir, exist_ok=True)

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
        return {}, channel['url']

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

def record_channel(channel):
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
    name = f"{channel['name'].replace(' ', '-')}:{now.strftime('%Y%m%dT%H%M%S')}:{duration}"
    target_file = os.path.join(args.save_dir, f"{name}.wav")

    with open(os.path.join(args.log_dir, f"{name}.json"), 'w') as f:
        json.dump(result, fp=f, indent=True, ensure_ascii=False)

    logging.info(f"{prefix}Starting saving into {target_file}. Will run for {hhmmss}.")
    command = [
        "ffmpeg",
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
    logger.info("Starting the workers!")
    channels = config['channels']
    with multiprocessing.Pool(processes=len(channels)) as p:
        correct = p.map(record_channel, channels)

    logger.info(
        f"All processes have finished. Correct? "\
        f"{dict(zip((x['name'] for x in channels), correct))}"
    )

