# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

"""
Recovering a label specification from files exported by CVAT.

The exports CVAT produces describe their labels in several different ways, so
this module normalizes all of them into the label specification the project and
task APIs accept, dropping everything that is not a label along the way.
"""

from __future__ import annotations

import json
import os
import zipfile
from collections.abc import Iterator
from typing import Any, BinaryIO

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from cvat.apps.engine.models import AttributeType, LabelType

MAX_UPLOAD_SIZE = 100 * 2**20
"""Uploads larger than this are rejected without being read."""

MAX_MEMBER_SIZE = 100 * 2**20
"""Members of an archive larger than this are skipped instead of being parsed."""

MAX_LABELS = 10000

_LABEL_NAME_MAX_LENGTH = 64
_KNOWN_LABEL_TYPES = frozenset(LabelType.list())
_KNOWN_ATTRIBUTE_TYPES = frozenset(str(item) for item in AttributeType)


class LabelExtractionError(Exception):
    pass


def extract_labels(file: BinaryIO) -> list[dict[str, Any]]:
    """
    Returns the labels described by an uploaded CVAT export.

    Raises LabelExtractionError if the file is not a supported export or if it
    does not describe any label.
    """

    size = _get_size(file)
    if size is not None and size > MAX_UPLOAD_SIZE:
        raise LabelExtractionError(
            f"The file is too large to be parsed, the limit is {MAX_UPLOAD_SIZE // 2**20} MB"
        )

    labels = _extract_from_file(file, name=getattr(file, "name", "") or "")
    if not labels:
        raise LabelExtractionError(
            "Could not find any label in the file. Supported files are CVAT task and "
            "project backups, backup annotations.json files, CVAT-for-images/video XML, "
            "Datumaro and COCO annotations, and ZIP archives containing any of these."
        )

    return labels[:MAX_LABELS]


def _get_size(file: BinaryIO) -> int | None:
    size = getattr(file, "size", None)
    if isinstance(size, int):
        return size

    try:
        current = file.tell()
        size = file.seek(0, os.SEEK_END)
        file.seek(current)
        return size
    except (AttributeError, OSError):
        return None


def _extract_from_file(file: BinaryIO, *, name: str) -> list[dict[str, Any]]:
    file.seek(0)
    if zipfile.is_zipfile(file):
        file.seek(0)
        return _extract_from_archive(file)

    file.seek(0)
    content = file.read()
    return _extract_from_content(content, name=name)


def _extract_from_content(content: bytes, *, name: str) -> list[dict[str, Any]]:
    stripped = content.lstrip()
    if stripped.startswith(b"<"):
        return _extract_from_cvat_xml(content)

    if stripped.startswith((b"{", b"[")):
        return _extract_from_json(content)

    raise LabelExtractionError(f"Unsupported file format: {name or 'uploaded file'}")


def _extract_from_archive(file: BinaryIO) -> list[dict[str, Any]]:
    with zipfile.ZipFile(file) as archive:
        for member in _archive_candidates(archive):
            if member.file_size > MAX_MEMBER_SIZE:
                continue

            with archive.open(member) as member_file:
                content = member_file.read()

            try:
                labels = _extract_from_content(content, name=member.filename)
            except (LabelExtractionError, ValueError, ElementTree.ParseError):
                continue

            if labels:
                return labels

    return []


def _archive_candidates(archive: zipfile.ZipFile) -> Iterator[zipfile.ZipInfo]:
    """
    Yields the archive members that may describe labels, most authoritative first.

    Backup manifests come first because they carry complete label definitions,
    while annotation files only carry the labels that were actually used.
    """

    members = [member for member in archive.infolist() if not member.is_dir()]

    def basename(member: zipfile.ZipInfo) -> str:
        return os.path.basename(member.filename).lower()

    groups = [
        lambda member: basename(member) in ("project.json", "task.json"),
        lambda member: basename(member) == "annotations.xml",
        lambda member: basename(member) == "annotations.json",
        lambda member: basename(member).endswith(".json"),
        lambda member: basename(member).endswith(".xml"),
    ]

    seen: set[str] = set()
    for matches in groups:
        for member in members:
            if member.filename not in seen and matches(member):
                seen.add(member.filename)
                yield member


def _extract_from_json(content: bytes) -> list[dict[str, Any]]:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as ex:
        raise LabelExtractionError(f"The file is not valid JSON: {ex}") from ex

    if isinstance(data, dict):
        # A task or project backup manifest, which stores a full label specification
        if isinstance(data.get("labels"), list):
            return _normalize_labels(data["labels"])

        # A Datumaro annotation file
        categories = data.get("categories")
        if isinstance(categories, dict):
            datumaro_labels = categories.get("label", {}).get("labels")
            if isinstance(datumaro_labels, list):
                return _normalize_labels(
                    [item for item in datumaro_labels if not item.get("parent")]
                )

        # A COCO annotation file
        if isinstance(categories, list):
            return _normalize_labels(categories)

        raise LabelExtractionError("The JSON file does not describe any label")

    if isinstance(data, list):
        # A backup annotations.json, which only names the labels that were used
        if any(isinstance(item, dict) and _is_annotations_entry(item) for item in data):
            return _labels_from_annotations(data)

        return _normalize_labels(data)

    raise LabelExtractionError("The JSON file does not describe any label")


def _is_annotations_entry(item: dict[str, Any]) -> bool:
    return any(key in item for key in ("shapes", "tracks", "tags"))


