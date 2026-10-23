import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import * as agentcore from 'aws-cdk-lib/aws-bedrockagentcore';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import { FoundationStack } from './foundation-stack';

const REPO = path.join(__dirname, '..', '..');
const S = agentcore.SchemaDefinitionType;
const CALLER = {
  type: S.OBJECT,
  description: 'Set by the gateway from the signed-in user. Any value a client sends is replaced.',
};

/**
 * MCP endpoint for Claude, Copilot, or any MCP client: AgentCore Gateway with Cognito JWT inbound
 * auth, a REQUEST interceptor that injects the caller's identity from the validated token, and one
 * Lambda target (in the VPC, next to Aurora) that runs the same ownership-checked tool handlers.
 */
export class McpGateway extends Construct {
  constructor(scope: Construct, id: string, f: FoundationStack) {
    super(scope, id);
    const stack = cdk.Stack.of(this);
    const poolId = ssm.StringParameter.valueForStringParameter(this, '/uptime-desk/cognito/user-pool-id');
    const clientId = ssm.StringParameter.valueForStringParameter(this, '/uptime-desk/cognito/client-id');
    const image = (cmd: string) => lambda.DockerImageCode.fromImageAsset(REPO, {
      file: 'services/Dockerfile', platform: cdk.aws_ecr_assets.Platform.LINUX_ARM64, cmd: [cmd],
    });

    // Interceptor: outside the VPC, no AWS calls; it only rewrites the request.
    const interceptor = new lambda.DockerImageFunction(this, 'Interceptor', {
      code: image('handlers.mcp_interceptor.handler'), architecture: lambda.Architecture.ARM_64,
      memorySize: 256, timeout: cdk.Duration.seconds(10), logRetention: logs.RetentionDays.ONE_WEEK,
    });

    const target = new lambda.DockerImageFunction(this, 'Tools', {
      code: image('handlers.mcp_target.handler'), architecture: lambda.Architecture.ARM_64,
      memorySize: 1024, timeout: cdk.Duration.seconds(30), logRetention: logs.RetentionDays.ONE_WEEK,
      vpc: f.vpc, vpcSubnets: f.lambdaSubnets, securityGroups: [f.lambdaSg],
      environment: { DB_SECRET_ARN: f.data.cluster.secret!.secretArn, KB_ID: f.data.knowledgeBaseId },
    });
    f.data.cluster.secret!.grantRead(target);
    target.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock:Retrieve'],
      resources: [`arn:aws:bedrock:${stack.region}:${stack.account}:knowledge-base/${f.data.knowledgeBaseId}`],
    }));

    const gateway = new agentcore.Gateway(this, 'Gateway', {
      gatewayName: 'uptime-desk-mcp',
      description: 'Uptime Desk technician tools over MCP (Cognito sign-in required)',
      authorizerConfiguration: agentcore.GatewayAuthorizer.usingCustomJwt({
        discoveryUrl: `https://cognito-idp.${stack.region}.amazonaws.com/${poolId}/.well-known/openid-configuration`,
        allowedAudience: [clientId],   // Cognito ID tokens carry the groups and custom:technician_id
      }),
      interceptorConfigurations: [agentcore.LambdaInterceptor.forRequest(interceptor, { passRequestHeaders: true })],
    });

    gateway.addLambdaTarget('ToolsTarget', {
      gatewayTargetName: 'uptime',
      description: 'Work orders, jobs, asset history, and manual search with ownership checks',
      lambdaFunction: target,
      toolSchema: agentcore.ToolSchema.fromInline([
        { name: 'get_work_order', description: 'Get one work order by id: status, priority, SLA, fault, and verified manual steps with sources.',
          inputSchema: { type: S.OBJECT, properties: { work_order_id: { type: S.STRING }, caller_context: CALLER }, required: ['work_order_id'] } },
        { name: 'list_my_jobs', description: "List the signed-in technician's assigned work orders with site, start time, and SLA.",
          inputSchema: { type: S.OBJECT, properties: { caller_context: CALLER } } },
        { name: 'get_asset_history', description: 'Get recorded history for an asset on one of your jobs.',
          inputSchema: { type: S.OBJECT, properties: { asset_id: { type: S.STRING }, caller_context: CALLER }, required: ['asset_id'] } },
        { name: 'search_manuals', description: 'Search the equipment manuals. Returns passages with manual id and page. equipment_class: RTU or AHU-MZVAV.',
          inputSchema: { type: S.OBJECT, properties: { query: { type: S.STRING }, equipment_class: { type: S.STRING }, caller_context: CALLER },
                         required: ['query'] } },
      ]),
    });

    new ssm.StringParameter(this, 'McpUrl', { parameterName: '/uptime-desk/mcp/url', stringValue: gateway.gatewayUrl ?? '' });
    new cdk.CfnOutput(stack, 'McpGatewayId', { value: gateway.gatewayId });
    new cdk.CfnOutput(stack, 'McpGatewayUrl', { value: gateway.gatewayUrl ?? '' });
  }
}
