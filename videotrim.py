#!/usr/bin/env python
import argparse
import sys
import http.client
import json
import os
import subprocess
from subprocess import Popen
import random
import time
import datetime
import re
import json
import copy
import hashlib
import uuid
from random import randrange
import logging
from pydub import AudioSegment
from pydub.silence import split_on_silence
from pydub.silence import detect_silence
from pydub.silence import detect_nonsilent
from moviepy.editor import VideoFileClip
from multiprocessing import Process, Semaphore

sys.path.append(".")

FORMAT = '%(asctime)s %(levelname)-5.5s [%(name)s][%(threadName)s] %(message)s'
logging.basicConfig(format=FORMAT)
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)

def get_all_values(d):
    if isinstance(d, dict):
        for v in d.values():
            yield from get_all_values(v)
    elif isinstance(d, list):
        for v in d:
            yield from get_all_values(v)
    else:
        yield d 

class Main(object):
    def __init__(self):
        parser = argparse.ArgumentParser(
            description='tools to manage voice audio chapters split into verses',
            usage='''splitvideo
''')
        parser.add_argument('command', help='Subcommand to run')
        # parse_args defaults to [1:] for args, but you need to
        # exclude the rest of the args too, or validation will fail
        args = parser.parse_args(sys.argv[1:2])

        print('Main {}'.format(args.command))

        if args.command == 'splitvideo':
            splitvideo = SplitVideo()
            splitvideo.start(args)
        else:
            print('Unrecognized command')
            parser.print_help()
            exit(1)

def walk_folder(media_dir, file_extension, modified_since=None):
    # print('walk_folder media_dir: {}'.format(repr(media_dir)))
    # print('walk_folder file_extension: {}'.format(repr(file_extension)))
    # print('walk_folder modified_since: {}'.format(repr(modified_since)))
    # print('os.path.abspath(f): {}'.format(repr(os.path.abspath(media_dir))))
    all_file_paths = get_filepaths(os.path.abspath(media_dir))
    ts_paths = []
    for f in all_file_paths:
        # print('walk_folder f: {}'.format(repr(f)))

        extension = os.path.splitext(f)[1][1:]
        # print('extension: {}'.format(repr(extension)))
        # if f.endswith('.{}'.format(file_extension)):
        if extension.lower() == file_extension:
            if modified_since is None:
                ts_paths.append(f)
                # print('output_name: {}'.format(f))
                basename = os.path.basename(f)
                # print('basename: {}'.format(basename))
            else:
                modtime = os.path.getmtime(f)
                print('modtime: {}'.format(modtime))
                # print('modified_since.timestamp(): {}'.format(modified_since.timestamp()))
                if modtime > modified_since.timestamp():
                    # print('file new enough to be appended: {}'.format(modtime))
                    ts_paths.append(f)
                    basename = os.path.basename(f)

    return sorted(ts_paths, key=lambda i: os.path.splitext(os.path.basename(i))[0])

def get_filepaths(directory):
    """
    This function will generate the file names in a directory
    tree by walking the tree either top-down or bottom-up. For each
    directory in the tree rooted at directory top (including top itself),
    it yields a 3-tuple (dirpath, dirnames, filenames).
    """
    file_paths = []  # List which will store all of the full filepaths.

    # Walk the tree.
    for root, directories, files in os.walk(directory):
        for filename in files:
            # Join the two strings in order to form the full filepath.
            filepath = os.path.join(root, filename)
            file_paths.append(filepath)  # Add it to the list.

    return file_paths # Self-explanatory.

def sanitize_filename(filepath):

    numbername = filepath.replace('#', 'Number_')
    percentname = numbername.replace('%', '_Percent')

    if percentname != filepath:
        os.rename(filepath, percentname)
        print('sanitized: {}'.format(percentname))
        return percentname
    else:
        return filepath


def build_options(filepath, options):
    components = filepath.split("/")
    filename = components[-1]
    folder_name = components[-2]
    options['filepath'] = filepath
    options['filename'] = filename
    options['folder_name'] = folder_name

    return copy.deepcopy(options)
from pathlib import Path


class SplitVideo(object):

    def __init__(self):
        print('SplitVideo init')

    def start(self, args):
        print('SplitVideo.start args {}'.format(args))
        parser = argparse.ArgumentParser(
            description='split video with provided second markers')
        # prefixing the argument with -- means it's optional
        # parser.add_argument('dir')
        parser.add_argument('video')#, help='<Required> Set flag', required=True)
        parser.add_argument('times', nargs='+', type=int) #, help='<Required> Set flag', required=True)
        parser.add_argument('--dry-run', dest='dry_run', action='store_true')
        parser.add_argument('--file-extension', dest='file_extension', help='walk dirs to find these types, default is mp4')
        # parser.add_argument('--sticker-pack-name', dest='sticker_pack_name', help='name of sticker pack to print')
        # parser.add_argument('--sticker-count', dest='sticker_count', help='number of stickers to print in job')
        # parser.add_argument('--sticker-size', dest='sticker_size', help='regular or mini')
        parser.add_argument('--modified-since', dest='modified_since', type=datetime.datetime.fromisoformat, help='date in ISO format')
        parser.set_defaults(dry_run=False)
        parser.set_defaults(modified_since=None)
        parser.set_defaults(file_extension='mp4')
        args = parser.parse_args(sys.argv[2:])
        print('Running SplitVideo.start, args: {}'.format(repr(args)))

        # video_files = []
        # paths = []
        # for directory in args.dirs:
        #     files = walk_folder(directory, args.file_extension, args.modified_since)
        #     paths.extend(files)


        # base_options = copy.deepcopy(args)
        # for path in paths:
        args_dict = args.__dict__
        print('args_dict: {}'.format(args_dict))
        sanitized = sanitize_filename(args.video)
        options = build_options(sanitized, args_dict)
        # video_files.append(options)


        if len(options["times"]) % 2 != 0:
            print("there must be an even number of times")
            exit()

        # for video in video_files:
        original_video = VideoFileClip(options["filepath"])
        duration = original_video.duration
        LOG.info("original_video duration: {}".format(duration))



        # it = iter(options["times"])

        # for t in it:
        #     starttime = t
        #     endtime = next(it)

        #     video_path = "{}-{}-output.mp4".format(starttime, endtime)
        #     ffmpeg_extract_subclip(options["filepath"], starttime, endtime, targetname=video_path)




        it = iter(options["times"])

        for t in it:
            starttime = t
            endtime = next(it)
            clip = VideoFileClip(options["filepath"]).subclip(starttime, endtime).resize((1280, 720))
            # clip.write_videofile("output_{}-{}.mp4".format(starttime, endtime), fps=original_video.fps, bitrate="3000k",
            #                  threads=1, preset='ultrafast', codec='h264')
            
            clip.write_videofile("output_{}-{}.mp4".format(starttime, endtime), fps=original_video.fps, bitrate="3000k",
                             threads=1, preset='ultrafast', codec='libx264', audio_codec='aac')



if __name__ == '__main__':
    Main()
