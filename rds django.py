import boto3
import random


'''Django instance with RDS DB Postgres connected'''

random_id = str(random.randrange(1000))

'''Parameters'''
hosted_zone_id = ''        # enter hosted zone
domain = ''                # enter domain name
aws_region = ''            # AWS Frankfurt region
vpc_id = ''                # Your VPC id
ami_id = ''                # AWS Linux 2 in Frankfurt ami

db_instance_name = 'psql-'+random_id
db_name = 'postgres'
db_engine_name = 'postgres'
db_master_user = 'psqladmin'
db_master_pass = 'psqlpass'
db_instance_type = 'db.t2.micro'
db_size = 20
db_port = 5432
db_vpc_sec_group_name = 'db-sg-'+random_id
db_vpc_sec_group_desc = 'Database ports'

dj_user_name = 'djuser'
dj_user_pass = 'djpassword'
dj_user_email = 'sample@email.com'

ec2 = boto3.client('ec2', region_name=aws_region)
rds = boto3.client('rds', region_name=aws_region)

record_name = 'django'+random_id+'.'+domain
key_pair_name = 'django-python-key-pair-'+random_id
sec_group_name = 'django-python-sg-'+random_id
sec_group_desc = 'Django server ports'
server_name = 'Django-Server-Python-'+random_id
django_port = 8000
'''Parameters'''


print('Creating key pair')
key_pair = ec2.create_key_pair(KeyName=key_pair_name)
KeyPairOut = str(key_pair['KeyMaterial'])
outfile = open(key_pair_name+'.pem', 'w')
outfile.write(KeyPairOut)


print('Creating security groups')
sec_group = ec2.create_security_group(GroupName=sec_group_name,
                                      Description=sec_group_desc,
                                      VpcId=vpc_id)
sec_group_id = sec_group['GroupId']
sec_group_rules = ec2.authorize_security_group_ingress(
    GroupId=sec_group_id,
    IpPermissions=[
        {'IpProtocol': 'tcp',
         'FromPort': django_port,
         'ToPort': django_port,
         'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
        {'IpProtocol': 'tcp',
         'FromPort': 22,
         'ToPort': 22,
         'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
    ]
)

db_vpc_sec_group = ec2.create_security_group(GroupName=db_vpc_sec_group_name,
                                             Description=db_vpc_sec_group_desc,
                                             VpcId=vpc_id)
db_vpc_sec_group_id = db_vpc_sec_group['GroupId']
db_vpc_sec_group_rules = ec2.authorize_security_group_ingress(
    GroupId=db_vpc_sec_group_id,
    IpPermissions=[
        {'IpProtocol': 'tcp',
         'FromPort': db_port,
         'ToPort': db_port,
         'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
    ]
)


print('Creating RDS PostgresDB')
db_instance_response = rds.create_db_instance(
                            DBInstanceIdentifier=db_instance_name,
                            DBInstanceClass=db_instance_type,
                            DBName=db_name,
                            Engine=db_engine_name,
                            AllocatedStorage=db_size,
                            Port=db_port,
                            PubliclyAccessible=True,
                            MultiAZ=False,
                            MasterUsername=db_master_user,
                            MasterUserPassword=db_master_pass,
                            VpcSecurityGroupIds=[db_vpc_sec_group_id],
                            Tags=[{'Key': 'Name', 'Value': db_instance_name}])


# check Create DB instance returned successfully
if db_instance_response['ResponseMetadata']['HTTPStatusCode'] == 200:
    print("Creating new database: %s" % db_instance_name)
else:
    print("The new database could not be created")

waiter = rds.get_waiter('db_instance_available')
waiter.wait(DBInstanceIdentifier=db_instance_response['DBInstance']['DBInstanceIdentifier'])
print('The database is ready')

db_instances = rds.describe_db_instances(DBInstanceIdentifier=db_instance_name)
db_endpoint = db_instances.get('DBInstances')[0].get('Endpoint').get('Address')


print('Creating Django instance')
user_data = '''#!/bin/bash
sudo yum update -y
sudo yum install python3 python-pip -y
sudo pip install -U pip
sudo yum install telnet -y
cd /home/ec2-user
python3 -m venv djangoenv
source djangoenv/bin/activate
pip install Django
pip install psycopg2-binary
django-admin.py startproject djangoapp
cd djangoapp
sudo sed -i "s|ALLOWED_HOSTS = \[]|ALLOWED_HOSTS = \['*']|g" djangoapp/settings.py
sudo sed -i "s|'NAME': BASE_DIR / 'db.sqlite3',||g" djangoapp/settings.py
sudo sed -i "s|'ENGINE': 'django.db.backends.sqlite3',|'ENGINE': 'django.db.backends.postgresql_psycopg2', 'NAME': '{}', 'USER': '{}', 'PASSWORD': '{}', 'HOST': '{}', 'PORT': '{}'|g" djangoapp/settings.py
export DJANGO_SUPERUSER_USERNAME={}
export DJANGO_SUPERUSER_PASSWORD={}
export DJANGO_SUPERUSER_EMAIL={}
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser --noinput
python manage.py runserver 0.0.0.0:8000'''.format(db_name, db_master_user, db_master_pass, db_endpoint, db_port, dj_user_name, dj_user_pass, dj_user_email)

servers = ec2.run_instances(
    MaxCount=1,
    MinCount=1,
    BlockDeviceMappings=[
        {
            'DeviceName': '/dev/xvda',
            'Ebs': {
                'DeleteOnTermination': True,
                'VolumeSize': 8,
                'VolumeType': 'gp2'
            },
        },
    ],
    ImageId=ami_id,
    InstanceType='t3.micro',
    KeyName=key_pair_name,
    SecurityGroupIds=[
        sec_group_id,
    ],
    UserData=user_data
)

django_server = servers['Instances'][0]
django_server_id = django_server['InstanceId']

waiter = ec2.get_waiter('instance_status_ok')
waiter.wait(InstanceIds=[django_server_id])

ec2.create_tags(Resources=[django_server_id], Tags=[{"Key": "Name", "Value": server_name}])
print('Django server has been created')


print('Creating and associating elastic IP address', end='')
elastic_ip_allocation = ec2.allocate_address(Domain='vpc')
ec2.associate_address(AllocationId=elastic_ip_allocation['AllocationId'],
                      InstanceId=django_server['InstanceId'])
print('ok')

# user-data log można sprawdzić w pliku: /var/log/cloud-init-output.log


r53 = boto3.client('route53')
public_ip = ec2.describe_instances(InstanceIds=[django_server['InstanceId']])['Reservations'][0]['Instances'][0]['PublicIpAddress']

print('Creating Route 53 new record associated with instance public IP')
r53.change_resource_record_sets(
    HostedZoneId=hosted_zone_id,
    ChangeBatch={
        'Comment': 'add A record',
        'Changes': [
            {
                'Action': 'UPSERT',
                'ResourceRecordSet': {
                    'Name': record_name,
                    'Type': 'A',
                    'TTL': 300,
                    'ResourceRecords': [{'Value': public_ip}]
                }
            }
        ]
    }
)

print('Url: http://'+record_name+':8000/')
print('Url: http://'+record_name+':8000/admin')
