import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as kinesis from 'aws-cdk-lib/aws-kinesis';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as sources from 'aws-cdk-lib/aws-lambda-event-sources';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { Construct } from 'constructs';
import { FoundationStack } from './foundation-stack';
import { CASE_MACHINE_NAME, REPLAY_MACHINE_NAME } from './api-layer';

const REPO = path.join(__dirname, '..', '..');
const DIAG_MODELS = ['openai.gpt-oss-120b-1:0', 'openai.gpt-oss-20b-1:0'];

interface PipelineProps {
  foundation: FoundationStack;
  stream: kinesis.Stream;
  cluster: ecs.Cluster;
  approvalTimeout: cdk.Duration;
}

/**
 * Demo-profile pipeline: replay -> Kinesis -> detection -> EventBridge -> case state machine
 * (aggregate, diagnose, verify and draft, approval pause, Fargate dispatch).
 */
export class Pipeline extends Construct {
  readonly replayMachine: sfn.StateMachine;
  readonly caseMachine: sfn.StateMachine;

  constructor(scope: Construct, id: string, props: PipelineProps) {
    super(scope, id);
    const f = props.foundation;
    const stack = cdk.Stack.of(this);
    const bucket = f.dataBucket;

    const image = (cmd: string) => lambda.DockerImageCode.fromImageAsset(REPO, {
      file: 'services/Dockerfile', platform: cdk.aws_ecr_assets.Platform.LINUX_ARM64, cmd: [cmd],
    });
    const fn = (name: string, cmd: string, opts: Partial<lambda.DockerImageFunctionProps> = {}) =>
      new lambda.DockerImageFunction(this, name, {
        code: image(cmd), architecture: lambda.Architecture.ARM_64, memorySize: 1024,
        timeout: cdk.Duration.minutes(2), logRetention: logs.RetentionDays.ONE_WEEK, ...opts,
      });
    const vpcOpts = {
      vpc: f.vpc, vpcSubnets: f.lambdaSubnets, securityGroups: [f.lambdaSg],
      environment: {
        DB_SECRET_ARN: f.data.cluster.secret!.secretArn, DATA_BUCKET: bucket.bucketName,
        KB_ID: f.data.knowledgeBaseId, GUARDRAIL_ID: f.data.guardrailId, GUARDRAIL_VERSION: f.data.guardrailVersion,
      },
    };

    // --- Outside the VPC: replay and detection reach S3, Kinesis, EventBridge on public endpoints ---
    const replay = fn('Replay', 'handlers.replay.handler', {
      timeout: cdk.Duration.minutes(5),
      environment: { STREAM_NAME: props.stream.streamName, DATA_BUCKET: bucket.bucketName },
    });
    bucket.grantRead(replay, 'episodes/*');
    props.stream.grantWrite(replay);

    const detect = fn('Detect', 'handlers.detect.handler', {
      memorySize: 2048, environment: { DATA_BUCKET: bucket.bucketName, EVENT_BUS: 'default' },
    });
    bucket.grantRead(detect, 'models/*');
    detect.addToRolePolicy(new iam.PolicyStatement({
      actions: ['events:PutEvents'], resources: [`arn:aws:events:${stack.region}:${stack.account}:event-bus/default`],
    }));
    detect.addEventSource(new sources.KinesisEventSource(props.stream, {
      startingPosition: lambda.StartingPosition.LATEST, batchSize: 25, maxBatchingWindow: cdk.Duration.seconds(2),
      retryAttempts: 2,
    }));

    // --- Inside the VPC: Aurora, Bedrock, Secrets Manager through endpoints ---
    const window = fn('Window', 'handlers.case.window', vpcOpts);
    const endOfDay = fn('EndOfDay', 'handlers.case.end_of_day', vpcOpts);
    const diagnose = fn('Diagnose', 'handlers.case.diagnose_case', { ...vpcOpts, timeout: cdk.Duration.minutes(5) });
    const verify = fn('VerifyDraft', 'handlers.case.verify_and_draft', { ...vpcOpts, timeout: cdk.Duration.minutes(5) });
    const storeToken = fn('StoreToken', 'handlers.case.store_token', vpcOpts);
    const escalate = fn('Escalate', 'handlers.case.escalate', vpcOpts);
    for (const l of [window, endOfDay, diagnose, verify, storeToken, escalate]) {
      f.data.cluster.secret!.grantRead(l);
    }
    const modelArns = DIAG_MODELS.map((m) => `arn:aws:bedrock:${stack.region}::foundation-model/${m}`);
    for (const l of [diagnose, verify]) {
      l.addToRolePolicy(new iam.PolicyStatement({ actions: ['bedrock:InvokeModel'], resources: modelArns }));
      l.addToRolePolicy(new iam.PolicyStatement({
        actions: ['bedrock:ApplyGuardrail'],
        resources: [`arn:aws:bedrock:${stack.region}:${stack.account}:guardrail/${f.data.guardrailId}`],
      }));
    }
    diagnose.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock:Retrieve'],
      resources: [`arn:aws:bedrock:${stack.region}:${stack.account}:knowledge-base/${f.data.knowledgeBaseId}`],
    }));

    // --- Fargate dispatch task (OR-Tools): public subnet, public IP, no inbound ---
    const taskDef = new ecs.FargateTaskDefinition(this, 'DispatchTask', {
      cpu: 1024, memoryLimitMiB: 2048,
      runtimePlatform: { cpuArchitecture: ecs.CpuArchitecture.ARM64, operatingSystemFamily: ecs.OperatingSystemFamily.LINUX },
    });
    const container = taskDef.addContainer('dispatch', {
      image: ecs.ContainerImage.fromAsset(REPO, { file: 'services/Dockerfile', platform: cdk.aws_ecr_assets.Platform.LINUX_ARM64 }),
      entryPoint: ['python', '-m', 'handlers.dispatch_task'],
      workingDirectory: '/var/task',
      environment: { DB_SECRET_ARN: f.data.cluster.secret!.secretArn, APP_ROOT: '/var/task/app', AWS_REGION: stack.region },
      logging: ecs.LogDrivers.awsLogs({ streamPrefix: 'dispatch', logRetention: logs.RetentionDays.ONE_WEEK }),
    });
    f.data.cluster.secret!.grantRead(taskDef.taskRole);
    const dispatchSg = new ec2.SecurityGroup(this, 'DispatchSg', {
      vpc: f.vpc, description: 'Fargate dispatch task: outbound only', allowAllOutbound: true,
    });

    // --- Case state machine ---
    const settle = new sfn.Wait(this, 'LetWindowsLand', { time: sfn.WaitTime.duration(cdk.Duration.seconds(15)) });
    const day = new tasks.LambdaInvoke(this, 'DecideDay', {
      lambdaFunction: endOfDay, payloadResponseOnly: true,
      payload: sfn.TaskInput.fromObject({ 'detail.$': '$.detail', 'execution_arn.$': '$$.Execution.Id' }),
    });
    const diag = new tasks.LambdaInvoke(this, 'DiagnoseCase', { lambdaFunction: diagnose, payloadResponseOnly: true });
    const draft = new tasks.LambdaInvoke(this, 'VerifyAndDraft', { lambdaFunction: verify, payloadResponseOnly: true });
    const wait = new tasks.LambdaInvoke(this, 'WaitForApproval', {
      lambdaFunction: storeToken, integrationPattern: sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
      payload: sfn.TaskInput.fromObject({ token: sfn.JsonPath.taskToken, 'work_order_id.$': '$.work_order_id' }),
      taskTimeout: sfn.Timeout.duration(props.approvalTimeout), resultPath: '$.approval',
    });
    const esc = new tasks.LambdaInvoke(this, 'EscalateExpired', {
      lambdaFunction: escalate, payloadResponseOnly: true,
      payload: sfn.TaskInput.fromObject({ 'work_order_id.$': '$.work_order_id' }),
    });
    const rejected = new sfn.Succeed(this, 'Rejected', { comment: 'Manager rejected the work order' });
    wait.addCatch(esc, { errors: ['States.Timeout'], resultPath: '$.timeout' });
    wait.addCatch(rejected, { errors: ['Rejected'], resultPath: '$.rejection' });
    const runDispatch = new tasks.EcsRunTask(this, 'DispatchOrTools', {
      integrationPattern: sfn.IntegrationPattern.RUN_JOB, cluster: props.cluster, taskDefinition: taskDef,
      launchTarget: new tasks.EcsFargateLaunchTarget({ platformVersion: ecs.FargatePlatformVersion.LATEST }),
      assignPublicIp: true, subnets: { subnetType: ec2.SubnetType.PUBLIC }, securityGroups: [dispatchSg],
      resultPath: sfn.JsonPath.DISCARD,
    });
    const done = new sfn.Succeed(this, 'Done');
    const noCase = new sfn.Succeed(this, 'NoDiagnosis', { comment: 'No fault detected, or routed to manual review (policy 1)' });
    const noApproval = new sfn.Succeed(this, 'NoApprovalNeeded', { comment: 'Blocked, manual review, or operations review' });
    const definition = settle.next(day).next(
      new sfn.Choice(this, 'DiagnoseNeeded?').when(sfn.Condition.booleanEquals('$.diagnose', true),
        diag.next(draft).next(new sfn.Choice(this, 'NeedsApproval?')
          .when(sfn.Condition.booleanEquals('$.needs_approval', true), wait.next(runDispatch).next(done))
          .otherwise(noApproval)))
        .otherwise(noCase));
    this.caseMachine = new sfn.StateMachine(this, 'CaseMachine', {
      stateMachineName: CASE_MACHINE_NAME,
      definitionBody: sfn.DefinitionBody.fromChainable(definition), timeout: cdk.Duration.hours(6),
      tracingEnabled: false,
      logs: { destination: new logs.LogGroup(this, 'CaseLogs', { retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY }), level: sfn.LogLevel.ERROR },
    });

    // --- Replay state machine (the API starts it) ---
    this.replayMachine = new sfn.StateMachine(this, 'ReplayMachine', {
      stateMachineName: REPLAY_MACHINE_NAME,
      definitionBody: sfn.DefinitionBody.fromChainable(
        new tasks.LambdaInvoke(this, 'ReplayRecordedDay', { lambdaFunction: replay, payloadResponseOnly: true })),
      timeout: cdk.Duration.minutes(10),
    });

    // --- EventBridge: windows to the aggregator, end of day to the case machine ---
    new events.Rule(this, 'WindowRule', {
      eventPattern: { source: ['uptime-desk.detection'], detailType: ['Window'] },
      targets: [new targets.LambdaFunction(window, { retryAttempts: 4 })],
    });
    new events.Rule(this, 'EndOfDayRule', {
      eventPattern: { source: ['uptime-desk.detection'], detailType: ['EndOfDay'] },
      targets: [new targets.SfnStateMachine(this.caseMachine)],
    });

    new cdk.CfnOutput(stack, 'ReplayMachineArn', { value: this.replayMachine.stateMachineArn });
    new cdk.CfnOutput(stack, 'CaseMachineArn', { value: this.caseMachine.stateMachineArn });
  }
}
