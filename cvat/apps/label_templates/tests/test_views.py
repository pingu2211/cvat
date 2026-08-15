# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

import io
import json
from http import HTTPStatus
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from cvat.apps.iam.permissions import OpenPolicyAgentPermission, PermissionResult
from cvat.apps.label_templates.models import LabelTemplate


def allow_everything(self):
    return PermissionResult(allow=True)


def no_filtering(self, queryset):
    return self.add_org_filter_proof(queryset)


@patch.object(OpenPolicyAgentPermission, "check_access", allow_everything)
@patch.object(OpenPolicyAgentPermission, "filter", no_filtering)
class TestLabelTemplateViewSet(TestCase):
    """
    Checks the endpoints with the access checks stubbed out, they are covered
    by the Rego policy of the application.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.create_user(username="template-author", password="pass")

    def setUp(self) -> None:
        self.client.force_login(self.user)

    def create_template(self, **overrides):
        data = {
            "name": "Traffic",
            "description": "Objects seen on a road",
            "labels": [{"name": "car", "type": "rectangle"}],
        }
        data.update(overrides)
        return self.client.post(
            "/api/label-templates", data=json.dumps(data), content_type="application/json"
        )

    def test_creates_a_template_with_a_full_label_specification(self) -> None:
        response = self.create_template(
            labels=[
                {
                    "name": "car",
                    "type": "rectangle",
                    "attributes": [{"name": "parked", "input_type": "checkbox"}],
                }
            ]
        )

        assert response.status_code == HTTPStatus.CREATED
        body = response.json()
        assert body["name"] == "Traffic"
        assert body["owner"]["username"] == self.user.username
        assert body["organization"] is None
        assert body["labels"] == [
            {
                "name": "car",
                "color": "",
                "type": "rectangle",
                "prompt": "",
                "sublabels": [],
                "svg": "",
                "attributes": [
                    {
                        "name": "parked",
                        "mutable": False,
                        "input_type": "checkbox",
                        "default_value": "",
                        "values": [],
                    }
                ],
            }
        ]

    def test_rejects_a_template_without_labels(self) -> None:
        assert self.create_template(labels=[]).status_code == HTTPStatus.BAD_REQUEST

    def test_rejects_duplicated_label_names(self) -> None:
        response = self.create_template(
            labels=[{"name": "car", "type": "rectangle"}, {"name": "car", "type": "polygon"}]
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_rejects_a_duplicated_template_name(self) -> None:
        assert self.create_template().status_code == HTTPStatus.CREATED
        assert self.create_template().status_code == HTTPStatus.BAD_REQUEST

    def test_rejects_a_skeleton_without_sublabels(self) -> None:
        response = self.create_template(labels=[{"name": "pose", "type": "skeleton"}])

        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_lists_templates(self) -> None:
        self.create_template()

        response = self.client.get("/api/label-templates")

        assert response.status_code == HTTPStatus.OK
        assert [item["name"] for item in response.json()["results"]] == ["Traffic"]

    def test_updates_a_template(self) -> None:
        template_id = self.create_template().json()["id"]

        response = self.client.patch(
            f"/api/label-templates/{template_id}",
            data=json.dumps({"name": "Road", "labels": [{"name": "bus", "type": "polygon"}]}),
            content_type="application/json",
        )

        assert response.status_code == HTTPStatus.OK
        assert response.json()["name"] == "Road"
        # a partial update stores labels just as complete as a creation does
        assert response.json()["labels"] == [
            {
                "name": "bus",
                "color": "",
                "type": "polygon",
                "prompt": "",
                "attributes": [],
                "sublabels": [],
                "svg": "",
            }
        ]

    def test_deletes_a_template(self) -> None:
        template_id = self.create_template().json()["id"]

        response = self.client.delete(f"/api/label-templates/{template_id}")

        assert response.status_code == HTTPStatus.NO_CONTENT
        assert not LabelTemplate.objects.filter(id=template_id).exists()

    def test_extracts_labels_from_an_upload(self) -> None:
        upload = io.BytesIO(
            json.dumps({"labels": [{"name": "cat", "type": "polygon"}]}).encode(),
        )
        upload.name = "task.json"

        response = self.client.post(
            "/api/label-templates/extract-labels", data={"file": upload}, format="multipart"
        )

        assert response.status_code == HTTPStatus.OK
        assert [label["name"] for label in response.json()["labels"]] == ["cat"]

    def test_reports_an_unusable_upload(self) -> None:
        upload = io.BytesIO(b"not an export")
        upload.name = "notes.txt"

        response = self.client.post(
            "/api/label-templates/extract-labels", data={"file": upload}, format="multipart"
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
