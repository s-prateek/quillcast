#!/usr/bin/env python3
import os
import sys

# Ensure project root and cdk/ are on the path
_cdk_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_cdk_dir)
sys.path.insert(0, _cdk_dir)
sys.path.insert(0, _project_root)

import aws_cdk as cdk  # noqa: E402
from stacks.lambda_stack import LambdaStack  # noqa: E402
from stacks.storage_stack import StorageStack  # noqa: E402

from shared.aws_env import resolve_account_id, resolve_region  # noqa: E402

app = cdk.App()

env = cdk.Environment(
    account=resolve_account_id(),
    region=resolve_region(),
)

StorageStack(app, "QuillcastStorageStack", env=env)

app.synth()
