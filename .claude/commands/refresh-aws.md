Refresh AWS credentials by assuming the GACdkFullDeployRole.

Run the following steps:

1. Execute this command to assume the role:
```
aws sts assume-role \
  --role-arn arn:aws:iam::992382611204:role/GACdkFullDeployRole \
  --role-session-name genai-session \
  --profile genai-agent \
  --duration-seconds 36000
```

2. Parse the JSON output and update the `assumed_role` profile credentials:
```
aws configure set aws_access_key_id <AccessKeyId> --profile assumed_role
aws configure set aws_secret_access_key <SecretAccessKey> --profile assumed_role
aws configure set aws_session_token <SessionToken> --profile assumed_role
```

3. Verify by running:
```
aws sts get-caller-identity --profile assumed_role
```

4. Report the expiration time to the user.
