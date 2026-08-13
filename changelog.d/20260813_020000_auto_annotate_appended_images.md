### Added

- Images appended to a task are now automatically annotated with the model configured
  on the task or its project. The run covers only the appended frames, so the existing
  annotations are left untouched. For text-prompt-driven detectors such as SAM3, the
  prompts are taken from the `prompt` field of the task labels.
