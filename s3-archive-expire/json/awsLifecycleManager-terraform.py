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

# to get around tzinfo in datatime.datetime type
def notSerial(time):
    #print '************** heres the time ***********'
    #print time
    from_zone = tz.gettz('UTC')
    to_zone = tz.gettz('America/Los_Angeles')
    #zuluGone = datetime.strptime(str(time), '%Y-%m-%d %H:%M:%S.%f+00:00')
    #zuluGone = datetime.strptime(str(time), '%Y-%m-%d %H:%M:%S.%d+00:00')
    #zuluGone = datetime.strptime(str(time), '%Y-%m-%d %H:%M:%S+00:00')
    zuluGone = datetime.strptime(str(time), '%Y-%m-%d %H:%M:%S+00:00')
    zuluGone = zuluGone.replace(tzinfo=from_zone)
    la_datetime = str(zuluGone.astimezone(to_zone) )
    return la_datetime

def buildTransitionOnly(policy, transformDays,bucketName,index, prefix):
    policy['Rules'].append(
         {
             'ID': bucketName + 'Rule' + str(index),
             'Prefix': prefix,
             'Status': 'Enabled',
             'Transitions': [
                 {
                     'Days': transformDays,
                     'StorageClass': 'GLACIER'
                 },
             ],
             'NoncurrentVersionTransitions': [
                 {
                     'NoncurrentDays': transformDays,
                     'StorageClass': 'GLACIER'
                 },
             ],
             'AbortIncompleteMultipartUpload': {
                 'DaysAfterInitiation': 7
             }
         }
    )

    return(policy)

def buildExpirationOnly(policy, expireDays,bucketName,index, prefix):
    policy['Rules'].append(
         {
             'Expiration': {
                 'Days': expireDays,
             },
             'ID': bucketName + 'Rule' + str(index),
             'Prefix': prefix,
             'Status': 'Enabled',
             'NoncurrentVersionExpiration': {
                 'NoncurrentDays': expireDays
             },
             'AbortIncompleteMultipartUpload': {
                 'DaysAfterInitiation': 7
             }
         }
    )

    return(policy)


def buildTransAndExpire(policy, transformDays,expireDays,bucketName,index, prefix):
    policy['Rules'].append(
         {
             'Expiration': {
                 'Days': expireDays,
             },
             'ID': bucketName + 'Rule' + str(index),
             'Prefix': prefix,
             'Status': 'Enabled',
             'Transitions': [
                 {
                     'Days': transformDays,
                     'StorageClass': 'GLACIER'
                 },
             ],
             'NoncurrentVersionTransitions': [
                 {
                     'NoncurrentDays': transformDays,
                     'StorageClass': 'GLACIER'
                 },
             ],
             'NoncurrentVersionExpiration': {
                 'NoncurrentDays': int(transformDays)*2
             },
             'AbortIncompleteMultipartUpload': {
                 'DaysAfterInitiation': 7
             }
         }
    )

    return(policy)

def folderFinder(aBucket):
    # get the 2-level folders
    aCommand = '/programming/shell/pythonHelper.bsh ' + aBucket
    
    strDirs = subprocess.Popen(aCommand, shell=True, stdout=subprocess.PIPE).stdout.read()
    sortedLevels = []
    for line in strDirs.splitlines():
        levelList = line.split()
        sortedLevels.append(levelList[0] + '/' + levelList[1] + '/')
    return(sortedLevels)

def buildLifecyclePolicy(theBucket,sortedLevels, transitionAnswer, daysToTransition, expirationAnswer, daysToExpiration):
    lifecyclePolicy = {'Rules' : [] }
    index = 1
    
    if transitionAnswer == 'Y' and expirationAnswer == 'Y':
        for prefix in sortedLevels:
            newLifecyclePolicy = buildTransAndExpire(lifecyclePolicy,int(daysToTransition),int(daysToExpiration),theBucket,index, prefix)
            index = index + 1
    if transitionAnswer == 'Y' and expirationAnswer == 'N':
        for prefix in sortedLevels:
            newLifecyclePolicy = buildTransitionOnly(lifecyclePolicy, int(daysToTransition),theBucket,index, prefix)
            index = index + 1
    if transitionAnswer == 'N' and expirationAnswer == 'Y':
        for prefix in sortedLevels:
            newLifecyclePolicy = buildExpirationOnly(lifecyclePolicy, int(daysToExpiration),theBucket,index, prefix)
            index = index + 1
    if transitionAnswer == 'N' and expirationAnswer == 'N':
        print "You have elected not to expire and not to transition"
        print "There is nothing for this program to do"
        exit(1)
    return(newLifecyclePolicy)

