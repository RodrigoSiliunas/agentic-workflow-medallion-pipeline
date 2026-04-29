"""Step `network` — cria VPC + subnets + NAT + SG + Databricks network config.

Primeiro step novo da saga completa (Caminho A). Cria infra rede AWS + registra
network configuration no Databricks Account pra customer-managed VPC.

Fluxo:
1. Criar VPC (CIDR 10.0.0.0/16) com DNS support + hostnames
2. Internet Gateway + Public subnet + Route table + NAT Gateway
3. 2 Private subnets em AZs diferentes (HA requirement Databricks)
4. Security Group com self-reference ingress (Databricks requirement)
5. POST /api/2.0/accounts/{id}/networks no Databricks Account

Idempotente via tag-based lookup: se VPC com tag `flowertex:deployment={id}`
existe, reutiliza.
"""

from __future__ import annotations

import asyncio
import contextlib

import boto3

from app.services.real_saga.base import SagaStepBase, StepContext
from app.services.real_saga.registry import register_saga_step


@register_saga_step("network")
class NetworkStep(SagaStepBase):
    step_id = "network"

    async def compensate(self, ctx: StepContext) -> None:
        """Rollback: delete DB network config + tear down VPC/NAT/IGW/SG/subnets.

        So delete recursos que foram CRIADOS nesta saga (flag created=True).
        Idempotente: ignora "not found" pra suportar retries do compensate.
        """
        env = ctx.env_vars()
        account_id = env.get("databricks_account_id", "")
        client_id = env.get("databricks_oauth_client_id", "")
        secret = env.get("databricks_oauth_secret", "")

        if (
            ctx.shared.databricks_network_created
            and ctx.shared.databricks_network_id
            and all([account_id, client_id, secret])
        ):
            net_id = ctx.shared.databricks_network_id
            import httpx

            async def _del_net() -> None:
                async with httpx.AsyncClient(timeout=30.0) as c:
                    tok = await c.post(
                        f"https://accounts.cloud.databricks.com/oidc/accounts/{account_id}/v1/token",
                        auth=(client_id, secret),
                        data={"grant_type": "client_credentials", "scope": "all-apis"},
                    )
                    tok.raise_for_status()
                    token = tok.json()["access_token"]
                    await c.delete(
                        f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/networks/{net_id}",
                        headers={"Authorization": f"Bearer {token}"},
                    )

            await self._safe_compensate(
                ctx, f"db_network({net_id})", _del_net, sync=False,
            )

        if not ctx.shared.aws_vpc_created or not ctx.shared.aws_vpc_id:
            return
        vpc_id = ctx.shared.aws_vpc_id

        session = boto3.Session(
            aws_access_key_id=ctx.credentials.aws_access_key_id,
            aws_secret_access_key=ctx.credentials.aws_secret_access_key,
            region_name=ctx.credentials.aws_region,
        )
        ec2 = session.client("ec2")

        await self._safe_compensate(
            ctx, f"vpc({vpc_id})",
            lambda: self._tear_down_vpc(ec2, vpc_id),
        )

    @staticmethod
    def _tear_down_vpc(ec2, vpc_id: str) -> None:
        """Tear down VPC + tudo que depende dele. Ordem importa por deps AWS."""
        # NAT gateways
        nats = ec2.describe_nat_gateways(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        ).get("NatGateways", [])
        nat_ids = [
            n["NatGatewayId"] for n in nats if n.get("State") not in ("deleted", "deleting")
        ]
        eip_alloc_ids: list[str] = []
        for n in nats:
            for addr in n.get("NatGatewayAddresses", []) or []:
                if addr.get("AllocationId"):
                    eip_alloc_ids.append(addr["AllocationId"])
        for nat_id in nat_ids:
            ec2.delete_nat_gateway(NatGatewayId=nat_id)
        if nat_ids:
            ec2.get_waiter("nat_gateway_deleted").wait(NatGatewayIds=nat_ids)

        for alloc_id in set(eip_alloc_ids):
            with contextlib.suppress(Exception):  # ja released
                ec2.release_address(AllocationId=alloc_id)

        # IGWs
        igws = ec2.describe_internet_gateways(
            Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
        ).get("InternetGateways", [])
        for igw in igws:
            iid = igw["InternetGatewayId"]
            with contextlib.suppress(Exception):
                ec2.detach_internet_gateway(InternetGatewayId=iid, VpcId=vpc_id)
            ec2.delete_internet_gateway(InternetGatewayId=iid)

        # Subnets
        subs = ec2.describe_subnets(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        ).get("Subnets", [])
        for s in subs:
            with contextlib.suppress(Exception):
                ec2.delete_subnet(SubnetId=s["SubnetId"])

        # Route tables (skip main)
        rts = ec2.describe_route_tables(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        ).get("RouteTables", [])
        for rt in rts:
            assocs = rt.get("Associations", []) or []
            if any(a.get("Main") for a in assocs):
                continue
            for a in assocs:
                if a.get("RouteTableAssociationId"):
                    with contextlib.suppress(Exception):
                        ec2.disassociate_route_table(
                            AssociationId=a["RouteTableAssociationId"]
                        )
            with contextlib.suppress(Exception):
                ec2.delete_route_table(RouteTableId=rt["RouteTableId"])

        # Security groups (skip default)
        sgs = ec2.describe_security_groups(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        ).get("SecurityGroups", [])
        for sg in sgs:
            if sg.get("GroupName") == "default":
                continue
            with contextlib.suppress(Exception):
                ec2.delete_security_group(GroupId=sg["GroupId"])

        ec2.delete_vpc(VpcId=vpc_id)

    async def execute(self, ctx: StepContext) -> None:
        env = ctx.env_vars()
        account_id = env.get("databricks_account_id", "")
        oauth_client_id = env.get("databricks_oauth_client_id", "")
        oauth_secret = env.get("databricks_oauth_secret", "")

        # Modo existing: VPC + network config ja existem, hidrata via
        # workspace_provision. Network nao tem nada pra fazer aqui.
        if env.get("workspace_mode") == "existing":
            await ctx.info(
                "workspace_mode=existing — pulando criacao de VPC + network config"
            )
            return

        if not all([account_id, oauth_client_id, oauth_secret]):
            await ctx.warn(
                "Skipping network step — Databricks Account OAuth nao configurado. "
                "Workspace deve ja existir com network_id manual."
            )
            return

        region = ctx.credentials.require("aws_region")
        deployment_tag = f"flowertex-{str(ctx.deployment_id)[:8]}"

        await ctx.info(f"Verificando VPC com tag '{deployment_tag}' em {region}")

        session = boto3.Session(
            aws_access_key_id=ctx.credentials.require("aws_access_key_id"),
            aws_secret_access_key=ctx.credentials.require("aws_secret_access_key"),
            region_name=region,
        )
        ec2 = session.client("ec2")

        vpc_id, subnet_ids, sg_id, vpc_created = await asyncio.to_thread(
            self._ensure_vpc, ec2, deployment_tag, region
        )
        await ctx.info(
            f"VPC {vpc_id}, subnets {subnet_ids}, SG {sg_id} (created={vpc_created})"
        )

        ctx.shared.aws_vpc_id = vpc_id
        ctx.shared.aws_subnet_ids = subnet_ids
        ctx.shared.aws_security_group_id = sg_id
        if vpc_created:
            ctx.shared.aws_vpc_created = True

        # Registrar network config no Databricks Account
        network_id, network_created = await self._register_databricks_network(
            ctx, account_id, oauth_client_id, oauth_secret,
            deployment_tag, vpc_id, subnet_ids, sg_id,
        )
        ctx.shared.databricks_network_id = network_id
        if network_created:
            ctx.shared.databricks_network_created = True

        await ctx.success(
            f"Network pronto: vpc={vpc_id} network_id={network_id}"
        )

    @staticmethod
    def _ensure_vpc(
        ec2, tag: str, region: str
    ) -> tuple[str, list[str], str, bool]:
        """Cria ou reutiliza VPC + subnets + SG. Retorna (vpc_id, [subnet_ids], sg_id, created)."""
        # Lookup existing via tag
        vpcs = ec2.describe_vpcs(
            Filters=[{"Name": "tag:Name", "Values": [tag]}]
        )["Vpcs"]
        if vpcs:
            vpc_id = vpcs[0]["VpcId"]
            # Subnets com tag indicando private-a/private-b
            subs = ec2.describe_subnets(
                Filters=[
                    {"Name": "vpc-id", "Values": [vpc_id]},
                    {"Name": "tag:Visibility", "Values": ["private"]},
                ]
            )["Subnets"]
            subnet_ids = sorted([s["SubnetId"] for s in subs])
            sgs = ec2.describe_security_groups(
                Filters=[
                    {"Name": "vpc-id", "Values": [vpc_id]},
                    {"Name": "group-name", "Values": [f"{tag}-sg"]},
                ]
            )["SecurityGroups"]
            sg_id = sgs[0]["GroupId"] if sgs else ""
            if subnet_ids and sg_id:
                return vpc_id, subnet_ids, sg_id, False

        # Create VPC
        vpc = ec2.create_vpc(
            CidrBlock="10.0.0.0/16",
            TagSpecifications=[{
                "ResourceType": "vpc",
                "Tags": [{"Key": "Name", "Value": tag}]
            }],
        )["Vpc"]
        vpc_id = vpc["VpcId"]
        ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsSupport={"Value": True})
        ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={"Value": True})

        # IGW
        igw = ec2.create_internet_gateway(
            TagSpecifications=[{
                "ResourceType": "internet-gateway",
                "Tags": [{"Key": "Name", "Value": f"{tag}-igw"}]
            }],
        )["InternetGateway"]
        igw_id = igw["InternetGatewayId"]
        ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)

        # Public subnet pra NAT
        pub_sub = ec2.create_subnet(
            VpcId=vpc_id, CidrBlock="10.0.0.0/24",
            AvailabilityZone=f"{region}a",
            TagSpecifications=[{
                "ResourceType": "subnet",
                "Tags": [
                    {"Key": "Name", "Value": f"{tag}-public"},
                    {"Key": "Visibility", "Value": "public"},
                ],
            }],
        )["Subnet"]
        pub_sub_id = pub_sub["SubnetId"]
        ec2.modify_subnet_attribute(SubnetId=pub_sub_id, MapPublicIpOnLaunch={"Value": True})

        # Public route table + IGW route
        pub_rt = ec2.create_route_table(
            VpcId=vpc_id,
            TagSpecifications=[{
                "ResourceType": "route-table",
                "Tags": [{"Key": "Name", "Value": f"{tag}-public-rt"}]
            }],
        )["RouteTable"]
        pub_rt_id = pub_rt["RouteTableId"]
        ec2.create_route(
            RouteTableId=pub_rt_id, DestinationCidrBlock="0.0.0.0/0", GatewayId=igw_id
        )
        ec2.associate_route_table(RouteTableId=pub_rt_id, SubnetId=pub_sub_id)

        # NAT Gateway (EIP + NAT)
        eip = ec2.allocate_address(Domain="vpc")
        nat = ec2.create_nat_gateway(
            SubnetId=pub_sub_id, AllocationId=eip["AllocationId"],
            TagSpecifications=[{
                "ResourceType": "natgateway",
                "Tags": [{"Key": "Name", "Value": f"{tag}-nat"}]
            }],
        )["NatGateway"]
        nat_id = nat["NatGatewayId"]
        ec2.get_waiter("nat_gateway_available").wait(NatGatewayIds=[nat_id])

        # Private subnets (2 AZs pra HA)
        priv_subs = []
        for cidr, az_suffix in [
            ("10.0.1.0/24", "a"),
            ("10.0.2.0/24", "b"),
        ]:
            s = ec2.create_subnet(
                VpcId=vpc_id, CidrBlock=cidr,
                AvailabilityZone=f"{region}{az_suffix}",
                TagSpecifications=[{
                    "ResourceType": "subnet",
                    "Tags": [
                        {"Key": "Name", "Value": f"{tag}-private-{az_suffix}"},
                        {"Key": "Visibility", "Value": "private"},
                    ],
                }],
            )["Subnet"]
            priv_subs.append(s["SubnetId"])

        # Private route table (via NAT)
        priv_rt = ec2.create_route_table(
            VpcId=vpc_id,
            TagSpecifications=[{
                "ResourceType": "route-table",
                "Tags": [{"Key": "Name", "Value": f"{tag}-private-rt"}]
            }],
        )["RouteTable"]
        priv_rt_id = priv_rt["RouteTableId"]
        ec2.create_route(
            RouteTableId=priv_rt_id, DestinationCidrBlock="0.0.0.0/0",
            NatGatewayId=nat_id,
        )
        for sid in priv_subs:
            ec2.associate_route_table(RouteTableId=priv_rt_id, SubnetId=sid)

        # Security Group — self-reference ingress (Databricks requirement)
        sg = ec2.create_security_group(
            GroupName=f"{tag}-sg",
            Description="Databricks workspace SG - internal traffic",
            VpcId=vpc_id,
            TagSpecifications=[{
                "ResourceType": "security-group",
                "Tags": [{"Key": "Name", "Value": f"{tag}-sg"}]
            }],
        )
        sg_id = sg["GroupId"]
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[{
                "IpProtocol": "-1",
                "UserIdGroupPairs": [{"GroupId": sg_id}],
            }],
        )

        return vpc_id, sorted(priv_subs), sg_id, True

    @staticmethod
    async def _register_databricks_network(
        ctx: StepContext,
        account_id: str,
        client_id: str,
        client_secret: str,
        name: str,
        vpc_id: str,
        subnet_ids: list[str],
        sg_id: str,
    ) -> tuple[str, bool]:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as c:
            token_resp = await c.post(
                f"https://accounts.cloud.databricks.com/oidc/accounts/{account_id}/v1/token",
                auth=(client_id, client_secret),
                data={"grant_type": "client_credentials", "scope": "all-apis"},
            )
            token_resp.raise_for_status()
            token = token_resp.json()["access_token"]

            list_resp = await c.get(
                f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/networks",
                headers={"Authorization": f"Bearer {token}"},
            )
            list_resp.raise_for_status()
            for net in list_resp.json() or []:
                if net.get("network_name") == name:
                    await ctx.info(f"Network {name} ja existe — reutilizando")
                    return net["network_id"], False

            create_resp = await c.post(
                f"https://accounts.cloud.databricks.com/api/2.0/accounts/{account_id}/networks",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "network_name": name,
                    "vpc_id": vpc_id,
                    "subnet_ids": subnet_ids,
                    "security_group_ids": [sg_id],
                },
            )
            create_resp.raise_for_status()
            return create_resp.json()["network_id"], True
