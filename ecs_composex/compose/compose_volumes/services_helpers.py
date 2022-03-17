#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

import re
from uuid import uuid4

from compose_x_common.compose_x_common import keyisset

from ecs_composex.common import LOG

from . import ComposeVolume


def match_volumes_services_config(service, vol_config, volumes):
    """
    Function to map volume config in services and top-level volumes

    :param service:
    :param vol_config:
    :param volumes:
    :raises LookupError:
    """
    if keyisset("source", vol_config) and vol_config["source"].startswith(r"/"):
        vol_config["volume"] = None
        service.volumes.append(vol_config)
        LOG.info(f"volumes.{vol_config['source']} - Mapped to {service.name}")
        return
    else:
        for volume in volumes:
            if not keyisset("source", vol_config) and not keyisset("volume", volume):
                LOG.error(f"volumes - Failure to process {volume}")
                continue
            if volume.name == vol_config["source"]:
                volume.services.append(service)
                vol_config["volume"] = volume
                service.volumes.append(vol_config)
                LOG.info(f"volumes.{volume.name} - Mapped to {service.name}")
                return
    raise LookupError(
        f"Volume {vol_config['source']} was not found in {[vol.name for vol in volumes]}"
    )


def handle_volume_str_config(service, config, volumes):
    """
    Function to return the volume configuration (long)
    :param ComposeService service:
    :param str config:
    :param list volumes:
    """
    volume_config = {"read_only": False}
    path_finder = re.compile(
        r"(?:(?P<source>[\S][^:]+):)?(?P<target>/[^:\n]+)(?::(?P<mode>ro|rw))?"
    )
    path_match = path_finder.match(config)
    if not path_match or (path_match and not path_match.group("target")):
        raise ValueError(
            f"Volume syntax {config} is invalid. Must follow the pattern",
            path_finder.pattern,
        )
    else:
        volume_config["target"] = path_match.group("target")
        if path_match.group("source"):
            volume_config["source"] = path_match.group("source")
        else:
            LOG.warning(f"No source defined with {config}. Creating docker volume")
            new_volume = ComposeVolume(str(uuid4().hex)[:6], {})
            new_volume.autogenerated = True
            volumes.append(new_volume)
            volume_config["source"] = new_volume.name
            volume_config["volume"] = new_volume
        if path_match.group("mode") and path_match.group("mode") == "ro":
            volume_config["read_only"] = True
    match_volumes_services_config(service, volume_config, volumes)


def is_tmpfs(config):
    """
    Function to identify whether the volume defined is tmpfs

    :param dict config:
    :return: whether the volume defined is tmpfs
    :rtype: bool
    """
    if keyisset("tmpfs", config) or (
        keyisset("type", config) and config["type"] == "tmpfs"
    ):
        return True
    return False


def handle_volume_dict_config(service, config, volumes):
    """
    :param ComposeService service:
    :param dict config:
    :param list volumes:
    """
    volume_config = {"read_only": False}
    required_keys = ["target", "source"]
    if not is_tmpfs(config) and not all(key in config.keys() for key in required_keys):
        raise KeyError(
            "Volume configuration, when not tmpfs, requires at least",
            required_keys,
            "Got",
            config.keys(),
        )
    volume_config.update(config)
    if not is_tmpfs(volume_config):
        match_volumes_services_config(service, volume_config, volumes)


def map_volumes(service, volumes=None) -> None:
    """
    Method to apply mapping of volumes to the service and define the mapping configuration

    :param service: The Service to map the volumes to.
    :param list volumes:
    """
    if keyisset(ComposeVolume.main_key, service.definition):
        for s_volume in service.definition[ComposeVolume.main_key]:
            if (
                isinstance(s_volume, dict)
                and (keyisset("type", s_volume) and s_volume["type"] == "tmpfs")
                or keyisset("tmpfs", s_volume)
            ):
                tmpfs_def = {}
                if not keyisset("target", s_volume):
                    raise KeyError(
                        f"{service.name}.volumes - When defining tmpfs as volume, you must define a target"
                    )
                tmpfs_def["ContainerPath"] = s_volume["target"]
                if (
                    keyisset("tmpfs", s_volume)
                    and isinstance(s_volume["tmpfs"], dict)
                    and keyisset("size", s_volume["tmpfs"])
                ):
                    tmpfs_def["Size"] = int(s_volume["tmpfs"]["size"])
                service.tmpfses.append(tmpfs_def)
            else:
                if not volumes:
                    continue
                if isinstance(s_volume, str):
                    handle_volume_str_config(service, s_volume, volumes)
                elif isinstance(s_volume, dict):
                    handle_volume_dict_config(service, s_volume, volumes)
