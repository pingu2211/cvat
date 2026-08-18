# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from typing import Any
from unittest import mock

import django_rq
import requests
import rq
from django.conf import settings
from django.test import SimpleTestCase
from rest_framework import status

from cvat.apps.lambda_manager.models import FunctionKind
from cvat.apps.lambda_manager.rq import LambdaRQMeta
from cvat.apps.lambda_manager.tests.test_lambda import (
    LAMBDA_REQUESTS_PATH,
    _LambdaTestCaseBase,
    id_function_detector,
    id_function_reid_with_response_data,
)
from cvat.apps.lambda_manager.views import LambdaFunction, LambdaJob


class FrameSetTestCase(SimpleTestCase):
    """
    A resumed run continues after a single frame, which is only enough because every
    scope is iterated in ascending order.
    """

    @staticmethod
    def _make_task(size: int) -> mock.MagicMock:
        db_task = mock.MagicMock()
        db_task.data.size = size
        return db_task

    def test_task_scope_is_ascending_and_can_be_resumed(self):
        db_task = self._make_task(10)

        self.assertEqual(list(range(10)), list(LambdaJob._get_frame_set(db_task, None)))
        self.assertEqual([7, 8, 9], list(LambdaJob._get_frame_set(db_task, None, resume_from=6)))

    def test_job_scope_is_ascending_and_can_be_resumed(self):
        db_task = self._make_task(10)
        db_task.data.start_frame = 3
        db_task.data.get_frame_step.return_value = 5

        db_job = mock.MagicMock()
        # deliberately unordered, as a segment frame set carries no order of its own
        db_job.segment.frame_set = {23, 3, 18, 8, 13}

        self.assertEqual([0, 1, 2, 3, 4], list(LambdaJob._get_frame_set(db_task, db_job)))
        self.assertEqual([3, 4], list(LambdaJob._get_frame_set(db_task, db_job, resume_from=2)))

    def test_a_restricted_scope_is_ascending_and_can_be_resumed(self):
        db_task = self._make_task(10)

        self.assertEqual(
            [1, 4, 6, 8], list(LambdaJob._get_frame_set(db_task, None, frames=[8, 1, 6, 4]))
        )
        self.assertEqual(
            [6, 8],
            list(LambdaJob._get_frame_set(db_task, None, frames=[8, 1, 6, 4], resume_from=4)),
        )

    def test_a_fully_annotated_scope_leaves_nothing_to_do(self):
        db_task = self._make_task(10)

        self.assertEqual([], list(LambdaJob._get_frame_set(db_task, None, resume_from=9)))


class _RecordingCollector:
    """
    Stands in for DetectionResultCollector: keeps the added results in memory and only
    writes them down once they are submitted, just like the real one does, so that the
    effect of the submit batching can be observed.
    """

    def __init__(self, written: list[int]) -> None:
        self.written = written
        self._pending: list[int] = []

    def add(self, data: dict) -> None:
        self._pending.extend(shape["frame"] for shape in data["shapes"])

    def submit(self) -> None:
        if not self._pending:
            return

        self.written.extend(self._pending)
        self._pending = []


def _do_nothing() -> None:
    """Stands in for the callable of the job under test, which is never run"""


def _create_started_rq_job() -> rq.job.Job:
    """A queued job the progress bookkeeping can be pointed at"""
    queue = django_rq.get_queue(settings.CVAT_QUEUES.AUTO_ANNOTATION.value)
    job = rq.job.Job.create(func=_do_nothing, connection=queue.connection, id="test-resume-point")
    job.save()
    job.set_status(rq.job.JobStatus.STARTED)

    return job


