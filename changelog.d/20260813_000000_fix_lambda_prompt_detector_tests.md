### Fixed

- Text prompt detector tests in the lambda manager suite now read task labels from
  `GET /api/labels`, instead of the `labels` field of the task detail response, which is a
  summary object rather than a list and made the tests fail with a `TypeError`
- The SAM3 serverless functions now pin the `facebook/sam3` checkpoint to an immutable
  commit, so that redeploying a function always fetches the same weights
