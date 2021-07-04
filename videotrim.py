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
            usage='''splittrailing <dir>
exporttomp3 <dir>
normalizefilenames <dir>
trimsamples <dir>
splitvideo
''')
        parser.add_argument('command', help='Subcommand to run')
        # parse_args defaults to [1:] for args, but you need to
        # exclude the rest of the args too, or validation will fail
        args = parser.parse_args(sys.argv[1:2])

        print('Main {}'.format(args.command))

        if args.command == 'splittrailing':
            splittrailing = SplitTrailing()
            splittrailing.start(args)
        elif args.command == 'exporttomp3':
            exporttomp3 = ExportToMP3()
            exporttomp3.start(args)
        elif args.command == 'normalizefilenames':
            normalizefilenames = NormalizeFilenames()
            normalizefilenames.start(args)
        elif args.command == 'trimsamples':
            trimsamples = TrimSamples()
            trimsamples.start(args)
        elif args.command == 'splitvideo':
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


class SplitTrailing(object):
    def __init__(self):
        print('SplitTrailing init')

    def start(self, args):
        print('SplitTrailing.start args {}'.format(args))
        parser = argparse.ArgumentParser(
            description='parse dirs to determine which images to print to label printer')
        # prefixing the argument with -- means it's optional
        # parser.add_argument('dir')
        parser.add_argument('dirs', nargs='+')#, help='<Required> Set flag', required=True)
        parser.add_argument('--dry-run', dest='dry_run', action='store_true')
        parser.add_argument('--file-extension', dest='file_extension', help='walk dirs to find these types, default is wav')
        # parser.add_argument('--sticker-pack-name', dest='sticker_pack_name', help='name of sticker pack to print')
        # parser.add_argument('--sticker-count', dest='sticker_count', help='number of stickers to print in job')
        # parser.add_argument('--sticker-size', dest='sticker_size', help='regular or mini')
        parser.add_argument('--modified-since', dest='modified_since', type=datetime.datetime.fromisoformat, help='date in ISO format')
        parser.set_defaults(dry_run=False)
        parser.set_defaults(modified_since=None)
        parser.set_defaults(file_extension='wav')
        args = parser.parse_args(sys.argv[2:])
        print('Running SplitTrailing.start, args: {}'.format(repr(args)))

        splittrailing_files = []
        paths = []
        for directory in args.dirs:
            files = walk_folder(directory, args.file_extension, args.modified_since)
            paths.extend(files)
        # base_options = copy.deepcopy(args)
        for path in paths:
            args_dict = args.__dict__
            print('args_dict: {}'.format(args_dict))
            sanitized = sanitize_filename(path)
            options = build_options(sanitized, args_dict)
            # options = build_options(sanitized, args_dict)
            # print('options: {}'.format(options))
            splittrailing_files.append(options)
        sorted_array = sorted(splittrailing_files, key=lambda x: x['filename'], reverse=False)
        if args.dry_run is False:
            if args.file_extension == 'wav':
                # self._splittrailing_chunks(sorted_array)
                linted_items = self._find_trailing_lint(sorted_array)

                for count, item in enumerate(linted_items):
                    split_item = self._split_linted_item(item)
                    self._prepend_lint_to_next_item(split_item, sorted_array)
                # self._splittrailing_chunks(sorted_array, args.sticker_pack_name, int(args.sticker_count), args.sticker_size)
        else:
            print('dry_run sorted_array: {} stickers'.format(len(sorted_array)))

    def _split_linted_item(self, linted_item):
        # for count, item in enumerate(linted_item):
        truncated_segment = self._export_truncated(linted_item, "WAV")
        trailing_lint_segment = self._export_trailing_lint(linted_item, "WAV")
        linted_item["truncated_segment"] = truncated_segment
        linted_item["trailing_lint_segment"] = trailing_lint_segment

        return copy.deepcopy(linted_item)

            # segment = AudioSegment.from_wav(item["item"]["filepath"])
            # LOG.info("_split_linted_items segment: {}".format(len(segment)))
            # trim_ms = item["silence_ranges"][-1][0]
            # LOG.info("trim_ms: {}".format(trim_ms))

            # # trim the trailing "lint"
            # truncated = segment[:trim_ms]

            # filename = item["item"]["filename"]
            # filename_name = os.path.splitext(filename)[0]
            # filename_name_truncated = filename_name + "_truncated"
            # filename_ext = os.path.splitext(filename)[1][1:]

            # truncated_filename = filename_name_truncated + "." + filename_ext

            # LOG.info("truncated: {}".format(truncated))
            # LOG.info("filename: {}".format(filename_name))
            # LOG.info("filename_name_truncated: {}".format(filename_name_truncated))
            # LOG.info("filename_plus: {}".format(filename_ext))

            # head, tail = os.path.split(item["item"]["filepath"])
            # LOG.info("head, tail: {}, {}".format(head, tail))
            # tail_noext = os.path.splitext(tail)[0]
            # LOG.info("tail_noext: {}".format(tail_noext))
            # tail_ext = os.path.splitext(tail)[1]
            # LOG.info("tail_ext: {}".format(tail_ext))

            # exportpath = os.path.join(head, truncated_filename)
            # LOG.info("exportpath: {}".format(exportpath))

            # truncated.export(exportpath, format="WAV")
            # truncated.export
    def _prepend_lint_to_next_item(self, linted_item, all_items):
        print('_prepend_lint_to_next_item {}'.format(linted_item))
        # for count, item in enumerate(linted_items):
        # print('_prepend_lint_to_next_item item to prepend: {}'.format(all_items[linted_item["next_item_index"]]))
        prepend_item = all_items[linted_item["next_item_index"]]
        print('_prepend_lint_to_next_item prepend_item: {}'.format(prepend_item))

        prepend_item_segment = AudioSegment.from_wav(prepend_item["filepath"])
        trailing_lint_segment = linted_item["trailing_lint_segment"]
        print('_prepend_lint_to_next_item trailing_lint_segment: {}'.format(trailing_lint_segment))

        # put the trailing lint segment of the previous track at the beginning of the
        # next track
        export_segment = trailing_lint_segment + prepend_item_segment

        # 210330_12.WAV
        filename = prepend_item["filename"]
        # 210330_12
        filename_name = os.path.splitext(filename)[0]
        # 210330_12_prepended
        filename_name_truncated = filename_name + "_prepended"
        # WAV
        filename_ext = os.path.splitext(filename)[1][1:]
        # 210330_12_prepended.WAV
        truncated_filename = filename_name_truncated + "." + filename_ext

        # LOG.info("truncated: {}".format(truncated))
        # LOG.info("filename: {}".format(filename_name))
        # LOG.info("filename_name_truncated: {}".format(filename_name_truncated))
        # LOG.info("filename_plus: {}".format(filename_ext))

        head, tail = os.path.split(prepend_item["filepath"])
        # LOG.info("head, tail: {}, {}".format(head, tail))
        tail_noext = os.path.splitext(tail)[0]
        # LOG.info("tail_noext: {}".format(tail_noext))
        tail_ext = os.path.splitext(tail)[1]
        # LOG.info("tail_ext: {}".format(tail_ext))

        exportpath = os.path.join(head, truncated_filename)
        export_segment.export(exportpath, format="WAV")


    def _find_trailing_lint(self, audio_items):
        trailing_lint = []
        all_silence_ranges = []

        for count, item in enumerate(audio_items):
        # for audio_segment in audio_items:
            # print('_printimages_images x {}'.format(x))
            # print('_printimages_images sticker_count {}'.format(sticker_count))

            segment = AudioSegment.from_wav(item["filepath"])
            LOG.info("{}: length segment: {}".format(item["filename"], len(segment)))
            # LOG.info("segment filename: {}".format(item["filename"]))

            # this can remain fairly coarse because we just need to determine if the 
            # very beginning of the audio file has non-silence
            silence_duration = 225
            silence_threshold = -40
            ranges = self._find_audible_ranges(segment, silence_duration, silence_threshold)
            # all_ranges.append(ranges)

            # these two values seem to be good for Scourby and the -6Db volume levels on the Sony PCM-D50
            silence_duration_non = 55
            silence_threshold_non = -45
            all_silence_ranges.append(self._find_inaudible_ranges(segment, silence_duration_non, silence_threshold_non))

            # if the first_audible_range[0] is a 0 then it is possible the previous item
            # was truncated or, has 'trailing lint' (because sample 0 was not silent)

            ## so get the PREVIOUS item SILENT ranges(all_silence_ranges), which might help up determine
            # where near the end of the file to split/trim-off the lint

            if len(ranges) > 0 and ranges[0][0] == 0:
                LOG.info("{}: sample 0 not silent".format(item["filename"]))
                if count > 0:
                    # prev_segment = AudioSegment.from_wav(audio_items[count-1]["filepath"])
                    # LOG.info("_find_inaudible_ranges for {}:".format(audio_items[count-1]["filename"]))
                    trailing_lint.append({"item": audio_items[count-1], "next_item_index": count, "silence_ranges": all_silence_ranges[count-1]})
            
        LOG.info("possible trailing lint: {}".format(trailing_lint))
        return trailing_lint

    def _export_truncated(self, item, file_format) -> AudioSegment:
        # print('_export_truncated {}'.format(item))
        segment = AudioSegment.from_wav(item["item"]["filepath"])
        # LOG.info("_export_truncated segment: {}".format(len(segment)))
        truncate_ms = item["silence_ranges"][-1][0]
        # LOG.info("truncate_ms: {}".format(truncate_ms))

        # trim the trailing "lint"
        truncated = segment[:truncate_ms]
        LOG.info("truncated length:{}".format(len(truncated)))

        filename = item["item"]["filename"]
        filename_name = os.path.splitext(filename)[0]
        filename_name_truncated = filename_name + "_truncated"
        filename_ext = os.path.splitext(filename)[1][1:]

        truncated_filename = filename_name_truncated + "." + filename_ext

        # LOG.info("truncated: {}".format(truncated))
        # LOG.info("filename: {}".format(filename_name))
        # LOG.info("filename_name_truncated: {}".format(filename_name_truncated))
        # LOG.info("filename_plus: {}".format(filename_ext))

        head, tail = os.path.split(item["item"]["filepath"])
        # LOG.info("head, tail: {}, {}".format(head, tail))
        tail_noext = os.path.splitext(tail)[0]
        # LOG.info("tail_noext: {}".format(tail_noext))
        tail_ext = os.path.splitext(tail)[1]
        # LOG.info("tail_ext: {}".format(tail_ext))

        exportpath = os.path.join(head, truncated_filename)
        LOG.info("exportpath: {}".format(exportpath))

        truncated.export(exportpath, format=file_format)
        
        return truncated

    def _export_trailing_lint(self, item, file_format) -> AudioSegment:
        # print('_export_trailing_lint {}'.format(item))
        segment = AudioSegment.from_wav(item["item"]["filepath"])
        # LOG.info("_export_trailing_lint segment: {}".format(len(segment)))
        truncate_ms = item["silence_ranges"][-1][0]
        # LOG.info("truncate_ms: {}".format(truncate_ms))

        # remove everything before the trailing "lint"

        lint = len(segment) - truncate_ms
        # LOG.info("trailing_lint lint:{}".format(lint))
        trailing_lint = segment[-lint:]
        # LOG.info("trailing_lint length:{}".format(len(trailing_lint)))

        filename = item["item"]["filename"]
        filename_name = os.path.splitext(filename)[0]
        filename_name_trailing_lint = filename_name + "_trailing_lint"
        filename_ext = os.path.splitext(filename)[1][1:]

        trailing_lint_filename = filename_name_trailing_lint + "." + filename_ext

        # LOG.info("trailing_lint: {}".format(trailing_lint))
        # LOG.info("filename: {}".format(filename_name))
        # LOG.info("filename_name_trailing_lint: {}".format(filename_name_trailing_lint))
        # LOG.info("filename_plus: {}".format(filename_ext))

        head, tail = os.path.split(item["item"]["filepath"])
        # LOG.info("head, tail: {}, {}".format(head, tail))
        tail_noext = os.path.splitext(tail)[0]
        # LOG.info("tail_noext: {}".format(tail_noext))
        tail_ext = os.path.splitext(tail)[1]
        # LOG.info("tail_ext: {}".format(tail_ext))

        exportpath = os.path.join(head, trailing_lint_filename)
        LOG.info("exportpath: {}".format(exportpath))

        # trailing_lint.export(exportpath, format=file_format)

        return trailing_lint


    # def _splittrailing_chunks(self, audio_segments):
    #     print('_splittrailing_chunks {}'.format(audio_segments))
    #     main_segment = None

    #     for audio_segment in audio_segments:
    #         # print('_printimages_images x {}'.format(x))
    #         # print('_printimages_images sticker_count {}'.format(sticker_count))

    #         main_segment = AudioSegment.from_wav(audio_segment["filepath"])
    #         # LOG.info("main_segment: {}".format(main_segment))
    #         LOG.info("main_segment filename: {}".format(audio_segment["filename"]))

    #         silence_duration = 225
    #         silence_threshold = -40
    #         self._find_audible_ranges(main_segment, silence_duration, silence_threshold)


            # random_sticker = audio_segments[randrange(len(audio_segments))]

        # if tail_ext == '.mp3':
        #     main_segment = AudioSegment.from_mp3(filename)
        # elif tail_ext == '.wav':
        #     main_segment = AudioSegment.from_wav(filename)
        # else:
        #     raise ValueError('This application supports WAV or MP3')
