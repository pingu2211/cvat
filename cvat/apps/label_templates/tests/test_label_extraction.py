# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

import io
import json
import zipfile

from django.test import SimpleTestCase

from cvat.apps.label_templates.label_extraction import LabelExtractionError, extract_labels

CVAT_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<annotations>
  <version>1.1</version>
  <meta><task><id>1</id><labels>
    <label>
      <name>car</name><color>#ff0000</color><type>rectangle</type>
      <attributes><attribute>
        <name>parked</name><mutable>True</mutable><input_type>select</input_type>
        <default_value>yes</default_value><values>yes&#10;no</values>
      </attribute></attributes>
    </label>
    <label><name>sky</name><color></color><type>mask</type><attributes></attributes></label>
  </labels></task></meta>
</annotations>"""


def as_file(data) -> io.BytesIO:
    if isinstance(data, (dict, list)):
        data = json.dumps(data).encode()

    return io.BytesIO(data)


class TestExtractLabels(SimpleTestCase):
    def test_reads_a_backup_manifest(self) -> None:
        labels = extract_labels(
            as_file(
                {
                    "name": "task",
                    "labels": [
                        {
                            "name": "cat",
                            "color": "#00ff00",
                            "type": "polygon",
                            "attributes": [
                                {
                                    "name": "age",
                                    "mutable": False,
                                    "input_type": "number",
                                    "default_value": "1",
                                    "values": ["1", "10", "1"],
                                }
                            ],
                            "sublabels": [],
                        }
                    ],
                }
            )
        )

        assert labels == [
            {
                "name": "cat",
                "color": "#00ff00",
                "type": "polygon",
                "prompt": "",
                "attributes": [
                    {
                        "name": "age",
                        "mutable": False,
                        "input_type": "number",
                        "default_value": "1",
                        "values": ["1", "10", "1"],
                    }
                ],
                "sublabels": [],
                "svg": "",
            }
        ]

    def test_reads_backup_annotations(self) -> None:
        labels = extract_labels(
            as_file(
                [
                    {
                        "version": 0,
                        "tags": [{"label": "daylight", "frame": 0}],
                        "shapes": [
                            {"type": "rectangle", "label": "car"},
                            {"type": "rectangle", "label": "car"},
                            {"type": "polygon", "label": "road"},
                        ],
                        "tracks": [{"type": "points", "label": "road"}],
                    }
                ]
            )
        )

        by_name = {label["name"]: label["type"] for label in labels}
        assert by_name == {
            "car": "rectangle",
            "daylight": "tag",
            # used by both a polygon and a track of points, so it stays untyped
            "road": "any",
        }

    def test_reads_cvat_xml(self) -> None:
        labels = extract_labels(as_file(CVAT_XML))

        assert [label["name"] for label in labels] == ["car", "sky"]
        assert labels[0]["color"] == "#ff0000"
        assert labels[0]["attributes"] == [
            {
                "name": "parked",
                "mutable": True,
                "input_type": "select",
                "default_value": "yes",
                "values": ["yes", "no"],
            }
        ]
        assert labels[1] == {
            "name": "sky",
            "color": "",
            "type": "mask",
            "prompt": "",
            "attributes": [],
            "sublabels": [],
            "svg": "",
        }

    def test_reads_datumaro_annotations(self) -> None:
        labels = extract_labels(
            as_file(
                {
                    "categories": {
                        "label": {
                            "labels": [
                                {"name": "cat", "parent": ""},
                                {"name": "leg", "parent": "cat"},
                            ]
                        }
                    },
                    "items": [],
                }
            )
        )

        # sublabels are only meaningful together with a skeleton layout
        assert [label["name"] for label in labels] == ["cat"]

    def test_reads_coco_annotations(self) -> None:
        labels = extract_labels(
            as_file({"categories": [{"id": 1, "name": "person"}], "annotations": []})
        )

        assert [label["name"] for label in labels] == ["person"]

    def test_prefers_the_manifest_of_an_archive(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "task_0/annotations.json",
                json.dumps([{"shapes": [{"type": "rectangle", "label": "used label"}]}]),
            )
            archive.writestr(
                "task_0/task.json",
                json.dumps({"labels": [{"name": "declared label", "type": "rectangle"}]}),
            )

        labels = extract_labels(buffer)

        assert [label["name"] for label in labels] == ["declared label"]

    def test_falls_back_to_annotations_of_an_archive(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("task_0/task.json", "{ not json")
            archive.writestr(
                "task_0/annotations.json",
                json.dumps([{"shapes": [{"type": "rectangle", "label": "used label"}]}]),
            )

        labels = extract_labels(buffer)

        assert [label["name"] for label in labels] == ["used label"]

    def test_keeps_a_complete_skeleton(self) -> None:
        labels = extract_labels(
            as_file(
                {
                    "labels": [
                        {
                            "name": "pose",
                            "type": "skeleton",
                            "svg": "<circle/>",
                            "sublabels": [{"name": "head", "type": "points"}],
                        }
                    ]
                }
            )
        )

        assert labels[0]["type"] == "skeleton"
        assert labels[0]["sublabels"] == [
            {"name": "head", "color": "", "type": "points", "prompt": "", "attributes": []}
        ]

    def test_downgrades_a_skeleton_without_a_layout(self) -> None:
        labels = extract_labels(
            as_file({"labels": [{"name": "pose", "type": "skeleton", "sublabels": []}]})
        )

        assert labels[0]["type"] == "any"
        assert labels[0]["sublabels"] == []

    def test_drops_duplicates_and_unusable_values(self) -> None:
        labels = extract_labels(
            as_file(
                {
                    "labels": [
                        {"name": "cat", "type": "made up type", "color": "red"},
                        {"name": "cat", "type": "polygon"},
                        {"name": "", "type": "polygon"},
                        "not a label",
                        {
                            "name": "dog",
                            "attributes": [{"name": "age", "input_type": "made up type"}],
                        },
                    ]
                }
            )
        )

        assert [label["name"] for label in labels] == ["cat", "dog"]
        assert labels[0]["type"] == "any"
        assert labels[0]["color"] == ""
        assert labels[1]["attributes"] == []

    def test_rejects_an_xml_bomb(self) -> None:
        bomb = b"""<?xml version="1.0"?>
        <!DOCTYPE annotations [
          <!ENTITY a "aaaaaaaaaa">
          <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
        ]>
        <annotations><meta><task><labels>
          <label><name>&b;</name></label>
        </labels></task></meta></annotations>"""

        with self.assertRaises(LabelExtractionError):
            extract_labels(as_file(bomb))

    def test_rejects_files_without_labels(self) -> None:
        for content in (b"not an export", b"{}", b"[]", json.dumps({"labels": []}).encode()):
            with self.subTest(content=content):
                with self.assertRaises(LabelExtractionError):
                    extract_labels(as_file(content))
