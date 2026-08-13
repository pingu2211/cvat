# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from typing import Any

from django.contrib.auth.models import Group, User
from rest_framework import status

from cvat.apps.engine.models import Project, Task
from cvat.apps.engine.tests.utils import ApiTestBase, ForceLogin

_FUNCTION_ID = "pth-facebookresearch-sam3-detector"


class AutoAnnotationConfigAPITestCase(ApiTestBase):
    """
    Tests for the auto annotation model configured on a project or a task.
    """

    @classmethod
    def setUpTestData(cls):
        Group.objects.get_or_create(name="user")
        cls.user = User.objects.create_user(username="user1", password="user1")

    def _create_project(self, **fields: Any) -> dict[str, Any]:
        with ForceLogin(self.user, self.client):
            response = self.client.post(
                "/api/projects",
                data={"name": "project", "labels": [{"name": "car"}], **fields},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.json()

    def _create_task(self, **fields: Any) -> dict[str, Any]:
        with ForceLogin(self.user, self.client):
            response = self.client.post(
                "/api/tasks", data={"name": "task", **fields}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.json()

    def _patch(self, path: str, data: dict[str, Any]):
        with ForceLogin(self.user, self.client):
            return self.client.patch(path, data=data, format="json")

    def _get(self, path: str) -> dict[str, Any]:
        with ForceLogin(self.user, self.client):
            response = self.client.get(path)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()

    def test_config_is_empty_by_default(self):
        project = self._create_project()
        self.assertEqual("", project["auto_annotation_function"])
        self.assertIsNone(project["auto_annotation_threshold"])
        self.assertIsNone(Project.objects.get(pk=project["id"]).get_auto_annotation_config())

        task = self._create_task(labels=[{"name": "car"}])
        self.assertEqual("", task["auto_annotation_function"])
        self.assertIsNone(task["auto_annotation_threshold"])
        self.assertIsNone(Task.objects.get(pk=task["id"]).get_auto_annotation_config())

    def test_can_configure_a_model_on_a_project(self):
        project = self._create_project(
            auto_annotation_function=_FUNCTION_ID, auto_annotation_threshold=0.6
        )
        self.assertEqual(_FUNCTION_ID, project["auto_annotation_function"])
        self.assertEqual(0.6, project["auto_annotation_threshold"])

        config = Project.objects.get(pk=project["id"]).get_auto_annotation_config()
        self.assertEqual((_FUNCTION_ID, 0.6), config)

    def test_can_configure_a_model_on_a_task(self):
        task = self._create_task(labels=[{"name": "car"}])

        response = self._patch(
            f"/api/tasks/{task['id']}",
            {"auto_annotation_function": _FUNCTION_ID, "auto_annotation_threshold": 0.4},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        config = Task.objects.get(pk=task["id"]).get_auto_annotation_config()
        self.assertEqual((_FUNCTION_ID, 0.4), config)

    def test_task_inherits_the_project_config(self):
        project = self._create_project(
            auto_annotation_function=_FUNCTION_ID, auto_annotation_threshold=0.6
        )
        task = self._create_task(project_id=project["id"])

        db_task = Task.objects.get(pk=task["id"])
        self.assertEqual((_FUNCTION_ID, 0.6), db_task.get_auto_annotation_config())

        # the task itself is not modified, only its effective configuration changes
        self.assertEqual("", task["auto_annotation_function"])

    def test_task_config_overrides_the_project_one_as_a_whole(self):
        project = self._create_project(
            auto_annotation_function=_FUNCTION_ID, auto_annotation_threshold=0.6
        )
        task = self._create_task(project_id=project["id"])

        response = self._patch(
            f"/api/tasks/{task['id']}", {"auto_annotation_function": "other-function"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        # the project threshold must not be combined with the task function
        db_task = Task.objects.get(pk=task["id"])
        self.assertEqual(("other-function", None), db_task.get_auto_annotation_config())

    def test_can_reset_the_config(self):
        project = self._create_project(
            auto_annotation_function=_FUNCTION_ID, auto_annotation_threshold=0.6
        )

        response = self._patch(
            f"/api/projects/{project['id']}",
            {"auto_annotation_function": "", "auto_annotation_threshold": None},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        self.assertIsNone(Project.objects.get(pk=project["id"]).get_auto_annotation_config())

    def test_cannot_set_a_threshold_out_of_range(self):
        project = self._create_project()

        for value in (-0.1, 1.5):
            with self.subTest(threshold=value):
                response = self._patch(
                    f"/api/projects/{project['id']}", {"auto_annotation_threshold": value}
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertIsNone(self._get(f"/api/projects/{project['id']}")["auto_annotation_threshold"])