def buildTerraformHeader(bucketName):
    mySession = boto3.session.Session()
    myRegion = mySession.region_name
    header = '''
{{
    "provider" : {{
        "aws" : {{
            "region" : "{myRegion}"
        }}
    }},

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
    with open(bucketName + '.tf.json', 'a') as outfile:
        outfile.write(fmtBody)
    outfile.close()
    return()

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

def main():
    # The working code starts here
    print "You are using ", os.environ["AWS_PROFILE"]
    s3 = boto3.client('s3')
    buckets =  s3.list_buckets()
    bucketList = buckets['Buckets']
    for bucket in bucketList:
        print bucket['Name']
    
    theBucket = raw_input("What bucket do you want to change lifecycle parameters for? ")
    print " "
    print "WARNING: the amount of time required to find level two directorys is proportial to the total number of objects in a bucket"
    print "Please wait for the folder listing to show up"
    
    # gets the listing of folders
    sortedLevels = folderFinder(theBucket) 
    #nada = raw_input("This is just to pause")
    
    print "\n\n"
    print "************** Here is the list of 2-level-folders in ", theBucket, " **************"
    for element in  sortedLevels:
        print element
    
    
    transitionAnswer = 'N'
    transitionAnswer = raw_input("Do you want to transition them to more cost effective Glacier storage? (Y/N) ").upper()
    print type(transitionAnswer)
    daysToTransition = ' '
    if transitionAnswer == 'Y':
        daysToTransition = raw_input("How many day from the creation day of object until transition?  Enter an integer ")
    
    expirationAnswer = 'N'
    #this is a dummy value and is not used to build lifecycle 
    daysToExpiration = ' '
    expirationAnswer = raw_input("Do you want to set the expiration for the objects in the listed folders? (Y/N) ").upper()
    if expirationAnswer == 'Y':
        print "The number of days to expire should be greater than those to transition"
        imSure = 'N'
        print " "
        imSure =  raw_input("REMEMBER: Expirations is permanent. Do you wish to proceed? (Y/N) ").upper()
        if imSure == 'Y':
            daysToExpiration = raw_input("How many days after creation do you want to pass before deletion? Enter an integer ")
        else:
            expirationAnswer = 'N'
    
    if transitionAnswer == 'N' and expirationAnswer == 'N':
        print "You have elected not to expire and not to transition"
        print "There is nothing for this program to do"
        exit(1)
    newLifecyclePolicy = buildLifecyclePolicy(theBucket,sortedLevels, transitionAnswer, daysToTransition, expirationAnswer, daysToExpiration) 
    print "/n********* Here's the new lifecycle *********"
    print json.dumps(newLifecyclePolicy, indent=4)
    
    goAhead = 'N'
    goAhead = raw_input("Please review the above lifecycle: do you want to implement it? (Y/N) ").upper()
    if goAhead == 'Y':
       s3.put_bucket_lifecycle_configuration(Bucket=theBucket,LifecycleConfiguration=newLifecyclePolicy)
       print " "
       print "The lifecycle has been implemented: you can review it in the console"

if __name__ == '__main__':
    if len(sys.argv) < 2:
        buildTerraformHeader('mvenskybucketoregon')
        #buildTerraformBody('mvenskybucketoregon')
        index = 1
        buildTerraformBody('mvenskybucketoregon', 'level-1/level-2/', 'mvenskybucketoregon'+'Rule'+str(index), 'Y', 30, 'Y', 365)
        index = 2
        buildTerraformBody('mvenskybucketoregon', 'layer-one/layer-two/', 'mvenskybucketoregon'+'Rule'+str(index), 'Y', 30, 'N', 365)
        index = 3
        buildTerraformBody('mvenskybucketoregon', 'layer-one/layer-two/', 'mvenskybucketoregon'+'Rule'+str(index), 'N', 30, 'Y', 365)
        buildTerraformTrailer('mvenskybucketoregon')
        main()
    if len(sys.argv) != 6 and len(sys.argv) > 1:
        print "Usage: ", sys.argv[0], " bucketName transitionAnswer(Y/N) daysToTransition expirationAnswer(Y/N) daysToExpiration"
    if len(sys.argv) == 6:
    # at this point well assume terraform is being used
        sortedLevels = folderFinder(sys.argv[1])
        newLifecyclePolicy = buildLifecyclePolicy(sys.argv[1],sortedLevels, sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        print json.dumps(newLifecyclePolicy, indent=4, default=notSerial)
        s3 = boto3.client('s3')
        s3.put_bucket_lifecycle_configuration(Bucket=sys.argv[1],LifecycleConfiguration=newLifecyclePolicy)
