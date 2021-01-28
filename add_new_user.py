import boto3
from botocore.client import ClientError
import random, string


'''Create new user, give SupportUser policy and specify temporary password'''

iam = boto3.client('iam')
user_name = 'Gosia'

print('Creating user:', user_name)
try:
    new_user = iam.create_user(UserName=user_name,
                               PermissionsBoundary='arn:aws:iam::aws:policy/job-function/SupportUser')
except ClientError as e:
    error = e.response['Error']
    if error['Code'] == 'EntityAlreadyExists':
        print(f'User with name {user_name} already exists.')
    else:
        print(error)
        exit()


print('Creating login, password for user:', user_name)
password = ''.join(random.choice(string.ascii_letters) for i in range(10)) + '!'

login_password = iam.create_login_profile(
        UserName=user_name,
        Password=password
)
with open(f'{user_name} credentials.txt', 'w+') as credentials:
    credentials.write(f'Login: {user_name}\n'
                      f'Password: {password}')
