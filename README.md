# broadcast-download

Script used to programmatically download multiple radio streams at a given time.

## Installation from precompiled binaries

The precompiled binaries are available in the [releases page](releases).
Please download the Linux / macOS / windows binary according to your system. They include all the requirements (ffmpeg, python, ...).

### Usage:

1. Download the binary, for example in your `Downloads` folder.
2. Download the config.yaml file and edit it to your need. Please be careful with `start` and `stop` formatting, the times are formatted using [UTC](https://en.wikipedia.org/wiki/Coordinated_Universal_Time), hence +2 for UTC+2 (Paris Summer Time / CEST).
3. In a terminal, run (change `broadcast-download-macos-latest` to the name of your downloaded file):
```bash
$HOME/Downloads/broadcast-download-macos-latest --config $HOME/Downloads/config.yaml
```
4. The recordings will be available in `Downloads/recordings` and the logs into `Downloads/logs`. Do not close the terminal until recordings are done (should print `All processes have finished.` along with information if each broadcast was downloaded successfully.)

---

## Installation from source

### Requirements:
- python3
- [`ffmpeg`](https://ffmpeg.org/download.html)
- Optional: [`pyradios`](https://pypi.org/project/pyradios/) (used to get streaming URL from a given radio name)


### Usage:

1. Download the source code.
2. Install the requirements, for example with
```bash
pip3 install -r requirements.txt
```
3. Edit the config.yaml file to your need
3. You can see the help of the tool with `./broadcast-download.py --help`
4. Run `./broadcast-download.py --config config.yaml`

