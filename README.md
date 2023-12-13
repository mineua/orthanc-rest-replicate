# orthanc-rest-replicate
Replicate an existing Orthanc instance to another using REST.
This Python script is based on the Replication.py script included with Orthanc.

## Introduction
Sometimes you need to transfer patient data from one Orthanc instance to another, but you don't have the ability to import individual DICOM files, or you just want to automate the transfer process without stopping the main Orthanc instance.

I ran into this problem when I had to migrate 3.3 TB of data from an old Orthanc server to a new one, while switching to a different database engine for Orthanc (from SQLite to MySQL). We also use DICOM compression, which makes things more difficult.

The whole process took me about a week, REST-based replication allowed data to be transferred without stopping the main server and it could continue to accept data about new patients. Even when the process was interrupted, I could quickly resume replication thanks to the feature of scanning the database and saving replication progress.

## How to use it
Run the `replicate.py` script in Python version 3.7 or higher:
```
python replicate.py http://source:8042 http://target:8042 --username=orthanc --password=orthanc
```
A complete description of all possible keys can be seen using the command:
```
$ python replicate.py -h
usage: replicate.py [-h] [--save SAVE] [--username USERNAME]
                    [--password PASSWORD] [--threads THREADS]
                    [--ignore-errors]
                    Source URL Target URL

Script to copy the content of one Orthanc server to another Orthanc server
through their REST API.

positional arguments:
  Source URL           URL of the server that will be the Source
  Target URL           URL of the server that will be the Target

optional arguments:
  -h, --help           show this help message and exit
  --save SAVE          save file (default: studies.list)
  --username USERNAME  username to the REST API (default: orthanc)
  --password PASSWORD  password to the REST API (default: orthanc)
  --threads THREADS    number of threads to transfer Instances (default: 2)
  --ignore-errors      do not stop if encountering any errors (default: False)
```
Please note: this script uses the alive-progress library, which must be installed via pip.

## Example script output
```
$ python replicate.py http://source:8042 http://target:8042 --username=orthanc --password=orthanc --threads=4 --ignore-errors
We found save file, restarting... 13978 Studies loaded.
We need to check the last one in case it's incomplete.

Getting Instances from the Source... found 14019 Studies.
[========================================] 14019/14019 [100%] in 5.3s (2693.32/s)

Checking Instances on the Target... found 13967 Studies.
[========================================] 13967/13967 [100%] in 12:51.1 (18.11/s)

Found 3.3 TB in 140446 Instances in 14019 Studies on the Source.
We've already transferred 4.1 GB in 139 Instances, so we'll skip them.
We've found 3.3 TB in 139743 Instances already on the Target, so we'll skip them too.
Creating save...

Starting to transfer 9.9 GB in 564 Instances to the Target...
on 2920707982: Unable to upload Instances for fd3b18d7-f488328d-14cdceda-ce89b3ec-c8e54297
on 2983714512: Unable to upload Instances for 109ff0be-9ce84012-99f2c280-e3645ac5-b543e5ac
on 2991591716: Unable to upload Instances for 109ff0be-9ce84012-99f2c280-e3645ac5-b543e5ac
on 2993953168: Unable to upload Instances for 3d4913a4-4b4acec2-f48f9f77-0faf990e-22b8fc5c
on 3053959384: Unable to upload Instances for 2c5d8108-e76de86f-a447f86c-3ea75854-df3b2b66
on 3059026526: Unable to upload Instances for 3279671f-cc46ddf9-ab387e18-6828b65a-293f7741
on 3061387992: Unable to upload Instances for e99b1ea4-a6e06f4a-9cc4c2fb-7096d858-ac4c7d90
on 3061527810: Unable to upload Instances for 46ab26f2-d77a595e-1ff4ccbb-3b2be878-5759e896
on 3181536670: Unable to upload Instances for 005939d5-d38ab117-0ef43409-e69c99df-be2cb33b
on 3250543298: Unable to upload Instances for 24bebab1-ad8939c5-657e8bbb-92254e89-44611554
on 3310549530: Unable to upload Instances for 975f3943-db11c768-a7a92e9d-b9f73d96-d96f0511
[========================================] 9.88GB/9.88GB [100%] in 43:05.3 (3.82MB/s)
Creating save...
```
As you can see, several errors occurred during data transfer; if you specify the `--ignore-errors` key, the script will skip them. You can run the script again later to try to trasfer them again.
