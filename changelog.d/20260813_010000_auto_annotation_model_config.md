### Added

- \[Server API\] Projects and tasks now carry an auto annotation model configuration
  (`auto_annotation_function` and `auto_annotation_threshold`). A task falls back to
  its project's configuration when it has none of its own. This is the model used to
  automatically annotate new frames, for example when images are appended to a task.
