
import logging as logthings
import re
import sys
from datetime import datetime as dt
from os import environ

import yaml
from troposphere import (
    Template, Parameter
)

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader
from ecs_composex.common import cfn_params
from ecs_composex.common import cfn_conditions


DATE = dt.utcnow().isoformat()
DATE_PREFIX = dt.utcnow().strftime('%Y/%m/%d/%H%M')
NONALPHANUM = re.compile(r'[\W]+')


def KEYISSET(x, y):
    """Macro to figure if the the dictionary contains a key and that the key is not empty

    :param x: The key to check presence in the dictionary
    :type x: str
    :param y: The dictionary to check for
    :type y: dict

    :returns: True/False
    :rtype: bool
    """
    if isinstance(y, dict) and x in y.keys() and y[x]:
        return True
    return False


def KEYPRESENT(x, y):
    """Macro to figure if the the dictionary contains a key and that the key is not empty

    :param x: The key to check presence in the dictionary
    :type x: str
    :param y: The dictionary to check for
    :type y: dict

    :returns: True/False
    :rtype: bool
    """
    if isinstance(y, dict) and x in y.keys():
        return True
    return False


def init_template(description=None):
    """Function to initialize the troposphere base template

    :param description: Description used for the CFN
    :type description: str

    :returns: template
    :rtype: Template
    """
    if description is not None:
        template = Template(description)
    else:
        template = Template(f'Template generated by ECS ComposeX')
    template.set_metadata({
        'GeneratedOn': DATE
    })
    return template


def add_parameters(template, parameters):
    """Function to add parameters to the template

    :param description: Description used for the CFN
    :type description: str

    :returns: template
    :rtype: Template
    """
    for param in parameters:
        if not isinstance(param, Parameter):
            raise TypeError(f'Parameter must be of type', Parameter)
        template.add_parameter(param)


def add_defaults(template):
    """Function to CFN parameters and conditions to the template whhich are used
    across ECS ComposeX

    :param template: source template to add the params and conditions to
    :type template: Template
    """
    template.add_parameter(cfn_params.USE_SSM_EXPORTS)
    template.add_parameter(cfn_params.USE_CFN_EXPORTS)
    template.add_parameter(cfn_params.ROOT_STACK_NAME)

    template.add_condition(
        cfn_conditions.USE_SSM_EXPORTS_T,
        cfn_conditions.USE_SSM_EXPORTS
    )
    template.add_condition(
        cfn_conditions.USE_CFN_EXPORTS_T,
        cfn_conditions.USE_CFN_EXPORTS
    )
    template.add_condition(
        cfn_conditions.NOT_USE_CFN_EXPORTS_T,
        cfn_conditions.NOT_USE_CFN_EXPORTS
    )
    template.add_condition(
        cfn_conditions.USE_CFN_AND_SSM_EXPORTS_T,
        cfn_conditions.USE_CFN_AND_SSM_EXPORTS
    )
    template.add_condition(
        cfn_conditions.USE_STACK_NAME_CON_T,
        cfn_conditions.USE_STACK_NAME_CON
    )
    template.add_condition(
        cfn_conditions.USE_SSM_ONLY_T,
        cfn_conditions.USE_SSM_ONLY
    )


def build_template(description=None, *parameters):
    """Entry point function to creating the template for ECS ComposeX resources

    :param description: Optional custom description for the CFN template
    :type description: str, optional

    :param parameters: List of optional parameters to add to the template.
    :type parameters: List<troposphere.Parameters>, optional

    :returns template: the troposphere template
    :rtype: Template
    """
    template = init_template(description)
    if parameters:
        add_parameters(template, *parameters)
    add_defaults(template)
    return template


def validate_resource_title(resource_name, resource_type=None):
    """Function to validate the key for the resource is valid

    :param resource_name: Name of the resource to evaluate
    :type resource_name: str
    :param resource_type: category of the resource, optional
    :type resource_type: str

    :returns: True/False
    :rtype: bool
    """
    if NONALPHANUM.findall(resource_name):
        raise ValueError(
            f"The resource {resource_name} in {resource_type} "
            "section contains non alphanumerical characters",
            NONALPHANUM.findall(resource_name)
        )
    return True


def validate_input(compose_content, res_key):
    """Function to validate the resources names in ComposeX File
    for a given resource key

    :param compose_content: the docker/ComposeX content
    :type compose_content: dict
    :param res_key: key of the category in docker compose to look for
    :type res_key: str

    :return: True/False if all keys are valid
    :rtype: bool
    """
    names = compose_content[res_key]
    for name in names:
        validate_resource_title(name, res_key)
    return True


def validate_kwargs(required_keys, kwargs, caller=None):
    """Function to ensure minimum keys in kwargs are present.

    :param required_keys: the list of keys that have to be present
    :type required_keys: list
    :param kwargs: the arguments to verify
    :type kwargs: dict or set
    :param caller: optional argument to help understand what's missing
    :type caller: str

    :return: True/False if all keys are valid
    :rtype: bool

    :raises: KeyError if key is missing from kwargs
    """
    for required_key in required_keys:
        if not KEYISSET(required_key, kwargs):
            raise KeyError(required_key, 'is required by module', caller)
    return True


def setup_logging():
    """Function to setup logging for ECS ComposeX.
    In case this is used in a Lambda function, removes the AWS Lambda default log handler

    :returns: the_logger
    :rtype: Logger
    """
    level = environ.get('LOGLEVEL')

    if level is not None and isinstance(level, str):
        print('SETTING TO', level.upper())
        logthings.basicConfig(level=level.upper())
    else:
        logthings.basicConfig(level='INFO')

    root_logger = logthings.getLogger()
    for h in root_logger.handlers:
        root_logger.removeHandler(h)
    the_logger = logthings.getLogger("EcsComposeX")

    if not the_logger.handlers:
        formatter = logthings.Formatter(
            "[%(levelname)s] %(asctime)s, %(funcName)s, %(message)s", "%Y-%m-%d %H:%M:%S"
        )
        handler = logthings.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        the_logger.addHandler(handler)

    return the_logger


def load_composex_file(file_path):
    """File to load and read the docker compose file

    :param file_path: path to the docker compose file
    :type file_path: str

    :return: content of the docker file
    :rtype: dict
    """
    with open(file_path, 'r') as composex_fd:
        return yaml.load(composex_fd.read(), Loader=Loader)


LOG = setup_logging()
