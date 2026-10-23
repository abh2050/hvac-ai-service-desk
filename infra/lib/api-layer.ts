import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import * as apigw from 'aws-cdk-lib/aws-apigatewayv2';
import * as authorizers from 'aws-cdk-lib/aws-apigatewayv2-authorizers';
import * as integrations from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import { FoundationStack } from './foundation-stack';

const REPO = path.join(__dirname, '..', '..');
export const REPLAY_MACHINE_NAME = 'uptime-desk-replay';
export const CASE_MACHINE_NAME = 'uptime-desk-case';

/**
 * Idle-profile API: FastAPI on Lambda (in the VPC, next to Aurora) behind an HTTP API whose JWT
 * authorizer validates Cognito ID tokens. The user pool is created by Amplify Gen 2 (app/amplify)
 * and read here from SSM. State machines are referenced by fixed name, so the always-on API does
 * not depend on the demo stack; when the demo profile is down, starting a run returns an error.
 */
export class ApiLayer extends Construct {
  readonly url: string;

  constructor(scope: Construct, id: string, f: FoundationStack, allowedOrigins: string[]) {
    super(scope, id);
    const stack = cdk.Stack.of(this);
    const poolId = ssm.StringParameter.valueForStringParameter(this, '/uptime-desk/cognito/user-pool-id');
    const clientId = ssm.StringParameter.valueForStringParameter(this, '/uptime-desk/cognito/client-id');
    const machineArn = (name: string) => `arn:aws:states:${stack.region}:${stack.account}:stateMachine:${name}`;

    const fn = new lambda.DockerImageFunction(this, 'Api', {
      code: lambda.DockerImageCode.fromImageAsset(REPO, {
        file: 'services/Dockerfile', platform: cdk.aws_ecr_assets.Platform.LINUX_ARM64, cmd: ['handlers.api.handler'],
      }),
      architecture: lambda.Architecture.ARM_64, memorySize: 2048, timeout: cdk.Duration.seconds(29),
      vpc: f.vpc, vpcSubnets: f.lambdaSubnets, securityGroups: [f.lambdaSg],
      environment: {
        DB_SECRET_ARN: f.data.cluster.secret!.secretArn, DATA_BUCKET: f.dataBucket.bucketName,
        KB_ID: f.data.knowledgeBaseId, GUARDRAIL_ID: f.data.guardrailId, GUARDRAIL_VERSION: f.data.guardrailVersion,
        REPLAY_MACHINE_ARN: machineArn(REPLAY_MACHINE_NAME),
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
    });
    f.data.cluster.secret!.grantRead(fn);
    f.dataBucket.grantRead(fn, 'episodes/*');
    f.dataBucket.grantRead(fn, 'manuals/*');
    fn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['states:StartExecution'], resources: [machineArn(REPLAY_MACHINE_NAME)],
    }));
    fn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['states:DescribeExecution', 'states:GetExecutionHistory'],
      resources: [REPLAY_MACHINE_NAME, CASE_MACHINE_NAME].map(
        (n) => `arn:aws:states:${stack.region}:${stack.account}:execution:${n}:*`),
    }));
    // Task-token callbacks have no resource ARN; AWS requires "*" for these two actions.
    fn.addToRolePolicy(new iam.PolicyStatement({ actions: ['states:SendTaskSuccess', 'states:SendTaskFailure'], resources: ['*'] }));
    fn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel'],
      resources: ['openai.gpt-oss-120b-1:0', 'openai.gpt-oss-20b-1:0'].map(
        (m) => `arn:aws:bedrock:${stack.region}::foundation-model/${m}`),
    }));
    fn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock:ApplyGuardrail'],
      resources: [`arn:aws:bedrock:${stack.region}:${stack.account}:guardrail/${f.data.guardrailId}`],
    }));
    fn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock:Retrieve'],
      resources: [`arn:aws:bedrock:${stack.region}:${stack.account}:knowledge-base/${f.data.knowledgeBaseId}`],
    }));

    const authorizer = new authorizers.HttpJwtAuthorizer('Cognito',
      `https://cognito-idp.${stack.region}.amazonaws.com/${poolId}`, { jwtAudience: [clientId] });
    const api = new apigw.HttpApi(this, 'HttpApi', {
      apiName: 'uptime-desk',
      corsPreflight: {
        allowOrigins: allowedOrigins, allowHeaders: ['authorization', 'content-type'],
        allowMethods: [apigw.CorsHttpMethod.GET, apigw.CorsHttpMethod.POST, apigw.CorsHttpMethod.OPTIONS],
        maxAge: cdk.Duration.hours(1),
      },
      defaultAuthorizer: authorizer,
      defaultIntegration: new integrations.HttpLambdaIntegration('ApiIntegration', fn),
    });
    // Browsers send CORS preflights without a token. A catch-all route with the JWT authorizer would
    // answer them 401, which the browser reports as a network failure. This OPTIONS route has no
    // authorizer, so API Gateway answers preflights from the CORS settings above. Every other method
    // still requires a valid Cognito token.
    api.addRoutes({
      path: '/{proxy+}', methods: [apigw.HttpMethod.OPTIONS],
      integration: new integrations.HttpLambdaIntegration('PreflightIntegration', fn),
      authorizer: new apigw.HttpNoneAuthorizer(),
    });

    // Public demo: cap request rate so a shared link cannot run up Bedrock or Lambda costs.
    const stage = api.defaultStage!.node.defaultChild as apigw.CfnStage;
    stage.defaultRouteSettings = { throttlingRateLimit: 5, throttlingBurstLimit: 10 };
    this.url = api.apiEndpoint;
    new ssm.StringParameter(this, 'ApiUrl', { parameterName: '/uptime-desk/api/url', stringValue: api.apiEndpoint });
    new cdk.CfnOutput(stack, 'ApiUrl', { value: api.apiEndpoint });
  }
}
