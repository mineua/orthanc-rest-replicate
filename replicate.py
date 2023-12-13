#!/usr/bin/env python

# Orthanc - A Lightweight, RESTful DICOM Store
# Copyright (C) 2012-2016 Sebastien Jodogne, Medical Physics
# Department, University Hospital of Liege, Belgium
# Copyright (C) 2017-2023 Osimis S.A., Belgium
# Copyright (C) 2021-2023 Sebastien Jodogne, ICTEAM UCLouvain, Belgium
#
# This program is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import argparse
import signal
import requests
import json
import os
import sys

from time import sleep
from threading import Thread
from requests.auth import HTTPBasicAuth
from alive_progress import alive_bar, alive_it

parser = argparse.ArgumentParser(description = 'Script to copy the content of one Orthanc server to another Orthanc server through their REST API.',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('--save',
                    default = 'studies.list',
                    help = 'save file')
parser.add_argument('--username',
                    default = 'orthanc',
                    help = 'username to the REST API')
parser.add_argument('--password',
                    default = 'orthanc',
                    help = 'password to the REST API')
parser.add_argument('--threads', help = 'number of threads to transfer Instances',
                    default = 2)
parser.add_argument('--ignore-errors', help = 'do not stop if encountering any errors',
                    action = 'store_true')
parser.add_argument('source', metavar = 'Source URL',
                    help = 'URL of the server that will be the Source')
parser.add_argument('target', metavar = 'Target URL',
                    help = 'URL of the server that will be the Target')

args = parser.parse_args()

source = dict()
studies_list = list()
threads = {"status": "none", "list": []}

def sizeof_fmt(num, suffix="B"):
    for unit in ("", "K", "M", "G", "T", "P", "E", "Z"):
        if abs(num) < 1000.0:
            return f"{num:3.1f} {unit}{suffix}"
        num /= 1000.0
    return f"{num:.1f} Y{suffix}"

# Saving state to a file to continue later
def save():
    global source, threads

    if threads["status"] != "none":
        print("\nPlease wait, finishing upload Instances...")
        threads["status"] = "stop"

    if source:
        print("Creating save...")
        with open(args.save, "w") as fp:
            json.dump(source, fp)

    exit()

def save_signum(signum, frame):
    save()

# Save the state when the script is interrupted
signal.signal(signal.SIGTSTP, save_signum)

def info():
    global source

    info = {
        "studies": {
            "total": 0
        },
        "instances": {
            "total": 0,
            "new": 0,
            "skipped": 0,
            "completed": 0
        },
        "bytes": {
            "total": 0,
            "new": 0,
            "skipped": 0,
            "completed": 0
        }
    }

    for study in source.keys():
        info["studies"]["total"] += 1

        for instance in source[study].keys():
            info["instances"]["total"] += 1
            info["bytes"]["total"] += source[study][instance]["size"]

            info["instances"][source[study][instance]["status"]] += 1
            info["bytes"][source[study][instance]["status"]] += source[study][instance]["size"]

    return info

def next_study():
    global studies_list

    try:
        return studies_list.pop(0)
    except IndexError:
        return False

def post(auth, bar):
    global source
    study = next_study()

    while study:
        bar.text(study)

        for instance in source[study].keys():
            # Skip Instances that we don't need to upload
            if source[study][instance]["status"] != "new":
                continue

            try:
                dicom = requests.get('%s/instances/%s/file' % (args.source, instance), auth = auth)
                r = requests.post('%s/instances' % args.target, auth = auth, data = dicom.content)

                r.raise_for_status()
                source[study][instance]["status"] = "completed"
            except:
                if args.ignore_errors:
                    print("Unable to upload Instances for %s" % study)
                else:
                    raise Exception("Unable to upload Instances for %s" % study)

            bar(source[study][instance]["size"])
            if threads["status"] == "stop": break;

        if threads["status"] == "stop": break;
        study = next_study()

def main():
    global source, studies_list

    if os.path.isfile(args.save):
        print("We found save file, restarting... ", end="")

        fp = open(args.save, "r")
        source = json.load(fp)
        fp.close()

        print("%d Studies loaded." % len(source.keys()))

        print("We need to check the last one in case it's incomplete.\n")
        source[list(source.keys())[-1]] = dict()

    print("Getting Instances from the Source... ", end="")

    # Searching for Studies on Source

    auth = HTTPBasicAuth(args.username, args.password)
    r = requests.get('%s/studies' % args.source, auth = auth)

    try:
        r.raise_for_status()
    except:
        raise Exception("Unable to get Studies from the Source at: " + args.source)

    studies = r.json()

    if (len(studies) > 1):
        print ("found %d Studies." % len(studies))
    else:
        raise Exception("Unable to find any Studies at the Source!")

    # Get Instances from Source

    with alive_bar(len(studies), theme="classic", spinner="dots") as bar:
        for study in studies:
            if study in source and len(source[study].keys()) > 0:
                bar.text(study)
                bar()

                continue

            r = requests.get('%s/studies/%s/instances' % (args.source, study), auth = auth)

            try:
                r.raise_for_status()
                instances = r.json()
            except:
                if args.ignore_errors:
                    print("Unable to get Instances for %s" % study)
                    instances = []
                else:
                    raise Exception("Unable to get Instances for %s" % study)

            if len(instances) > 0:
                if not study in source:
                    source[study] = dict()

                for instance in instances:
                    if not instance["ID"] in source[study]:
                        source[study][instance["ID"]] = {
                          "size": instance["FileSize"],
                          "status": "new"
                        }

            bar.text(study)
            bar()

    print("\nChecking Instances on the Target... ", end="")

    # Searching for Studies on Target

    auth = HTTPBasicAuth(args.username, args.password)
    r = requests.get('%s/studies' % args.target, auth = auth)

    try:
        r.raise_for_status()
    except:
        raise Exception("Unable to get Studies from the Target at: " + args.source)

    target = r.json()

    if (len(studies) > 1):
        print ("found %d Studies." % len(target))
    else:
        print ("and it's empty!")

    # Get Instances from Target

    with alive_bar(len(target), theme="classic", spinner="dots") as bar:
        for study in target:
            r = requests.get('%s/studies/%s/instances' % (args.target, study), auth = auth)

            try:
                r.raise_for_status()
                instances = r.json()
            except:
                instances = []

            for instance in instances:
                if instance["ID"] in source[study] and source[study][instance["ID"]]["status"] != "completed":
                    if instance["FileSize"] == source[study][instance["ID"]]["size"]:
                        source[study][instance["ID"]]["status"] = "skipped"

            bar.text(study)
            bar()

    # Get info about the Source
    source_info = info()

    print("\nFound %s in %d Instances in %d Studies on the Source." % (sizeof_fmt(source_info["bytes"]["total"]), source_info["instances"]["total"], source_info["studies"]["total"]))

    if source_info["instances"]["completed"]:
        print("We've already transferred %s in %d Instances, so we'll skip them." % (sizeof_fmt(source_info["bytes"]["completed"]), source_info["instances"]["completed"]))

    if source_info["instances"]["skipped"]:
        if source_info["instances"]["completed"]: suffix = " too"
        else: suffix = ""

        print("We've found %s in %d Instances already on the Target, so we'll skip them%s." % (sizeof_fmt(source_info["bytes"]["skipped"]), source_info["instances"]["skipped"], suffix))

    print("Creating save...")
    with open(args.save, "w") as fp:
        json.dump(source, fp)

    # Transfer Instances to Target

    print("\nStarting to transfer %s in %d Instances to the Target..." % (sizeof_fmt(source_info["bytes"]["new"]), source_info["instances"]["new"]))
    studies_list = list(source.keys())

    with alive_bar(source_info["bytes"]["new"], theme="classic", spinner="dots", unit="B", scale="SI", precision=1, refresh_secs=0.05) as bar:
        threads["status"] = "start"

        for i in range(int(args.threads)):
            # Creating post thread
            threads["list"].append(Thread(target=post, args=(auth, bar, )))

            # Starting thread
            threads["list"][-1].start()

        for thread in threads["list"]:
            # Wait until all threads is completely executed
            thread.join()

    print("Creating save...")
    with open(args.save, "w") as fp:
        json.dump(source, fp)

try:
    main()
except KeyboardInterrupt:
    save()
