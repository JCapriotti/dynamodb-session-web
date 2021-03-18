from setuptools import setup, find_packages

version = f'0.0.1'

setup(name='dynamodb-session-web',
      version=version,
      description='Contains the core API for a DynamoDB-backed session',
      author='Jason Capriotti',
      author_email='jason.capriotti@gmail.com',
      packages=find_packages(),
      install_requires=[
            'boto3',
      ])
