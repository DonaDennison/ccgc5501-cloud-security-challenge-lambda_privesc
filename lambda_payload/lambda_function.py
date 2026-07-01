import json
import boto3

def lambda_handler(event, context):
    iam = boto3.client("iam")

    user_name = event.get("user_name")
    policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"

    iam.attach_user_policy(
        UserName=user_name,
        PolicyArn=policy_arn
    )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": f"AdministratorAccess attached to {user_name}"
        })
    }
