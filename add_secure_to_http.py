import boto3
from botocore.client import ClientError
from datetime import datetime
import time
import json


'''
Create HTTPS certificate, create and connect to CloudFront distribution and update Route 53 record.
'''

current_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
acm_north_virginia = boto3.client('acm', region_name='us-east-1')
domain_name = ''                                                    # enter domain name
certificate_not_exists = True

print('Requesting and validating certificate: ', end='')
certificates_list = acm_north_virginia.list_certificates(CertificateStatuses=['ISSUED'])
for i in certificates_list['CertificateSummaryList']:
    if i['DomainName'] == domain_name:
        certificate_arn = i['CertificateArn']
        certificate_not_exists = False
        print('certificate already exists')


if certificate_not_exists:
    certificate = acm_north_virginia.request_certificate(
        DomainName=domain_name,
        ValidationMethod='DNS',
        Tags=[{
            'Key': 'Name',
            'Value': f'Certificate for {domain_name}'
        }]
    )
    time.sleep(10)

    certificate_arn = certificate['CertificateArn']
    desc_certificate = acm_north_virginia.describe_certificate(CertificateArn=certificate_arn)

    route53 = boto3.client('route53')
    hosted_zone = ''                        # enter hosted zone
    cer_name = desc_certificate['Certificate']['DomainValidationOptions'][0]['ResourceRecord']['Name']
    cer_type = desc_certificate['Certificate']['DomainValidationOptions'][0]['ResourceRecord']['Type']
    cer_value = desc_certificate['Certificate']['DomainValidationOptions'][0]['ResourceRecord']['Value']

    add_cname = route53.change_resource_record_sets(
        HostedZoneId=hosted_zone,
        ChangeBatch={
            'Comment': 'Add CNAME validation',
            'Changes': [
                {
                    'Action': 'CREATE',
                    'ResourceRecordSet': {
                        'Name': cer_name,
                        'Type': cer_type,
                        'TTL': 300,
                        'ResourceRecords': [{
                            'Value': cer_value
                        }]
                    }
                }
            ]
        }
    )
    waiter = acm_north_virginia.get_waiter('certificate_validated')
    waiter.wait(CertificateArn=certificate_arn)
    print('certificate issued')

cloudfront = boto3.client('cloudfront')

distribution = cloudfront.create_distribution(
    DistributionConfig={
        'CallerReference': f'Distribution for {domain_name}, {current_date_time}',
        'DefaultRootObject': 'index.html',
        'Origins': {
                    'Quantity': 1,
                    'Items': [
                        {
                            'Id': f'S3-{domain_name}',
                            'DomainName': domain_name,
                            'CustomOriginConfig': {
                                'HTTPPort': 80,
                                'HTTPSPort': 443,
                                'OriginProtocolPolicy': 'https-only',
                            },
                            'ConnectionAttempts': 3,
                            'ConnectionTimeout': 10
                        }
                    ]
        },
        'DefaultCacheBehavior': {
            'TargetOriginId': f'S3-{domain_name}',
            'ViewerProtocolPolicy': 'redirect-to-https'
        },
        'Comment': f'HTTPS for {domain_name}',
        'Enabled': True,
        'ViewerCertificate': {
            'CloudFrontDefaultCertificate': False,
            'ACMCertificateArn': certificate_arn,
            'SSLSupportMethod': 'sni-only',
            'MinimumProtocolVersion': 'TLSv1.2_2019'
        },
        'HttpVersion': 'http2',
        'IsIPV6Enabled': True
    }
)

s3 = boto3.client('S3')
bucket_name = domain_name
origin_access_id = distribution['Distribution']['DistributionConfig']['Origins']['Items'][0]['S3OriginConfig']['OriginAccessIdentity']
new_statement = {
    'Sid': 'AllowCloudFrontAccessToS3',
    'Effect': 'Allow',
    'Principal': {
        'AWS': f'arn:aws:iam::cloudfront:user/CloudFront Origin Access Identity {origin_access_id}'
    },
    'Action': 's3:GetObject',
    'Resource': f'arn:aws:s3:::{bucket_name}/*'
}

retrieve_bucket_policy = s3.get_bucket_policy(Bucket=bucket_name)

bucket_policy = json.loads(retrieve_bucket_policy['Policy'])
bucket_statement = bucket_policy['bucket_policy']['Statement']
bucket_statement.pop(0)
bucket_statement.append(new_statement)
new_bucket_policy = json.dumps(bucket_policy)

s3.put_bucket_policy(
    Bucket=bucket_name,
    Policy=new_bucket_policy
)


route53 = boto3.client('route53')
hosted_zone_id = ''                             # enter hosted zone id

print('Redirecting user to CloudFront in Route53 hosted zone: ', end='')
try:
    record_upsert = route53.change_resource_record_sets(
        HostedZoneId=hosted_zone_id,
        ChangeBatch={
            'Comment': f'Update alias to CloudFront',
            'Changes': [
                {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': domain_name,
                        'Type': 'A',
                        'TTL': 300,
                        'ResourceRecords': [{'Value': distribution['Distribution']['DomainName']}]
                    }
                }
            ]
        }
    )
    print('ok')
except ClientError as e:
    error = e.response['Error']
    print(error['Message'])
