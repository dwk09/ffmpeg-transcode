#!/bin/python3
import argparse
import os
import string
import subprocess
import sys

FFMPEG_PATH = "/bin/ffmpeg"

DEFAULT_CRF = "19"
DEFAULT_EXT = "mkv"
DEFAULT_LANG = "eng"

X264_PRESET = "slow"

def detect_line_breaks(s):
    DOS = "\r\n"
    UNIX = "\n"
    MACOS = "\r"

    if DOS in s:
        return DOS
    elif MACOS in s:
        return MACOS
    return UNIX
    
def get_stream_info(s):
    # This is a bunch of magic bs and I need to figure out a better way to find what we're looking
    # for that's not as likely to randomly break when ffmpeg updates
    ss = s.split(":")[1].split("(")
    ss[1] = ss[1][:-1]
    codec = s.split(":")[3].split(",")[0]
    return ss[0].strip(), ss[1].strip(), codec.strip()

def get_streams(file):
    ffmpeg = subprocess.Popen([FFMPEG_PATH, "-i", file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = ffmpeg.communicate()
    output = err.decode()
    output = output.split(detect_line_breaks(output))
    streams = [o for o in output if "Stream" in o]
    info = {"Audio": [], "Video": [], "Subtitle": [], "Other": []}
    for s in streams:
        stream = {}
        sid, lang, codec = get_stream_info(s)
        stream["id"] = sid
        stream["lang"] = lang
        stream["codec"] = codec
        if "Video" in s:
            stream["type"] = "Video"
        elif "Audio" in s:
            stream["type"] = "Audio"
        elif "Subtitle" in s:
            stream["type"] = "Subtitle"
        else:
            stream["type"] = "UNKNOWN"
        info[stream["type"]].append(stream)
    return info

def get_stream_id_for_language(streams, lang):
    for s in streams:
        if s["lang"] == lang:
            return s["id"]
    return None

def transcode(file, streams, args):
    cmd = [FFMPEG_PATH]
    quality = args["quality"]

    # Fumble about with subtitles
    sub_stream = get_stream_id_for_language(streams["Subtitle"], args["sublang"])
    subs = not sub_stream is None and (args["forced_subs"] or args["all_subs"])
    forced_subs = subs and args["forced_subs"] and not args["all_subs"]
    if (subs or forced_subs) and sub_stream is None:
        print("Cannot find subtitles for {}".format(args["sublang"]))
        print("Available subtitles {}".format(streams["Subtitle"]))
        return

    # Find the audio stream we want
    audio_stream = get_stream_id_for_language(streams["Audio"], args["lang"])
    if not audio_stream:
        print("Cannot find audio stream for langauge {}".format(args["lang"]))
        print("Available audio streams {}".format(streams["Audio"]))
        return

    # Forced subtitles (generally foreign languge audio on mostly single-language movies)
    if forced_subs:
        cmd.extend(["-forced_subs_only", "1"])

    # Input file
    cmd.extend(["-i", file])

    # Deinterlace
    if args["deinterlace"]:
        cmd.extend(["-vf", "yadif"])

    # Map input video and audio streams to destination
    cmd.extend(["-map", "0:{}".format(streams["Video"][0]["id"])])
    cmd.extend(["-map", "0:{}".format(audio_stream)])

    # Burn in subtitles, if wanted
    if subs:
        cmd.extend(["-filter_complex", "[0:v:0][0:{}]overlay".format(sub_stream)])

    # Video transcode
    cmd.extend(["-c:v", "libx264", "-crf", quality, "-preset", X264_PRESET])

    # Audio copy
    cmd.extend(["-c:a:{}".format(audio_stream), "copy"])

    filename, extension = os.path.splitext(file)
    cmd.append("{}.mp4".format(filename))

    print("Using audio codec {}".format(audio_stream))

    subprocess.call(cmd)

def create_args():
    parser = argparse.ArgumentParser(prog='transcode', description='Invoke ffmpeg to transcode videos')
    parser.add_argument('-a', '--all_subs', action='store_true', default=False)
    parser.add_argument('-d', '--directory', action='store_true', default=False)
    parser.add_argument('-e', '--ext', default=DEFAULT_EXT)
    parser.add_argument('-f', '--forced_subs', action='store_true', default=False)
    parser.add_argument('-i', '--deinterlace', action="store_true", default=False)
    parser.add_argument('-l', '--lang', default=DEFAULT_LANG)
    parser.add_argument('-q', '--quality', default=DEFAULT_CRF)
    parser.add_argument('-s', '--sublang', default=DEFAULT_LANG)
    parser.add_argument('--source', default=None)
    parser.add_argument('path', nargs='?', default='.')

    return vars(parser.parse_args())

def get_files(args):
    if args["source"]:
        return [args["source"]]

    return [os.path.join(args["path"], file) 
        for file in os.listdir(args["path"]) if file.endswith(".{}".format(args["ext"]))]

def main():
    args = create_args()
    for file in get_files(args):
        print(file)
        streams = get_streams(file)
        transcode(file, streams, args)

if __name__ == "__main__":
    main()
