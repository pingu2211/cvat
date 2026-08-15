### Changed

- The SAM3 interactor reuses the vision features it computed for the previous call when
  the frame has not changed, so every click after the first one in an interaction only
  pays for prompt decoding instead of re-running the vision encoder.

- The CPU SAM3 functions now run a single worker instead of two, size PyTorch's thread
  pool from the container's CPU allowance, and install the CPU-only PyTorch wheels. Two
  workers each held their own multi-GB copy of the model and their own pool of threads
  over the same cores, which on a memory-constrained host meant swapping.

- The resolution and precision the SAM3 functions run at can be set at deploy time via
  the `SAM3_IMAGE_SIZE` and `SAM3_DTYPE` environment variables.

### Fixed

- Interactive SAM3 calls no longer fail after two minutes in the annotation UI. The
  serverless deployment now raises `CVAT_NUCLIO_DEFAULT_TIMEOUT` to match the function's
  own event timeout; previously the server gave up long before the function did.
