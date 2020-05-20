import os
import boto3
import json

SKIP_SHUTDOWN_TAG = 'skipshutdown'

# Main
def lambda_handler(event, context):

    ec2Client = boto3.client('ec2')
    regions = [region['RegionName'] for region in ec2Client.describe_regions()['Regions']]
    #regions = ['eu-north-1']

    for regionName in regions:
        print('~~~~~~Region:{0}~~~~~~'.format(regionName))
        ec2Client = boto3.client('ec2', region_name=regionName)
        response = ec2Client.describe_instances(MaxResults=1000)

        instancesToStop = []
        for reservations in response['Reservations']:
            instanceId = ''
            instanceName = ''
            state = ''

            for instanceDetails in reservations['Instances']:
                instanceId = instanceDetails['InstanceId']

                # ignore spot and scheduled instances
                if 'InstanceLifecycle' in instanceDetails.keys():
                    continue

                state = instanceDetails['State']
                if state['Name'] == 'running':
                    instancesToStop.append(instanceId)
                    
                if 'Tags' in instanceDetails:
                    for tag in instanceDetails['Tags']:
                        if tag['Key'] == 'Name':
                            instanceName = tag['Value'] if tag['Value'] != '' else 'Instance with no name'

                        if tag['Key'].lower() == SKIP_SHUTDOWN_TAG.lower():
                            SkipShutdown = True if tag['Value'].lower() == 'true' else False
                            if SkipShutdown and state['Name'].lower() == 'running':
                                print ('Instance "{0}" with skip shutdown tag -> ignoring'.format(instanceName))
                                instancesToStop.remove(instanceId)
                
        if (len (instancesToStop) <= 0):
            print ('No Instances found to stop')
        else:
            res = ec2Client.stop_instances(
                InstanceIds = instancesToStop)

        print ('~~~~~~Region {0} - End Of Day - Stopped {1} instnaces~~~~~~'.format(regionName, len(instancesToStop)))

        rdsClient = boto3.client('rds', region_name=regionName)
        print ('### Region {0} - Stoping RDS Clusters...'.format(regionName))
        rdsClusters = rdsClient.describe_db_clusters()
        print (rdsClusters)
        
        for cluster in rdsClusters["DBClusters"]:
            stopCluster = True
            tagsList = rdsClient.list_tags_for_resource(
                ResourceName=cluster["DBClusterArn"])

            for tag in tagsList["TagList"]:
                print (tag)
                if tag['Key'].lower() == SKIP_SHUTDOWN_TAG.lower():
                            SkipShutdown = True if tag['Value'].lower() == 'true' else False
                            if SkipShutdown and cluster['Status'] == 'available':
                                print ('DB cluster "{0}" with skip shutdown tag -> ignoring'.format(cluster["DBClusterIdentifier"]))
                                stopCluster = False
            
            if stopCluster and cluster['Status'] == 'available':                    
                print ('Shutting down cluster {0}'.format(cluster["DBClusterIdentifier"]))
                
                response = rdsClient.stop_db_cluster(
                    DBClusterIdentifier=cluster["DBClusterIdentifier"])
