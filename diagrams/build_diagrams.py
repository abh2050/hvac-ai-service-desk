"""Write the draw.io diagrams (AWS4 shape library) from code, so layout changes stay reviewable.

Usage: python3 diagrams/build_diagrams.py && scripts/export-diagrams.sh
Every component and table here exists in infra/ or services/api/schema.sql.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parent
INK, MUTED, ACCENT, DEMO = "#232F3E", "#5A6B7B", "#E8590C", "#7B3FE4"

# AWS Architecture Icons category colors.
COLOR = {"compute": "#ED7100", "database": "#C925D1", "analytics": "#8C4FFF", "integration": "#E7157B",
         "ml": "#01A88D", "security": "#DD344C", "storage": "#7AA116", "management": "#E7157B",
         "frontend": "#DD344C", "network": "#8C4FFF", "containers": "#ED7100"}


class Diagram:
    def __init__(self, name: str, width: int, height: int):
        self.name, self.width, self.height = name, width, height
        self.cells: list[str] = []
        self.n = 1

    def _id(self) -> str:
        self.n += 1
        return f"c{self.n}"

    def add(self, value: str, style: str, x: float, y: float, w: float, h: float) -> str:
        i = self._id()
        self.cells.append(f'<mxCell id="{i}" value="{escape(value)}" style="{style}" vertex="1" parent="1">'
                          f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        return i

    def edge(self, src: str, dst: str, label: str = "", style: str = "", points: list[tuple[float, float]] | None = None,
             step: str | None = None, at: float = -0.1, label_dy: float = 0) -> str:
        i = self._id()
        base = (f"edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeColor={INK};strokeWidth=1.5;endArrow=block;"
                f"endFill=1;fontSize=11;fontColor={INK};labelBackgroundColor=#FFFFFF;")
        pts = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in points or [])
        arr = f'<Array as="points">{pts}</Array>' if pts else ""
        off = f'<mxPoint y="{label_dy}" as="offset"/>' if label_dy else ""
        geo = f'<mxGeometry relative="1" as="geometry">{arr}{off}</mxGeometry>'
        self.cells.append(f'<mxCell id="{i}" value="{escape(label)}" style="{base}{style}" edge="1" parent="1" '
                          f'source="{src}" target="{dst}">{geo}</mxCell>')
        if step:      # numbered flow badge on the edge
            j = self._id()
            self.cells.append(f'<mxCell id="{j}" value="{step}" style="ellipse;html=1;fillColor={ACCENT};strokeColor=#FFFFFF;'
                              f'strokeWidth=2;fontColor=#FFFFFF;fontStyle=1;fontSize=12;" vertex="1" connectable="0" parent="{i}">'
                              f'<mxGeometry x="{at}" width="24" height="24" relative="1" as="geometry">'
                              f'<mxPoint x="-12" y="-12" as="offset"/></mxGeometry></mxCell>')
        return i

    # --- AWS shapes ---
    def icon(self, label: str, res: str, cat: str, x: float, y: float, size: int = 56, sub: str = "") -> str:
        text = f"<b>{escape(label)}</b>" + (f"<br><font color='{MUTED}' style='font-size:10px'>{escape(sub).replace('&lt;br&gt;', '<br>')}</font>" if sub else "")
        style = (f"sketch=0;outlineConnect=0;fontColor={INK};gradientColor=none;fillColor={COLOR[cat]};strokeColor=#ffffff;"
                 f"dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=11;aspect=fixed;"
                 f"shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{res};")
        i = self._id()
        self.cells.append(f'<mxCell id="{i}" value="{escape(text)}" style="{style}" vertex="1" parent="1">'
                          f'<mxGeometry x="{x}" y="{y}" width="{size}" height="{size}" as="geometry"/></mxCell>')
        return i

    def user(self, label: str, x: float, y: float, sub: str = "") -> str:
        text = f"<b>{escape(label)}</b>" + (f"<br><font color='{MUTED}' style='font-size:10px'>{escape(sub).replace('&lt;br&gt;', '<br>')}</font>" if sub else "")
        style = (f"sketch=0;outlineConnect=0;fontColor={INK};fillColor={INK};strokeColor=none;dashed=0;verticalLabelPosition=bottom;"
                 f"verticalAlign=top;align=center;html=1;fontSize=11;aspect=fixed;shape=mxgraph.aws4.user;")
        i = self._id()
        self.cells.append(f'<mxCell id="{i}" value="{escape(text)}" style="{style}" vertex="1" parent="1">'
                          f'<mxGeometry x="{x}" y="{y}" width="48" height="48" as="geometry"/></mxCell>')
        return i

    def group(self, label: str, kind: str, x: float, y: float, w: float, h: float) -> str:
        kinds = {
            "cloud": f"grIcon=mxgraph.aws4.group_aws_cloud_alt;strokeColor={INK};fillColor=none;fontColor={INK};",
            "region": "grIcon=mxgraph.aws4.group_region;strokeColor=#00A4A6;fillColor=none;fontColor=#147EBA;dashed=1;",
            "vpc": "grIcon=mxgraph.aws4.group_vpc2;strokeColor=#8C4FFF;fillColor=none;fontColor=#8C4FFF;",
            "public": "grIcon=mxgraph.aws4.group_security_group;grStroke=0;strokeColor=#7AA116;fillColor=#F2F6E8;fontColor=#248814;",
            "private": "grIcon=mxgraph.aws4.group_security_group;grStroke=0;strokeColor=#00A4A6;fillColor=#E6F6F7;fontColor=#147EBA;",
            "zone": f"grIcon=mxgraph.aws4.group_on_premise;strokeColor={MUTED};fillColor=#FAFAFA;fontColor={MUTED};dashed=1;",
        }
        style = ("points=[];outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=12;fontStyle=1;container=0;"
                 "pointerEvents=0;collapsible=0;recursiveResize=0;shape=mxgraph.aws4.group;verticalAlign=top;align=left;"
                 "spacingLeft=30;dashed=0;" + kinds[kind])
        return self.add(label, style, x, y, w, h)

    def note(self, text: str, x: float, y: float, w: float, h: float, color: str = MUTED, size: int = 11, bold=False) -> str:
        return self.add(text, f"text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize={size};fontColor={color};"
                              f"fontStyle={1 if bold else 0};", x, y, w, h)

    def box(self, text: str, x: float, y: float, w: float, h: float, fill="#FFFFFF", stroke=INK, shape="rounded=1;arcSize=12;",
            size=12, bold=False, font=INK) -> str:
        return self.add(text, f"{shape}whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};fontColor={font};"
                              f"fontSize={size};fontStyle={1 if bold else 0};strokeWidth=1.5;", x, y, w, h)

    def write(self) -> Path:
        xml = (f'<mxfile host="build_diagrams.py"><diagram name="{self.name}" id="{self.name}">'
               f'<mxGraphModel dx="{self.width}" dy="{self.height}" grid="0" gridSize="10" guides="1" tooltips="1" connect="1" '
               f'arrows="1" fold="1" page="1" pageScale="1" pageWidth="{self.width}" pageHeight="{self.height}" math="0" shadow="0" '
               f'background="#FFFFFF"><root><mxCell id="0"/><mxCell id="1" parent="0"/>{"".join(self.cells)}</root>'
               f'</mxGraphModel></diagram></mxfile>')
        p = OUT / f"{self.name}.drawio"
        p.write_text(xml)
        return p


def anchor(d: Diagram, x: float, y: float) -> str:
    """Invisible point for sequence-diagram arrows."""
    return d.add("", "shape=waypoint;fillColor=none;strokeColor=none;size=1;", x, y, 1, 1)


def aws_architecture() -> Path:
    d = Diagram("aws-architecture", 1800, 1160)
    d.note("Uptime Desk on AWS, us-east-2", 20, 14, 900, 30, INK, 20, True)
    d.note("Orange badges follow one incident from replay to dispatch. The demo profile (scripts/demo-up.sh) adds the "
           "replay and detection lane and the Fargate task; everything else is the always-on idle profile.",
           20, 44, 1500, 20, MUTED, 12)
    mgr = d.user("Manager", 60, 196)
    tech = d.user("Technician or MCP client", 60, 312)
    d.box("<b>LBNL recorded data</b><br><font style='font-size:10px' color='#5A6B7B'>lab and field CSV, uploaded<br>once to S3, "
          "read by the replay Lambda</font>", 20, 1000, 170, 70, "#FFFFFF", MUTED, "shape=note;size=14;", 11)

    d.group("AWS Cloud", "cloud", 200, 90, 1580, 1050)
    d.group("Region us-east-2", "region", 215, 125, 1550, 1000)

    d.group("Front door", "zone", 235, 160, 780, 175)
    amp = d.icon("Amplify Hosting", "amplify", "frontend", 280, 196, sub="React app, 8 pages")
    api = d.icon("API Gateway", "api_gateway", "integration", 460, 196, sub="HTTP API, 5 req/s")
    cog = d.icon("Cognito", "cognito", "security", 640, 196, sub="user pool, 2 groups")
    agw = d.icon("AgentCore Gateway", "bedrock", "ml", 900, 196, sub="MCP, JWT, interceptor")

    d.group("Replay and detection (demo profile)", "zone", 235, 375, 1055, 185)
    rsm = d.icon("Step Functions", "step_functions", "integration", 250, 420, sub="replay machine")
    rpl = d.icon("Lambda: replay", "lambda", "compute", 370, 420, sub="4 h per second")
    kin = d.icon("Kinesis Data Streams", "kinesis_data_streams", "analytics", 560, 420, sub="24 h retention")
    det = d.icon("Lambda: detect", "lambda", "compute", 720, 420, sub="rules + XGBoost")
    evb = d.icon("EventBridge", "eventbridge", "integration", 1000, 420, sub="Window, EndOfDay")
    csm = d.icon("Step Functions", "step_functions", "integration", 1180, 420, sub="case machine")

    d.group("VPC, no NAT gateway", "vpc", 235, 615, 1055, 490)
    d.group("Isolated subnet, one AZ", "private", 255, 655, 800, 290)
    l_api = d.icon("Lambda: API", "lambda", "compute", 460, 700, sub="FastAPI + Mangum")
    l_diag = d.icon("Lambda: diagnose", "lambda", "compute", 640, 700, sub="propose, retrieve, cite")
    l_ver = d.icon("Lambda: verify, draft", "lambda", "compute", 780, 700, sub="quote + entailment")
    l_mcp = d.icon("Lambda: MCP tools", "lambda", "compute", 900, 700, sub="ownership checks")
    s3e = d.icon("S3 gateway endpoint", "endpoints", "network", 300, 840, 44, sub="free")
    eps = d.icon("Interface endpoints", "endpoints", "network", 600, 840, 44, sub="bedrock-runtime, bedrock-agent-runtime,<br>secretsmanager, states")
    d.group("Public subnet", "public", 1075, 655, 195, 290)
    far = d.icon("Fargate: OR-Tools", "fargate", "containers", 1180, 700, sub="public IP, no inbound")
    d.group("Isolated subnets, two AZs", "private", 255, 965, 1015, 120)
    aur = d.icon("Aurora PostgreSQL", "aurora", "database", 640, 985, 52, sub="Serverless v2, 0 to 2 ACU")

    d.group("Managed AI, data, and operations", "zone", 1320, 160, 430, 945)
    bed = d.icon("Bedrock models", "bedrock", "ml", 1380, 196, sub="gpt-oss-120b, gpt-oss-20b")
    kb = d.icon("Knowledge Base", "bedrock", "ml", 1600, 196, sub="S3 Vectors, Titan v2")
    d.icon("Guardrail", "bedrock", "ml", 1380, 370, sub="on every model call")
    d.icon("S3", "s3", "storage", 1600, 370, sub="episodes, manuals, model")
    d.icon("Secrets Manager", "secrets_manager", "security", 1380, 540, sub="Aurora credentials")
    d.icon("Systems Manager", "systems_manager", "management", 1600, 540, sub="Parameter Store")
    d.icon("CloudWatch", "cloudwatch_2", "management", 1380, 710, sub="dashboard, EMF metrics")
    d.icon("ECR", "ecr", "containers", 1600, 710, sub="one arm64 image")
    d.note("The diagnose and verify Lambdas reach Bedrock only through the interface endpoints. "
           "The Fargate task reaches ECR and Aurora without a NAT gateway.", 1345, 880, 380, 80, MUTED, 11)

    d.edge(mgr, amp, "sign in", step="1", at=-0.6)
    d.edge(amp, api, "JWT")
    d.edge(api, cog, "verify JWT", style="dashed=1;")
    d.edge(api, l_api, "", step="2", style="exitX=0.5;exitY=1;entryX=0.5;entryY=0;", at=0.75)
    d.edge(l_api, rsm, "start replay", style="exitX=0;exitY=0.5;entryX=0;entryY=0.5;", points=[(225, 728), (225, 448)])
    d.edge(rsm, rpl, "", step="3")
    d.edge(rpl, kin, "")
    d.edge(kin, det, "", step="4")
    d.edge(det, evb, "events")
    d.edge(evb, csm, "", step="5")
    d.edge(csm, l_diag, "", step="6", style="exitX=0;exitY=1;entryX=0.5;entryY=0;", points=[(1180, 590), (668, 590)], at=0.3)
    d.edge(l_diag, l_ver, "")
    d.edge(l_diag, eps, "", style="exitX=0.5;exitY=1;entryX=0.5;entryY=0;")
    d.edge(eps, bed, "private link", step="7", style="exitX=1;exitY=0.5;entryX=0;entryY=0.5;",
           points=[(1065, 862), (1065, 955), (1305, 955), (1305, 224)], at=0.2)
    d.edge(l_ver, aur, "draft order", step="8", style="exitX=0.5;exitY=1;entryX=1;entryY=0.25;", points=[(808, 998)])
    d.edge(csm, far, "approved", step="9", style="exitX=0.5;exitY=1;entryX=0.5;entryY=0;", at=0.5)
    d.edge(far, aur, "assignment", style="exitX=1;exitY=0.5;entryX=1;entryY=0.75;", points=[(1255, 728), (1255, 1024)])
    d.edge(tech, agw, "ask", step="10", style="entryX=0.5;entryY=1;", points=[(860, 336), (928, 336)])
    d.edge(agw, l_mcp, "", style="exitX=1;exitY=0.5;entryX=1;entryY=0.5;", points=[(980, 224), (980, 728)])
    d.edge(l_mcp, aur, "own jobs only", style="exitX=0.5;exitY=1;entryX=1;entryY=0.5;", points=[(928, 1011)])
    return d.write()


def network() -> Path:
    d = Diagram("network", 1500, 940)
    d.note("Network: private by default, no NAT gateway", 20, 14, 1000, 30, INK, 20, True)
    d.note("foundation-stack.ts. Lambdas that touch Aurora run in one isolated subnet and reach AWS APIs through interface "
           "endpoints. Security groups allow only the ports below.", 20, 44, 1400, 20, MUTED, 12)
    d.group("VPC, 2 AZs, natGateways: 0", "vpc", 30, 90, 1060, 820)
    d.group("Public subnet, AZ a", "public", 60, 140, 300, 220)
    far = d.icon("Fargate: OR-Tools task", "fargate", "containers", 170, 190, sub="public IP, SG: no inbound")
    d.group("Public subnet, AZ b", "public", 60, 390, 300, 120)
    d.note("unused by tasks", 90, 440, 200, 20, MUTED)
    d.group("Isolated subnet, AZ a: in-VPC Lambdas and endpoints", "private", 390, 140, 670, 410)
    lam = d.icon("In-VPC Lambdas (11)", "lambda", "compute", 470, 190, sub="API, case steps, diagnose,<br>verify, MCP tools, db init")
    s3e = d.icon("S3 gateway endpoint", "endpoints", "network", 960, 196, 44, sub="free, route table")
    eps = d.icon("Interface endpoints", "endpoints", "network", 474, 380, 48, sub="bedrock-runtime<br>bedrock-agent-runtime<br>secretsmanager, states")
    d.box("<b>Endpoint security group</b><br>ingress 443 from VPC CIDR", 640, 300, 300, 50, "#FFFFFF", "#DD344C", "rounded=1;", 11)
    d.box("<b>Lambda security group</b><br>egress 443 to VPC CIDR (endpoints)<br>egress 5432 to VPC CIDR (Aurora)<br>"
          "egress 443 to S3 prefix list pl-7ba54012<br>no other egress", 640, 420, 300, 110, "#FFFFFF", "#DD344C",
          "rounded=1;", 11)
    d.group("Isolated subnets, AZ a and AZ b (RDS needs two)", "private", 60, 570, 1000, 310)
    aur = d.icon("Aurora PostgreSQL 16", "aurora", "database", 250, 640, 56, sub="Serverless v2, writer only,<br>not publicly accessible")
    d.box("<b>Database security group</b><br>ingress 5432 from VPC CIDR only", 450, 650, 330, 60, "#FFFFFF", "#DD344C",
          "rounded=1;", 11)
    d.box("<b>Why one AZ for endpoints</b><br>Each interface endpoint costs about $7.30 per month per AZ (AWS list price, "
          "not measured). Four endpoints in one AZ instead of two saves about $29 per month. The trade-off is that the "
          "in-VPC Lambdas stop if AZ a fails.", 450, 740, 590, 110, "#FFF9DB", "#E67700", "rounded=1;", 11)
    d.group("AWS managed services (regional)", "zone", 1120, 90, 350, 820)
    bed = d.icon("Bedrock runtime", "bedrock", "ml", 1260, 150, sub="InvokeModel, ApplyGuardrail")
    kb = d.icon("Bedrock agent runtime", "bedrock", "ml", 1260, 300, sub="Knowledge Base Retrieve")
    sec = d.icon("Secrets Manager", "secrets_manager", "security", 1260, 450, sub="Aurora secret")
    sfn = d.icon("Step Functions", "step_functions", "integration", 1260, 600, sub="SendTaskSuccess, history")
    s3 = d.icon("S3", "s3", "storage", 1260, 750, sub="episodes, manuals")
    ecr = d.icon("ECR, CloudWatch Logs", "ecr", "containers", 170, 760, 44, sub="Fargate pulls over its public IP")
    d.edge(lam, eps, "443")
    for target, ty in ((bed, 178), (kb, 328), (sec, 478), (sfn, 628)):
        d.edge(eps, target, "", style="exitX=1;exitY=0.5;entryX=0;entryY=0.5;", points=[(1110, 404), (1110, ty)])
    d.edge(lam, aur, "5432", style="exitX=0;exitY=0.5;entryX=0.5;entryY=0;", points=[(420, 218), (420, 610), (278, 610)])
    d.edge(lam, s3e, "443")
    d.edge(s3e, s3, "", style="exitX=1;exitY=0.5;entryX=0;entryY=0.5;", points=[(1085, 218), (1085, 778)])
    d.edge(far, aur, "5432", style="exitX=0.5;exitY=1;entryX=0;entryY=0.5;", points=[(198, 668)])
    d.edge(far, ecr, "", style="dashed=1;exitX=0;exitY=0.5;entryX=0;entryY=0.5;", points=[(90, 218), (90, 782)])
    return d.write()


def security() -> Path:
    d = Diagram("security", 1560, 1000)
    d.note("Identity and access: every request carries a verified identity", 20, 14, 1100, 30, INK, 20, True)
    d.note("Cognito issues the identity. API Gateway and AgentCore Gateway verify it. Code, not the model, decides "
           "what each identity may read. Each Lambda role names its own resources.", 20, 44, 1400, 20, MUTED, 12)
    mgr = d.user("Manager", 60, 140, "group: manager")
    tech = d.user("Technician T01", 60, 330, "group: technician,<br>custom:technician_id = T01")
    cog = d.icon("Cognito user pool", "cognito", "security", 300, 220, sub="SRP sign-in, ID token,<br>sign-up hidden")
    api = d.icon("API Gateway", "api_gateway", "integration", 560, 140, sub="JWT authorizer on every route<br>except OPTIONS preflight")
    agw = d.icon("AgentCore Gateway", "bedrock", "ml", 560, 340, sub="CUSTOM_JWT, audience = client id")
    icp = d.icon("Interceptor Lambda", "lambda", "compute", 860, 340, sub="drops client caller_context,<br>injects token identity")
    l_api = d.icon("Lambda: API", "lambda", "compute", 860, 140, sub="manager_only() on approve,<br>reject, start replay")
    tools = d.icon("Lambda: MCP tools", "lambda", "compute", 1160, 340, sub="owner_of(work order) ==<br>caller technician_id")
    aur = d.icon("Aurora: audit_log", "aurora", "database", 1162, 140, 52, sub="every denied call recorded")
    cw = d.icon("CloudWatch", "cloudwatch_2", "management", 1420, 140, sub="DeniedCalls metric")
    d.edge(mgr, cog, "sign in", style="exitX=1;exitY=0.5;entryX=0;entryY=0.25;", points=[(240, 164), (240, 234)])
    d.edge(tech, cog, "sign in", style="exitX=1;exitY=0.5;entryX=0;entryY=0.75;", points=[(240, 354), (240, 262)])
    d.edge(cog, api, "ID token", style="exitX=1;exitY=0.25;entryX=0;entryY=0.5;", points=[(480, 234), (480, 168)])
    d.edge(cog, agw, "ID token", style="exitX=1;exitY=0.75;entryX=0;entryY=0.5;", points=[(480, 262), (480, 368)])
    d.edge(api, l_api, "claims")
    d.edge(agw, icp, "REQUEST")
    d.edge(icp, tools, "caller_context")
    d.edge(l_api, aur, "")
    d.edge(tools, aur, "deny + audit")
    d.edge(aur, cw, "EMF")
    d.note("IAM: one role per Lambda, scoped to named resources", 40, 520, 900, 26, INK, 15, True)
    rows = [("Lambda: API", "states:StartExecution on the replay machine; DescribeExecution, GetExecutionHistory on both "
             "machines; SendTaskSuccess and SendTaskFailure on * (task tokens have no ARN); InvokeModel on the two gpt-oss "
             "models; ApplyGuardrail on one guardrail; Retrieve on one Knowledge Base; S3 read on episodes/* and manuals/*; "
             "read on the Aurora secret"),
            ("Lambda: replay", "S3 read on episodes/*; Kinesis write on one stream"),
            ("Lambda: detect", "S3 read on models/*; events:PutEvents on the default bus"),
            ("Lambdas: diagnose, verify", "InvokeModel on the two gpt-oss models; ApplyGuardrail on one guardrail; Retrieve on "
             "one Knowledge Base (diagnose only); read on the Aurora secret"),
            ("Lambda: MCP tools", "Retrieve on one Knowledge Base; read on the Aurora secret"),
            ("Fargate task role", "read on the Aurora secret"),
            ("Knowledge Base role", "S3 read on the KB prefix; InvokeModel on Titan embeddings v2; s3vectors Put, Get, Delete, "
             "Query on one index")]
    y = 560
    for who, what in rows:
        d.box(f"<b>{who}</b>", 40, y, 220, 44, "#F1F3F5", "#ADB5BD", "rounded=0;", 11)
        d.box(what, 260, y, 1200, 44, "#FFFFFF", "#ADB5BD", "rounded=0;align=left;spacingLeft=8;", 11)
        y += 50
    d.note("Data at rest: S3 block public access, S3-managed encryption, TLS required; Kinesis managed encryption; "
           "Aurora credentials only in Secrets Manager; demo passwords and third-party keys only in SSM SecureString.",
           40, y + 10, 1420, 40, MUTED, 11)
    return d.write()


def case_machine() -> Path:
    d = Diagram("case-state-machine", 1300, 1180)
    d.note("Step Functions: the case machine (uptime-desk-case)", 20, 14, 1000, 30, INK, 20, True)
    d.note("pipeline.ts. Each Lambda task returns facts; Choice states route on them. The approval wait holds a task "
           "token in Aurora until the manager acts or 4 hours pass.", 20, 44, 1250, 20, MUTED, 12)
    st = lambda t, y, x=470, w=300, h=50, fill="#FFFFFF", stroke=INK: d.box(t, x, y, w, h, fill, stroke, "rounded=1;arcSize=40;", 12)  # noqa: E731
    ch = lambda t, y, x=530: d.box(t, x, y, 180, 70, "#FFFFFF", INK, "rhombus;", 11)  # noqa: E731
    s = st("<b>Start</b>: EventBridge EndOfDay event", 90, fill="#F1F3F5")
    w = st("<b>LetWindowsLand</b>  Wait 15 s", 170)
    dd = st("<b>DecideDay</b>  Lambda, policies 1 and 2", 250)
    c1 = ch("DiagnoseNeeded?", 330)
    nd = st("NoDiagnosis  Succeed", 345, x=860, w=260, fill="#EBFBEE", stroke="#2B8A3E")
    dc = st("<b>DiagnoseCase</b>  Lambda, timeout 5 min", 430)
    vd = st("<b>VerifyAndDraft</b>  Lambda, timeout 5 min", 510)
    c2 = ch("NeedsApproval?", 590)
    na = st("NoApprovalNeeded  Succeed<br>(blocked, manual or operations review)", 597, x=860, w=300, h=56, fill="#FFF9DB", stroke="#E67700")
    wa = st("<b>WaitForApproval</b>  Lambda StoreToken,<br>waitForTaskToken, timeout 4 h", 690, h=60, fill="#FFF4EC", stroke=ACCENT)
    api = d.icon("Lambda: API", "lambda", "compute", 140, 690, sub="approve: SendTaskSuccess<br>reject: SendTaskFailure")
    mg = d.user("Manager", 30, 700)
    esc = st("<b>EscalateExpired</b>  Lambda, policy 9", 690, x=860, w=300, fill="#FDECEC", stroke="#C92A2A")
    rj = st("Rejected  Succeed", 800, x=860, w=300, fill="#FDECEC", stroke="#C92A2A")
    dp = st("<b>DispatchOrTools</b>  ECS RunTask (.sync),<br>Fargate, OR-Tools CP-SAT", 800, h=60)
    dn = st("<b>Done</b>  Succeed", 910, fill="#EBFBEE", stroke="#2B8A3E")
    for a, b in [(s, w), (w, dd), (dd, c1), (dc, vd), (vd, c2), (dp, dn)]:
        d.edge(a, b, "")
    d.edge(c1, dc, "diagnose = true")
    d.edge(c1, nd, "otherwise")
    d.edge(c2, wa, "needs_approval = true")
    d.edge(c2, na, "otherwise")
    d.edge(wa, dp, "task success")
    d.edge(wa, esc, "catch States.Timeout")
    d.edge(wa, rj, "catch Rejected", style="exitX=1;exitY=1;", points=[(800, 750), (800, 825)])
    d.edge(mg, api, "")
    d.edge(api, wa, "task token", style="dashed=1;")
    d.note("Machine timeout 6 h. Logging level ERROR to a log group kept 7 days. The replay machine (uptime-desk-replay) "
           "is separate: it runs the replay Lambda until the recorded day ends, timeout 10 min.", 40, 1000, 1200, 40, MUTED, 11)
    return d.write()


def replay_sequence() -> Path:
    d = Diagram("replay-sequence", 1500, 900)
    d.note("Event-driven replay: one recorded day through the live pipeline", 20, 14, 1200, 30, INK, 20, True)
    d.note("Measured on the hosted app (reports/gate-5.json): median 39.4 s from replay start to a drafted work order, "
           "77.3 s to a dispatched technician, over 8 passing runs.", 20, 44, 1400, 20, MUTED, 12)
    names = ["Manager (app)", "API Lambda", "Replay machine", "Replay Lambda", "Kinesis", "Detect Lambda",
             "EventBridge", "Case machine", "Aurora"]
    xs = [70 + i * 165 for i in range(len(names))]
    for x, n in zip(xs, names):
        d.box(f"<b>{n}</b>", x - 70, 90, 140, 40, "#F1F3F5", "#ADB5BD", "rounded=1;", 11)
        d.add("", f"endArrow=none;dashed=1;html=1;strokeColor=#ADB5BD;shape=line;direction=south;", x - 1, 130, 2, 740)
    msgs = [(0, 1, "POST /runs"), (1, 8, "insert pipeline_runs"), (1, 2, "StartExecution"), (2, 3, "invoke"),
            (3, 4, "PutRecords, 4 recorded h per s"), (4, 5, "batch of sensor rows"), (5, 6, "Window event per hour"),
            (6, 8, "Window Lambda stores detection_windows"), (5, 6, "EndOfDay event"), (6, 7, "start case execution"),
            (7, 8, "cases, work_orders, steps"), (0, 1, "GET /runs/{id} every 3 s"), (1, 7, "GetExecutionHistory")]
    y = 160
    for a, b, label in msgs:
        p, q = anchor(d, xs[a], y), anchor(d, xs[b], y)
        d.edge(p, q, label, style="edgeStyle=none;labelBackgroundColor=none;" + ("dashed=1;" if "every" in label or "History" in label else ""),
               label_dy=-10)
        y += 52
    return d.write()


def rag() -> Path:
    d = Diagram("knowledge-base", 1560, 780)
    d.note("Manual retrieval and citation checks", 20, 14, 1000, 30, INK, 20, True)
    d.note("A quote reaches a work order only if it appears on the cited page and a second model judges that the page "
           "supports it. The database rejects unverified steps.", 20, 44, 1400, 20, MUTED, 12)
    d.note("Ingest, once", 40, 90, 300, 24, INK, 14, True)
    pdf = d.box("<b>8 OEM manual PDFs</b><br><font color='#5A6B7B' style='font-size:10px'>SHA256 in data/SOURCES.md</font>",
                40, 130, 170, 60, "#FFFFFF", MUTED, "shape=note;size=14;", 11)
    pages = d.box("<b>One document per page</b><br><font color='#5A6B7B' style='font-size:10px'>654 pages, chunking NONE,<br>"
                  "metadata: manual_id, page, classes</font>", 260, 125, 210, 70, "#F1F3F5", "#ADB5BD")
    s3 = d.icon("S3", "s3", "storage", 530, 130, 52, sub="kb/ prefix")
    emb = d.icon("Titan text embeddings v2", "bedrock", "ml", 700, 130, 52, sub="1024 dimensions")
    vec = d.icon("S3 Vectors index", "s3", "storage", 900, 130, 52, sub="Knowledge Base storage")
    d.edge(pdf, pages, "")
    d.edge(pages, s3, "")
    d.edge(s3, emb, "ingestion job")
    d.edge(emb, vec, "")
    d.note("Per case, at run time", 40, 290, 300, 24, INK, 14, True)
    case = d.box("<b>Case evidence</b><br><font style='font-size:10px' color='#5A6B7B'>alarm hours, rules fired, feature "
                 "summaries, equipment class</font>", 40, 330, 200, 70, "#F1F3F5", "#ADB5BD")
    pro = d.icon("gpt-oss-120b: propose", "bedrock", "ml", 300, 335, 52, sub="cause, component, query")
    kb = d.icon("Knowledge Base Retrieve", "bedrock", "ml", 500, 335, 52, sub="filter: classes contains<br>equipment class, k = 6")
    cite = d.icon("gpt-oss-120b: cite", "bedrock", "ml", 700, 335, 52, sub="quotes with manual and page")
    ver = d.box("<b>Verifier</b><br>1. trigram coverage of the quote on that page at least 0.6<br>"
                "2. gpt-oss-20b judges entailment<br>3. both must pass", 880, 320, 340, 90, "#FFF4EC", ACCENT)
    pol = d.box("<b>Policy code</b><br>no supported passage: abstain<br>no sourced lockout: block<br>class-only match: "
                "compatibility uncertain", 1260, 320, 260, 90, "#FFFFFF", INK)
    db = d.icon("Aurora: work_order_steps", "aurora", "database", 1364, 500, 52, sub="CHECK (verified)")
    d.edge(case, pro, "")
    d.edge(pro, kb, "manual_query")
    d.edge(kb, cite, "6 pages")
    d.edge(cite, ver, "")
    d.edge(ver, pol, "")
    d.edge(pol, db, "")
    d.edge(vec, kb, "vector search", style="dashed=1;exitX=1;exitY=0.5;entryX=0.5;entryY=0;", points=[(990, 156), (990, 285), (526, 285)])
    d.note("Measured in Gate 2 (reports/gate-2.json, run 3, 92 cases): 88.0% of checked citations supported, against "
           "12.2% for the keyword baseline. On 60 held-out field days (gate-2-holdout.json): 91.5%. The guardrail wraps "
           "every model call.", 40, 600, 1400, 50, MUTED, 12)
    return d.write()


def mcp_sequence() -> Path:
    d = Diagram("mcp-sequence", 1500, 860)
    d.note("Technician question over MCP: identity comes from the token, never from the model", 20, 14, 1400, 30, INK, 20, True)
    d.note("Checked live with real Cognito tokens (reports/gate-5-e2e/mcp-gateway-check.json): no token got 401; "
           "T01 reading T16's order was denied; a spoofed manager claim was replaced and denied.", 20, 44, 1400, 20, MUTED, 12)
    names = ["Technician T01", "MCP client", "AgentCore Gateway", "Interceptor Lambda", "MCP tools Lambda", "Aurora"]
    xs = [100 + i * 250 for i in range(len(names))]
    for x, n in zip(xs, names):
        d.box(f"<b>{n}</b>", x - 85, 90, 170, 40, "#F1F3F5", "#ADB5BD", "rounded=1;", 11)
        d.add("", "endArrow=none;dashed=1;html=1;strokeColor=#ADB5BD;shape=line;direction=south;", x - 1, 130, 2, 680)
    msgs = [(0, 1, "\"read work order WO-...-cdaee1\""),
            (1, 2, "tools/call uptime___get_work_order, Bearer ID token, caller_context: {role: manager}"),
            (2, 2, "validate JWT: issuer, audience"), (2, 3, "REQUEST interception"),
            (3, 2, "body with caller_context replaced: technician T01"), (2, 4, "invoke tool"),
            (4, 5, "owner_of(work order)"), (5, 4, "T16"), (4, 5, "insert audit_log allowed = false"),
            (4, 2, "error: assigned to another technician"), (2, 1, "tool result: denied"),
            (1, 0, "\"I cannot access that work order.\"")]
    y = 160
    for a, b, label in msgs:
        if a == b:
            d.box(label, xs[a] + 10, y - 12, 230, 26, "#FFF4EC", ACCENT, "rounded=1;", 10)
        else:
            p, q = anchor(d, xs[a], y), anchor(d, xs[b], y)
            d.edge(p, q, label, style="edgeStyle=none;labelBackgroundColor=none;" + ("dashed=1;" if b < a else ""), label_dy=-10)
        y += 52
    return d.write()


def deployment() -> Path:
    d = Diagram("deployment", 1500, 860)
    d.note("Infrastructure as code and cost profiles", 20, 14, 1000, 30, INK, 20, True)
    d.note("AWS CDK in TypeScript (aws-cdk-lib 2.274.0), profile awsnew, region us-east-2. Every deploy was preceded by a "
           "posted cdk diff (reports/gate-5-phase*-diff.txt).", 20, 44, 1400, 20, MUTED, 12)
    dev = d.box("<b>Developer laptop</b><br>npx cdk diff, cdk deploy<br>scripts/demo-up.sh, demo-down.sh", 40, 120, 250, 80,
                "#F1F3F5", "#ADB5BD")
    gh = d.box("<b>GitHub: abh2050/hvac-ai-service-desk</b><br>branch main", 40, 300, 250, 60, "#FFFFFF", INK)
    cfn = d.icon("CloudFormation", "cloudformation", "management", 400, 130, 52, sub="CDKToolkit bootstrap v32")
    ecr = d.icon("ECR asset", "ecr", "containers", 400, 290, 52, sub="services/Dockerfile, arm64")
    d.group("UptimeDesk-Foundation: idle profile, always on", "zone", 560, 100, 420, 560)
    for i, (t, sub) in enumerate([("VPC, 4 interface endpoints, S3 gateway endpoint", "network"),
                                  ("Aurora Serverless v2, auto-pause after 10 min", "data"),
                                  ("Bedrock Knowledge Base, Guardrail, S3 bucket", "AI and data"),
                                  ("HTTP API, API Lambda", "api-layer.ts"),
                                  ("AgentCore Gateway, interceptor, MCP tools", "mcp-gateway.ts"),
                                  ("CloudWatch dashboard uptime-desk", "dashboard.ts")]):
        d.box(f"<b>{t}</b><br><font color='#5A6B7B' style='font-size:10px'>{sub}</font>", 580, 140 + i * 82, 380, 64,
              "#FFFFFF", "#ADB5BD", "rounded=1;", 11)
    d.group("UptimeDesk-Demo: demo profile, up only for demos", "zone", 1010, 100, 440, 400)
    for i, t in enumerate(["Kinesis stream", "Replay and detect Lambdas, EventBridge rules", "Case and replay state machines",
                           "ECS cluster, Fargate task definition"]):
        d.box(f"<b>{t}</b>", 1030, 140 + i * 82, 400, 60, "#F3EEFF", DEMO, "rounded=1;", 11)
    amp = d.icon("Amplify Gen 2", "amplify", "frontend", 400, 450, 52, sub="builds app/ on every push")
    ver = d.box("<b>Vercel</b><br>static recorded demo, built from main<br>(no backend, survives teardown)", 40, 470, 250, 70,
                "#FFFFFF", MUTED)
    d.edge(dev, cfn, "cdk deploy")
    d.edge(dev, ecr, "image asset", style="exitX=1;exitY=1;")
    d.edge(cfn, ecr, "", style="dashed=1;endArrow=none;")
    d.edge(gh, amp, "push", style="exitX=1;exitY=1;")
    d.edge(gh, ver, "push", style="exitX=0.5;exitY=1;")
    d.edge(cfn, ecr, "")
    d.box("<b>Cost controls</b><br>Each stack carries a cost-profile tag (idle or demo). No NAT gateway. Aurora pauses at "
          "0 ACU. Kinesis, state machines, and Fargate exist only in the demo stack. Log groups keep 7 days. "
          "Measured model cost: $0.00206 per incident on average (gate-5.json). Idle cost: not measured yet.",
          1010, 540, 440, 140, "#FFF9DB", "#E67700", "rounded=1;", 11)
    return d.write()


def observability() -> Path:
    d = Diagram("observability", 1500, 700)
    d.note("Observability: cost and denial are first-class metrics", 20, 14, 1000, 30, INK, 20, True)
    d.note("services/handlers/metrics.py writes CloudWatch embedded metric format (EMF) lines; no metrics agent and no "
           "PutMetricData calls from inside the VPC.", 20, 44, 1400, 20, MUTED, 12)
    srcs = [("Lambda: diagnose", "StageSeconds{Stage=diagnose}"),
            ("Lambda: verify, draft", "StageSeconds{Stage=verify_and_draft}<br>IncidentModelCostUSD<br>WorkOrders{Status}"),
            ("Lambdas: API, MCP tools", "DeniedCalls{Action}"),
            ("Bedrock", "InputTokenCount, OutputTokenCount per model"),
            ("Step Functions", "ExecutionTime, case machine")]
    cw = d.icon("CloudWatch dashboard uptime-desk", "cloudwatch_2", "management", 900, 300, 64,
                sub="7-day default range, 1-hour periods")
    y = 110
    for name, metric in srcs:
        b = d.box(f"<b>{name}</b><br><font style='font-size:10px' color='#5A6B7B'>{metric}</font>", 60, y, 330, 70,
                  "#FFFFFF", "#ADB5BD", "rounded=1;", 11)
        d.edge(b, cw, "", style="exitX=1;exitY=0.5;entryX=0;entryY=0.5;")
        y += 100
    d.box("<b>What the dashboard answered in Gate 5</b><br>model cost per incident: average $0.00206, range $0.00197 to "
          "$0.00226 over 10 incidents<br>work orders in the batch: 8 draft, 2 blocked<br>denied calls appear per action, "
          "matching the audit_log rows", 1080, 270, 390, 150, "#FFF4EC", ACCENT, "rounded=1;", 11)
    return d.write()


def system_context() -> Path:
    d = Diagram("system-context", 1400, 760)
    d.note("Uptime Desk: system context", 20, 14, 800, 30, INK, 20, True)
    d.note("Who uses the system, what it reads, and what it calls. Dashed borders mark parts that are planned, not built.",
           20, 44, 1100, 20, MUTED, 12)
    core = d.box("<b style='font-size:18px'>Uptime Desk</b><br><br>detects faults in recorded sensor data<br>"
                 "drafts a diagnosis that quotes the manuals<br>waits for a manager's approval<br>"
                 "assigns a qualified technician<br>answers technicians about their own jobs",
                 520, 250, 360, 220, "#FFF4EC", ACCENT, "rounded=1;arcSize=8;", 13)
    mgr = d.user("Service manager", 160, 180, "approves, edits, or rejects work orders")
    tech = d.user("Field technician", 160, 520, "sees own jobs and quoted steps")
    lbnl = d.box("<b>LBNL fault datasets</b><br><font color='#5A6B7B' style='font-size:11px'>recorded building sensor data, "
                 "lab tests and two field rooftop units, with published fault labels</font>", 560, 80, 280, 90, "#FFFFFF", MUTED)
    man = d.box("<b>OEM equipment manuals</b><br><font color='#5A6B7B' style='font-size:11px'>8 public PDFs: Trane, Daikin, "
                "Honeywell, Siemens, Johnson Controls</font>", 560, 560, 280, 90, "#FFFFFF", MUTED)
    llm = d.box("<b>Amazon Bedrock</b><br><font color='#5A6B7B' style='font-size:11px'>gpt-oss-120b, gpt-oss-20b, "
                "Titan text embeddings v2</font>", 1040, 160, 280, 90, "#E6F7F4", "#01A88D")
    mcp = d.box("<b>MCP clients</b><br><font color='#5A6B7B' style='font-size:11px'>any agent that speaks MCP, for example "
                "Claude. Checked with direct JSON-RPC calls.</font>", 1040, 330, 280, 90, "#FFFFFF", INK)
    cop = d.box("<b>Microsoft Copilot Studio agent</b><br><font color='#5A6B7B' style='font-size:11px'>Release 3, planned: "
                "custom connector to the API (docs/copilot.md)</font>", 1040, 500, 280, 90, "#FFFFFF", MUTED,
                "rounded=1;dashed=1;", 12)
    d.edge(mgr, core, "web app, Cognito sign-in", style="exitX=1;exitY=0.5;entryX=0;entryY=0.25;", points=[(320, 204), (320, 305)])
    d.edge(tech, core, "web app or MCP", style="exitX=1;exitY=0.5;entryX=0;entryY=0.75;", points=[(320, 544), (320, 415)])
    d.edge(lbnl, core, "replayed through Kinesis")
    d.edge(man, core, "indexed page by page")
    d.edge(core, llm, "proposals, entailment checks", style="exitX=1;exitY=0.15;", points=[(960, 283), (960, 205)])
    d.edge(mcp, core, "Cognito JWT, own jobs only", style="entryX=1;entryY=0.5;")
    d.edge(cop, core, "planned", style="dashed=1;entryX=1;entryY=0.85;", points=[(960, 545), (960, 437)])
    return d.write()


def fault_flow() -> Path:
    d = Diagram("fault-flow", 1500, 1500)
    d.note("From sensor window to dispatched work order", 20, 14, 900, 30, INK, 20, True)
    d.note("Gray boxes are steps, white diamonds are decisions made by code, the orange box is the only human decision. "
           "P1 to P10 name the decision policies tested in Gate 3.", 20, 44, 1300, 20, MUTED, 12)
    step = lambda t, x, y, w=260, h=56: d.box(t, x, y, w, h, "#F1F3F5", "#ADB5BD")  # noqa: E731
    dec = lambda t, x, y, w=230, h=96: d.box(t, x, y, w, h, "#FFFFFF", INK, "rhombus;", 11)  # noqa: E731
    stop = lambda t, x, y, w=230, h=56, fill="#FDECEC", stroke="#C92A2A": d.box(t, x, y, w, h, fill, stroke,  # noqa: E731
                                                                                 "rounded=1;arcSize=30;", 11)
    C = 520
    a = step("<b>Replay</b>: recorded sensor rows stream through Kinesis at 4 hours per second", C, 90)
    b = step("<b>Detect</b>: each 60-minute window gets the rules baseline and the XGBoost model", C, 180)
    c = dec("Two or more<br>alarm windows<br>in the day?", C + 15, 265)
    c1 = stop("No case opened", 900, 285, fill="#EBFBEE", stroke="#2B8A3E")
    p1 = dec("<b>P1</b> detection<br>confidence high<br>enough?", C + 15, 395)
    p1n = stop("Manual review, not diagnosed", 900, 415, fill="#FFF9DB", stroke="#E67700")
    p2 = dec("<b>P2</b> rules and<br>model agree?", C + 15, 525)
    p2n = d.box("Flag: manager review required", 900, 553, 230, 40, "#FFF9DB", "#E67700", "rounded=1;", 11)
    dg = step("<b>Diagnose</b>: the model proposes a cause, the Knowledge Base returns manual pages, the model quotes them",
              C, 655, 260, 70)
    vf = step("<b>Verify</b>: each quote must appear on its page (P4) and a second model must judge that the page supports it",
              C, 755, 260, 70)
    p3 = dec("<b>P3</b> any supported<br>passage?", C + 15, 860)
    p3n = stop("Insufficient evidence: blocked, manual review", 900, 880, fill="#FDECEC")
    p5 = d.box("<b>P5</b> manual matches the class, not the model: mark compatibility uncertain", 120, 870, 300, 60,
               "#FFF9DB", "#E67700", "rounded=1;", 11)
    ops = dec("Building<br>operations<br>fault?", C + 15, 990)
    opsn = stop("Operations review, no technician sent", 900, 1010, fill="#FFF9DB", stroke="#E67700")
    p6 = dec("<b>P6</b> lockout step<br>quoted from<br>a manual?", C + 15, 1120)
    p6n = stop("Blocked: no sourced lockout step", 900, 1140)
    apv = d.box("<b>Manager reviews the draft</b><br>approve, untick steps, or reject.<br>Free text cannot be added.", C, 1245,
                260, 74, "#FFF4EC", ACCENT, "rounded=1;", 12)
    p9 = stop("<b>P9</b> no answer in 4 hours: escalated, not dispatched", 120, 1255, 300, 56)
    rej = stop("Rejected with a reason", 900, 1260)
    disp = dec("<b>P7, P8</b> OR-Tools<br>finds a qualified,<br>feasible slot?", C + 15, 1345, 230, 100)
    ok = stop("<b>Assigned</b>, with runner-up and reason", C + 15, 1460, 230, 34, "#EBFBEE", "#2B8A3E")
    nok = stop("Escalated unassigned (P7) or reschedule requested (P8)", 900, 1370, 260, 50)
    p10 = d.box("<b>P10</b> a technician asking about another technician's job is denied and audited", 120, 1100, 300, 60,
                "#FDECEC", "#C92A2A", "rounded=1;", 11)
    d.edge(a, b, "")
    d.edge(b, c, "")
    d.edge(c, c1, "no")
    d.edge(c, p1, "yes")
    d.edge(p1, p1n, "no")
    d.edge(p1, p2, "yes")
    d.edge(p2, p2n, "no")
    d.edge(p2, dg, "")
    d.edge(dg, vf, "")
    d.edge(vf, p3, "")
    d.edge(p3, p3n, "no")
    d.edge(p3, ops, "yes")
    d.edge(p3, p5, "", style="dashed=1;endArrow=none;")
    d.edge(ops, opsn, "yes")
    d.edge(ops, p6, "no")
    d.edge(p6, p6n, "no")
    d.edge(p6, apv, "yes")
    d.edge(apv, p9, "timeout", style="dashed=1;")
    d.edge(apv, rej, "reject")
    d.edge(apv, disp, "approve")
    d.edge(disp, ok, "yes")
    d.edge(disp, nok, "no")
    return d.write()


TABLES = {
    "sites": ["site_id PK", "name, town, lat, lon", "criticality", "sla_response_hours", "badge_required, escort_required",
              "allowed_hours"],
    "assets": ["asset_id PK", "site_id FK", "equipment_class", "lbnl_unit, brick_model"],
    "technicians": ["technician_id PK", "cognito_sub UNIQUE", "home, lat, lon", "certs[], shift, days[]", "site_access[]",
                    "escort_cleared"],
    "work_orders": ["work_order_id PK", "asset_id FK", "case_id, run_id", "status, status_reason", "priority, sla_due_at",
                    "route, required_certs[]", "compatibility_uncertain", "detection_disagreement", "approval_task_token",
                    "approved_by, approved_at, edited"],
    "work_order_steps": ["step_id PK", "work_order_id FK", "kind: safety, check, citation", "quote, manual_id, page",
                         "verified CHECK (true)"],
    "dispatch_decisions": ["decision_id PK", "work_order_id FK", "method: ortools or baseline", "technician_id FK",
                           "runner_up_id FK", "start_at, travel, lateness", "reason, scenario_id"],
    "asset_history": ["history_id PK", "asset_id FK", "occurred_at, kind", "summary, source_ref"],
    "audit_log": ["audit_id PK", "actor, actor_role", "action, resource", "allowed", "detail jsonb"],
    "pipeline_runs": ["run_id PK", "episode_id, source_type", "started_by", "replay_execution_arn"],
    "detection_windows": ["run_id FK + window_start PK", "rule_alarm, rules_fired", "rule_hint", "model_prob, model_alarm",
                          "features jsonb"],
    "cases": ["case_id PK", "run_id FK UNIQUE", "asset_id FK", "detection jsonb, route", "diagnosis jsonb", "execution_arn"],
}


def data_model() -> Path:
    d = Diagram("data-model", 1500, 980)
    d.note("Aurora PostgreSQL tables and keys", 20, 14, 900, 30, INK, 20, True)
    d.note("services/api/schema.sql. The database itself refuses unverified steps: work_order_steps.verified has CHECK (verified).",
           20, 44, 1300, 20, MUTED, 12)
    pos = {"sites": (40, 100), "assets": (330, 100), "technicians": (40, 420), "asset_history": (330, 330),
           "work_orders": (620, 100), "work_order_steps": (940, 100), "dispatch_decisions": (620, 520),
           "audit_log": (40, 740), "pipeline_runs": (1220, 330), "detection_windows": (1220, 520), "cases": (940, 400)}
    ids = {}
    for name, cols in TABLES.items():
        x, y = pos[name]
        w, h = (250 if name not in ("work_orders", "dispatch_decisions") else 280), 30 + 22 * len(cols)
        rows = "".join(f"<div style='padding:2px 8px;border-top:1px solid #E9ECEF;text-align:left'>"
                       f"{'<b>' if 'PK' in c else ''}{escape(c)}{'</b>' if 'PK' in c else ''}</div>" for c in cols)
        hdr = "#FFF4EC" if name in ("work_orders", "work_order_steps") else "#F1F3F5"
        ids[name] = d.add(f"<div style='background:{hdr};padding:6px 8px;font-weight:bold;text-align:left'>{name}</div>{rows}",
                          f"rounded=0;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor={INK};fontColor={INK};fontSize=11;"
                          f"verticalAlign=top;align=left;spacing=0;overflow=fill;", x, y, w, h)
    fk = "endArrow=ERmany;startArrow=ERone;endFill=0;startFill=0;"
    for parent, child in [("sites", "assets"), ("assets", "work_orders"), ("assets", "asset_history"),
                          ("work_orders", "work_order_steps"), ("work_orders", "dispatch_decisions"),
                          ("technicians", "dispatch_decisions"), ("pipeline_runs", "detection_windows"),
                          ("pipeline_runs", "cases")]:
        d.edge(ids[parent], ids[child], "", style=fk)
    return d.write()


if __name__ == "__main__":
    for f in (system_context, aws_architecture, network, security, case_machine, replay_sequence, rag, mcp_sequence,
              fault_flow, data_model, deployment, observability):
        print(f())
