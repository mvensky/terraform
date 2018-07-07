#!/usr/bin/env python
# This script works great; remember to set AWS_PROFILE before use ; the use of the pythonHelper.bsh
# script gets you around the issue of 1000 object limit for boto3's list_object
#
# This script will instead of doing the actual put_bucket_lifecycle_configuration will build the tf.json files for terraform:w

from boto.s3.lifecycle import Lifecycle, Transitions, Rule
import os
import sys
from boto.s3.connection import S3Connection
import boto3
import json
from datetime import datetime
from dateutil import tz
import time
import re
import subprocess

indent = 4

def folderFinder(aBucket):
    # get the 2-level folders
    aCommand = '/programming/shell/pythonHelper.bsh ' + aBucket
    
    strDirs = subprocess.Popen(aCommand, shell=True, stdout=subprocess.PIPE).stdout.read()
    sortedLevels = []
    for line in strDirs.splitlines():
        levelList = line.split()
        sortedLevels.append(levelList[0] + '/' + levelList[1] + '/')
    return(sortedLevels)

def buildTerraformHeader(bucketName):
    mySession = boto3.session.Session()
    myRegion = mySession.region_name

    profile = '''
{{
    "provider" : {{
        "aws" : {{
            "region" : "{myRegion}"
        }}
    }},
}}
    '''

    with open('providerOnly.tf.json' , 'w') as outfile:
        outfile.write(profile.format(myRegion=myRegion) )
    outfile.close()

    header = '''
{{

    "resource" : {{
        "aws_s3_bucket" : {{
            "{bucketName}" : {{
                "bucket" : "{bucketName}",
    '''

    print(header.format(bucketName=bucketName, myRegion=myRegion) )
    fmtHeader = header.format(bucketName=bucketName, myRegion=myRegion)
    with open(bucketName + '.tf.json', 'w') as outfile:
        outfile.write(fmtHeader)
    outfile.close()
    return()

def buildTerraformBody(bucketName, prefix, ruleName, transition, transitionDays, expiration, expirationDays):
    if transition == 'Y' and expiration == 'Y':
        lifecycleRule = '''
                "lifecycle_rule" : {{
                    "id" : "{ruleName}",
                     "enabled" : true,
                    "prefix" : "{prefix}",
                    "transition" : {{
                        "days" : {transitionDays},
                        "storage_class" : "GLACIER"
                    }},
                    "expiration" : {{
                        "days" : {expirationDays}
                    }}
                }},
        '''
    elif transition == 'Y' and expiration == 'N':
        lifecycleRule = '''
                "lifecycle_rule" : {{
                    "id" : "{ruleName}",
                     "enabled" : true,
                    "prefix" : "{prefix}",
                    "transition" : {{
                        "days" : {transitionDays},
                        "storage_class" : "GLACIER"
                    }},
                }},
        '''
    elif transition == 'N' and expiration == 'Y':
        lifecycleRule = '''
                "lifecycle_rule" : {{
                    "id" : "{ruleName}",
                     "enabled" : true,
                    "prefix" : "{prefix}",
                    "expiration" : {{
                        "days" : {expirationDays}
                    }}
                }},
        '''

    print(lifecycleRule.format(ruleName=ruleName, prefix=prefix, transitionDays=transitionDays, expirationDays=expirationDays) )
    fmtBody = lifecycleRule.format(ruleName=ruleName, prefix=prefix, transitionDays=transitionDays, expirationDays=expirationDays) 
    return(fmtBody)

def buildTerraformTrailer(bucketName):
    trailer = '''
            }}
        }}
    }}
}}
    '''

    print(trailer.format() )
    fmtTrailer = trailer.format()
    with open(bucketName + '.tf.json', 'a') as outfile:
        outfile.write(fmtTrailer)
    outfile.close()
    return()

if __name__ == '__main__':
    if len(sys.argv) != 6:
        print "Usage: ", sys.argv[0], " bucketName transitionAnswer(Y/N) daysToTransition expirationAnswer(Y/N) daysToExpiration"
    elif len(sys.argv) == 6:
    # at this point well assume terraform is being used
        if sys.argv[2] == 'N' and sys.argv[4] == 'N':
            print "Usage: ", sys.argv[0], " bucketName transitionAnswer(Y/N) daysToTransition expirationAnswer(Y/N) daysToExpiration"
            exit(1)
        else:
            sortedLevels = folderFinder(sys.argv[1])
            buildTerraformHeader(sys.argv[1])
            index = 1
            outfile = open(sys.argv[1] + '.tf.json', 'a')
            for twoLevels in sortedLevels:
                fmtBody = buildTerraformBody(sys.argv[1], twoLevels, sys.argv[1]+'Rule'+str(index), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
                outfile.write(fmtBody)
                index = index+1
            outfile.close()
            buildTerraformTrailer(sys.argv[1])