#             sys.exit(0)

#         main_segment = main_segment[(400*1000):(700*1000)]
#         main_segment = main_segment[(1932*1000):(1938*1000)]
#         main_segment = main_segment[(900*1000):(930*1000)]

            # ''' generate a mono channel AudioSegment '''
            
    def _find_audible_ranges(self, segment, silence_duration, silence_threshold):
        ranges = detect_nonsilent(segment, silence_duration, silence_threshold)
        # for range in ranges:
        #     LOG.info("range: {}".format(range))
            # self.phrases.append(Phrase(self.chunk[range[0]:range[1]]))
        
        # LOG.info("ranges: {}".format(ranges))
        return ranges
        # self.found_ranges = True

    def _find_inaudible_ranges(self, segment, silence_duration, silence_threshold):
        # LOG.info("_find_inaudible_ranges segment: {}".format(segment))
        ranges = detect_silence(segment, silence_duration, silence_threshold)
        # LOG.info('speech all silence ranges: {}'.format(ranges))

        
        # LOG.info("ranges: {}".format(ranges))
        return ranges
        # self.found_ranges = True




            # channels = main_segment.split_to_mono()
            # LOG.info('chunk channels: {channels}'.format(**locals()))
            # monochunk = channels[0]
            # segment = monochunk

class ExportToMP3(object):
    def __init__(self):
        print('ExportToMP3 init')

    def start(self, args):
        print('ExportToMP3.start args {}'.format(args))
        parser = argparse.ArgumentParser(
            description='parse dirs to determine which images to print to label printer')
        # prefixing the argument with -- means it's optional
        # parser.add_argument('dir')
        parser.add_argument('dirs', nargs='+')#, help='<Required> Set flag', required=True)
        parser.add_argument('--dry-run', dest='dry_run', action='store_true')
        parser.add_argument('--file-extension', dest='file_extension', help='walk dirs to find these types, default is wav')
        # parser.add_argument('--sticker-pack-name', dest='sticker_pack_name', help='name of sticker pack to print')
        # parser.add_argument('--sticker-count', dest='sticker_count', help='number of stickers to print in job')
        # parser.add_argument('--sticker-size', dest='sticker_size', help='regular or mini')
        # parser.add_argument('--modified-since', dest='modified_since', type=datetime.datetime.fromisoformat, help='date in ISO format')
        parser.set_defaults(dry_run=False)
        parser.set_defaults(modified_since=None)
        parser.set_defaults(file_extension='wav')
        args = parser.parse_args(sys.argv[2:])
        print('Running ExportToMP3.start, args: {}'.format(repr(args)))

        exporttomp3_files = []
        paths = []
        for directory in args.dirs:
            files = walk_folder(directory, args.file_extension, args.modified_since)
            paths.extend(files)
        # base_options = copy.deepcopy(args)
        for path in paths:
            args_dict = args.__dict__
            print('args_dict: {}'.format(args_dict))
            sanitized = sanitize_filename(path)
            options = build_options(sanitized, args_dict)
            # options = build_options(sanitized, args_dict)
            # print('options: {}'.format(options))
            exporttomp3_files.append(options)
        sorted_array = sorted(exporttomp3_files, key=lambda x: x['filename'], reverse=False)
        if args.dry_run is False:
            if args.file_extension == 'wav':
                for count, item in enumerate(sorted_array):
                    self.export(item, args.dry_run)
        else:
            print('dry_run sorted_array: {} stickers'.format(len(sorted_array)))

    def export(self, item, dry_run):
        head, tail = os.path.split(item["filepath"])
        LOG.info("head: {}".format(head))
        LOG.info("tail: {}".format(tail))
        head_path_array = head.split("/")
        # remove last path item because we want to go "up" one dir
        head_path_array = head_path_array[:-1]
        LOG.info("head_path_array: {}".format(head_path_array))

        parent_path = "/" + os.path.join(*head_path_array)
        LOG.info("parent_path: {}".format(parent_path))

        # make "mp3" dir in the parent dir
        exportdir = os.path.join(parent_path, "mp3")
        os.makedirs(exportdir, exist_ok=True)

        # head_parent = head_path_array[-2]
        # LOG.info("head_parent: {}".format(head_parent))
        folder_name = item["folder_name"]
        LOG.info("folder_name: {}".format(folder_name))
        exportdir = os.path.join(exportdir, folder_name + "-mp3")
        LOG.info("exportdir: {}".format(exportdir))
        os.makedirs(exportdir, exist_ok=True)
        filename_name = os.path.splitext(tail)[0] + ".mp3"
        LOG.info("filename_name: {}".format(filename_name))
        exportpath = os.path.join(exportdir, filename_name)
        LOG.info("exportpath: {}".format(exportpath))
        segment = AudioSegment.from_wav(item["filepath"])

        if dry_run is False:
            segment.export(exportpath, format="mp3")

