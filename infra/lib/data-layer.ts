import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as s3vectors from 'aws-cdk-lib/aws-s3vectors';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

const REPO = path.join(__dirname, '..', '..');

interface DataLayerProps {
  vpc: ec2.Vpc;
  dataBucket: s3.Bucket;
  lambdaSg: ec2.SecurityGroup;
  lambdaSubnets: ec2.SubnetSelection;
}

/**
 * Idle-profile data layer: Aurora Serverless v2 (auto pause to 0 ACU), the manual Knowledge Base
 * on S3 Vectors with Titan Text Embeddings v2, the Bedrock Guardrail, and the files the app reads
 * (manual PDFs for presigned URLs, KB source chunks, detector models).
 */
export class DataLayer extends Construct {
  readonly cluster: rds.DatabaseCluster;
  readonly dbSecurityGroup: ec2.SecurityGroup;
  readonly knowledgeBaseId: string;
  readonly guardrailId: string;
  readonly guardrailVersion: string;

  constructor(scope: Construct, id: string, props: DataLayerProps) {
    super(scope, id);
    const stack = cdk.Stack.of(this);

    // --- Aurora Serverless v2 PostgreSQL, isolated subnets, auto pause after 10 idle minutes ---
    this.dbSecurityGroup = new ec2.SecurityGroup(this, 'DbSg', {
      vpc: props.vpc,
      description: 'Aurora PostgreSQL, reachable only from inside the VPC',
      allowAllOutbound: false,
    });
    this.dbSecurityGroup.addIngressRule(ec2.Peer.ipv4(props.vpc.vpcCidrBlock), ec2.Port.tcp(5432));
    this.cluster = new rds.DatabaseCluster(this, 'Aurora', {
      engine: rds.DatabaseClusterEngine.auroraPostgres({ version: rds.AuroraPostgresEngineVersion.VER_16_13 }),
      writer: rds.ClusterInstance.serverlessV2('writer', { publiclyAccessible: false }),
      serverlessV2MinCapacity: 0,
      serverlessV2MaxCapacity: 2,
      serverlessV2AutoPauseDuration: cdk.Duration.minutes(10),
      vpc: props.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      securityGroups: [this.dbSecurityGroup],
      defaultDatabaseName: 'uptime',
      credentials: rds.Credentials.fromGeneratedSecret('uptime_admin', { secretName: 'uptime-desk/aurora' }),
      storageEncrypted: true,
      backup: { retention: cdk.Duration.days(1) },
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      deletionProtection: false,
    });

    // --- Files the app and the Knowledge Base read ---
    const kbPrefix = 'kb/';
    new s3deploy.BucketDeployment(this, 'KbDocs', {
      sources: [s3deploy.Source.asset(path.join(REPO, 'data/kb_docs'))],
      destinationBucket: props.dataBucket,
      destinationKeyPrefix: kbPrefix,
      memoryLimit: 512,
    });
    new s3deploy.BucketDeployment(this, 'Manuals', {
      sources: [s3deploy.Source.asset(path.join(REPO, 'data/raw/manuals'))],
      destinationBucket: props.dataBucket,
      destinationKeyPrefix: 'manuals/',
      memoryLimit: 512,
    });
    new s3deploy.BucketDeployment(this, 'Models', {
      sources: [s3deploy.Source.asset(path.join(REPO, 'data/models'))],
      destinationBucket: props.dataBucket,
      destinationKeyPrefix: 'models/',
    });

    // Recorded episodes the replay reads (Release 1 lab and field days) and the scenario catalog.
    new s3deploy.BucketDeployment(this, 'Episodes', {
      sources: [s3deploy.Source.asset(path.join(REPO, 'data/deploy/episodes'))],
      destinationBucket: props.dataBucket,
      destinationKeyPrefix: 'episodes/',
      memoryLimit: 2048,
      ephemeralStorageSize: cdk.Size.gibibytes(2),
    });
    new s3deploy.BucketDeployment(this, 'Catalog', {
      sources: [s3deploy.Source.asset(path.join(REPO, 'data/deploy'), { exclude: ['episodes', 'episodes/**'] })],
      destinationBucket: props.dataBucket,
      destinationKeyPrefix: 'catalog/',
    });

    // --- Schema and configuration seed, applied on every deploy (idempotent) ---
    const dbInit = new lambda.DockerImageFunction(this, 'DbInit', {
      code: lambda.DockerImageCode.fromImageAsset(REPO, {
        file: 'services/Dockerfile', platform: cdk.aws_ecr_assets.Platform.LINUX_ARM64, cmd: ['handlers.db_init.handler'],
      }),
      architecture: lambda.Architecture.ARM_64, memorySize: 512, timeout: cdk.Duration.minutes(5),
      vpc: props.vpc, vpcSubnets: props.lambdaSubnets, securityGroups: [props.lambdaSg],
      environment: { DB_SECRET_ARN: this.cluster.secret!.secretArn },
      logRetention: logs.RetentionDays.ONE_WEEK,
    });
    this.cluster.secret!.grantRead(dbInit);
    const provider = new cr.Provider(this, 'DbInitProvider', { onEventHandler: dbInit });
    const init = new cdk.CustomResource(this, 'DbInitResource', {
      serviceToken: provider.serviceToken,
      properties: { schemaHash: cdk.FileSystem.fingerprint(path.join(REPO, 'services/api')),
                    configHash: cdk.FileSystem.fingerprint(path.join(REPO, 'config')),
                 seedHash: cdk.FileSystem.fingerprint(path.join(REPO, 'pipelines/evaluation/gate4_seed.py')) },
    });
    init.node.addDependency(this.cluster);

    // --- S3 Vectors index (1024-dim Titan v2, cosine) and the Knowledge Base ---
    const vectorBucket = new s3vectors.CfnVectorBucket(this, 'VectorBucket', {
      vectorBucketName: `uptime-desk-kb-${stack.account}`,
    });
    const index = new s3vectors.CfnIndex(this, 'VectorIndex', {
      vectorBucketName: vectorBucket.vectorBucketName!,
      indexName: 'manual-pages',
      dataType: 'float32',
      dimension: 1024,
      distanceMetric: 'cosine',
      // Bedrock stores the chunk text and its metadata JSON here; they are too large to filter on.
      metadataConfiguration: { nonFilterableMetadataKeys: ['AMAZON_BEDROCK_TEXT', 'AMAZON_BEDROCK_METADATA'] },
    });
    index.addResourceDependency(vectorBucket);

    const embeddingModelArn = `arn:aws:bedrock:${stack.region}::foundation-model/amazon.titan-embed-text-v2:0`;
    const kbRole = new iam.Role(this, 'KbRole', {
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com', {
        conditions: { StringEquals: { 'aws:SourceAccount': stack.account } },
      }),
      description: 'Bedrock Knowledge Base: read manual chunks, embed with Titan v2, write S3 Vectors',
    });
    props.dataBucket.grantRead(kbRole, `${kbPrefix}*`);
    kbRole.addToPolicy(new iam.PolicyStatement({ actions: ['bedrock:InvokeModel'], resources: [embeddingModelArn] }));
    kbRole.addToPolicy(new iam.PolicyStatement({
      actions: ['s3vectors:PutVectors', 's3vectors:GetVectors', 's3vectors:DeleteVectors', 's3vectors:QueryVectors',
                's3vectors:GetIndex'],
      resources: [index.attrIndexArn],
    }));

    const kb = new bedrock.CfnKnowledgeBase(this, 'ManualsKb', {
      name: 'uptime-desk-manuals',
      description: 'OEM manual pages, one chunk per page section, page metadata on every chunk',
      roleArn: kbRole.roleArn,
      knowledgeBaseConfiguration: {
        type: 'VECTOR',
        vectorKnowledgeBaseConfiguration: {
          embeddingModelArn,
          embeddingModelConfiguration: { bedrockEmbeddingModelConfiguration: { dimensions: 1024, embeddingDataType: 'FLOAT32' } },
        },
      },
      storageConfiguration: { type: 'S3_VECTORS', s3VectorsConfiguration: { indexArn: index.attrIndexArn } },
    });
    kb.node.addDependency(kbRole);
    new bedrock.CfnDataSource(this, 'ManualsSource', {
      knowledgeBaseId: kb.attrKnowledgeBaseId,
      name: 'manual-chunks',
      dataSourceConfiguration: {
        type: 'S3',
        s3Configuration: { bucketArn: props.dataBucket.bucketArn, inclusionPrefixes: [kbPrefix] },
      },
      // Files are already page-aligned chunks; Bedrock must not re-chunk them.
      vectorIngestionConfiguration: { chunkingConfiguration: { chunkingStrategy: 'NONE' } },
      dataDeletionPolicy: 'DELETE',
    });
    this.knowledgeBaseId = kb.attrKnowledgeBaseId;

    // --- Guardrail on diagnosis and assistant calls ---
    const guardrail = new bedrock.CfnGuardrail(this, 'Guardrail', {
      name: 'uptime-desk',
      description: 'Blocks prompt attacks and harmful content on diagnosis and technician assistant calls',
      blockedInputMessaging: 'This request was blocked by the Uptime Desk guardrail.',
      blockedOutputsMessaging: 'This response was blocked by the Uptime Desk guardrail.',
      contentPolicyConfig: {
        filtersConfig: [
          { type: 'PROMPT_ATTACK', inputStrength: 'HIGH', outputStrength: 'NONE' },
          { type: 'HATE', inputStrength: 'HIGH', outputStrength: 'HIGH' },
          { type: 'INSULTS', inputStrength: 'HIGH', outputStrength: 'HIGH' },
          { type: 'SEXUAL', inputStrength: 'HIGH', outputStrength: 'HIGH' },
          { type: 'VIOLENCE', inputStrength: 'MEDIUM', outputStrength: 'MEDIUM' },
          { type: 'MISCONDUCT', inputStrength: 'HIGH', outputStrength: 'HIGH' },
        ],
      },
      sensitiveInformationPolicyConfig: {
        piiEntitiesConfig: [
          { type: 'EMAIL', action: 'ANONYMIZE' },
          { type: 'PHONE', action: 'ANONYMIZE' },
        ],
      },
    });
    const gv = new bedrock.CfnGuardrailVersion(this, 'GuardrailVersion', { guardrailIdentifier: guardrail.attrGuardrailId });
    this.guardrailId = guardrail.attrGuardrailId;
    this.guardrailVersion = gv.attrVersion;

    // --- Parameters the services and the app read at runtime ---
    const params: Record<string, string> = {
      '/uptime-desk/kb/id': kb.attrKnowledgeBaseId,
      '/uptime-desk/guardrail/id': guardrail.attrGuardrailId,
      '/uptime-desk/guardrail/version': gv.attrVersion,
      '/uptime-desk/db/secret-arn': this.cluster.secret!.secretArn,
      '/uptime-desk/db/endpoint': this.cluster.clusterEndpoint.hostname,
      '/uptime-desk/data/bucket': props.dataBucket.bucketName,
    };
    for (const [name, value] of Object.entries(params)) {
      new ssm.StringParameter(this, `Param${name.replace(/[^A-Za-z0-9]/g, '')}`, { parameterName: name, stringValue: value });
    }
    new cdk.CfnOutput(stack, 'KnowledgeBaseId', { value: kb.attrKnowledgeBaseId });
    new cdk.CfnOutput(stack, 'AuroraEndpoint', { value: this.cluster.clusterEndpoint.hostname });
    new cdk.CfnOutput(stack, 'GuardrailId', { value: guardrail.attrGuardrailId });
  }
}
