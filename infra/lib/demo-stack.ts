import * as cdk from 'aws-cdk-lib';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as kinesis from 'aws-cdk-lib/aws-kinesis';
import { Construct } from 'constructs';
import { FoundationStack } from './foundation-stack';
import { Pipeline } from './pipeline';

interface DemoStackProps extends cdk.StackProps {
  foundation: FoundationStack;
}

/**
 * Demo profile resources that cost money while they exist. demo-up.sh deploys this stack and
 * demo-down.sh destroys it. It holds the Kinesis stream, the ECS cluster, and the replay,
 * detection, and case pipeline (Lambdas, Step Functions, EventBridge, Fargate dispatch task).
 */
export class DemoStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: DemoStackProps) {
    super(scope, id, props);

    // One provisioned shard costs about $0.015/hour; on-demand has a higher hourly floor.
    const stream = new kinesis.Stream(this, 'SensorReplayStream', {
      shardCount: 1,
      retentionPeriod: cdk.Duration.hours(24),
      encryption: kinesis.StreamEncryption.MANAGED,
    });
    stream.applyRemovalPolicy(cdk.RemovalPolicy.DESTROY);

    // An ECS cluster has no standing charge; Fargate tasks bill only while running.
    const cluster = new ecs.Cluster(this, 'DispatchCluster', { vpc: props.foundation.vpc });

    // Approval timeout comes from config/policy.yaml (work_order.approval_timeout_hours = 4).
    new Pipeline(this, 'Pipeline', {
      foundation: props.foundation, stream, cluster, approvalTimeout: cdk.Duration.hours(4),
    });

    new cdk.CfnOutput(this, 'StreamName', { value: stream.streamName });
  }
}
