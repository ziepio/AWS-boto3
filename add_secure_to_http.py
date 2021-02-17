import boto3
from botocore.client import ClientError


'''
Create HTTPS certificate, create and connect to CloudFront distribution and update Route 53 record.
'''

acm_north_virginia = boto3.client('acm', region_name='us-east-1')
domain_name = ''                                                    # enter domain name
certificate_not_exists = True

print('Request certificate: ', end='')
try:
    certificate_request = acm_north_virginia.request_certificate(
        DomainName=domain_name,
        ValidationMethod='DNS',
        Tags=[{
            'Key': 'Name',
            'Value': f'Certificate for {domain_name}'
        }]
    )
    print('ok')
except ClientError as e:
    error = e.response['Error']
    if error['Message'] == '???':
        certificate_not_exists = False
        print('Already exists')
    else:
        print(error['Message'])


if certificate_not_exists:
    certificate_arn = certificate_request['CertificateArn']
    describe_certificate = acm_north_virginia.describe_certificate(CertificateArn=certificate_arn)

    route53 = boto3.client('route53')
    hosted_zone = ''                    # enter hosted zone

    print('Add CNAME record: ', end='')
    add_cname = route53.change_resource_record_sets(
        HostedZoneId=hosted_zone,
        ChangeBatch={
            'Comment': 'Add CNAME validation',
            'Changes': [
                {
                    'Action': 'CREATE',
                    'ResourceRecordSet': {
                        'Name': describe_certificate['Certificate']['DomainValidationOptions'][0]['ResourceRecord']['Name'],
                        'Type': describe_certificate['Certificate']['DomainValidationOptions'][0]['ResourceRecord']['Type'],
                        'TTL': 300,
                        'ResourceRecords': [{
                            'Value': describe_certificate['Certificate']['DomainValidationOptions'][0]['ResourceRecord']['Value']
                        }]
                    }
                }
            ]
        }
    )
    print('ok')

    print('Waiting for issued status: ', end='')
    waiter = acm_north_virginia.get_waiter('certificate_validated')
    waiter.wait(CertificateArn=certificate_arn)
    print('ok')

