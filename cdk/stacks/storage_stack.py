import aws_cdk as cdk
from aws_cdk import (
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    aws_ssm as ssm,
    CfnOutput,
)
from constructs import Construct


class StorageStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── DynamoDB table ────────────────────────────────────────────────────
        self.table = dynamodb.Table(
            self,
            "DraftsTable",
            table_name="quillcast-drafts",
            partition_key=dynamodb.Attribute(
                name="PostID",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # RETAIN so a `cdk destroy` never deletes your post history
            removal_policy=RemovalPolicy.RETAIN,
        )

        # GSI: query all PENDING drafts sorted by creation time
        self.table.add_global_secondary_index(
            index_name="OverallStatus-CreatedAt-index",
            partition_key=dynamodb.Attribute(
                name="OverallStatus",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="CreatedAt",
                type=dynamodb.AttributeType.STRING,
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ── S3 bucket for config files (platforms.yaml, topics.yaml) ─────────
        self.config_bucket = s3.Bucket(
            self,
            "ConfigBucket",
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # ── Store resource names in SSM so Lambdas can look them up ──────────
        ssm.StringParameter(
            self,
            "TableNameParam",
            parameter_name="/quillcast/drafts_table_name",
            string_value=self.table.table_name,
        )

        ssm.StringParameter(
            self,
            "ConfigBucketParam",
            parameter_name="/quillcast/config_bucket_name",
            string_value=self.config_bucket.bucket_name,
        )

        # ── CloudFormation outputs (visible in AWS Console after deploy) ──────
        CfnOutput(self, "DraftsTableName", value=self.table.table_name)
        CfnOutput(self, "DraftsTableArn", value=self.table.table_arn)
        CfnOutput(self, "ConfigBucketName", value=self.config_bucket.bucket_name)