class NormalizeFilenames(object):
    def __init__(self):
        print('NormalizeFilenames init')

    def start(self, args):
        print('NormalizeFilenames.start args {}'.format(args))
        parser = argparse.ArgumentParser(
            description='parse dirs to determine which images to print to label printer')
        # prefixing the argument with -- means it's optional
        # parser.add_argument('dir')
        parser.add_argument('dirs', nargs='+')#, help='<Required> Set flag', required=True)
        parser.add_argument('--dry-run', dest='dry_run', action='store_true')
        parser.add_argument('--file-extension', dest='file_extension', help='walk dirs to find these types, default is mp3')
        # parser.add_argument('--sticker-pack-name', dest='sticker_pack_name', help='name of sticker pack to print')
        # parser.add_argument('--sticker-count', dest='sticker_count', help='number of stickers to print in job')
        # parser.add_argument('--sticker-size', dest='sticker_size', help='regular or mini')
        # parser.add_argument('--modified-since', dest='modified_since', type=datetime.datetime.fromisoformat, help='date in ISO format')
        parser.set_defaults(dry_run=False)
        parser.set_defaults(modified_since=None)
        parser.set_defaults(file_extension='mp3')
        args = parser.parse_args(sys.argv[2:])
        print('Running NormalizeFilenames.start, args: {}'.format(repr(args)))

        normalizefilenames_files = []
        paths = []
        for directory in args.dirs:
            files = walk_folder(directory, args.file_extension, args.modified_since)
            paths.extend(files)
        # base_options = copy.deepcopy(args)
        for path in paths:
            args_dict = args.__dict__
            print('args_dict: {}'.format(args_dict))
            sanitized = sanitize_filename(path)
            options = build_options(sanitized, args_dict)
            # options = build_options(sanitized, args_dict)
            # print('options: {}'.format(options))
            normalizefilenames_files.append(options)
        sorted_array = sorted(normalizefilenames_files, key=lambda x: x['filename'], reverse=False)
        if args.dry_run is False:
            if args.file_extension == 'mp3':
                for count, item in enumerate(sorted_array):
                    self.normalize_filename(item)
        else:
            print('dry_run sorted_array: {} stickers'.format(len(sorted_array)))

    def normalize_filename(self, item):
        # remove _truncated, _prepended from all files
        head, tail = os.path.split(item["filepath"])
        LOG.info("tail: {}".format(tail))

        if "_truncated" in tail:
            normalized = tail.replace("_truncated", "")
            LOG.info("normalized: {}".format(normalized))
            source = os.path.join(head, normalized)
            destination = os.path.join(head, tail)
            os.replace(destination, source)
        
        if "_prepended" in tail:
            normalized = tail.replace("_prepended", "")
            LOG.info("normalized: {}".format(normalized))
            source = os.path.join(head, normalized)
            destination = os.path.join(head, tail)
            os.replace(destination, source)