def _labels_from_annotations(jobs: list[Any]) -> list[dict[str, Any]]:
    """
    Rebuilds labels from exported annotations, whose only trace of a label is
    the name used by each shape. The label type is guessed from the shapes that
    reference it, and a label used by several shape types becomes "any".
    """

    types_by_name: dict[str, set[str]] = {}

    def register(name: Any, label_type: str) -> None:
        if isinstance(name, str) and name:
            types_by_name.setdefault(name, set()).add(label_type)

    for job in jobs:
        if not isinstance(job, dict):
            continue

        for key in ("shapes", "tracks"):
            for item in job.get(key) or []:
                if isinstance(item, dict):
                    shape_type = item.get("type")
                    register(
                        item.get("label"),
                        shape_type if shape_type in _KNOWN_LABEL_TYPES else str(LabelType.ANY),
                    )

        for tag in job.get("tags") or []:
            if isinstance(tag, dict):
                register(tag.get("label"), str(LabelType.TAG))

    labels = []
    for name, types in types_by_name.items():
        # A skeleton cannot be rebuilt without its point layout, so it stays untyped
        label_type = types.pop() if len(types) == 1 else str(LabelType.ANY)
        if label_type == str(LabelType.SKELETON):
            label_type = str(LabelType.ANY)

        labels.append({"name": name, "type": label_type})

    return _normalize_labels(labels)


def _extract_from_cvat_xml(content: bytes) -> list[dict[str, Any]]:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as ex:
        raise LabelExtractionError(f"The file is not valid XML: {ex}") from ex
    except DefusedXmlException as ex:
        # entity expansion and external references are refused by defusedxml,
        # an export has no use for them anyway
        raise LabelExtractionError(f"The XML file uses a forbidden feature: {ex}") from ex

    meta = root.find("meta")
    if meta is None:
        raise LabelExtractionError("The XML file is not a CVAT annotations file")

    labels = []
    for element in meta.iterfind(".//labels/label"):
        name = element.findtext("name", default="").strip()
        if not name:
            continue

        labels.append(
            {
                "name": name,
                "color": element.findtext("color", default="").strip(),
                "type": element.findtext("type", default="").strip(),
                "attributes": [
                    {
                        "name": attribute.findtext("name", default="").strip(),
                        "mutable": attribute.findtext("mutable", default="").strip().lower()
                        == "true",
                        "input_type": attribute.findtext("input_type", default="").strip(),
                        "default_value": attribute.findtext("default_value", default=""),
                        "values": [
                            value
                            for value in attribute.findtext("values", default="").split("\n")
                            if value
                        ],
                    }
                    for attribute in element.iterfind("./attributes/attribute")
                ],
            }
        )

    return _normalize_labels(labels)


def _normalize_labels(raw_labels: list[Any]) -> list[dict[str, Any]]:
    labels = []
    used_names: set[str] = set()

    for raw_label in raw_labels:
        if not isinstance(raw_label, dict):
            continue

        name = _normalize_name(raw_label.get("name"))
        if not name or name in used_names:
            continue

        used_names.add(name)
        label = {
            "name": name,
            "color": _normalize_color(raw_label.get("color")),
            "type": _normalize_type(raw_label.get("type")),
            "prompt": str(raw_label.get("prompt") or "")[:1024],
            "attributes": _normalize_attributes(raw_label.get("attributes")),
            "sublabels": [],
            "svg": str(raw_label.get("svg") or ""),
        }

        if label["type"] == str(LabelType.SKELETON):
            label["sublabels"] = [
                {
                    key: value
                    for key, value in sublabel.items()
                    if key in ("name", "color", "type", "prompt", "attributes")
                }
                for sublabel in _normalize_labels(raw_label.get("sublabels") or [])
            ]

            # Without its points a skeleton cannot be drawn, so keep it as a plain label
            if not label["sublabels"] or not label["svg"]:
                label["type"] = str(LabelType.ANY)
                label["sublabels"] = []
                label["svg"] = ""

        labels.append(label)

    return labels


def _normalize_name(name: Any) -> str:
    if not isinstance(name, str):
        return ""

    return name.strip()[:_LABEL_NAME_MAX_LENGTH]


def _normalize_color(color: Any) -> str:
    if not isinstance(color, str):
        return ""

    color = color.strip()
    if len(color) == 7 and color.startswith("#"):
        return color

    return ""


def _normalize_type(label_type: Any) -> str:
    if isinstance(label_type, str) and label_type in _KNOWN_LABEL_TYPES:
        return label_type

    return str(LabelType.ANY)


def _normalize_attributes(raw_attributes: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_attributes, list):
        return []

    attributes = []
    used_names: set[str] = set()

    for raw_attribute in raw_attributes:
        if not isinstance(raw_attribute, dict):
            continue

        name = _normalize_name(raw_attribute.get("name"))
        input_type = raw_attribute.get("input_type")
        if not name or name in used_names or input_type not in _KNOWN_ATTRIBUTE_TYPES:
            continue

        used_names.add(name)
        values = raw_attribute.get("values")
        attributes.append(
            {
                "name": name,
                "mutable": bool(raw_attribute.get("mutable")),
                "input_type": input_type,
                "default_value": str(raw_attribute.get("default_value") or "")[:128],
                "values": (
                    [str(value)[:200] for value in values] if isinstance(values, list) else []
                ),
            }
        )

    return attributes
