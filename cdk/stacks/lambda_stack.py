import os
import shutil
import subprocess

import aws_cdk as cdk
from aws_cdk import Duration
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct
from stacks.storage_stack import StorageStack


def _bundle_generate_post(project_root: str) -> str:
    bundle_dir = os.path.join(project_root, "build", "generate_post")
    if os.path.isdir(bundle_dir):
        shutil.rmtree(bundle_dir)
    os.makedirs(bundle_dir, exist_ok=True)

    subprocess.run(
        [
            "pip",
            "install",
            "-r",
            "lambdas/generate_post/requirements.txt",
            "-t",
            bundle_dir,
        ],
        cwd=project_root,
        check=True,
    )
    shutil.copytree(
        os.path.join(project_root, "shared"),
        os.path.join(bundle_dir, "shared"),
    )
    for filename in ("handler.py", "bedrock.py", "rss.py"):
        shutil.copy2(
            os.path.join(project_root, "lambdas/generate_post", filename),
            bundle_dir,
        )
    return bundle_dir


class LambdaStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        storage_stack: StorageStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        bundle_dir = _bundle_generate_post(project_root)

        generate_post_fn = lambda_.Function(
            self,
            "GeneratePostFunction",
            function_name="quillcast-generate-post",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            timeout=Duration.minutes(5),
            memory_size=512,
            code=lambda_.Code.from_asset(bundle_dir),
            environment={
                "CONFIG_BUCKET": storage_stack.config_bucket.bucket_name,
                "DRAFTS_TABLE_NAME": storage_stack.table.table_name,
                "BEDROCK_MODEL_ID": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            },
        )

        storage_stack.config_bucket.grant_read(generate_post_fn)
        storage_stack.table.grant_write_data(generate_post_fn)

        generate_post_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.*",
                    f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/us.anthropic.*",
                ],
            )
        )

        cdk.CfnOutput(self, "GeneratePostFunctionName", value=generate_post_fn.function_name)
        cdk.CfnOutput(self, "GeneratePostFunctionArn", value=generate_post_fn.function_arn)

        self.generate_post_fn = generate_post_fn
