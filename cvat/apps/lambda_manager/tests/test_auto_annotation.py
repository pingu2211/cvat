# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from typing import Any

from rest_framework import status

from cvat.apps.engine.tests.utils import ForceLogin, generate_image_file
from cvat.apps.lambda_manager.tests.test_lambda import (
    _LambdaTestCaseBase,
    id_function_interactor,
    id_function_prompt_detector,
)


class AutoAnnotationOfAppendedImagesTestCase(_LambdaTestCaseBase):
    """
    Tests for automatically annotating the images appended to a task
    with the model configured on the task or its project.
    """

    def _create_task_with_images(self, image_names: list[str], **task_spec: Any) -> int:
        data = {
            f"client_files[{i}]": generate_image_file(name) for i, name in enumerate(image_names)
        }
        data["image_quality"] = 75

        spec = {
            "name": "task to append to",
            "labels": [{"name": "car", "prompt": "a car"}],
            **task_spec,
        }
        if spec.get("project_id"):
            # a task takes its labels from its project
            del spec["labels"]

        return self._create_task(task_spec=spec, data=data, owner=self.admin)["id"]

    def _append_images(self, task_id: int, image_names: list[str]) -> None:
        data = {
            f"client_files[{i}]": generate_image_file(name) for i, name in enumerate(image_names)
        }

        # the auto annotation is started from an on_commit hook, which a TestCase
        # would otherwise never run, as it rolls the outer transaction back
        with ForceLogin(self.admin, self.client), self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f"/api/tasks/{task_id}/data/append", data=data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)

        rq_id = response.json()["rq_id"]
        response = self._get_request(f"/api/requests/{rq_id}", self.admin)
        self.assertEqual(response.json()["status"], "finished", response.json()["message"])

    def _get_annotated_frames(self, task_id: int) -> list[int]:
        response = self._get_request(f"/api/tasks/{task_id}/annotations", self.admin)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return sorted({shape["frame"] for shape in response.json()["shapes"]})

    def test_appended_images_are_annotated_with_the_configured_model(self):
        task_id = self._create_task_with_images(
            ["image_1.jpg", "image_2.jpg"],
            auto_annotation_function=id_function_prompt_detector,
            auto_annotation_threshold=0.5,
        )
        self.assertEqual([], self._get_annotated_frames(task_id))

        self._append_images(task_id, ["image_3.jpg", "image_4.jpg"])

        # only the appended frames must be annotated
        self.assertEqual([2, 3], self._get_annotated_frames(task_id))

    def test_appended_images_are_annotated_with_the_project_model(self):
        with ForceLogin(self.admin, self.client):
            response = self.client.post(
                "/api/projects",
                data={
                    "name": "project with a model",
                    "labels": [{"name": "car", "prompt": "a car"}],
                    "auto_annotation_function": id_function_prompt_detector,
                },
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        task_id = self._create_task_with_images(["image_1.jpg"], project_id=response.json()["id"])

        self._append_images(task_id, ["image_2.jpg"])

        self.assertEqual([1], self._get_annotated_frames(task_id))

    def test_existing_annotations_are_kept(self):
        task_id = self._create_task_with_images(
            ["image_1.jpg", "image_2.jpg"],
            auto_annotation_function=id_function_prompt_detector,
        )

        response = self._get_request(f"/api/tasks/{task_id}", self.admin)
        label_id = self._get_request(f"/api/labels?task_id={task_id}", self.admin).json()[
            "results"
        ][0]["id"]
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        with ForceLogin(self.admin, self.client):
            response = self.client.put(
                f"/api/tasks/{task_id}/annotations",
                data={
                    "version": 0,
                    "tags": [],
                    "tracks": [],
                    "shapes": [
                        {
                            "type": "rectangle",
                            "occluded": False,
                            "outside": False,
                            "z_order": 0,
                            "rotation": 0,
                            "points": [1.0, 2.0, 30.0, 40.0],
                            "frame": 0,
                            "label_id": label_id,
                            "group": 0,
                            "source": "manual",
                            "attributes": [],
                            "elements": [],
                        }
                    ],
                },
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        self._append_images(task_id, ["image_3.jpg"])

        # the manual annotation on frame 0 must survive, and frame 2 must be annotated
        self.assertEqual([0, 2], self._get_annotated_frames(task_id))

    def test_nothing_is_annotated_without_a_configured_model(self):
        task_id = self._create_task_with_images(["image_1.jpg"])

        self._append_images(task_id, ["image_2.jpg"])

        self.assertEqual([], self._get_annotated_frames(task_id))

    def test_appending_succeeds_when_the_configured_model_cannot_be_run(self):
        task_id = self._create_task_with_images(
            ["image_1.jpg"],
            # an interactor cannot be run as a batch detector
            auto_annotation_function=id_function_interactor,
        )

        self._append_images(task_id, ["image_2.jpg"])

        # the frames are appended even though the annotation could not be started
        response = self._get_request(f"/api/tasks/{task_id}/data/meta", self.admin)
        self.assertEqual(2, response.json()["size"])
        self.assertEqual([], self._get_annotated_frames(task_id))