class TrimSamples(object):
    def __init__(self):
        print('TrimSamples init')

    def start(self, args):
        print('TrimSamples.start args {}'.format(args))
        parser = argparse.ArgumentParser(
            description='parse dirs to determine which images to print to label printer')
        # prefixing the argument with -- means it's optional
        # parser.add_argument('dir')
        parser.add_argument('audiofiles', nargs='+')#, help='<Required> Set flag', required=True)
        parser.add_argument('milliseconds', type=int, help='number of ms to trim. Use a positive value to trim beginning of audio file(s), negative value to trim end of audio file(s)')
        parser.add_argument('--dry-run', dest='dry_run', action='store_true')
        parser.add_argument('--replace', dest='replace', action='store_true',  help='delete original audio file and replace with sliced file')
        parser.add_argument('--file-extension', dest='file_extension', help='walk dirs to find these types, default is wav')
        # parser.add_argument('--sticker-pack-name', dest='sticker_pack_name', help='name of sticker pack to print')
        # parser.add_argument('--sticker-count', dest='sticker_count', help='number of stickers to print in job')
        # parser.add_argument('--sticker-size', dest='sticker_size', help='regular or mini')
        # parser.add_argument('--modified-since', dest='modified_since', type=datetime.datetime.fromisoformat, help='date in ISO format')
        parser.set_defaults(dry_run=False)
        parser.set_defaults(replace=False)
        parser.set_defaults(file_extension='wav')
        args = parser.parse_args(sys.argv[2:])
        print('Running TrimSamples.start, args: {}'.format(repr(args)))

        trimsamples_files = []
        # paths = []
        # for directory in args.images:
        #     files = walk_folder(directory, args.file_extension, args.modified_since)
        #     paths.extend(files)
        # base_options = copy.deepcopy(args)
        for path in args.audiofiles:
            args_dict = args.__dict__
            print('args_dict: {}'.format(args_dict))
            sanitized = sanitize_filename(path)
            options = build_options(sanitized, args_dict)
            # options = build_options(sanitized, args_dict)
            # print('options: {}'.format(options))
            trimsamples_files.append(options)
        sorted_array = sorted(trimsamples_files, key=lambda x: x['filename'], reverse=False)
        if args.dry_run is False:
            if args.file_extension == 'wav':
                self.trim_samples(sorted_array, args.milliseconds, args.replace)
        else:
            print('dry_run sorted_array: {} stickers'.format(len(sorted_array)))

    def trim_samples(self, items, milliseconds, replace_original):
        # remove _truncated, _prepended from all files

        LOG.info("milliseconds: {}".format(milliseconds))

        for count, item in enumerate(items):
            segment = AudioSegment.from_wav(item["filepath"])
            LOG.info("{}: length segment: {}".format(item["filename"], len(segment)))

            sliced = []
            full_length = len(segment)

            if full_length > abs(milliseconds):
                if milliseconds >= 0:
                    ending_trimmed_count = full_length - milliseconds
                    beginning_trimmed = segment[-ending_trimmed_count:]
                    sliced = beginning_trimmed
                else:
                    ending_trimmed_count = full_length + milliseconds
                    ending_trimmed = segment[:ending_trimmed_count]
                    sliced = ending_trimmed
            else:
                LOG.info("trim amount is greater than samples in audio file")

            LOG.info("length of trimmed segment: {}".format(len(sliced)))

            # 210330_12.WAV
            filename = item["filename"]
            # 210330_12
            filename_name = os.path.splitext(filename)[0]
            # 210330_12_prepended
            filename_name_sliced = filename_name + "_trimmed"
            # WAV
            filename_ext = os.path.splitext(filename)[1][1:]
            # 210330_12_trimmed.WAV
            truncated_filename = filename_name_sliced + "." + filename_ext

            # LOG.info("truncated: {}".format(truncated))
            # LOG.info("filename: {}".format(filename_name))
            # LOG.info("filename_name_sliced: {}".format(filename_name_sliced))
            # LOG.info("filename_plus: {}".format(filename_ext))

            head, tail = os.path.split(item["filepath"])
            # LOG.info("head, tail: {}, {}".format(head, tail))
            tail_noext = os.path.splitext(tail)[0]
            # LOG.info("tail_noext: {}".format(tail_noext))
            tail_ext = os.path.splitext(tail)[1]
            # LOG.info("tail_ext: {}".format(tail_ext))

            exportpath = os.path.join(head, truncated_filename)
            LOG.info("exportpath: {}".format(exportpath))
            sliced.export(exportpath, format="WAV")

        # if "_truncated" in tail:
        #     normalized = tail.replace("_truncated", "")
        #     LOG.info("normalized: {}".format(normalized))
        #     source = os.path.join(head, normalized)
        #     destination = os.path.join(head, tail)
        #     os.replace(destination, source)
        
        # if "_prepended" in tail:
        #     normalized = tail.replace("_prepended", "")
        #     LOG.info("normalized: {}".format(normalized))
        #     source = os.path.join(head, normalized)
        #     destination = os.path.join(head, tail)
        #     os.replace(destination, source)


# brother_ql --model QL-800 -b pyusb -p usb://0x04f9:0x209b print --label 62 --rotate 90 /Users/michael/Downloads/The\ White\ Rose\ Archive\ 5/Stickers/_freedom-pak1/LiveInFear.jpg

if __name__ == '__main__':
    Main()
