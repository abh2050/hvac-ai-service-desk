import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

/**
 * Always-on (idle profile) resources. Gate 0 holds storage and networking only; later gates
 * add Aurora, Cognito wiring, the API, and the MCP tools here.
 *
 * Networking: no NAT gateway. In-VPC Lambdas reach AWS services through one S3 gateway
 * endpoint (free) and four interface endpoints placed in a single AZ to hold idle cost near
 * $29/month. Aurora's subnet group still spans two AZs, which RDS requires.
 */
export class FoundationStack extends cdk.Stack {
  readonly vpc: ec2.Vpc;
  readonly dataBucket: s3.Bucket;
  readonly lambdaSubnets: ec2.SubnetSelection;

  constructor(scope: Construct, id: string, props: cdk.StackProps) {
    super(scope, id, props);

    this.dataBucket = new s3.Bucket(this, 'DataBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      versioned: false,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    this.vpc = new ec2.Vpc(this, 'Vpc', {
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [
        { name: 'public', subnetType: ec2.SubnetType.PUBLIC, cidrMask: 24 },
        { name: 'isolated', subnetType: ec2.SubnetType.PRIVATE_ISOLATED, cidrMask: 24 },
      ],
      gatewayEndpoints: { S3: { service: ec2.GatewayVpcEndpointAwsService.S3 } },
    });

    // In-VPC Lambdas run in the first isolated subnet only, alongside the endpoints.
    this.lambdaSubnets = { subnets: [this.vpc.isolatedSubnets[0]] };

    const endpointSg = new ec2.SecurityGroup(this, 'EndpointSg', {
      vpc: this.vpc,
      description: 'HTTPS from inside the VPC to interface endpoints',
      allowAllOutbound: false,
    });
    endpointSg.addIngressRule(ec2.Peer.ipv4(this.vpc.vpcCidrBlock), ec2.Port.tcp(443));

    const interfaceEndpoints: Record<string, ec2.InterfaceVpcEndpointAwsService> = {
      BedrockRuntime: ec2.InterfaceVpcEndpointAwsService.BEDROCK_RUNTIME,
      BedrockAgentRuntime: ec2.InterfaceVpcEndpointAwsService.BEDROCK_AGENT_RUNTIME,
      SecretsManager: ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
      StepFunctions: ec2.InterfaceVpcEndpointAwsService.STEP_FUNCTIONS,
    };
    for (const [name, service] of Object.entries(interfaceEndpoints)) {
      this.vpc.addInterfaceEndpoint(name, {
        service,
        subnets: this.lambdaSubnets,
        securityGroups: [endpointSg],
        privateDnsEnabled: true,
      });
    }

    new cdk.CfnOutput(this, 'DataBucketName', { value: this.dataBucket.bucketName });
    new cdk.CfnOutput(this, 'VpcId', { value: this.vpc.vpcId });
  }
}
