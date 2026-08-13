### Added

- \[Server API\] New `POST /api/tasks/{id}/data/append` endpoint that adds more images
  to a task that already has data attached to it. The appended frames are placed after
  the existing ones and are only covered by newly created jobs, so the annotations of
  the existing jobs are preserved.