class ResumePointTestCase(SimpleTestCase):
    """
    The point a resumed run continues from must be the last frame whose results were
    submitted, and not the last one that was processed: results are only written every
    100 frames, so the ones in between are still in memory when a run dies.
    """

    def setUp(self):
        super().setUp()

        self.rq_job = _create_started_rq_job()
        self.addCleanup(self.rq_job.delete)
        self.written: list[int] = []
        self.collector = _RecordingCollector(self.written)
        self.failing_frame: int | None = None
        self.cancelled_at_frame: int | None = None

        for target, replacement in (
            ("cvat.apps.lambda_manager.views.DetectionResultConverter", mock.MagicMock()),
            (
                "cvat.apps.lambda_manager.views.DetectionResultCollector",
                mock.MagicMock(side_effect=lambda db_task, db_job: self.collector),
            ),
            ("rq.get_current_job", mock.MagicMock(return_value=self.rq_job)),
        ):
            patcher = mock.patch(target, replacement)
            self.addCleanup(patcher.stop)
            patcher.start()

    def _invoke(self, db_task, *, db_job, data, converter):
        frame = data["frame"]

        if frame == self.failing_frame:
            raise requests.ConnectionError("the function is gone")

        if frame == self.cancelled_at_frame:
            # cancelling deletes the queued job, which is what breaks the run loop
            self.rq_job.delete()

        return {"tags": [], "shapes": [{"frame": frame}], "tracks": []}

    def _run(self, *, size: int = 250, resume_from: int | None = None) -> None:
        db_task = mock.MagicMock()
        db_task.data.size = size
        db_task.data.deleted_frames = []

        function = mock.MagicMock()
        function.invoke.side_effect = self._invoke

        LambdaJob._call_detector(
            function, db_task, 0.5, None, False, db_job=None, resume_from=resume_from
        )

    @property
    def _resume_point(self) -> int | None:
        return LambdaRQMeta.for_job(self.rq_job).last_submitted_frame

    def test_a_completed_run_records_its_last_frame(self):
        self._run(size=250)

        self.assertEqual(list(range(250)), self.written)
        self.assertEqual(249, self._resume_point)

    def test_an_interrupted_run_records_the_last_submitted_frame(self):
        self.failing_frame = 137

        with self.assertRaises(requests.ConnectionError):
            self._run(size=250)

        # the results of frames 101 to 136 were computed but never written down, so
        # the run has to be continued from frame 100 rather than from frame 136
        self.assertEqual(list(range(101)), self.written)
        self.assertEqual(100, self._resume_point)

        # the reported progress stands well past the point that is safe to resume
        # from, which is exactly why it cannot be used as one
        progress = LambdaRQMeta.for_job(self.rq_job).progress
        self.assertGreater(progress * 250 // 100, self._resume_point)

    def test_a_cancelled_run_records_the_frame_its_results_reach(self):
        self.cancelled_at_frame = 137

        self._run(size=250)

        # the loop breaks before the results of frame 137 are collected, and what was
        # collected before it is submitted on the way out
        self.assertEqual(list(range(137)), self.written)
        self.assertEqual(136, self._resume_point)

    def test_a_run_that_submits_nothing_records_no_resume_point(self):
        self.failing_frame = 42

        with self.assertRaises(requests.ConnectionError):
            self._run(size=250)

        self.assertEqual([], self.written)
        self.assertIsNone(self._resume_point)

    def test_a_resumed_run_keeps_its_own_starting_point(self):
        self.failing_frame = 101

        with self.assertRaises(requests.ConnectionError):
            self._run(size=250, resume_from=100)

        # nothing new was submitted, so a further resume must still start at frame
        # 100 instead of running the whole scope over again
        self.assertEqual([], self.written)
        self.assertEqual(100, self._resume_point)

    def test_a_resumed_run_only_covers_the_remaining_frames(self):
        self._run(size=250, resume_from=100)

        self.assertEqual(list(range(101, 250)), self.written)
        self.assertEqual(249, self._resume_point)

    def test_a_run_that_finds_nothing_still_records_its_last_frame(self):
        with mock.patch.object(_RecordingCollector, "add", lambda self, data: None):
            self._run(size=250)

        self.assertEqual([], self.written)
        self.assertEqual(249, self._resume_point)


class ResumeRequestTestCase(_LambdaTestCaseBase):
    """Tests for continuing a failed automatic annotation run through the API"""

    def _invoke_function(self, func, payload):
        if func.kind == FunctionKind.REID:
            return [0]

        return [
            {
                "confidence": "0.99",
                "label": "car",
                "points": [3, 3, 15, 15],
                "type": "rectangle",
            },
        ]

    def setUp(self):
        super().setUp()

        self.failing_frames: set[int] = set()

        # the frame is not part of what reaches the gateway, so the interruption is
        # simulated one level up, where the function is called for a single frame
        original_invoke = LambdaFunction.invoke

        def invoke(func, db_task, data, **kwargs):
            # a reid call covers a pair of frames and has no single frame of its own
            if data.get("frame", data.get("frame0")) in self.failing_frames:
                raise requests.ConnectionError("the function container has been redeployed")

            return original_invoke(func, db_task, data, **kwargs)

        invoke_patcher = mock.patch.object(LambdaFunction, "invoke", invoke)
        self.addCleanup(invoke_patcher.stop)
        invoke_patcher.start()

        self.task = self._create_task(
            task_spec={
                "name": "task to resume",
                "labels": [{"name": "car"}],
                "segment_size": 4,
            },
            data=self._generate_task_images(8),
            owner=self.admin,
        )
        self.label_id = self._get_task_label_ids_by_name(self.task["id"])["car"]
        self.jobs = sorted(
            self._get_request(
                "/api/jobs", self.admin, query_params={"task_id": self.task["id"]}
            ).json()["results"],
            key=lambda job: job["start_frame"],
        )

    def _start_run(self, function_id: str = id_function_detector, **extra: Any) -> str:
        response = self._post_request(
            LAMBDA_REQUESTS_PATH,
            self.admin,
            data={"function": function_id, "task": self.task["id"], **extra},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        return response.json()["id"]

    def _set_resume_point(self, request_id: str, frame: int) -> None:
        queue = django_rq.get_queue(settings.CVAT_QUEUES.AUTO_ANNOTATION.value)
        meta = LambdaRQMeta.for_job(queue.fetch_job(request_id))
        meta.last_submitted_frame = frame
        meta.save()

    def _resume(self, request_id: str, user=None):
        return self._post_request(
            f"{LAMBDA_REQUESTS_PATH}/{request_id}/resume", user or self.admin, data={}
        )

    def _put_manual_shapes(self, frames: list[int]) -> None:
        response = self._put_request(
            f'/api/tasks/{self.task["id"]}/annotations',
            self.admin,
            data={
                "tags": [],
                "tracks": [],
                "shapes": [
                    {
                        "frame": frame,
                        "attributes": [],
                        "group": None,
                        "label_id": self.label_id,
                        "occluded": False,
                        "points": [0, 5, 5, 0],
                        "source": "manual",
                        "type": "rectangle",
                        "z_order": 0,
                    }
                    for frame in frames
                ],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

    def _get_shapes_by_source(self) -> dict[str, list[int]]:
        response = self._get_request(f'/api/tasks/{self.task["id"]}/annotations', self.admin)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        shapes: dict[str, list[int]] = {}
        for shape in response.json()["shapes"]:
            shapes.setdefault(shape["source"], []).append(shape["frame"])

        return {source: sorted(frames) for source, frames in shapes.items()}

    def test_a_failed_run_stays_listed_and_is_marked_resumable(self):
        self.failing_frames = {5}
        request_id = self._start_run()
        self.assertEqual("failed", self._wait_lambda_request(request_id))

        response = self._get_request(LAMBDA_REQUESTS_PATH, self.admin)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        listed = {request["id"]: request for request in response.json()}

        self.assertIn(request_id, listed)
        self.assertTrue(listed[request_id]["resumable"])

    def test_resume_continues_after_the_recorded_frame_and_keeps_the_results(self):
        self.failing_frames = {5}
        request_id = self._start_run(cleanup=True)
        self.assertEqual("failed", self._wait_lambda_request(request_id))

        # stand in for the results the interrupted run had already written
        self._put_manual_shapes([0, 1, 2])
        self._set_resume_point(request_id, 2)

        self.failing_frames = set()
        response = self._resume(request_id)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual("finished", self._wait_lambda_request(response.json()["id"]))

        # a repeated cleanup would have removed exactly what is being recovered
        self.assertEqual(
            {"manual": [0, 1, 2], "auto": [3, 4, 5, 6, 7]}, self._get_shapes_by_source()
        )

    def test_resume_without_a_recorded_frame_runs_the_whole_scope(self):
        self.failing_frames = {5}
        request_id = self._start_run()
        self.assertEqual("failed", self._wait_lambda_request(request_id))

        self.failing_frames = set()
        self.assertEqual(status.HTTP_200_OK, self._resume(request_id).status_code)
        self.assertEqual("finished", self._wait_lambda_request(request_id))

        self.assertEqual({"auto": [0, 1, 2, 3, 4, 5, 6, 7]}, self._get_shapes_by_source())

    def test_resume_keeps_a_job_scoped_run_within_its_job(self):
        self.failing_frames = {6}
        request_id = self._start_run(job=self.jobs[1]["id"])
        self.assertEqual("failed", self._wait_lambda_request(request_id))

        self._set_resume_point(request_id, 5)

        self.failing_frames = set()
        self.assertEqual(status.HTTP_200_OK, self._resume(request_id).status_code)
        self.assertEqual("finished", self._wait_lambda_request(request_id))

        self.assertEqual({"auto": [6, 7]}, self._get_shapes_by_source())

    def test_a_finished_run_cannot_be_resumed(self):
        request_id = self._start_run()
        self.assertEqual("finished", self._wait_lambda_request(request_id))

        response = self._resume(request_id)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_a_reid_run_cannot_be_resumed(self):
        self._put_manual_shapes(list(range(8)))

        self.failing_frames = {0}
        request_id = self._start_run(id_function_reid_with_response_data)
        self.assertEqual("failed", self._wait_lambda_request(request_id))

        response = self._get_request(f"{LAMBDA_REQUESTS_PATH}/{request_id}", self.admin)
        self.assertFalse(response.json()["resumable"])

        response = self._resume(request_id)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_an_unknown_run_cannot_be_resumed(self):
        response = self._resume("autoannotate-task-99999")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, response.content)

    def test_a_user_without_access_to_the_task_cannot_resume_a_run(self):
        self.failing_frames = {5}
        request_id = self._start_run()
        self.assertEqual("failed", self._wait_lambda_request(request_id))

        response = self._resume(request_id, user=self.user)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.content)
