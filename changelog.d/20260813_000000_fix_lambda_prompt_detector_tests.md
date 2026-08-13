### Fixed

- Text prompt detector tests in the lambda manager suite now read task labels from
  `GET /api/labels`, instead of the `labels` field of the task detail response, which is a
  summary object rather than a list and made the tests fail with a `TypeError`
