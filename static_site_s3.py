import boto3
from botocore.client import ClientError
import json
import zipfile
import mimetypes


'''Create a static page in S3'''

s3 = boto3.client('s3')
bucket_name = ''   # enter bucket name


print('Create bucket S3 in the Frankfurt region (with public access) ', bucket_name)
try:
    bucket = s3.create_bucket(Bucket=bucket_name, ACL='public-read',
                              CreateBucketConfiguration={'LocationConstraint': 'eu-central-1'})
except ClientError as e:
    error = e.response['Error']
    if error['Code'] == 'BucketAlreadyOwnedByYou':
        print('S3 bucket already exists')
    else:
        print(error)
        exit()


print('Set up the file access rights through bucket policy')
bucket_policy = {
    'Version': '2012-10-17',
    'Statement': [{
        'Sid': 'AllowPublicAccessToS3',
        'Effect': 'Allow',
        'Principal': '*',
        'Action': ['s3:GetObject'],
        'Resource': f'arn:aws:s3:::{bucket_name}/*'
    }]
}

bucket_policy_json = json.dumps(bucket_policy)
s3.put_bucket_policy(Bucket=bucket_name, Policy=bucket_policy_json)


print('Set up static website hosting on S3')
s3.put_bucket_website(Bucket=bucket_name, WebsiteConfiguration={
    'ErrorDocument': {'Key': 'error.index'},
    'IndexDocument': {'Suffix': 'index.html'}
    }
)


zipfile_name = 'kenedy.zip'
print('Unpack the zip file directly on S3')
zfile = zipfile.PyZipFile(zipfile_name, mode='r')
for filename in zfile.namelist():
    print(filename)
    content_type = mimetypes.guess_type(filename)[0]
    if content_type is None:
        content_type = 'text/html'
    s3.upload_fileobj(zfile.open(filename), bucket_name, filename,
                      ExtraArgs={'ContentType': content_type})


r53 = boto3.client('route53')
hosted_zone_id = ''             # enter your hosted zone

print('Create a record in Route 53 and assign it an alias to S3')
r53.change_resource_record_sets(
    HostedZoneId=hosted_zone_id,
    ChangeBatch={
        'Comment': 'Add S3 A record',
        'Changes': [
            {
                'Action': 'UPSERT',
                'ResourceRecordSet': {
                    'Name': bucket_name,
                    'Type': 'A',
                    'AliasTarget': {
                        'HostedZoneId': 'Z21DNDUVLTQW6Q',
                        'DNSName': 's3-website.eu-central-1.amazonaws.com',
                        'EvaluateTargetHealth': False
                    }
                }
            }
        ]
    }
)
