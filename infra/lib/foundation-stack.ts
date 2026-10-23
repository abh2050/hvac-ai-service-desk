import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';
import { DataLayer } from './data-layer';
import { ApiLayer } from './api-layer';
import { McpGateway } from './mcp-gateway';
import { Dashboard } from './dashboard';

// Managed prefix list for S3 in us-east-2 (com.amazonaws.us-east-2.s3).
const PREFIX_LIST_S3: Record<string, string> = { 'us-east-2': 'pl-7ba54012' };

/**
 * Always-on (idle profile) resources: storage, networking, and the data layer (Aurora, the
 * manual Knowledge Base, the Guardrail). Later phases add the API and the MCP tools.
 *
 * Networking: no NAT gateway. In-VPC Lambdas reach AWS services through one S3 gateway
 * endpoint (free) and four interface endpoints placed in a single AZ to hold idle cost near
 * $29/month. Aurora's subnet group still spans two AZs, which RDS requires.
 */
export class FoundationStack extends cdk.Stack {
  readonly vpc: ec2.Vpc;
  readonly dataBucket: s3.Bucket;
  readonly lambdaSubnets: ec2.SubnetSelection;
  readonly data: DataLayer;
  readonly lambdaSg: ec2.SecurityGroup;

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

    // In-VPC Lambdas: outbound only, HTTPS to the endpoints and PostgreSQL to Aurora.
    this.lambdaSg = new ec2.SecurityGroup(this, 'LambdaSg', {
      vpc: this.vpc, description: 'In-VPC Lambdas: HTTPS to endpoints, 5432 to Aurora', allowAllOutbound: false,
    });
    this.lambdaSg.addEgressRule(ec2.Peer.ipv4(this.vpc.vpcCidrBlock), ec2.Port.tcp(443));
    this.lambdaSg.addEgressRule(ec2.Peer.ipv4(this.vpc.vpcCidrBlock), ec2.Port.tcp(5432));
    // The S3 gateway endpoint routes S3 traffic by prefix list.
    this.lambdaSg.addEgressRule(ec2.Peer.prefixList(PREFIX_LIST_S3[this.region] ?? 'pl-7ba54012'), ec2.Port.tcp(443));

    this.data = new DataLayer(this, 'Data', { vpc: this.vpc, dataBucket: this.dataBucket, lambdaSg: this.lambdaSg,
                                              lambdaSubnets: this.lambdaSubnets });

    // The API needs the Cognito pool that Amplify Gen 2 creates; deploy it once that pool exists.
    if (this.node.tryGetContext('withApi') !== 'false') {
      new ApiLayer(this, 'Api', this, ['https://main.du00v4uwlekbh.amplifyapp.com', 'https://uptime-desk.vercel.app', 'http://localhost:5173']);
      new McpGateway(this, 'Mcp', this);
      new Dashboard(this, 'Dashboard');
    }

    new cdk.CfnOutput(this, 'DataBucketName', { value: this.dataBucket.bucketName });
    new cdk.CfnOutput(this, 'VpcId', { value: this.vpc.vpcId });
  }
}
