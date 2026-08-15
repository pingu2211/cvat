### Added

- An "Automatic annotation" entry in the job actions menu, so a detector can be run
  against a single job instead of the whole task. Useful for redoing one job of a large
  task after a batch run failed part way through. The entry is disabled while another
  automatic annotation request is running for the parent task, and progress is reported
  on the parent task as before.
