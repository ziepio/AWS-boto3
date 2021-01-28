import boto3


'''Allow to download file or upload to a specified bucket'''

s3 = boto3.client('s3')
bucket_name = ''                        # enter bucket name

file_name = 'test1.txt'                 # choose file
download, upload = False, True          # choose action


print(f'Bucket {bucket_name} contains:\n')
bucket_object_list = s3.list_objects(Bucket=bucket_name)
for bucket_object in bucket_object_list['Contents']:
    print(bucket_object['Key'])


if download:
    print(f'Downloading an S3 object {file_name}')
    s3.download_file(Bucket=bucket_name, Key=file_name, Filename=file_name)

if upload:
    print(f'Uploading an S3 object {file_name} to {bucket_name} bucket')
    s3.upload_file(Bucket=bucket_name, Key=file_name, Filename=file_name)
