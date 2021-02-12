import boto3
from botocore.client import ClientError


'''Create Security Group, EC2 instance associated with Elastic IP address 
and connected to domain in Route53.'''

ec2 = boto3.client('ec2')
security_group_name = 'linux-web-server-security-group'

print(f'Create security group {security_group_name}: ', end='')
vpc_id = 'vpc-262faa4c'
try:
    security_group = ec2.create_security_group(
        Description=security_group_name,
        GroupName=security_group_name,
        VpcId=vpc_id
    )
    print('ok')

    print('Adding ingress rules: ', end='')
    sg_ingress_rules = ec2.authorize_security_group_ingress(
        GroupName=security_group_name,
        IpPermissions=[
            {'FromPort': 80,
             'IpProtocol': 'tcp',
             'ToPort': 80,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'FromPort': 443,
             'IpProtocol': 'tcp',
             'ToPort': 443,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
            {'FromPort': 22,
             'IpProtocol': 'tcp',
             'ToPort': 22,
             'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
        ]
    )
    print('ok')
except ClientError as e:
    error = e.response['Error']
    if error['Code'] == 'InvalidGroup.Duplicate':
        print(f'security group already exists.')


print('Creating key pair: ', end='')
keypair_name = 'linux-server-keypair'
try:
    key_pair = ec2.create_key_pair(
        KeyName=keypair_name
    )
    print('ok')

    with open(f'{keypair_name}.pem', 'w+') as credentials:
        credentials.write(key_pair['KeyMaterial'])
except ClientError as e:
    error = e.response['Error']
    print(error['Message'])


server_name = 'linux-server'
amazon_linux_2_ami = 'ami-0a6dc7529cd559185'
user_data = '''#!/bin/bash
sudo yum update -y
sudo yum install httpd -y
sudo systemctl start httpd
'''

print('Running instance..')
instance = ec2.run_instances(
    BlockDeviceMappings=[
        {
            'DeviceName': '/dev/xvda',
            'Ebs': {
                'DeleteOnTermination': True,
                'VolumeSize': 8,
                'VolumeType': 'gp2'
            }
        }
    ],
    ImageId=amazon_linux_2_ami,
    InstanceType='t2.micro',
    KeyName=keypair_name,
    MaxCount=1,
    MinCount=1,
    Monitoring={'Enabled': False},
    SecurityGroups=[security_group_name],
    UserData=user_data,
    TagSpecifications=[
        {
            'ResourceType': 'instance',
            'Tags': [
                {
                    'Key': 'Name',
                    'Value': server_name
                }
            ]
        }
    ]
)

instance_id = instance['Instances'][0]['InstanceId']

print('Instance status: ', end='')
instance_running_waiter = ec2.get_waiter(waiter_name='instance_running')
instance_running_waiter.wait(InstanceIds=[instance_id])
print('running')


print('Allocating and associating an Elastic IP: ', end='')
allocate_elastic_ip = ec2.allocate_address(Domain='vpc')
associate_elastic_ip = ec2.associate_address(
    AllocationId=allocate_elastic_ip['AllocationId'],
    InstanceId=instance_id
)
print('ok')


route53 = boto3.client('route53')
hosted_zone_id = ''                                     # enter hosted zone id
elastic_ip_address = allocate_elastic_ip['PublicIp']
new_record_name = ''                                    # enter Route53 new record name

print('Redirecting instance address to Route53 hosted zone: ', end='')
try:
    associate_new_record = route53.change_resource_record_sets(
        HostedZoneId=hosted_zone_id,
        ChangeBatch={
            'Comment': f'Add {new_record_name}',
            'Changes': [
                {
                    'Action': 'CREATE',
                    'ResourceRecordSet': {
                        'Name': new_record_name,
                        'Type': 'A',
                        'TTL': 300,
                        'ResourceRecords': [{'Value': elastic_ip_address}]
                    }
                }
            ]
        }
    )
    print('ok')
    print(f'Instance available at {new_record_name}')
except ClientError as e:
    error = e.response['Error']
    print(error['Message'])
