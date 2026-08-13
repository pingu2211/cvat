# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from typing import Any

from django.contrib.auth.models import Group, User
from rest_framework import status

from cvat.apps.engine.models import Task
from cvat.apps.engine.tests.utils import (
    ApiTestBase,
    ForceLogin,
    generate_image_file,
    generate_video_file,
)


class TaskDataAppendAPITestCase(ApiTestBase):
    """
    Tests for POST /api/tasks/{id}/data/append, which adds more images
    to a task that already has data attached to it.
    """

    @classmethod
    def setUpTestData(cls):
        Group.objects.get_or_create(name="user")
        cls.user = User.objects.create_user(username="user1", password="user1")

    def _create_task(self, *, media: dict[str, Any], **task_spec) -> int:
        spec = {
            "name": "task with appendable data",
            "labels": [{"name": "car"}],
            **task_spec,
        }

        with ForceLogin(self.user, self.client):
            response = self.client.post("/api/tasks", data=spec, format="json")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            task_id = response.data["id"]

            response = self.client.post(
                f"/api/tasks/{task_id}/data", data={"image_quality": 75, **media}
            )
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
            self._assert_request_finished(response.json()["rq_id"])

        return task_id

    def _append_images(self, task_id: int, data: dict[str, Any], *, user: User | None = None):
        with ForceLogin(user or self.user, self.client):
            return self.client.post(f"/api/tasks/{task_id}/data/append", data=data)

    def _assert_request_finished(self, rq_id: str) -> None:
        with ForceLogin(self.user, self.client):
            response = self.client.get(f"/api/requests/{rq_id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_json = response.json()
        self.assertEqual(response_json["status"], "finished", response_json["message"])

    def _get_meta(self, task_id: int) -> dict[str, Any]:
        with ForceLogin(self.user, self.client):
            response = self.client.get(f"/api/tasks/{task_id}/data/meta")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()

    def _get_jobs(self, task_id: int) -> list[dict[str, Any]]:
        with ForceLogin(self.user, self.client):
            response = self.client.get("/api/jobs", query_params={"task_id": task_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return sorted(response.json()["results"], key=lambda job: job["start_frame"])

    def _put_annotations(self, job_id: int, annotations: dict[str, Any]) -> None:
        with ForceLogin(self.user, self.client):
            response = self.client.put(
                f"/api/jobs/{job_id}/annotations", data=annotations, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def _get_annotations(self, job_id: int) -> dict[str, Any]:
        with ForceLogin(self.user, self.client):
            response = self.client.get(f"/api/jobs/{job_id}/annotations")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()

    def test_can_append_images_and_keep_existing_annotations(self):
        task_id = self._create_task(
            segment_size=2,
            media={
                "client_files[0]": generate_image_file("image_1.jpg"),
                "client_files[1]": generate_image_file("image_2.jpg"),
                "client_files[2]": generate_image_file("image_3.jpg"),
            },
        )

        jobs_before = self._get_jobs(task_id)
        self.assertEqual(
            [(0, 1), (2, 2)], [(j["start_frame"], j["stop_frame"]) for j in jobs_before]
        )

        label_id = self._get_meta(task_id) and Task.objects.get(pk=task_id).label_set.first().id
        annotations = {
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
        }
        self._put_annotations(jobs_before[0]["id"], annotations)

        response = self._append_images(
            task_id,
            {
                "client_files[0]": generate_image_file("image_4.jpg"),
                "client_files[1]": generate_image_file("image_5.jpg"),
                "client_files[2]": generate_image_file("image_6.jpg"),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
        self._assert_request_finished(response.json()["rq_id"])

        meta = self._get_meta(task_id)
        self.assertEqual(6, meta["size"])
        self.assertEqual(0, meta["start_frame"])
        self.assertEqual(5, meta["stop_frame"])
        self.assertEqual(
            [f"image_{i}.jpg" for i in range(1, 7)], [frame["name"] for frame in meta["frames"]]
        )

        # the appended frames must only be covered by new jobs
        jobs_after = self._get_jobs(task_id)
        self.assertEqual(
            [(0, 1), (2, 2), (3, 4), (5, 5)],
            [(j["start_frame"], j["stop_frame"]) for j in jobs_after],
        )
        self.assertEqual(
            [j["id"] for j in jobs_before], [j["id"] for j in jobs_after[: len(jobs_before)]]
        )

        # the annotations of the existing jobs must be intact
        job_annotations = self._get_annotations(jobs_before[0]["id"])
        self.assertEqual(1, len(job_annotations["shapes"]))
        self.assertEqual([1.0, 2.0, 30.0, 40.0], job_annotations["shapes"][0]["points"])

        # the appended frames must be readable
        with ForceLogin(self.user, self.client):
            response = self.client.get(
                f"/api/jobs/{jobs_after[-1]['id']}/data",
                query_params={"type": "frame", "quality": "original", "number": 5},
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_can_append_images_in_the_requested_order(self):
        task_id = self._create_task(
            media={
                "client_files[0]": generate_image_file("image_1.jpg"),
            },
        )

        response = self._append_images(
            task_id,
            {
                "client_files[0]": generate_image_file("image_2.jpg"),
                "client_files[1]": generate_image_file("image_3.jpg"),
                "upload_file_order[0]": "image_3.jpg",
                "upload_file_order[1]": "image_2.jpg",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)
        self._assert_request_finished(response.json()["rq_id"])

        meta = self._get_meta(task_id)
        self.assertEqual(
            ["image_1.jpg", "image_3.jpg", "image_2.jpg"],
            [frame["name"] for frame in meta["frames"]],
        )

    def test_cannot_append_images_with_incomplete_file_order(self):
        task_id = self._create_task(
            media={"client_files[0]": generate_image_file("image_1.jpg")},
        )

        response = self._append_images(
            task_id,
            {
                "client_files[0]": generate_image_file("image_2.jpg"),
                "client_files[1]": generate_image_file("image_3.jpg"),
                "upload_file_order[0]": "image_2.jpg",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)

        self._assert_request_failed(response.json()["rq_id"], "image_3.jpg")
        self.assertEqual(1, self._get_meta(task_id)["size"])

    def test_cannot_append_image_with_an_already_used_name(self):
        task_id = self._create_task(
            media={"client_files[0]": generate_image_file("image_1.jpg")},
        )

        response = self._append_images(
            task_id, {"client_files[0]": generate_image_file("image_1.jpg")}
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)

        self._assert_request_failed(response.json()["rq_id"], "already present in the task")

        meta = self._get_meta(task_id)
        self.assertEqual(1, meta["size"])
        self.assertEqual(["image_1.jpg"], [frame["name"] for frame in meta["frames"]])

    def test_cannot_append_non_image_files(self):
        task_id = self._create_task(
            media={"client_files[0]": generate_image_file("image_1.jpg")},
        )

        _, video_file = generate_video_file("video_1.mp4", width=64, height=64, duration=1)
        response = self._append_images(task_id, {"client_files[0]": video_file})
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED, response.data)

        self._assert_request_failed(response.json()["rq_id"], "Only image files can be appended")
        self.assertEqual(1, self._get_meta(task_id)["size"])

    def test_cannot_append_images_to_a_video_task(self):
        _, video_file = generate_video_file("video_1.mp4", width=64, height=64, duration=1)
        task_id = self._create_task(media={"client_files[0]": video_file})

        response = self._append_images(
            task_id, {"client_files[0]": generate_image_file("image_1.jpg")}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("image-based tasks", str(response.data))

    def test_cannot_append_images_to_a_task_without_data(self):
        with ForceLogin(self.user, self.client):
            response = self.client.post(
                "/api/tasks",
                data={"name": "empty task", "labels": [{"name": "car"}]},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            task_id = response.data["id"]

        response = self._append_images(
            task_id, {"client_files[0]": generate_image_file("image_1.jpg")}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not been initialized", str(response.data))

    def test_cannot_append_images_as_another_user(self):
        task_id = self._create_task(
            media={"client_files[0]": generate_image_file("image_1.jpg")},
        )

        other_user = User.objects.create_user(username="user2", password="user2")
        response = self._append_images(
            task_id,
            {"client_files[0]": generate_image_file("image_2.jpg")},
            user=other_user,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def _assert_request_failed(self, rq_id: str, expected_message_part: str) -> None:
        with ForceLogin(self.user, self.client):
            response = self.client.get(f"/api/requests/{rq_id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_json = response.json()
        self.assertEqual(response_json["status"], "failed", response_json)
        self.assertIn(expected_message_part, response_json["message"])
