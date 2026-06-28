#!/usr/bin/env python3
import os
import sys

# Ensure cdk/ is on the path so stack imports resolve correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aws_cdk as cdk

from stacks.storage_stack import StorageStack

app = cdk.App()

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1"),
)

StorageStack(app, "QuillcastStorageStack", env=env)

app.synth()
