import argparse
import subprocess
import time
import boto3
# import logging


# logging.basicConfig(level=logging.INFO)
# boto3.set_stream_logger('botocore', level=logging.DEBUG)



def create_aws_cloudwatch_group_stream(aws_access_key, aws_secret_key, region, group_name, stream_name):
    cw_client = boto3.client('logs',
                            aws_access_key_id=aws_access_key,
                            aws_secret_access_key=aws_secret_key,
                            region_name=region
                        )

    # Create CloudWatch log group if not exists
    try:
        cw_client.create_log_group(logGroupName=group_name)
    except cw_client.exceptions.ResourceAlreadyExistsException:
        pass

    # Create CloudWatch log stream if not exists
    try:
        cw_client.create_log_stream(logGroupName=group_name, logStreamName=stream_name)
    except cw_client.exceptions.ResourceAlreadyExistsException:
        pass
    
    return cw_client, group_name, stream_name

def send_logs_to_cloudwatch(cw_client, group_name, stream_name, logs):
    logs = [
        {
            'timestamp': int(time.time() * 1000),  # current timestamp in milliseconds
            'message': log
        }for log in logs 
    ]
    
    # with open('local_logs.txt', 'a') as f:
    #     for log in logs:
    #         f.write(log['message'] + '\n')

    cw_client.put_log_events(
        logGroupName=group_name,
        logStreamName=stream_name,
        logEvents=logs
    )


def main():
    parser = argparse.ArgumentParser(
        description="Docker Logger to AWS CloudWatch")
    parser.add_argument("--docker-image", required=True,
                        help="Name of the Docker image")
    parser.add_argument("--bash-command", required=True,
                        help="Bash command to run inside the Docker image")
    parser.add_argument("--aws-cloudwatch-group", required=True,
                        help="Name of AWS CloudWatch group")
    parser.add_argument("--aws-cloudwatch-stream",
                        required=True, help="Name of AWS CloudWatch stream")
    parser.add_argument("--aws-access-key-id",
                        required=True, help="AWS Access Key ID")
    parser.add_argument("--aws-secret-access-key",
                        required=True, help="AWS Secret Access Key")
    parser.add_argument("--aws-region", required=True, help="AWS Region")

    args = parser.parse_args()
    
    # Create Docker container
    process = subprocess.Popen(["docker", "run", 
                                args.docker_image, 
                                "bash", "-c",
                                args.bash_command], 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE, 
                                text=True
                            )

    # AWS CloudWatch setup
    cw_client, group_name, stream_name = create_aws_cloudwatch_group_stream(
        args.aws_access_key_id,
        args.aws_secret_access_key,
        args.aws_region,
        args.aws_cloudwatch_group,
        args.aws_cloudwatch_stream
    )

    try:
        # Monitor logs and send to CloudWatch
        while True:
            log_line = process.stdout.readline()
            if not log_line and process.poll() is not None:
                break
            
            logs = [log_line.strip()]
            send_logs_to_cloudwatch(cw_client, group_name, stream_name, logs)
            
        # Ensure all remaining logs are sent
        remaining_logs = process.stdout.readlines()
        
        if remaining_logs:
            send_logs_to_cloudwatch(cw_client, group_name, stream_name, remaining_logs)

    except KeyboardInterrupt:
        print("Interrupted. Cleaning up...")

    finally:
        process.terminate()


if __name__ == "__main__":
    main()
