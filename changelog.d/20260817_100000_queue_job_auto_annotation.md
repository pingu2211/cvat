### Added

- Automatic annotation requests for individual jobs are now queued per job instead of
  per task, so several jobs of one task can be lined up at once and annotated one after
  another. A request is still rejected when the same job is already being annotated, when
  the whole task is being annotated, or when the whole task is requested while any of its
  jobs is being annotated. Progress for all the requests of a task is reported together on
  the task card.
