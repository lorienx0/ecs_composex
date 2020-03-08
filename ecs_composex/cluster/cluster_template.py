# -*- coding: utf-8 -*-

"""
Main module generating the ECS Cluster template.
"""

from troposphere import Ref, If, GetAtt
from troposphere.cloudformation import Stack
from troposphere.ecs import Cluster

from ecs_composex.common.outputs import formatted_outputs
from ecs_composex.cluster import cluster_params, cluster_conditions
from ecs_composex.cluster.hosts_template import add_hosts_resources
from ecs_composex.cluster.spot_fleet import generate_spot_fleet_template, DEFAULT_SPOT_CONFIG
from ecs_composex.common import build_template, KEYISSET, LOG
from ecs_composex.common import cfn_conditions
from ecs_composex.common.cfn_params import ROOT_STACK_NAME, ROOT_STACK_NAME_T
from ecs_composex.common.templates import upload_template
from ecs_composex.vpc import vpc_params


def add_spotfleet_stack(template, region_azs, compose_content, launch_template, **kwargs):
    """
    Function to build the spotfleet stack and add it to the Cluster parent template

    :param launch_template: the launch template
    :type launch_template: troposphere.ec2.LaunchTemplate
    :param template: parent cluster template
    :type template: troposphere.Template
    :param compose_content: docker / composex file content
    :type compose_content: dict
    :param region_azs: List of AWS Azs i.e. ['eu-west-1a', 'eu-west-1b']
    :type region_azs: list

    :returns: void
    """
    spot_config = None
    if KEYISSET('configs', compose_content):
        configs = compose_content['configs']
        if KEYISSET('spot_config', configs):
            spot_config = configs['spot_config']

    if spot_config:
        kwargs.update({'spot_config': spot_config})
    else:
        LOG.warn('No spot_config set in configs of ComposeX File. Setting to defaults')
        kwargs.update({'spot_config': DEFAULT_SPOT_CONFIG})
    fleet_template = generate_spot_fleet_template(region_azs, **kwargs)
    fleet_template_url = upload_template(
        fleet_template.to_json(),
        kwargs['BucketName'],
        'spot_fleet.json'
    )
    if not fleet_template_url:
        LOG.warn('Fleet template URL not returned. Not adding SpotFleet to Cluster stack')
        return
    template.add_resource(Stack(
        'SpotFleet',
        Condition=cluster_conditions.USE_SPOT_CON_T,
        TemplateURL=fleet_template_url,
        Parameters={
            ROOT_STACK_NAME_T: If(
                cfn_conditions.USE_STACK_NAME_CON_T,
                Ref('AWS::StackName'),
                Ref(ROOT_STACK_NAME)
            ),
            cluster_params.LAUNCH_TEMPLATE_ID_T: Ref(launch_template),
            cluster_params.LAUNCH_TEMPLATE_VersionNumber_T: GetAtt(
                launch_template, 'LatestVersionNumber'
            ),
            cluster_params.MAX_CAPACITY_T: Ref(cluster_params.MAX_CAPACITY),
            cluster_params.MIN_CAPACITY_T: Ref(cluster_params.MIN_CAPACITY),
            cluster_params.TARGET_CAPACITY_T: Ref(cluster_params.TARGET_CAPACITY)
        }
    ))


def generate_cluster_template(region_azs, compose_content=None, **kwargs):
    """Function that generates the ECS Cluster

    :param region_azs: List of AZs for hosts, i.e. ['eu-west-1', 'eu-west-b']
    :type region_azs: list
    :param compose_content: Compose dictionary to parse for services etc.
    :type compose_content: dict

    :return: ECS Cluster Template
    :rtype: troposphere.Template
    """
    template = build_template(
        'Cluster template generated by ECS Compose X',
        [
            cluster_params.CLUSTER_NAME,
            cluster_params.USE_FLEET,
            cluster_params.USE_ONDEMAND,
            cluster_params.ECS_AMI_ID,
            cluster_params.TARGET_CAPACITY,
            cluster_params.MIN_CAPACITY,
            cluster_params.MAX_CAPACITY,
            vpc_params.APP_SUBNETS,
            vpc_params.VPC_ID,
            ecs_params.CLUSTER_NAME
        ]
    )
    template.add_condition(
        cluster_conditions.MAX_IS_MIN_T,
        cluster_conditions.MAX_IS_MIN
    )
    template.add_condition(
        cluster_conditions.USE_SPOT_CON_T,
        cluster_conditions.USE_SPOT_CON
    )
    template.add_condition(
        cluster_conditions.GENERATED_CLUSTER_NAME_CON_T,
        cluster_conditions.GENERATED_CLUSTER_NAME_CON
    )
    template.add_condition(
        cluster_conditions.CLUSTER_NAME_CON_T,
        cluster_conditions.CLUSTER_NAME_CON
    )
    cluster = Cluster(
        'EcsCluster',
        ClusterName=If(
            cluster_conditions.GENERATED_CLUSTER_NAME_CON_T,
            Ref('AWS::NoValue'),
            If(
                cluster_conditions.CLUSTER_NAME_CON_T,
                Ref(ROOT_STACK_NAME),
                Ref('AWS::StackName')
            )
        ),
        template=template
    )
    launch_template = add_hosts_resources(template, cluster)
    add_spotfleet_stack(
        template, region_azs,
        compose_content, launch_template, **kwargs
    )
    template.add_output(formatted_outputs([
        {cluster_params.CLUSTER_NAME_T: Ref(cluster)}
    ]))
    return template
